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


class WorkTaskState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    work_task_kind: str
    executor_config: dict[str, Any]
    plan_config: dict[str, Any]
    review_config: dict[str, Any]
    clarification_config: dict[str, Any]
    input: dict[str, Any]
    plan_steps: list[dict[str, Any]]
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


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


def _emit(run_ctx: GraphRunContext | None, event: str, data: dict[str, Any], node_id: str = "") -> None:
    writer = getattr(run_ctx, "writer", None) if run_ctx else None
    if not writer:
        return
    writer({"event": event, "data": data, "timestamp": time.time(), "node_id": node_id})


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


def _build_stage_steps(state: WorkTaskState, review_enabled: bool = False) -> list[dict[str, Any]]:
    stages = [
        {"id": "stage_clarify", "title": "需求明确", "description": "确认任务目标、交付形式和完成标准", "status": "pending", "executor_type": "agent", "executor_id": _work_agent_id(state, "assistant")},
        {"id": "stage_plan", "title": "规划", "description": "生成最多二级任务树和依赖关系", "status": "pending", "executor_type": "agent", "executor_id": _work_agent_id(state, "assistant")},
        {"id": "stage_execute", "title": "执行", "description": "按前置依赖顺序执行任务", "status": "pending", "executor_type": "agent", "executor_id": _work_agent_id(state, "executor"), "reviewer_id": _work_agent_id(state, "reviewer")},
    ]
    if review_enabled:
        stages.append({"id": "stage_review", "title": "审查", "description": "审查任务结果是否符合要求", "status": "pending", "executor_type": "agent", "executor_id": _work_agent_id(state, "reviewer")})
    stages.append({"id": "stage_deliver", "title": "交付", "description": "验收结果并生成最终交付物", "status": "pending", "executor_type": "agent", "executor_id": _work_agent_id(state, "reporter")})
    for i, s in enumerate(stages):
        s["depth"] = 1
        s["sort_order"] = i
        s["dependencies"] = [stages[i - 1]["id"]] if i > 0 else []
    return stages


def _emit_stage_update(run_ctx: GraphRunContext | None, state: WorkTaskState, completed_stage_id: str, next_stage_id: str | None = None, progress: int = 0) -> None:
    review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
    stage_steps = _build_stage_steps(state, review_enabled)
    for step in stage_steps:
        if step["id"] == completed_stage_id:
            step["status"] = "done"
        elif step["id"] == next_stage_id:
            step["status"] = "running"
    _emit(run_ctx, "phase", {"steps": stage_steps, "progress": progress}, completed_stage_id)


async def prepare_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
    stage_steps = _build_stage_steps(state, review_enabled)
    stage_steps[0]["status"] = "running"
    _emit(run_ctx, "phase", {"phase": "prepare", "label": "准备任务上下文", "progress": 5, "steps": stage_steps}, "prepare")
    return {
        "plan_steps": state.get("plan_steps", []),
        "step_results": state.get("step_results", []),
        "current_step_index": state.get("current_step_index", 0),
        "rework_count": state.get("rework_count", 0),
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

    card = build_hitl_card(
        template=template,
        template_id=template_id,
        content_payload=content_payload,
        task_id=state.get("task_id", ""),
        session_id=state.get("session_id", ""),
        interaction_type="clarification",
        meta={"task_id": state.get("task_id", ""), "template_id": template_id},
    )

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
        _emit(run_ctx, "text_delta", {"text": confirmation_summary}, "clarify")
    if response.action_key == "clarify_more":
        _emit(
            run_ctx,
            "phase",
            {"phase": "clarification_more", "label": "已收到补充需求，将继续确认", "progress": 8, "status": "running"},
            "clarify",
        )
        return {"clarification": values, "clarification_action": "clarify_more"}
    _emit(run_ctx, "phase", {"phase": "clarification_done", "label": "需求已明确", "progress": 12, "status": "running"}, "clarify")
    _emit_stage_update(run_ctx, state, "stage_clarify", "stage_plan", progress=12)
    return {"clarification": values, "clarification_action": "confirm"}


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
    prompt = (
        f"请为 Work 任务制定可执行计划。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"已确认需求：\n{_clarification_text(state)}\n\n"
        f"{_context_text(state)}\n\n"
        f"规划深度：{effort}\n\n"
        f"{feedback_text}"
        "你必须调用 submit_work_plan 工具提交计划，不要直接输出文本格式的计划。\n\n"
        "调用示例：\n"
        'submit_work_plan(steps=[{"title": "明确需求与约束", "description": "确认任务目标、交付标准和关键约束条件", "dependencies": []}, '
        '{"title": "收集资料与准备", "description": "获取完成任务所需的上下文、资料和工具条件", "dependencies": [1]}, '
        '{"title": "执行核心工作", "description": "按计划完成主要任务，形成可检查的阶段结果", "dependencies": [2]}, '
        '{"title": "整理交付物", "description": "汇总结果，标注关键结论、风险和后续建议", "dependencies": [3]}])\n\n'
        "要求：\n"
        "1. 输出 3-7 个一级步骤，按依赖顺序排列\n"
        "2. 每个步骤必须包含 title（标题）、description（说明+交付物）、dependencies（前置步骤序号，首步骤为空数组）\n"
        "3. 复杂步骤可拆出 1-3 个二级子任务（children）\n"
        "4. 如果工具返回格式错误，请根据错误信息和示例修正后重新调用\n"
    )
    plan_config = state.get("plan_config", {}) or {}
    timeout_seconds = max(10, int(plan_config.get("timeout_seconds", 30) or 30))
    session_id = state.get("session_id", "work")
    from astrbot.core.tools.work_plan_tools import get_cached_plan
    result: dict[str, Any] = {}
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            result = await asyncio.wait_for(
                _agent_operator.execute(
                    {
                        "system_prompt": (
                            "你是 NiceBot Work 的任务规划助手，擅长把目标拆成可审查的执行步骤。\n"
                            "你的唯一任务是调用 submit_work_plan 工具提交结构化计划。\n"
                            "绝对不要直接输出文本格式的计划，必须通过工具调用提交。\n"
                            "如果工具返回格式错误，你必须根据错误信息修正参数后重新调用，直到成功。"
                        ),
                        "user_prompt": prompt,
                        "messages": [],
                        "provider_id": state.get("provider_id"),
                        "session_id": session_id,
                        "func_tools": ["submit_work_plan"],
                    },
                    run_ctx,
                    write_stream=True,
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
            break
        if result.get("error"):
            _emit(
                run_ctx,
                "error",
                {"message": f"计划生成失败：{result.get('error')}。已生成可人工调整的兜底计划。"},
                "plan",
            )
            break

        cached_steps = get_cached_plan(session_id)
        if cached_steps:
            break
        if attempt < max_retries:
            _emit(run_ctx, "text_delta", {"text": f"计划未成功提交，正在重试（{attempt + 1}/{max_retries}）..."}, "plan")
            prompt = (
                f"上一次你没有成功调用 submit_work_plan 工具提交计划。请这次务必调用工具。\n\n"
                f"调用示例：\n"
                f'submit_work_plan(steps=[{{"title": "步骤1", "description": "说明", "dependencies": []}}, '
                f'{{"title": "步骤2", "description": "说明", "dependencies": [1]}}])\n\n'
                f"原任务：{task_name}\n{task_desc}\n\n"
                f"请立即调用 submit_work_plan 工具提交计划。"
            )
        else:
            break

    cached_steps = get_cached_plan(session_id)

    if cached_steps:
        steps = _convert_tool_steps(cached_steps)
        text = _format_plan_for_display(steps)
    else:
        text = result.get("final_text", "")
        if not text.strip():
            text = _fallback_plan_text(state)
        parsed_json_steps = _try_parse_json_steps(text)
        if parsed_json_steps:
            _emit(run_ctx, "text_delta", {"text": "已从文本输出中提取结构化计划。"}, "plan")
            steps = _convert_tool_steps(parsed_json_steps)
            text = _format_plan_for_display(steps)
        else:
            steps = _parse_steps(text)

    plan_display = _format_plan_for_display(steps) if steps else text
    _emit(run_ctx, "text_delta", {"text": plan_display}, "plan")
    _emit(run_ctx, "phase", {"phase": "plan_done", "label": "计划已生成", "steps": steps, "progress": 25}, "plan")
    _emit_stage_update(run_ctx, state, "stage_plan", "stage_execute", progress=25)
    return {"plan_steps": steps, "plan_text_full": text, "current_step_index": 0, "step_results": [], "approval_action": "", "plan_feedback": ""}


async def approve_plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    steps = state.get("plan_steps", [])
    plan_text_full = state.get("plan_text_full", "")
    plan_body = _format_plan_for_approval(steps) if steps else (plan_text_full or "无计划内容")
    card = InteractionCard(
        interaction_id=f"work_plan_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title=f"执行计划审批：{state.get('task_name', '')}",
        body=f"请审批以下执行计划：\n\n{plan_body}",
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
        _emit(run_ctx, "phase", {"phase": "plan_approved", "label": "计划已批准", "progress": 30, "status": "running"}, "approve_plan")
        return {"review_passed": False, "approval_action": "approve"}
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


async def execute_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    steps = state.get("plan_steps", [])
    if not steps:
        steps = [{"id": 1, "description": state.get("task_desc") or state.get("task_name", ""), "status": "pending"}]
    idx = state.get("current_step_index", 0)
    if idx >= len(steps):
        return {}

    step = dict(steps[idx])
    step["status"] = "running"
    steps[idx] = step
    progress = 30 + int((idx / max(len(steps), 1)) * 45)
    _emit(run_ctx, "phase", {"phase": "execute", "label": step["description"], "steps": steps, "progress": progress}, "execute")

    executor = state.get("executor_config", {}) or {}
    agent_id = step.get("executor_id") or executor.get("agent_id") or _work_agent_id(state, "executor")
    agent_label = step.get("executor") or agent_id or "通用任务执行智能体"
    prompt = (
        f"请执行 Work 任务步骤。\n\n"
        f"任务：{state.get('task_name', '')}\n"
        f"当前步骤：{step.get('description', '')}\n\n"
        f"{_context_text(state)}\n\n"
        "请输出可作为任务交付依据的结果。"
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": f"你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。只执行当前步骤，不负责审查自己的结果。",
            "user_prompt": prompt,
            "messages": [],
            "provider_id": state.get("provider_id") or executor.get("provider_id"),
            "session_id": state.get("session_id", "work"),
        },
        run_ctx,
        write_stream=True,
    )
    step["status"] = "done"
    step["result"] = result.get("final_text", "")
    steps[idx] = step
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
    if next_idx >= len(steps):
        review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
        next_stage = "stage_review" if review_enabled else "stage_deliver"
        _emit_stage_update(run_ctx, state, "stage_execute", next_stage, progress=75)
    return {"plan_steps": steps, "step_results": results, "current_step_index": next_idx}


async def review_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    review_config = state.get("review_config", {}) or {}
    if not review_config.get("enabled", False):
        return {"review_passed": True}
    if run_ctx is None:
        return {"review_passed": True}
    _emit(run_ctx, "phase", {"phase": "review", "label": "审查任务结果", "progress": 82}, "review")
    results_text = "\n\n".join(
        f"- {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": "你是 NiceBot Work 的审查智能体。只要结果明显未达成目标才判定返工。",
            "user_prompt": (
                f"请审查以下任务结果是否达成目标。\n\n"
                f"任务：{state.get('task_name', '')}\n\n"
                f"{_context_text(state)}\n\n"
                f"执行结果：\n{results_text}\n\n"
                "如果通过，回复 PASS。需要返工，回复 RETRY 并说明原因。"
            ),
            "messages": [],
            "provider_id": state.get("provider_id"),
            "session_id": state.get("session_id", "work"),
        },
        run_ctx,
        write_stream=True,
    )
    text = result.get("final_text", "").upper()
    passed = "PASS" in text and "RETRY" not in text
    rework_count = state.get("rework_count", 0)
    _emit(run_ctx, "phase", {"phase": "review_done", "label": "审查完成", "passed": passed, "progress": 88}, "review")
    if passed:
        _emit_stage_update(run_ctx, state, "stage_review", "stage_deliver", progress=88)
        return {"review_passed": True, "rework_count": rework_count}
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
    card = InteractionCard(
        interaction_id=f"work_rework_{uuid.uuid4().hex[:12]}",
        type="error_recovery",
        title="审查未通过",
        body="任务审查未通过且已达到预设返工次数，请确认是否继续返工或结束任务。",
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
    results_text = "\n\n".join(
        f"## {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    if run_ctx is None:
        return {"final_summary": results_text}
    _emit(run_ctx, "phase", {"phase": "finalize", "label": "生成交付物", "progress": 95}, "finalize")
    result = await _agent_operator.execute(
        {
            "system_prompt": f"你是 NiceBot Work 的汇报专家（{_work_agent_id(state, 'reporter')}）。请只整理最终交付物，不混入过程日志。",
            "user_prompt": (
                f"请将以下任务执行结果整理成最终交付物。\n\n"
                f"任务：{state.get('task_name', '')}\n\n{results_text}"
            ),
            "messages": [],
            "provider_id": state.get("provider_id"),
            "session_id": state.get("session_id", "work"),
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
            "artifact_type": "markdown",
            "content": summary,
        },
        "finalize",
    )
    _emit(run_ctx, "phase", {"phase": "completed", "label": "任务完成", "progress": 100}, "finalize")
    _emit_stage_update(run_ctx, state, "stage_deliver", None, progress=100)
    return {"final_summary": summary}


def route_after_prepare(state: WorkTaskState) -> str:
    clarification_config = state.get("clarification_config", {}) or {}
    if clarification_config.get("enabled", False):
        return "clarify"
    if state.get("cancelled"):
        return "end"
    if (state.get("plan_config", {}) or {}).get("enabled", False):
        return "plan"
    return "execute"


def route_after_clarify(state: WorkTaskState) -> str:
    if state.get("cancelled") or state.get("clarification_action") == "cancel":
        return "end"
    if state.get("clarification_action") == "clarify_more":
        return "clarify"
    if (state.get("plan_config", {}) or {}).get("enabled", False):
        return "plan"
    return "execute"


def route_after_approval(state: WorkTaskState) -> str:
    if state.get("approval_action") == "modify":
        return "plan"
    if state.get("cancelled"):
        return "end"
    if state.get("current_step_index", 0) >= 999999:
        return "end"
    return "execute"


def route_after_execute(state: WorkTaskState) -> str:
    if state.get("current_step_index", 0) >= len(state.get("plan_steps", [])):
        review_config = state.get("review_config", {}) or {}
        if review_config.get("enabled", False):
            return "review"
        return "finalize"
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


def _try_parse_json_steps(text: str) -> list[dict[str, Any]] | None:
    import json
    import re
    cleaned = text.strip()
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1).strip()
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    steps = data.get("steps", [])
    if not isinstance(steps, list) or len(steps) < 3:
        return None
    from astrbot.core.tools.work_plan_tools import validate_plan_steps
    errors = validate_plan_steps(steps)
    if errors:
        return None
    return steps


def _convert_tool_steps(steps_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for i, step in enumerate(steps_data, 1):
        step_id = f"step_{i}"
        deps = [f"step_{d}" for d in step.get("dependencies", []) if isinstance(d, int) and 1 <= d <= len(steps_data)]
        children: list[dict[str, Any]] = []
        for j, child in enumerate(step.get("children") or [], 1):
            children.append({
                "id": f"step_{i}_{j}",
                "title": str(child.get("title", ""))[:80],
                "description": str(child.get("description", child.get("title", ""))),
                "status": "pending",
                "dependencies": [],
                "parent_id": step_id,
                "depth": 2,
                "sort_order": j,
                "executor_type": "agent",
                "executor_id": "agent_nicebot_work_executor",
                "reviewer_id": "agent_nicebot_work_reviewer",
            })
        result.append({
            "id": step_id,
            "title": str(step.get("title", ""))[:80],
            "description": str(step.get("description", step.get("title", ""))),
            "status": "pending",
            "dependencies": deps,
            "parent_id": None,
            "depth": 1,
            "sort_order": i,
            "executor_type": "agent",
            "executor_id": "agent_nicebot_work_executor",
            "reviewer_id": "agent_nicebot_work_reviewer",
            "children": children,
        })
    return result


def _parse_steps(text: str) -> list[dict[str, Any]]:
    import re
    parent_steps: list[dict[str, Any]] = []
    child_steps: list[dict[str, Any]] = []
    current_parent_id: str | None = None
    parent_counter = 0
    child_counter = 0
    main_step_pattern = re.compile(r'^(\d+)[.、)）]\s')
    sub_num_pattern = re.compile(r'^(\d+)\.(\d+)\s')
    indent_pattern = re.compile(r'^(\s{2,}|\t+)')
    sub_prefix_pattern = re.compile(r'^(子任务|sub[- ]?task)\s*\d*', re.IGNORECASE)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_main_step = bool(main_step_pattern.match(stripped))
        is_sub = False
        sub_num_match = sub_num_pattern.match(stripped)
        indent_match = indent_pattern.match(line)
        sub_prefix_match = sub_prefix_pattern.match(stripped)

        if sub_num_match:
            is_sub = True
        elif indent_match and not is_main_step:
            is_sub = True
        elif sub_prefix_match:
            is_sub = True

        cleaned = stripped.lstrip("-*0123456789.、)） ").strip()
        if not cleaned:
            continue

        if is_sub and current_parent_id:
            child_counter += 1
            child_id = f"step_{parent_counter}_{child_counter}"
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
    return defaults.get(role) or config.get(f"{role}_agent_id") or fallback.get(role, "")


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

    prompt = (
        f"请为以下任务生成需求确认项，以 JSON 格式返回。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"{_context_text(state)}\n\n"
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
        '      "allow_custom": false,\n'
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
    )

    if run_ctx is None:
        return _fallback_clarify_content(state)

    try:
        result = await asyncio.wait_for(
            _agent_operator.execute(
                {
                    "system_prompt": "你是 NiceBot Work 任务助手，擅长根据任务内容生成精准的需求确认项。只返回 JSON，不要其他内容。",
                    "user_prompt": prompt,
                    "messages": [],
                    "provider_id": state.get("provider_id"),
                    "session_id": state.get("session_id", "work"),
                },
                run_ctx,
                write_stream=False,
            ),
            timeout=20,
        )
        text = result.get("final_text", "").strip()
        if text:
            items = _parse_confirmation_items(text)
            if items:
                return {"confirmation_items": items}
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
    builder.add_node("execute", execute_node)
    builder.add_node("review", review_node)
    builder.add_node("rework_hitl", rework_hitl_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("prepare")
    builder.add_conditional_edges("prepare", route_after_prepare, {"clarify": "clarify", "plan": "plan", "execute": "execute", "end": END})
    builder.add_conditional_edges("clarify", route_after_clarify, {"clarify": "clarify", "plan": "plan", "execute": "execute", "end": END})
    builder.add_edge("plan", "approve_plan")
    builder.add_conditional_edges("approve_plan", route_after_approval, {"plan": "plan", "execute": "execute", "end": END})
    builder.add_conditional_edges("execute", route_after_execute, {"execute": "execute", "review": "review", "finalize": "finalize"})
    builder.add_conditional_edges("review", route_after_review, {"execute": "execute", "hitl": "rework_hitl", "finalize": "finalize"})
    builder.add_conditional_edges("rework_hitl", route_after_rework_hitl, {"execute": "execute", "finalize": "finalize"})
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
