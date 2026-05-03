from __future__ import annotations

import time
import uuid
from typing import Any

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

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
    input: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    step_results: list[dict[str, Any]]
    current_step_index: int
    review_passed: bool
    rework_count: int
    final_summary: str


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


async def prepare_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    _emit(run_ctx, "phase", {"phase": "prepare", "label": "准备任务上下文", "progress": 5}, "prepare")
    return {
        "plan_steps": state.get("plan_steps", []),
        "step_results": state.get("step_results", []),
        "current_step_index": state.get("current_step_index", 0),
        "rework_count": state.get("rework_count", 0),
    }


async def plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    _emit(run_ctx, "phase", {"phase": "plan", "label": "生成执行计划", "progress": 15}, "plan")
    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    effort = (state.get("plan_config", {}) or {}).get("effort", "medium")
    prompt = (
        f"请为 Work 任务制定可执行计划。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"{_context_text(state)}\n\n"
        f"规划深度：{effort}\n\n"
        "请输出 3-7 个步骤，每个步骤包含清晰交付物。"
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": "你是 NiceBot Work 的任务规划助手，擅长把目标拆成可审查的执行步骤。",
            "user_prompt": prompt,
            "messages": [],
            "provider_id": state.get("provider_id"),
            "session_id": state.get("session_id", "work"),
        },
        run_ctx,
        write_stream=True,
    )
    text = result.get("final_text", "")
    steps = _parse_steps(text)
    _emit(run_ctx, "phase", {"phase": "plan_done", "label": "计划已生成", "steps": steps, "progress": 25}, "plan")
    return {"plan_steps": steps, "current_step_index": 0, "step_results": []}


async def approve_plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    steps = state.get("plan_steps", [])
    steps_text = "\n".join(
        f"{idx + 1}. {step.get('description', '')}" for idx, step in enumerate(steps)
    )
    card = InteractionCard(
        interaction_id=f"work_plan_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title="Work 执行计划审批",
        body=f"任务「{state.get('task_name', '')}」的执行计划如下：\n\n{steps_text}",
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
    response = await get_interaction_manager().send_and_wait(card, thread_id=state.get("task_id", ""), channel="chatui")
    if response.action_key == "approve":
        _emit(run_ctx, "phase", {"phase": "plan_approved", "label": "计划已批准", "progress": 30}, "approve_plan")
        return {"review_passed": False}
    if response.action_key == "modify":
        modify_text = response.field_values.get("modify_text", "")
        updated = list(steps)
        if modify_text:
            updated.append({
                "id": len(updated) + 1,
                "description": f"根据人工意见调整：{modify_text}",
                "status": "pending",
            })
        _emit(run_ctx, "phase", {"phase": "plan_modified", "label": "计划已按人工意见调整", "steps": updated, "progress": 30}, "approve_plan")
        return {"plan_steps": updated, "review_passed": False}
    _emit(run_ctx, "error", {"message": "执行计划被拒绝"}, "approve_plan")
    return {"review_passed": False, "current_step_index": 999999}


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
    agent_label = executor.get("agent_id") or executor.get("crew_id") or "任务助手"
    prompt = (
        f"请执行 Work 任务步骤。\n\n"
        f"任务：{state.get('task_name', '')}\n"
        f"当前步骤：{step.get('description', '')}\n\n"
        f"{_context_text(state)}\n\n"
        "请输出可作为任务交付依据的结果。"
    )
    result = await _agent_operator.execute(
        {
            "system_prompt": f"你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。",
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
        "status": "done",
        "stats": result.get("stats", {}),
    })
    _emit(run_ctx, "token", {"stats": result.get("stats", {}), "step_id": step.get("id", idx + 1)}, "execute")
    return {"plan_steps": steps, "step_results": results, "current_step_index": idx + 1}


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
    return {"review_passed": passed, "rework_count": rework_count + (0 if passed else 1)}


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
    response = await get_interaction_manager().send_and_wait(card, thread_id=state.get("task_id", ""), channel="chatui")
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
            "system_prompt": "你是 NiceBot Work 的交付物整理助手。",
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
    return {"final_summary": summary}


def route_after_prepare(state: WorkTaskState) -> str:
    if (state.get("plan_config", {}) or {}).get("enabled", False):
        return "plan"
    return "execute"


def route_after_approval(state: WorkTaskState) -> str:
    if state.get("current_step_index", 0) >= 999999:
        return "end"
    return "execute"


def route_after_execute(state: WorkTaskState) -> str:
    if state.get("current_step_index", 0) >= len(state.get("plan_steps", [])):
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


def _parse_steps(text: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = stripped.lstrip("-*0123456789.、)） ").strip()
        if cleaned and (stripped[0].isdigit() or stripped.startswith(("-", "*"))):
            steps.append({"id": len(steps) + 1, "description": cleaned, "status": "pending"})
    if not steps:
        steps.append({"id": 1, "description": text.strip()[:500] or "完成任务交付", "status": "pending"})
    return steps[:7]


def build_work_task_graph(config: dict | None = None, checkpointer=None) -> StateGraph:
    builder = StateGraph(WorkTaskState)
    builder.add_node("prepare", prepare_node)
    builder.add_node("plan", plan_node)
    builder.add_node("approve_plan", approve_plan_node)
    builder.add_node("execute", execute_node)
    builder.add_node("review", review_node)
    builder.add_node("rework_hitl", rework_hitl_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("prepare")
    builder.add_conditional_edges("prepare", route_after_prepare, {"plan": "plan", "execute": "execute"})
    builder.add_edge("plan", "approve_plan")
    builder.add_conditional_edges("approve_plan", route_after_approval, {"execute": "execute", "end": END})
    builder.add_conditional_edges("execute", route_after_execute, {"execute": "execute", "review": "review"})
    builder.add_conditional_edges("review", route_after_review, {"execute": "execute", "hitl": "rework_hitl", "finalize": "finalize"})
    builder.add_conditional_edges("rework_hitl", route_after_rework_hitl, {"execute": "execute", "finalize": "finalize"})
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
