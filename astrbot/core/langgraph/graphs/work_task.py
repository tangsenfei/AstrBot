from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.hitl_card_builder import build_hitl_card
from astrbot.core.langgraph.interaction import CardAction, CardField, InteractionCard
from astrbot.core.langgraph.interaction_manager import get_interaction_manager
from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()

_NODE_STAGE_MAP = {
    "prepare": "stage_clarify",
    "clarify": "stage_clarify",
    "plan": "stage_plan",
    "approve_plan": "stage_plan",
    "assign": "stage_assign",
    "execute": "stage_execute",
    "review": "stage_review",
    "rework_hitl": "stage_review",
    "finalize": "stage_deliver",
}

_WORK_AGENT_LABELS = {
    "agent_nicebot_work_assistant": "NiceBot 任务助手",
    "agent_nicebot_work_executor": "通用任务执行智能体",
    "agent_nicebot_work_reviewer": "通用任务审查智能体",
    "agent_nicebot_research_expert": "调查专家",
    "agent_nicebot_report_expert": "汇报专家",
}

_WORK_ROLE_LABELS = {
    "assistant": "NiceBot 任务助手",
    "executor": "通用任务执行智能体",
    "reviewer": "通用任务审查智能体",
    "researcher": "调查专家",
    "reporter": "汇报专家",
}


class WorkTaskState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    work_task_kind: str
    task_mode: str
    executor_config: dict[str, Any]
    plan_config: dict[str, Any]
    review_config: dict[str, Any]
    clarification_config: dict[str, Any]
    input: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    stage_steps: list[dict[str, Any]]
    plan_text_full: str
    step_results: list[dict[str, Any]]
    current_step_index: int
    review_passed: bool
    rework_count: int
    final_summary: str
    approval_action: str
    plan_feedback: str
    cancelled: bool
    clarification: dict[str, Any]
    clarification_action: str
    clarification_feedback: str


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


def _trace_context(
    node_id: str,
    *,
    stage_id: str | None = None,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "stage_id": stage_id or _NODE_STAGE_MAP.get(node_id, ""),
        "step_id": str(step_id or ""),
        "agent_id": agent_id or "",
        "agent_label": agent_label or agent_id or "",
    }


def _emit(
    run_ctx: GraphRunContext | None,
    event: str,
    data: dict[str, Any],
    node_id: str = "",
    *,
    stage_id: str | None = None,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> None:
    writer = getattr(run_ctx, "writer", None) if run_ctx else None
    if not writer:
        return
    payload = dict(data or {})
    trace = _trace_context(
        node_id,
        stage_id=stage_id or payload.get("stage_id"),
        step_id=step_id if step_id is not None else payload.get("step_id"),
        agent_id=agent_id or payload.get("agent_id"),
        agent_label=agent_label or payload.get("agent_label"),
    )
    for key, value in trace.items():
        if value not in (None, "") and key not in payload:
            payload[key] = value
    writer({"event": event, "data": payload, "timestamp": time.time(), "node_id": node_id})


def _emit_reasoning_from_result(
    run_ctx: GraphRunContext | None,
    result: dict[str, Any],
    node_id: str,
    *,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> None:
    reasoning_text = str((result or {}).get("reasoning_text") or "").strip()
    if reasoning_text:
        _emit(
            run_ctx,
            "reasoning",
            {"text": reasoning_text},
            node_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )


def _context_text(state: WorkTaskState) -> str:
    input_data = state.get("input", {}) or {}
    work_context = input_data.get("work_context", {}) or {}
    parts = []
    if work_context.get("directory"):
        parts.append(f"工作目录：{work_context['directory']}")
    if work_context.get("goal"):
        parts.append(f"项目目标：\n{work_context['goal']}")
    if work_context.get("rules"):
        parts.append(f"规则：\n{work_context['rules']}")
    if input_data.get("goal"):
        parts.append(f"交付目标：\n{input_data['goal']}")
    return "\n\n".join(parts)


def _is_agent_id(value: Any) -> bool:
    text = str(value or "")
    return text.startswith(("agent_", "expert_"))


def _work_agent_label(state: WorkTaskState, role: str, agent_id: str | None = None) -> str:
    agent_id = agent_id or _work_agent_id(state, role)
    config = state.get("executor_config", {}) or {}
    label_map = config.get("agent_labels", {}) or config.get("default_agent_labels", {}) or {}
    if agent_id and label_map.get(agent_id):
        return str(label_map[agent_id])
    if agent_id and _WORK_AGENT_LABELS.get(agent_id):
        return _WORK_AGENT_LABELS[agent_id]
    return _WORK_ROLE_LABELS.get(role, "") or agent_id or ""


def _step_agent_label(state: WorkTaskState, step: dict[str, Any], role: str = "executor") -> str:
    explicit = str(step.get("executor") or step.get("agent_label") or "").strip()
    agent_id = str(step.get("executor_id") or step.get("agent_id") or _work_agent_id(state, role) or "").strip()
    if explicit and not _is_agent_id(explicit):
        return explicit
    return _work_agent_label(state, role, agent_id)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_prompt_template(template: Any, variables: dict[str, Any], fallback: str) -> str:
    text = str(template or "").strip()
    if not text:
        return fallback
    safe_variables = _SafeFormatDict({key: "" if value is None else value for key, value in variables.items()})
    try:
        return text.format_map(safe_variables)
    except Exception:
        return fallback


async def prepare_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
    clarification_enabled = (state.get("clarification_config", {}) or {}).get("enabled", False)
    plan_enabled = (state.get("plan_config", {}) or {}).get("enabled", False)
    stage_steps = [
        {"id": "stage_clarify", "title": "需求明确", "description": "确认任务目标、交付形式和完成标准", "status": "running" if clarification_enabled else "done", "depth": 1, "sort_order": 0, "dependencies": [], "executor": "需求确认助手", "executor_type": "agent", "executor_id": _work_agent_id(state, "assistant")},
        {"id": "stage_plan", "title": "规划", "description": "生成最多二级任务树和依赖关系", "status": "running" if (not clarification_enabled and plan_enabled) else "pending", "depth": 1, "sort_order": 1, "dependencies": ["stage_clarify"], "executor": "任务规划助手", "executor_type": "agent", "executor_id": _work_agent_id(state, "assistant")},
        {"id": "stage_assign", "title": "分配", "description": "分配执行智能体", "status": "pending", "depth": 1, "sort_order": 2, "dependencies": ["stage_plan"], "executor": "任务分配助手", "executor_type": "agent", "executor_id": _work_agent_id(state, "assistant")},
        {"id": "stage_execute", "title": "执行", "description": "按前置依赖顺序执行任务", "status": "pending", "depth": 1, "sort_order": 3, "dependencies": ["stage_assign"], "executor": _work_agent_label(state, "executor"), "executor_type": "agent", "executor_id": _work_agent_id(state, "executor"), "reviewer_id": _work_agent_id(state, "reviewer")},
    ]
    if review_enabled:
        stage_steps.append(
            {"id": "stage_review", "title": "审查", "description": "审查任务结果是否达标", "status": "pending", "depth": 1, "sort_order": 4, "dependencies": ["stage_execute"], "executor": "任务审查智能体", "executor_type": "agent", "executor_id": _work_agent_id(state, "reviewer")},
        )
    last_dep = "stage_review" if review_enabled else "stage_execute"
    stage_steps.append(
        {"id": "stage_deliver", "title": "交付", "description": "生成最终交付物", "status": "pending", "depth": 1, "sort_order": len(stage_steps), "dependencies": [last_dep], "executor": _work_agent_label(state, "reporter"), "executor_type": "agent", "executor_id": _work_agent_id(state, "reporter")},
    )
    _emit(run_ctx, "phase", {"phase": "prepare", "label": "准备任务上下文", "progress": 5, "steps": stage_steps}, "prepare")
    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get("task_mode", "normal")
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    return {
        "stage_steps": stage_steps,
        "plan_steps": state.get("plan_steps", []),
        "step_results": state.get("step_results", []),
        "current_step_index": state.get("current_step_index", 0),
        "rework_count": state.get("rework_count", 0),
        "task_mode": task_mode,
    }


async def clarify_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    _emit(run_ctx, "phase", {"phase": "clarification", "label": "需求明确", "progress": 8}, "clarify")

    clarification_config = state.get("clarification_config", {}) or {}
    content_provider_type = clarification_config.get("content_provider_type", "agent")
    template_id = clarification_config.get("template_id", "builtin_work_requirement_clarification")

    template = _load_hitl_template(template_id)
    content_payload = await _resolve_clarify_content(
        content_provider_type, clarification_config, state, run_ctx, config,
    )
    clarify_reasoning_text = str(content_payload.pop("_reasoning_text", "") or "") if isinstance(content_payload, dict) else ""

    card = build_hitl_card(
        template=template,
        template_id=template_id,
        content_payload=content_payload,
        task_id=state.get("task_id", ""),
        session_id=state.get("session_id", ""),
        interaction_type="clarification",
        meta={"task_id": state.get("task_id", ""), "template_id": template_id},
    )
    card.fields.append(CardField(
        key="clarify_more_text",
        label="补充信息",
        field_type="textarea",
        required=False,
        description="如需补充或调整需求，请在此填写",
        custom_placeholder="例如：交付时间要求本周内完成、需要包含竞品对比分析...",
    ))

    task_name = state.get("task_name", "")
    if task_name and not content_payload.get("title"):
        card.title = f"需求确认：{task_name}"
    if not card.body or card.body == "请确认以下信息。默认已选推荐项，如不合适可改选或填写自定义补充。":
        card.body = (
            f"任务「{task_name}」开始前，请确认关键需求。\n\n"
            "默认项已按推荐选择；如果不合适，可以改选或在自定义补充中说明。"
        )

    _emit(run_ctx, "interaction", card.to_dict(), "clarify")
    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=state.get("task_id", ""),
        channel="chatui",
        channel_extra={"task_id": state.get("task_id", ""), "sync_chatui": True},
    )
    if response.action_key == "cancel":
        _emit(run_ctx, "phase", {"phase": "cancelled", "label": "任务已取消", "progress": 8, "status": "cancelled"}, "clarify")
        return {"cancelled": True, "clarification_action": "cancel"}
    values = dict(response.field_values or {})
    confirmation_summary = _format_clarification_summary(values, card)
    if confirmation_summary:
        clarify_agent_id = clarification_config.get("content_provider_agent_id", "agent_nicebot_work_assistant")
        clarify_agent_label = _work_agent_label(state, "assistant", clarify_agent_id)
        if clarify_reasoning_text:
            _emit(
                run_ctx,
                "reasoning",
                {"text": clarify_reasoning_text},
                "clarify",
                agent_id=clarify_agent_id,
                agent_label=clarify_agent_label,
            )
        _emit(
            run_ctx,
            "text_delta",
            {"text": confirmation_summary},
            "clarify",
            agent_id=clarify_agent_id,
            agent_label=clarify_agent_label,
        )
    if response.action_key == "clarify_more":
        feedback = values.pop("clarify_more_text", "") if isinstance(values, dict) else ""
        _emit(
            run_ctx,
            "phase",
            {"phase": "clarification_more", "label": "已收到补充需求，将重新生成确认卡片", "progress": 8, "status": "running"},
            "clarify",
        )
        return {"clarification": values, "clarification_feedback": feedback, "clarification_action": "clarify_more"}
    _emit(run_ctx, "phase", {"phase": "clarification_done", "label": "需求已明确", "progress": 12, "status": "running"}, "clarify")
    stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_clarify", "done")
    stages = _update_stage_status(stages, "stage_plan", "running")
    _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "clarify")
    return {"clarification": values, "clarification_action": "confirm", "stage_steps": stages}


async def plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    _emit(run_ctx, "phase", {"phase": "plan", "label": "生成执行计划", "progress": 15}, "plan")
    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    effort = (state.get("plan_config", {}) or {}).get("effort", "medium")
    plan_feedback = state.get("plan_feedback", "")
    feedback_text = f"人工调整意见：{plan_feedback}\n\n" if plan_feedback else ""
    plan_config = state.get("plan_config", {}) or {}
    prompt_variables = {
        "task_name": task_name,
        "task_desc": task_desc,
        "clarification": _clarification_text(state),
        "work_context": _context_text(state),
        "effort": effort,
        "feedback_text": feedback_text,
    }
    default_prompt = (
        f"请为 Work 任务制定可执行计划。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"已确认需求：\n{_clarification_text(state)}\n\n"
        f"{_context_text(state)}\n\n"
        f"规划深度：{effort}\n\n"
        f"{feedback_text}"
        "请输出 3-7 个一级步骤，每个步骤包含清晰交付物。如果步骤较复杂，可拆出 1-3 个二级子步骤。\n\n"
        "格式要求（严格遵守，不得使用缩进或其他格式）：\n"
        "1. 步骤标题\n"
        "   交付物：xxx\n"
        "   1.1 子步骤标题\n"
        "   1.2 子步骤标题\n\n"
        "2. 步骤标题\n"
        "   交付物：xxx\n"
        "   2.1 子步骤标题\n\n"
        "二级子步骤必须使用「父步骤号.子序号」格式（如1.1、2.3），不得使用缩进或「子任务」前缀。最多两级。步骤按依赖顺序排列。"
    )
    prompt = _render_prompt_template(plan_config.get("prompt_template") or plan_config.get("prompt"), prompt_variables, default_prompt)
    plan_agent_id = plan_config.get("agent_id") or _work_agent_id(state, "assistant")
    system_prompt = _render_prompt_template(
        plan_config.get("system_prompt"),
        prompt_variables,
        "你是 NiceBot Work 的任务规划助手，擅长把目标拆成可审查的执行步骤。",
    )
    timeout_seconds = max(10, int(plan_config.get("timeout_seconds", 30) or 30))
    result: dict[str, Any] = {}
    try:
        result = await asyncio.wait_for(
            _agent_operator.execute(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": prompt,
                    "messages": [],
                    "provider_id": state.get("provider_id"),
                    "session_id": state.get("session_id", "work"),
                    "trace_context": _trace_context("plan", agent_id=plan_agent_id, agent_label=_work_agent_label(state, "assistant", plan_agent_id)),
                },
                run_ctx,
                write_stream=False,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        _emit(
            run_ctx,
            "error",
            {"message": f"计划生成超过 {timeout_seconds} 秒，已生成可人工调整的兜底计划。"},
            "plan",
        )
    text = result.get("final_text", "")
    stats = result.get("stats", {}) if isinstance(result, dict) else {}
    if stats:
        tok_usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}
        _emit(run_ctx, "token", {
            "input": tok_usage.get("input", 0),
            "output": tok_usage.get("output", 0),
        }, "plan")
    if result.get("error"):
        _emit(
            run_ctx,
            "error",
            {"message": f"计划生成失败：{result.get('error')}。已生成可人工调整的兜底计划。"},
            "plan",
        )
    if not text.strip():
        text = _fallback_plan_text(state)
    steps = _parse_steps(text)
    stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_plan", "running")
    plan_display = text
    _emit_reasoning_from_result(
        run_ctx,
        result,
        "plan",
        agent_id=plan_agent_id,
        agent_label=_work_agent_label(state, "assistant", plan_agent_id),
    )
    _emit(
        run_ctx,
        "text_delta",
        {"text": plan_display},
        "plan",
        agent_id=plan_agent_id,
        agent_label=_work_agent_label(state, "assistant", plan_agent_id),
    )
    _emit(run_ctx, "phase", {"phase": "plan_done", "label": "计划已生成", "steps": stages, "progress": 25}, "plan")
    return {"plan_steps": steps, "stage_steps": stages, "plan_text_full": text, "current_step_index": 0, "step_results": [], "approval_action": "", "plan_feedback": ""}


async def approve_plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    steps = state.get("plan_steps", [])
    plan_text_full = state.get("plan_text_full", "")
    plan_body = plan_text_full if plan_text_full else (_format_plan_for_approval(steps) if steps else "无计划内容")
    plan_config = state.get("plan_config", {}) or {}
    body = _render_prompt_template(
        plan_config.get("approval_body_template"),
        {"plan_body": plan_body, "task_name": state.get("task_name", ""), "task_desc": state.get("task_desc", "")},
        f"请审批以下执行计划：\n\n{plan_body}",
    )
    card = InteractionCard(
        interaction_id=f"work_plan_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title=f"执行计划审批：{state.get('task_name', '')}",
        body=body,
        fields=[
            CardField(
                key="modify_text",
                label="修改意见",
                field_type="textarea",
                required=False,
            )
        ],
        actions=[
            CardAction(key="approve", label="批准执行", style="primary"),
            CardAction(key="modify", label="调整计划", style="default"),
            CardAction(key="reject", label="拒绝", style="danger"),
        ],
        meta={"task_id": state.get("task_id", "")},
    )
    _emit(run_ctx, "interaction", card.to_dict(), "approve_plan")
    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=state.get("task_id", ""),
        channel="chatui",
        channel_extra={"task_id": state.get("task_id", ""), "sync_chatui": True},
    )
    if response.action_key == "approve":
        approved_text = plan_text_full
        re_parsed_steps = _parse_steps(approved_text) if approved_text else steps
        stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_plan", "done")
        stages = _update_stage_status(stages, "stage_assign", "running")
        _emit(run_ctx, "phase", {"phase": "plan_approved", "label": "计划已批准", "progress": 30, "status": "running", "steps": stages}, "approve_plan")
        return {"review_passed": False, "approval_action": "approve", "stage_steps": stages, "plan_steps": re_parsed_steps}
    if response.action_key == "modify":
        modify_text = response.field_values.get("modify_text") or response.field_values.get("feedback") or ""
        _emit(
            run_ctx,
            "phase",
            {"phase": "plan_revision_requested", "label": "已收到调整计划要求，将重新规划", "progress": 18, "status": "running"},
            "approve_plan",
        )
        return {"approval_action": "modify", "plan_feedback": modify_text, "review_passed": False}
    _emit(run_ctx, "error", {"message": "执行计划被拒绝，任务已取消", "status": "cancelled"}, "approve_plan")
    _emit(run_ctx, "phase", {"phase": "cancelled", "label": "任务已取消", "progress": state.get("progress", 0), "status": "cancelled"}, "approve_plan")
    return {"review_passed": False, "current_step_index": 999999, "approval_action": "reject", "cancelled": True}


async def assign_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get("task_mode", "normal")
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    _emit(run_ctx, "phase", {"phase": "assign", "label": "分配执行步骤", "progress": 28}, "assign")

    plan_steps = state.get("plan_steps", [])
    plan_text_full = state.get("plan_text_full", "")
    if not plan_steps:
        plan_steps = [{"id": "step_1", "title": state.get("task_desc") or state.get("task_name", ""), "description": state.get("task_desc") or state.get("task_name", ""), "status": "pending"}]

    mode_instructions = {
        "quick": (
            "快速模式：将整个计划作为一个交付单元分配给一个执行者。\n"
            "只输出一个一级步骤，包含全部任务内容，不拆分子步骤。\n"
        ),
        "normal": (
            "常规模式：按一级子任务分配执行者。\n"
            "保留原始计划的一级步骤结构，为每个一级步骤分配执行者。\n"
            "如果原始计划有二级子步骤，将它们作为该一级步骤的子任务保留。\n"
        ),
        "deep": (
            "深度模式：按二级子任务分配执行者。\n"
            "完整保留原始计划的所有二级子步骤内容，不得省略或合并。\n"
            "如果原始计划缺少二级结构，请基于原文补齐二级子步骤。\n"
            "每个二级子步骤都必须分配独立的执行者。\n"
        ),
    }

    prompt = (
        f"请根据以下已审批的执行计划，为每个步骤分配执行者、审查者，并设定依赖关系。\n\n"
        f"任务名称：{state.get('task_name', '')}\n"
        f"任务描述：{state.get('task_desc', '')}\n\n"
        f"已审批的原始计划（这是权威来源，必须以此为准）：\n{plan_text_full or _format_plan_for_approval(plan_steps)}\n\n"
        f"{mode_instructions.get(task_mode, mode_instructions['normal'])}\n"
        f"当前任务模式：{task_mode}\n\n"
        f"可用智能体角色：\n"
        f"- assistant（任务助理）：负责规划、协调、分配\n"
        f"- executor（执行者）：负责具体执行\n"
        f"- reviewer（审查者）：负责结果审查\n"
        f"- researcher（研究员）：负责信息收集和分析\n"
        f"- reporter（汇报专家）：负责整理交付物\n\n"
        f"请以 JSON 格式返回扁平步骤列表，格式如下：\n"
        f'```json\n'
        f'[\n'
        f'  {{\n'
        f'    "id": "step_1",\n'
        f'    "title": "步骤标题",\n'
        f'    "description": "步骤描述",\n'
        f'    "depth": 1,\n'
        f'    "parent_id": null,\n'
        f'    "dependencies": [],\n'
        f'    "executor_type": "agent",\n'
        f'    "executor_id": "agent_nicebot_work_executor",\n'
        f'    "reviewer_id": "agent_nicebot_work_reviewer",\n'
        f'    "status": "pending",\n'
        f'    "sort_order": 0\n'
        f'  }},\n'
        f'  {{\n'
        f'    "id": "step_1_1",\n'
        f'    "title": "子步骤标题",\n'
        f'    "description": "子步骤描述",\n'
        f'    "depth": 2,\n'
        f'    "parent_id": "step_1",\n'
        f'    "dependencies": [],\n'
        f'    "executor_type": "agent",\n'
        f'    "executor_id": "agent_nicebot_work_executor",\n'
        f'    "reviewer_id": "",\n'
        f'    "status": "pending",\n'
        f'    "sort_order": 0\n'
        f'  }}\n'
        f']\n'
        f'```\n\n'
        f"要求：\n"
        f"1. 最多两级步骤，depth 只能是 1 或 2\n"
        f"2. 一级步骤的 parent_id 为 null，二级步骤的 parent_id 为其父步骤的 id\n"
        f"3. dependencies 是前置步骤 id 列表，第一个步骤的 dependencies 为空\n"
        f"4. executor_id 使用智能体角色对应的 ID（如 agent_nicebot_work_executor）\n"
        f"5. sort_order 表示同级步骤的排序\n"
        f"6. 只返回 JSON 数组，不要包含其他内容\n"
    )

    plan_config = state.get("plan_config", {}) or {}
    executor_config = state.get("executor_config", {}) or {}
    assignment_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "approved_plan": plan_text_full or _format_plan_for_approval(plan_steps),
        "task_mode": task_mode,
        "mode_instructions": mode_instructions.get(task_mode, mode_instructions["normal"]),
    }
    prompt = _render_prompt_template(executor_config.get("assignment_prompt_template"), assignment_variables, prompt)
    assignment_system_prompt = _render_prompt_template(
        executor_config.get("assignment_system_prompt"),
        assignment_variables,
        "你是 NiceBot Work 的任务分配助手，擅长根据执行计划分配执行者和设定依赖关系。只返回 JSON 数组，不要包含其他内容。",
    )
    assign_agent_id = _work_agent_id(state, "assistant")
    assign_agent_label = _work_agent_label(state, "assistant", assign_agent_id)
    timeout_seconds = max(10, int(plan_config.get("timeout_seconds", 30) or 30))
    assigned_steps: list[dict[str, Any]] = []
    approved_plan = _approved_plan_text(state, plan_steps)
    try:
        if task_mode == "quick":
            assigned_steps = _fallback_assign_steps(plan_steps, task_mode, state)
        elif run_ctx:
            result = await asyncio.wait_for(
                _agent_operator.execute(
                {
                    "system_prompt": assignment_system_prompt,
                    "user_prompt": prompt,
                    "messages": [],
                    "provider_id": state.get("provider_id"),
                    "session_id": state.get("session_id", "work"),
                    "trace_context": _trace_context("assign", agent_id=assign_agent_id, agent_label=assign_agent_label),
                },
                    run_ctx,
                    write_stream=False,
                ),
                timeout=timeout_seconds,
            )
            text = result.get("final_text", "").strip()
            stats = result.get("stats", {}) if isinstance(result, dict) else {}
            if stats:
                tok_usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}
                _emit(run_ctx, "token", {
                    "input": tok_usage.get("input", 0),
                    "output": tok_usage.get("output", 0),
                }, "assign")
            if text:
                assigned_steps = _parse_assigned_steps(text)
    except asyncio.TimeoutError:
        _emit(run_ctx, "error", {"message": f"分配步骤超过 {timeout_seconds} 秒，使用兜底分配。"}, "assign")
    except Exception as e:
        _emit(run_ctx, "error", {"message": f"分配步骤失败：{e}，使用兜底分配。"}, "assign")

    if not _validate_assigned_steps(assigned_steps, plan_steps, task_mode, approved_plan):
        if assigned_steps:
            _emit(run_ctx, "phase", {"phase": "assign_fallback", "label": "分配结果未完整覆盖审批计划，已使用确定性分配。"}, "assign")
        assigned_steps = _fallback_assign_steps(plan_steps, task_mode, state)
    assigned_steps = _apply_executor_labels(assigned_steps, state)

    stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_assign", "done")
    stages = _update_stage_status(stages, "stage_execute", "running")
    assign_display = _format_plan_for_display(assigned_steps)
    _emit_reasoning_from_result(
        run_ctx,
        result if "result" in locals() else {},
        "assign",
        agent_id=assign_agent_id,
        agent_label=assign_agent_label,
    )
    _emit(
        run_ctx,
        "text_delta",
        {"text": assign_display},
        "assign",
        agent_id=assign_agent_id,
        agent_label=assign_agent_label,
    )
    _emit(run_ctx, "phase", {"phase": "assign_done", "label": "步骤已分配", "steps": stages, "progress": 32}, "assign")
    return {"plan_steps": assigned_steps, "stage_steps": stages, "plan_text_full": approved_plan, "current_step_index": 0, "step_results": []}


async def execute_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    steps = state.get("plan_steps", [])
    if not steps:
        steps = [{"id": "step_1", "description": state.get("task_desc") or state.get("task_name", ""), "status": "pending"}]

    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get("task_mode", "normal")
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    executable_steps = _collect_executable_steps(steps, task_mode)
    idx = state.get("current_step_index", 0)
    if idx >= len(executable_steps):
        return {}

    step = dict(executable_steps[idx])
    step["status"] = "running"
    _update_step_in_tree(steps, step["id"], {"status": "running"})
    progress = 30 + int((idx / max(len(executable_steps), 1)) * 45)
    executor = state.get("executor_config", {}) or {}
    agent_id = step.get("executor_id") or executor.get("agent_id") or _work_agent_id(state, "executor")
    agent_label = _step_agent_label(state, step, "executor")
    _emit(
        run_ctx,
        "phase",
        {"phase": "execute", "label": step.get("description", ""), "steps": steps, "progress": progress},
        "execute",
        step_id=step.get("id"),
        agent_id=agent_id,
        agent_label=agent_label,
    )
    step_scope = _step_scope_text(state, steps, step, state.get("step_results", []), task_mode)
    prompt_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "requirements": _requirement_text(state),
        "approved_plan": _approved_plan_text(state, steps),
        "step_scope": step_scope,
        "task_mode": task_mode,
        "agent_label": agent_label,
    }
    prompt = _render_prompt_template(
        executor.get("execute_prompt_template") or executor.get("prompt"),
        prompt_variables,
        _build_execute_prompt(state, steps, step, state.get("step_results", []), task_mode),
    )
    system_prompt = _render_prompt_template(
        executor.get("execute_system_prompt") or executor.get("system_prompt"),
        prompt_variables,
        f"你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。只执行当前步骤，不负责审查自己的结果。",
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "messages": [],
            "provider_id": state.get("provider_id") or executor.get("provider_id"),
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context("execute", step_id=step.get("id"), agent_id=agent_id, agent_label=agent_label),
        },
        run_ctx,
        write_stream=True,
    )
    step["status"] = "done"
    step["result"] = result.get("final_text", "")
    updates = {"status": "done", "result": step["result"], "executor": agent_label}
    if task_mode == "normal" and step.get("children"):
        updates["children"] = _children_with_status(step.get("children") or [], "done")
    _update_step_in_tree(steps, step["id"], updates)
    _update_parent_status(steps, step.get("parent_id"))
    _emit(run_ctx, "phase", {
        "phase": "step_done",
        "label": f"{step['description']} 已完成",
        "steps": steps,
        "progress": progress,
    }, "execute", step_id=step.get("id"), agent_id=agent_id, agent_label=agent_label)
    results = list(state.get("step_results", []))
    results.append({
        "step_id": step.get("id", idx + 1),
        "description": step.get("description", ""),
        "result": step["result"],
        "agent": agent_label,
        "executor_type": step.get("executor_type") or "agent",
        "executor_id": agent_id,
        "status": "done",
        "stats": result.get("stats", {}),
    })
    next_idx = idx + 1
    all_done = next_idx >= len(executable_steps)
    result_dict: dict[str, Any] = {"plan_steps": steps, "step_results": results, "current_step_index": next_idx}
    if all_done:
        review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
        stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_execute", "done")
        if review_enabled:
            stages = _update_stage_status(stages, "stage_review", "running")
        else:
            stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "execute")
        result_dict["stage_steps"] = stages
    return result_dict


async def review_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    review_config = state.get("review_config", {}) or {}
    if not review_config.get("enabled", False):
        stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_execute", "done")
        stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "review")
        return {"review_passed": True, "stage_steps": stages}
    if run_ctx is None:
        return {"review_passed": True}
    _emit(run_ctx, "phase", {"phase": "review", "label": "审查任务结果", "progress": 82}, "review")
    results_text = "\n\n".join(
        f"- {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    review_agent_id = review_config.get("reviewer_id") or _work_agent_id(state, "reviewer")
    review_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "work_context": _context_text(state),
        "results_text": results_text,
    }
    review_prompt = _render_prompt_template(
        review_config.get("prompt_template") or review_config.get("prompt"),
        review_variables,
        (
            f"请审查以下任务结果是否达成目标。\n\n"
            f"任务：{state.get('task_name', '')}\n\n"
            f"{_context_text(state)}\n\n"
            f"执行结果：\n{results_text}\n\n"
            "如果通过，回复 PASS。需要返工，回复 RETRY 并说明原因。"
        ),
    )
    review_system_prompt = _render_prompt_template(
        review_config.get("system_prompt"),
        review_variables,
        "你是 NiceBot Work 的审查智能体。只要结果明显未达成目标才判定返工。",
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": review_system_prompt,
            "user_prompt": review_prompt,
            "messages": [],
            "provider_id": state.get("provider_id"),
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context("review", agent_id=review_agent_id, agent_label=_work_agent_label(state, "reviewer", review_agent_id)),
        },
        run_ctx,
        write_stream=True,
    )
    text = result.get("final_text", "").upper()
    passed = "PASS" in text and "RETRY" not in text
    rework_count = state.get("rework_count", 0)
    _emit(run_ctx, "phase", {"phase": "review_done", "label": "审查完成", "passed": passed, "progress": 88}, "review")
    if passed:
        stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_review", "done")
        stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "review")
        return {"review_passed": True, "rework_count": rework_count, "stage_steps": stages}
    steps = list(state.get("plan_steps", []))
    review_text = result.get("final_text", "")
    rework_step = {
        "id": f"rework_{rework_count + 1}",
        "title": f"返工 {rework_count + 1}",
        "description": review_text or "根据审查意见补全任务结果",
        "status": "pending",
        "dependencies": [str(steps[-1].get("id"))] if steps else [],
        "parent_id": None,
        "depth": 1,
        "sort_order": len(steps),
        "executor_type": "agent",
        "executor_id": _work_agent_id(state, "executor"),
        "reviewer_id": _work_agent_id(state, "reviewer"),
    }
    steps.append(rework_step)
    _emit(run_ctx, "phase", {"phase": "rework_planned", "label": "已加入返工步骤", "steps": steps, "progress": 70}, "review")
    return {"review_passed": False, "rework_count": rework_count + 1, "plan_steps": steps, "current_step_index": len(steps) - 1}


async def rework_hitl_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    review_config = state.get("review_config", {}) or {}
    card = InteractionCard(
        interaction_id=f"work_rework_{uuid.uuid4().hex[:12]}",
        type="error_recovery",
        title=str(review_config.get("rework_title") or "审查未通过"),
        body=str(review_config.get("rework_body") or "任务审查未通过且已达到预设返工次数，请确认是否继续返工或结束任务。"),
        fields=[
            CardField(key="guidance", label="返工要求", field_type="textarea", required=False)
        ],
        actions=[
            CardAction(key="retry", label="继续返工", style="primary"),
            CardAction(key="finish", label="接受当前结果", style="default"),
            CardAction(key="cancel", label="取消任务", style="danger"),
        ],
        meta={"task_id": state.get("task_id", "")},
    )
    _emit(run_ctx, "interaction", card.to_dict(), "rework_hitl")
    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=state.get("task_id", ""),
        channel="chatui",
        channel_extra={"task_id": state.get("task_id", ""), "sync_chatui": True},
    )
    if response.action_key == "retry":
        guidance = response.field_values.get("guidance", "")
        steps = list(state.get("plan_steps", []))
        steps.append({
            "id": len(steps) + 1,
            "description": f"返工：{guidance or '根据审查意见补全任务结果'}",
            "status": "pending",
        })
        return {"plan_steps": steps, "current_step_index": len(steps) - 1, "review_passed": False}
    if response.action_key == "cancel":
        _emit(run_ctx, "error", {"message": "任务已由人工取消"}, "rework_hitl")
    return {"review_passed": True}


async def finalize_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    executor = state.get("executor_config", {}) or {}
    results_text = "\n\n".join(
        f"## {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    if run_ctx is None:
        return {"final_summary": results_text}
    _emit(run_ctx, "phase", {"phase": "finalize", "label": "生成交付物", "progress": 95}, "finalize")
    reporter_id = _work_agent_id(state, "reporter")
    finalize_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "results_text": results_text,
        "reporter_id": reporter_id,
    }
    finalize_prompt = _render_prompt_template(
        executor.get("finalize_prompt_template") or executor.get("finalize_prompt"),
        finalize_variables,
        f"请将以下任务执行结果整理成最终交付物。\n\n任务：{state.get('task_name', '')}\n\n{results_text}",
    )
    finalize_system_prompt = _render_prompt_template(
        executor.get("finalize_system_prompt"),
        finalize_variables,
        f"你是 NiceBot Work 的汇报专家（{reporter_id}）。请只整理最终交付物，不混入过程日志。",
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": finalize_system_prompt,
            "user_prompt": finalize_prompt,
            "messages": [],
            "provider_id": state.get("provider_id"),
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context("finalize", agent_id=reporter_id, agent_label=_work_agent_label(state, "reporter", reporter_id)),
        },
        run_ctx,
        write_stream=True,
    )
    summary = result.get("final_text", "") or results_text
    _emit(
        run_ctx,
        "artifact",
        {
            "title": state.get("task_name", "Work 任务交付物"),
            "artifact_type": executor.get("artifact_type") or "markdown",
            "content": summary,
        },
        "finalize",
    )
    _emit(run_ctx, "phase", {"phase": "completed", "label": "任务完成", "progress": 100}, "finalize")
    stages = _update_stage_status(list(state.get("stage_steps", [])), "stage_deliver", "done")
    _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "finalize")
    return {"final_summary": summary, "stage_steps": stages}


def route_after_prepare(state: WorkTaskState) -> str:
    clarification_config = state.get("clarification_config", {}) or {}
    if clarification_config.get("enabled", False):
        return "clarify"
    if state.get("cancelled"):
        return "end"
    if (state.get("plan_config", {}) or {}).get("enabled", False):
        return "plan"
    return "assign"


def route_after_clarify(state: WorkTaskState) -> str:
    if state.get("cancelled") or state.get("clarification_action") == "cancel":
        return "end"
    if state.get("clarification_action") == "clarify_more":
        return "clarify"
    if (state.get("plan_config", {}) or {}).get("enabled", False):
        return "plan"
    return "assign"


def route_after_approval(state: WorkTaskState) -> str:
    if state.get("approval_action") == "modify":
        return "plan"
    if state.get("cancelled"):
        return "end"
    if state.get("current_step_index", 0) >= 999999:
        return "end"
    return "assign"


def route_after_execute(state: WorkTaskState) -> str:
    steps = state.get("plan_steps", [])
    executable = _collect_executable_steps(steps)
    if state.get("current_step_index", 0) >= len(executable):
        return "review"
    return "execute"


def route_after_review(state: WorkTaskState) -> str:
    if state.get("review_passed", True):
        return "finalize"
    review = state.get("review_config", {}) or {}
    max_rework = int(review.get("max_rework", 1))
    if state.get("rework_count", 0) > max_rework:
        return "hitl"
    return "execute"


def route_after_rework_hitl(state: WorkTaskState) -> str:
    if state.get("review_passed", False):
        return "finalize"
    return "execute"


def _append_step_detail(step: dict[str, Any], line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    if text.startswith(("交付物：", "交付物:", "输出：", "输出:")):
        value = text.split("：", 1)[-1] if "：" in text else text.split(":", 1)[-1]
        step["deliverable"] = value.strip()
    desc = str(step.get("description") or "").strip()
    if text not in desc:
        step["description"] = f"{desc}\n{text}".strip() if desc else text


def _parse_steps(text: str) -> list[dict[str, Any]]:
    import re
    parent_steps: list[dict[str, Any]] = []
    child_steps: list[dict[str, Any]] = []
    current_parent_id: str | None = None
    current_child_id: str | None = None
    parent_counter = 0
    child_counter = 0
    main_step_pattern = re.compile(r'^(\d+)[.、)）]\s')
    sub_num_pattern = re.compile(r'^(\d+)\.(\d+)\s')

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_main_step = bool(main_step_pattern.match(stripped))
        sub_num_match = sub_num_pattern.match(stripped)
        is_sub = bool(sub_num_match)

        cleaned = stripped.lstrip("-*0123456789.、)） ").strip()
        if not cleaned:
            continue

        if is_sub and current_parent_id:
            child_counter += 1
            child_id = f"step_{parent_counter}_{child_counter}"
            current_child_id = child_id
            child_steps.append({
                "id": child_id,
                "title": cleaned[:80],
                "description": cleaned,
                "status": "pending",
                "dependencies": [],
                "parent_id": current_parent_id,
                "depth": 2,
                "sort_order": child_counter,
                "executor_type": "agent",
                "executor_id": "agent_nicebot_work_executor",
                "reviewer_id": "agent_nicebot_work_reviewer",
            })
        elif is_main_step:
            parent_counter += 1
            child_counter = 0
            step_id = f"step_{parent_counter}"
            current_parent_id = step_id
            current_child_id = None
            parent_steps.append({
                "id": step_id,
                "title": cleaned[:80],
                "description": cleaned,
                "status": "pending",
                "dependencies": [] if not parent_steps else [f"step_{len(parent_steps)}"],
                "parent_id": None,
                "depth": 1,
                "sort_order": parent_counter,
                "executor_type": "agent",
                "executor_id": "agent_nicebot_work_executor",
                "reviewer_id": "agent_nicebot_work_reviewer",
            })
        elif current_child_id:
            for child in child_steps:
                if child.get("id") == current_child_id:
                    _append_step_detail(child, cleaned)
                    break
        elif current_parent_id:
            for parent in parent_steps:
                if parent.get("id") == current_parent_id:
                    _append_step_detail(parent, cleaned)
                    break

    if not parent_steps:
        parent_steps.append({
            "id": "step_1",
            "title": "完成任务交付",
            "description": text.strip()[:500] or "完成任务交付",
            "status": "pending",
            "dependencies": [],
            "parent_id": None,
            "depth": 1,
            "sort_order": 0,
            "executor_type": "agent",
            "executor_id": "agent_nicebot_work_executor",
            "reviewer_id": "agent_nicebot_work_reviewer",
        })

    result = list(parent_steps[:7])
    for ps in result:
        pid = ps["id"]
        children = [cs for cs in child_steps if cs.get("parent_id") == pid][:10]
        ps["children"] = children
    return result


def _parse_assigned_steps(text: str) -> list[dict[str, Any]]:
    import json as _json
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        data = _json.loads(cleaned)
    except _json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            try:
                data = _json.loads(cleaned[start:end + 1])
            except _json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    valid_steps: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("id") or f"step_{index + 1}")
        depth = int(item.get("depth") or 1)
        if depth < 1 or depth > 2:
            depth = 1
        parent_id = item.get("parent_id") or None
        if depth == 1:
            parent_id = None
        dependencies = item.get("dependencies") or []
        if not isinstance(dependencies, list):
            dependencies = [dependencies] if dependencies else []
        title = str(item.get("title") or item.get("name") or item.get("description") or f"步骤 {index + 1}")
        description = str(item.get("description") or title)
        valid_steps.append({
            "id": step_id,
            "title": title[:80],
            "description": description,
            "status": "pending",
            "dependencies": [str(d) for d in dependencies if d],
            "parent_id": parent_id,
            "depth": depth,
            "sort_order": int(item.get("sort_order") or index),
            "executor": str(item.get("executor") or item.get("agent_label") or ""),
            "executor_type": str(item.get("executor_type") or "agent"),
            "executor_id": str(item.get("executor_id") or "agent_nicebot_work_executor"),
            "reviewer_id": str(item.get("reviewer_id") or ""),
        })
    if not valid_steps:
        return []
    child_by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for step in valid_steps:
        child_by_parent.setdefault(step.get("parent_id"), []).append(step)
    result = [s for s in valid_steps if s["depth"] == 1][:7]
    for ps in result:
        pid = ps["id"]
        children = [cs for cs in valid_steps if cs.get("parent_id") == pid][:10]
        ps["children"] = children
    return result


def _approved_plan_text(state: WorkTaskState, plan_steps: list[dict[str, Any]] | None = None) -> str:
    text = str(state.get("plan_text_full") or "").strip()
    if text:
        return text
    steps = plan_steps if plan_steps is not None else state.get("plan_steps", [])
    if steps:
        return _format_plan_for_approval(steps).strip()
    return _fallback_plan_text(state)


def _step_text(step: dict[str, Any]) -> str:
    parts = [
        str(step.get("title") or "").strip(),
        str(step.get("description") or "").strip(),
        str(step.get("deliverable") or step.get("deliverables") or "").strip(),
        str(step.get("result") or "").strip(),
    ]
    for child in step.get("children") or []:
        parts.append(_step_text(child))
    return "\n".join(part for part in parts if part)


def _steps_text(steps: list[dict[str, Any]]) -> str:
    return "\n".join(_step_text(step) for step in steps or [])


def _leaf_count(steps: list[dict[str, Any]]) -> int:
    count = 0
    for step in steps or []:
        children = step.get("children") or []
        count += _leaf_count(children) if children else 1
    return count


def _validate_assigned_steps(
    assigned_steps: list[dict[str, Any]],
    plan_steps: list[dict[str, Any]],
    task_mode: str,
    approved_plan_text: str,
) -> bool:
    if not assigned_steps:
        return False
    if task_mode == "quick":
        text = _steps_text(assigned_steps)
        return len(assigned_steps) == 1 and _leaf_count(assigned_steps) == 1 and len(text) >= min(80, max(20, len(approved_plan_text) // 4))

    expected_roots = len(plan_steps or [])
    if expected_roots > 1 and len(assigned_steps) < expected_roots:
        return False
    if task_mode == "deep":
        expected_leaves = _leaf_count(plan_steps)
        if expected_leaves > 1 and _leaf_count(assigned_steps) < expected_leaves:
            return False

    source_text = (approved_plan_text or _steps_text(plan_steps)).strip()
    assigned_text = _steps_text(assigned_steps).strip()
    if len(source_text) > 160 and len(assigned_text) < min(140, max(80, len(source_text) // 3)):
        return False
    return True


def _apply_executor_labels(steps: list[dict[str, Any]], state: WorkTaskState, role: str = "executor") -> list[dict[str, Any]]:
    result = []
    for raw in steps or []:
        step = dict(raw)
        step["executor_id"] = step.get("executor_id") or _work_agent_id(state, role)
        step["executor"] = _step_agent_label(state, step, role)
        step["executor_type"] = step.get("executor_type") or "agent"
        if step.get("reviewer_id") is None:
            step["reviewer_id"] = ""
        step["children"] = _apply_executor_labels(step.get("children") or [], state, role)
        result.append(step)
    return result


def _fallback_assign_steps(plan_steps: list[dict[str, Any]], task_mode: str, state: WorkTaskState) -> list[dict[str, Any]]:
    executor_id = _work_agent_id(state, "executor")
    reviewer_id = _work_agent_id(state, "reviewer")
    executor_label = _work_agent_label(state, "executor", executor_id)
    if task_mode == "quick":
        goal = ((state.get("input", {}) or {}).get("goal") or state.get("task_desc") or state.get("task_name") or "完成任务").strip()
        approved_plan = _approved_plan_text(state, plan_steps)
        description = f"按已审批计划完整执行：\n{approved_plan}".strip()
        return [{
            "id": "step_1",
            "title": (state.get("task_name") or goal)[:80],
            "description": description,
            "status": "pending",
            "dependencies": [],
            "parent_id": None,
            "depth": 1,
            "sort_order": 0,
            "executor": executor_label,
            "executor_type": "agent",
            "executor_id": executor_id,
            "reviewer_id": reviewer_id,
            "children": [],
        }]
    if task_mode == "deep":
        result: list[dict[str, Any]] = []
        child_counter = 0
        for parent_idx, parent in enumerate(plan_steps[:7], 1):
            parent_id = f"step_{parent_idx}"
            parent_step = {
                "id": parent_id,
                "title": str(parent.get("title") or parent.get("description") or f"步骤 {parent_idx}")[:80],
                "description": str(parent.get("description") or parent.get("title") or ""),
                "status": "pending",
                "dependencies": [] if parent_idx == 1 else [f"step_{parent_idx - 1}"],
                "parent_id": None,
                "depth": 1,
                "sort_order": parent_idx - 1,
                "executor_type": "agent",
                "executor_id": executor_id,
                "reviewer_id": reviewer_id,
            }
            children = parent.get("children", [])
            child_steps = []
            if children:
                for child_idx, child in enumerate(children[:10], 1):
                    child_counter += 1
                    child_id = f"step_{parent_idx}_{child_idx}"
                    child_steps.append({
                        "id": child_id,
                        "title": str(child.get("title") or child.get("description") or f"子步骤 {parent_idx}.{child_idx}")[:80],
                        "description": str(child.get("description") or child.get("title") or ""),
                        "status": "pending",
                        "dependencies": [] if child_idx == 1 else [f"step_{parent_idx}_{child_idx - 1}"],
                        "parent_id": parent_id,
                        "depth": 2,
                        "sort_order": child_idx - 1,
                        "executor_type": "agent",
                        "executor_id": executor_id,
                        "reviewer_id": "",
                    })
            else:
                child_counter += 1
                child_steps.append({
                    "id": f"step_{parent_idx}_1",
                    "title": f"执行：{parent_step['title'][:60]}",
                    "description": parent_step["description"],
                    "status": "pending",
                    "dependencies": [],
                    "parent_id": parent_id,
                    "depth": 2,
                    "sort_order": 0,
                    "executor_type": "agent",
                    "executor_id": executor_id,
                    "reviewer_id": "",
                })
            parent_step["children"] = child_steps
            result.append(parent_step)
        if not result:
            result.append({
                "id": "step_1",
                "title": state.get("task_name", "完成任务"),
                "description": state.get("task_desc") or state.get("task_name", ""),
                "status": "pending",
                "dependencies": [],
                "parent_id": None,
                "depth": 1,
                "sort_order": 0,
                "executor_type": "agent",
                "executor_id": executor_id,
                "reviewer_id": reviewer_id,
                "children": [{
                    "id": "step_1_1",
                    "title": "执行任务",
                    "description": state.get("task_desc") or state.get("task_name", ""),
                    "status": "pending",
                    "dependencies": [],
                    "parent_id": "step_1",
                    "depth": 2,
                    "sort_order": 0,
                    "executor_type": "agent",
                    "executor_id": executor_id,
                    "reviewer_id": "",
                }],
            })
        return result
    result = []
    for parent_idx, parent in enumerate(plan_steps[:7], 1):
        parent_id = f"step_{parent_idx}"
        children = parent.get("children", [])
        child_steps = []
        for child_idx, child in enumerate(children[:10], 1):
            child_steps.append({
                "id": f"step_{parent_idx}_{child_idx}",
                "title": str(child.get("title") or child.get("description") or f"子步骤 {parent_idx}.{child_idx}")[:80],
                "description": str(child.get("description") or child.get("title") or ""),
                "status": "pending",
                "dependencies": [],
                "parent_id": parent_id,
                "depth": 2,
                "sort_order": child_idx - 1,
                "executor_type": "agent",
                "executor_id": executor_id,
                "reviewer_id": "",
            })
        result.append({
            "id": parent_id,
            "title": str(parent.get("title") or parent.get("description") or f"步骤 {parent_idx}")[:80],
            "description": str(parent.get("description") or parent.get("title") or ""),
            "status": "pending",
            "dependencies": [] if parent_idx == 1 else [f"step_{parent_idx - 1}"],
            "parent_id": None,
            "depth": 1,
            "sort_order": parent_idx - 1,
            "executor_type": "agent",
            "executor_id": executor_id,
            "reviewer_id": reviewer_id,
            "children": child_steps,
        })
    if not result:
        result.append({
            "id": "step_1",
            "title": state.get("task_name", "完成任务"),
            "description": state.get("task_desc") or state.get("task_name", ""),
            "status": "pending",
            "dependencies": [],
            "parent_id": None,
            "depth": 1,
            "sort_order": 0,
            "executor_type": "agent",
            "executor_id": executor_id,
            "reviewer_id": reviewer_id,
            "children": [],
        })
    return result


def _update_stage_status(steps: list[dict], stage_id: str, new_status: str) -> list[dict]:
    updated = []
    for s in steps:
        if s.get("id") == stage_id:
            s = dict(s)
            s["status"] = new_status
        updated.append(s)
    return updated


def _collect_executable_steps(steps: list[dict[str, Any]], task_mode: str = "deep") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if task_mode == "normal":
        return [step for step in steps if not str(step.get("id") or "").startswith("stage_")]
    for step in steps:
        children = step.get("children", [])
        if children:
            for child in children:
                result.append(child)
        else:
            result.append(step)
    return result


def _find_step_by_id(steps: list[dict[str, Any]], step_id: Any) -> dict[str, Any] | None:
    target = str(step_id or "")
    if not target:
        return None
    for step in steps or []:
        if str(step.get("id") or "") == target:
            return step
        found = _find_step_by_id(step.get("children") or [], target)
        if found:
            return found
    return None


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_format_value(val)}" for key, val in value.items() if val not in (None, "", []))
    return str(value or "")


def _requirement_text(state: WorkTaskState) -> str:
    input_data = state.get("input", {}) or {}
    lines = []
    if state.get("task_name"):
        lines.append(f"- 任务名称：{state['task_name']}")
    if state.get("task_desc"):
        lines.append(f"- 任务描述：{state['task_desc']}")
    if input_data.get("goal"):
        lines.append(f"- 交付目标：{input_data['goal']}")
    clarification = _clarification_text(state)
    if clarification:
        lines.append(f"- 人工确认需求：\n{clarification}")
    context = _context_text(state)
    if context:
        lines.append(f"- 工作上下文：\n{context}")
    return "\n".join(lines) or "按任务名称、任务描述和用户确认信息执行。"


def _step_scope_text(
    state: WorkTaskState,
    steps: list[dict[str, Any]],
    step: dict[str, Any],
    step_results: list[dict[str, Any]],
    task_mode: str,
) -> str:
    lines = [f"- 当前模式：{task_mode}"]
    parent = _find_step_by_id(steps, step.get("parent_id"))
    if parent:
        lines.append(f"- 所属父步骤：{parent.get('title') or parent.get('description')}")
        parent_desc = str(parent.get("description") or "").strip()
        if parent_desc and parent_desc != (parent.get("title") or ""):
            lines.append(f"  父步骤说明：{parent_desc}")
    lines.append(f"- 当前步骤：{step.get('title') or step.get('description') or step.get('id')}")
    description = str(step.get("description") or "").strip()
    if description and description != (step.get("title") or ""):
        lines.append(f"  步骤说明：\n{description}")
    deliverable = step.get("deliverable") or step.get("deliverables")
    if deliverable:
        lines.append(f"  交付物：{_format_value(deliverable)}")
    children = step.get("children") or []
    if children:
        lines.append("  子任务：")
        for child in children:
            lines.append(f"  - {child.get('title') or child.get('description')}")
    dependencies = step.get("dependencies") or []
    if dependencies:
        dep_titles = []
        for dep_id in dependencies:
            dep = _find_step_by_id(steps, dep_id)
            dep_titles.append(str(dep.get("title") or dep.get("description") or dep_id) if dep else str(dep_id))
        lines.append(f"- 前置依赖：{'；'.join(dep_titles)}")
    result_lines = []
    dep_set = {str(dep) for dep in dependencies}
    for item in step_results or []:
        item_id = str(item.get("step_id") or "")
        if dep_set and item_id not in dep_set:
            continue
        desc = item.get("description") or item.get("step_id") or "已完成步骤"
        result = str(item.get("result") or "").strip()
        if result:
            result_lines.append(f"- {desc}：\n{result[:1200]}")
    if not result_lines and step_results:
        for item in step_results[-3:]:
            desc = item.get("description") or item.get("step_id") or "已完成步骤"
            result = str(item.get("result") or "").strip()
            if result:
                result_lines.append(f"- {desc}：\n{result[:800]}")
    if result_lines:
        lines.append("- 已完成结果参考：\n" + "\n".join(result_lines))
    return "\n".join(lines)


def _build_execute_prompt(
    state: WorkTaskState,
    steps: list[dict[str, Any]],
    step: dict[str, Any],
    step_results: list[dict[str, Any]],
    task_mode: str,
) -> str:
    return (
        "请执行 Work 任务中的当前负责部分。\n\n"
        f"## 任务需求\n{_requirement_text(state)}\n\n"
        f"## 已审批整体计划\n{_approved_plan_text(state, steps)}\n\n"
        f"## 当前负责部分\n{_step_scope_text(state, steps, step, step_results, task_mode)}\n\n"
        "## 执行要求\n"
        "1. 先对齐任务需求和已审批整体计划，再完成当前负责部分。\n"
        "2. 只执行当前负责部分，不重写整体计划，也不要扩展到未分配步骤。\n"
        "3. 输出要能被后续步骤或最终交付复用，保留关键依据、结论和仍不确定的点。\n"
        "4. 如果当前负责部分与需求或计划冲突，明确指出冲突并给出最小可行处理。"
    )


def _children_with_status(children: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    updated = []
    for child in children or []:
        item = dict(child)
        item["status"] = status
        item["children"] = _children_with_status(item.get("children") or [], status)
        updated.append(item)
    return updated


def _update_step_in_tree(steps: list[dict[str, Any]], step_id: str, updates: dict[str, Any]) -> None:
    for step in steps:
        if step.get("id") == step_id:
            step.update(updates)
            return
        for child in step.get("children", []):
            if child.get("id") == step_id:
                child.update(updates)
                return


def _update_parent_status(steps: list[dict[str, Any]], parent_id: str | None) -> None:
    if not parent_id:
        return
    for step in steps:
        if step.get("id") != parent_id:
            continue
        children = step.get("children", [])
        if not children:
            continue
        all_done = all(c.get("status") in ("done", "completed") for c in children)
        any_failed = any(c.get("status") == "failed" for c in children)
        if any_failed:
            step["status"] = "failed"
        elif all_done:
            step["status"] = "done"
        return


def _work_agent_id(state: WorkTaskState, role: str) -> str:
    config = state.get("executor_config", {}) or {}
    defaults = config.get("default_agents", {}) or {}
    fallback = {
        "assistant": "agent_nicebot_work_assistant",
        "executor": "agent_nicebot_work_executor",
        "reviewer": "agent_nicebot_work_reviewer",
        "researcher": "agent_nicebot_research_expert",
        "reporter": "agent_nicebot_report_expert",
    }
    return config.get(f"{role}_agent_id") or defaults.get(role) or fallback.get(role, "")


def _load_hitl_template(template_id: str) -> dict[str, Any] | None:
    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.hitl_template_service import HITLTemplateService
        db = get_database()
        svc = HITLTemplateService(db)
        row = svc.get_template(template_id)
        if row:
            return row
    except Exception:
        pass
    return None


async def _resolve_clarify_content(
    provider_type: str,
    clarification_config: dict[str, Any],
    state: WorkTaskState,
    run_ctx: GraphRunContext | None,
    config: RunnableConfig,
) -> dict[str, Any]:
    if provider_type == "agent":
        return await _agent_clarify_content(clarification_config, state, run_ctx)
    if provider_type == "static":
        return clarification_config.get("content_payload", {})
    if provider_type == "upstream":
        upstream = state.get("input", {}) or {}
        return upstream.get("clarify_content", {})
    return _fallback_clarify_content(state)


async def _agent_clarify_content(
    clarification_config: dict[str, Any],
    state: WorkTaskState,
    run_ctx: GraphRunContext | None,
) -> dict[str, Any]:
    agent_id = clarification_config.get("content_provider_agent_id", "agent_nicebot_work_assistant")
    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")

    previous = state.get("clarification", {}) or {}
    previous_feedback = state.get("clarification_feedback", "")

    history_context = ""
    if previous:
        history_lines = []
        for k, v in previous.items():
            if k == "clarify_more_text":
                continue
            val_str = "、".join(str(x) for x in v) if isinstance(v, list) else str(v)
            history_lines.append(f"  - {k}: {val_str}")
        history_context = "已提交的需求信息：\n" + "\n".join(history_lines) + "\n\n"
        if previous_feedback:
            history_context += f"用户的补充意见：\n{previous_feedback}\n\n"
        history_context += (
            "请根据以上已提交信息和补充意见，重新生成需求确认卡片。\n"
            "要求：\n"
            "1. 保留之前已提交的选择作为对应字段的推荐/默认值\n"
            "2. 根据补充意见调整或新增确认项\n"
            "3. 对于用户已明确选择的字段，options 中应将该选择标注为推荐\n"
        )

    default_prompt = (
        f"请为以下任务生成需求确认项，以 JSON 格式返回。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"{_context_text(state)}\n\n"
        f"{history_context}"
        "请返回如下 JSON 结构（不要包含 markdown 代码块标记）：\n"
        "{\n"
        '  "confirmation_items": [\n'
        "    {\n"
        '      "key": "字段英文key",\n'
        '      "label": "字段中文标签",\n'
        '      "description": "该确认项的说明",\n'
        '      "field_type": "select 或 multiselect 或 textarea",\n'
        '      "required": true,\n'
        '      "recommended": "推荐选项或默认值",\n'
        '      "options": ["选项1", "选项2", "推荐选项"],\n'
        '      "allow_custom": true,\n'
        '      "custom_placeholder": "自定义时填写"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "要求：\n"
        "1. 根据任务内容生成 2-5 个最相关的确认项\n"
        "2. 每个确认项的 options 应包含 3-6 个选项，推荐项以\"推荐：\"开头\n"
        "3. field_type 选择规则：\n"
        "   - select：单选，有明确互斥选项时使用\n"
        "   - multiselect：多选，需要同时选择多个选项时使用（如：关注维度、目标品牌、数据来源）\n"
        "   - textarea：需要自由输入时使用\n"
        "4. 确保推荐项与任务内容相关，不要使用通用默认值\n"
        "5. 当确认项天然需要多选时（如\"关注哪些维度\"\"需要哪些数据源\"），使用 multiselect\n"
        "6. 每个 select/multiselect 类型字段必须设置 allow_custom 为 true\n"
    )
    prompt_variables = {
        "task_name": task_name,
        "task_desc": task_desc,
        "work_context": _context_text(state),
        "history_context": history_context,
    }
    prompt = _render_prompt_template(clarification_config.get("content_prompt"), prompt_variables, default_prompt)
    system_prompt = _render_prompt_template(
        clarification_config.get("content_system_prompt"),
        prompt_variables,
        "你是 NiceBot Work 任务助手，擅长根据任务内容生成精准的需求确认项。只返回 JSON，不要其他内容。",
    )

    if run_ctx is None:
        return _fallback_clarify_content(state)

    try:
        result = await asyncio.wait_for(
            _agent_operator.execute(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": prompt,
                    "messages": [],
                    "provider_id": state.get("provider_id"),
                    "session_id": state.get("session_id", "work"),
                    "trace_context": _trace_context("clarify", agent_id=agent_id, agent_label=_work_agent_label(state, "assistant", agent_id)),
                },
                run_ctx,
                write_stream=False,
            ),
            timeout=20,
        )
        text = result.get("final_text", "").strip()
        stats = result.get("stats", {}) if isinstance(result, dict) else {}
        if stats:
            tok_usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}
            _emit(run_ctx, "token", {
                "input": tok_usage.get("input", 0),
                "output": tok_usage.get("output", 0),
            }, "clarify")
        if text:
            items = _parse_confirmation_items(text)
            if items:
                items = _ensure_allow_custom(items)
                return {"confirmation_items": items, "_reasoning_text": result.get("reasoning_text", "")}
    except (asyncio.TimeoutError, Exception):
        pass

    return _fallback_clarify_content(state)


def _parse_confirmation_items(text: str) -> list[dict[str, Any]]:
    import json
    cleaned = text
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    items = data.get("confirmation_items", [])
    if not isinstance(items, list):
        return []
    valid = []
    for item in items:
        if isinstance(item, dict) and item.get("key") and item.get("label"):
            valid.append(item)
    return valid


def _ensure_allow_custom(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        ft = item.get("field_type", "select")
        if ft in ("select", "multiselect"):
            item["allow_custom"] = True
    return items


def _format_clarification_summary(values: dict[str, Any], card: InteractionCard) -> str:
    if not values:
        return ""
    field_labels: dict[str, str] = {}
    for f in (card.fields or []):
        if isinstance(f, dict):
            field_labels[f.get("key", "")] = f.get("label", f.get("key", ""))
        else:
            field_labels[f.key] = f.label
    lines = ["✅ 需求已确认："]
    for key, val in values.items():
        if val is None or val == "":
            continue
        label = field_labels.get(key, key)
        if isinstance(val, list):
            val_str = "、".join(str(v) for v in val)
        else:
            val_str = str(val)
        lines.append(f"- {label}：{val_str}")
    return "\n".join(lines)


def _fallback_clarify_content(state: WorkTaskState) -> dict[str, Any]:
    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    context_hint = ""
    if task_desc:
        context_hint = f"（任务描述：{task_desc[:60]}）" if len(task_desc) > 60 else f"（任务描述：{task_desc}）"

    return {
        "confirmation_items": [
            {
                "key": "task_goal",
                "label": "任务目标",
                "description": f"确认「{task_name}」的核心目标{context_hint}",
                "field_type": "textarea",
                "required": True,
                "recommended": task_desc or task_name,
                "allow_custom": True,
                "custom_placeholder": "请描述你期望的任务目标",
            },
            {
                "key": "deliverable_format",
                "label": "交付形式",
                "description": "期望的最终交付物形式",
                "field_type": "select",
                "required": True,
                "recommended": "推荐：结构化报告",
                "options": ["推荐：结构化报告", "清单", "步骤方案", "文件", "对话结论", "自定义"],
                "allow_custom": True,
                "custom_placeholder": "请描述期望的交付形式",
            },
            {
                "key": "success_criteria",
                "label": "完成标准",
                "description": "任务达到什么状态算完成",
                "field_type": "textarea",
                "required": True,
                "recommended": "结果可直接使用，关键依据清楚，风险和假设明确",
                "allow_custom": True,
                "custom_placeholder": "请描述你的完成标准",
            },
            {
                "key": "custom_requirements",
                "label": "自定义补充",
                "description": "其他需要补充的要求或约束",
                "field_type": "textarea",
                "required": False,
                "allow_custom": True,
                "custom_placeholder": "可选，补充任何额外要求",
            },
        ],
    }


def _clarification_text(state: WorkTaskState) -> str:
    values = state.get("clarification", {}) or {}
    if not values:
        return "尚无人工补充，按任务描述和工作目录规则执行。"
    lines = []
    for key, val in values.items():
        if val:
            lines.append(f"- {key}：{val}")
    return "\n".join(lines) or "尚无人工补充，按任务描述和工作目录规则执行。"


def _fallback_plan_text(state: WorkTaskState) -> str:
    goal = ((state.get("input", {}) or {}).get("goal") or state.get("task_desc") or state.get("task_name") or "完成任务").strip()
    return "\n".join(
        [
            f"1. 明确任务目标和约束：{goal}",
            "2. 收集并核对完成任务所需的上下文、资料和工具条件。",
            "3. 执行核心工作，形成可检查的阶段结果。",
            "4. 整理最终交付物，并标注关键结论、风险和后续建议。",
        ]
    )


def _format_plan_for_display(steps: list[dict[str, Any]]) -> str:
    lines = ["## 执行计划\n"]
    for i, step in enumerate(steps, 1):
        desc = step.get("description", str(step))
        status_icon = {
            "pending": "⬜",
            "running": "🔄",
            "done": "✅",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }.get(step.get("status", "pending"), "⬜")
        lines.append(f"{i}. {status_icon} {desc}")
        for child in step.get("children", []):
            child_desc = child.get("description", str(child))
            lines.append(f"   - {child_desc}")
    lines.append("\n请确认以上计划，或进行修改后确认执行。")
    return "\n".join(lines)


def _format_plan_for_approval(steps: list[dict[str, Any]]) -> str:
    lines = []
    for i, step in enumerate(steps, 1):
        title = step.get("title", step.get("description", ""))
        lines.append(f"步骤{i}：{title}")
        desc = step.get("description", "")
        if desc and desc != title:
            lines.append(f"  说明：{desc}")
        deliverable = step.get("deliverable") or step.get("deliverables", "")
        if deliverable:
            lines.append(f"  交付物：{deliverable}")
        deps = step.get("dependencies", [])
        if deps:
            dep_labels = [d for d in deps if d.startswith("step_")]
            if dep_labels:
                lines.append(f"  前置：{', '.join(dep_labels)}")
        else:
            lines.append(f"  前置：无")
        children = step.get("children", [])
        if children:
            child_names = [c.get("title", c.get("description", ""))[:60] for c in children]
            lines.append(f"  子任务：{'；'.join(child_names)}")
        lines.append("")
    return "\n".join(lines)


def build_work_task_graph(config: dict | None = None, checkpointer=None) -> StateGraph:
    builder = StateGraph(WorkTaskState)
    builder.add_node("prepare", prepare_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("plan", plan_node)
    builder.add_node("approve_plan", approve_plan_node)
    builder.add_node("assign", assign_node)
    builder.add_node("execute", execute_node)
    builder.add_node("review", review_node)
    builder.add_node("rework_hitl", rework_hitl_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("prepare")
    builder.add_conditional_edges("prepare", route_after_prepare, {"clarify": "clarify", "plan": "plan", "assign": "assign", "end": END})
    builder.add_conditional_edges("clarify", route_after_clarify, {"clarify": "clarify", "plan": "plan", "assign": "assign", "end": END})
    builder.add_edge("plan", "approve_plan")
    builder.add_conditional_edges("approve_plan", route_after_approval, {"plan": "plan", "assign": "assign", "end": END})
    builder.add_edge("assign", "execute")
    builder.add_conditional_edges("execute", route_after_execute, {"execute": "execute", "review": "review"})
    builder.add_conditional_edges("review", route_after_review, {"execute": "execute", "hitl": "rework_hitl", "finalize": "finalize"})
    builder.add_conditional_edges("rework_hitl", route_after_rework_hitl, {"execute": "execute", "finalize": "finalize"})
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
