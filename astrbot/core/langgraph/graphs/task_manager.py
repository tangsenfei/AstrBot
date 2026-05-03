from __future__ import annotations

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()


class TaskManagerState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    plan_steps: list[dict]
    current_step_index: int
    step_results: list[dict]
    pending_input: str
    check_pass: bool
    plan_approved: bool


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


async def plan_node(state: TaskManagerState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    pending = state.get("pending_input", "")

    extra = ""
    if pending:
        extra = f"\n\n[用户补充要求]\n{pending}"

    prompt = (
        f"请将以下任务拆解为具体的执行步骤（3-7步）：\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}{extra}\n\n"
        "请按以下格式输出：\n"
        "## 执行步骤\n"
        "1. [步骤1描述]\n"
        "2. [步骤2描述]\n"
        "..."
    )
    agent_state = {
        "system_prompt": "你是一个任务规划助手。请将任务拆解为可执行的步骤。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    plan_text = result.get("final_text", "")
    steps = []
    for line in plan_text.split("\n"):
        line = line.strip()
        if line and (
            line[0].isdigit() or line.startswith("- ") or line.startswith("* ")
        ):
            desc = line.lstrip("0123456789.-*) ").strip()
            if desc:
                steps.append(
                    {"id": len(steps) + 1, "description": desc, "status": "pending"}
                )

    if not steps:
        steps = [{"id": 1, "description": task_desc or task_name, "status": "pending"}]

    return {
        "plan_steps": steps,
        "current_step_index": 0,
        "step_results": [],
        "pending_input": "",
    }


async def todo_node(state: TaskManagerState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    plan_steps = state.get("plan_steps", [])
    current_idx = state.get("current_step_index", 0)
    step_results = list(state.get("step_results", []))
    pending = state.get("pending_input", "")

    if current_idx >= len(plan_steps):
        return {}

    step = plan_steps[current_idx]
    step["status"] = "running"
    step_desc = step.get("description", "")

    context_parts = [
        f"执行以下任务步骤（{current_idx + 1}/{len(plan_steps)}）：{step_desc}"
    ]
    if pending:
        context_parts.insert(0, f"[用户最新要求]\n{pending}\n\n请优先考虑上述要求。")
    prompt = "\n\n".join(context_parts)

    agent_state = {
        "system_prompt": "You are a task execution assistant. Execute the given step precisely.",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    step["status"] = "done"
    step["result"] = result.get("final_text", "")
    step_results.append(
        {
            "step_id": step.get("id"),
            "description": step_desc,
            "result": result.get("final_text", ""),
            "status": "done",
        }
    )

    return {
        "current_step_index": current_idx + 1,
        "step_results": step_results,
        "plan_steps": plan_steps,
        "pending_input": "",
    }


async def check_node(state: TaskManagerState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {"check_pass": True}

    step_results = state.get("step_results", [])
    task_name = state.get("task_name", "")
    results_text = "\n\n".join(
        f"Step {r.get('step_id', '?')}: {r.get('description', '')}\nResult: {r.get('result', '')}"
        for r in step_results
    )

    prompt = (
        f"请评估以下任务执行结果是否符合要求：\n\n"
        f"任务：{task_name}\n\n"
        f"执行结果：\n{results_text}\n\n"
        "判断：结果是否完整达成了任务目标？\n"
        "回复 'PASS' 表示通过，回复 'RETRY' 表示需要重新执行（附简要原因）。"
    )
    agent_state = {
        "system_prompt": "你是一个质量验证助手。请评估任务执行结果。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    check_text = result.get("final_text", "").strip().upper()
    passed = "PASS" in check_text and "RETRY" not in check_text

    return {
        "check_pass": passed,
        "step_results": step_results,
    }


async def finalize_node(state: TaskManagerState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    step_results = state.get("step_results", [])
    task_name = state.get("task_name", "")
    summary_text = "\n".join(
        f"- {r.get('description', '')}: {r.get('result', '')[:300]}"
        for r in step_results
    )
    prompt = (
        f"请为以下已完成的任务生成最终摘要：\n\n"
        f"任务：{task_name}\n\n"
        f"执行结果：\n{summary_text}\n\n"
        "请用简洁的中文总结任务成果。"
    )
    agent_state = {
        "system_prompt": "你是一个任务摘要助手。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    return {
        "step_results": step_results,
        "check_pass": True,
        "final_summary": result.get("final_text", ""),
    }


def after_plan(state: TaskManagerState) -> str:
    steps = state.get("plan_steps", [])
    if not steps:
        return "rejected"
    return "to_approve"


async def approve_plan_node(state: TaskManagerState, config: RunnableConfig) -> dict:
    import uuid

    from astrbot.core.langgraph.interaction import CardAction, InteractionCard
    from astrbot.core.langgraph.interaction_manager import get_interaction_manager

    steps = state.get("plan_steps", [])
    task_name = state.get("task_name", "")
    steps_text = "\n".join(
        f"{s.get('id', i + 1)}. {s.get('description', '')}" for i, s in enumerate(steps)
    )

    card = InteractionCard(
        interaction_id=f"plan_approve_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title="执行计划审批",
        body=(
            f"任务「{task_name}」的执行计划如下：\n\n"
            f"{steps_text}\n\n"
            f"共 {len(steps)} 个步骤"
        ),
        actions=[
            CardAction(key="approve", label="批准执行", style="primary"),
            CardAction(key="reject", label="拒绝", style="danger"),
        ],
    )
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(card, thread_id="", channel="chatui")

    return {
        "plan_approved": response.action_key == "approve",
    }


def after_approve(state: TaskManagerState) -> str:
    if state.get("plan_approved", False):
        return "approved"
    return "rejected"


def after_todo(state: TaskManagerState) -> str:
    steps = state.get("plan_steps", [])
    current = state.get("current_step_index", 0)
    if current >= len(steps):
        return "done"
    return "continue"


def after_check(state: TaskManagerState) -> str:
    if state.get("check_pass", True):
        return "pass"
    return "retry"


def build_task_manager_graph(
    config: dict | None = None, checkpointer=None
) -> StateGraph:
    builder = StateGraph(TaskManagerState)

    builder.add_node("plan", plan_node)
    builder.add_node("approve_plan", approve_plan_node)
    builder.add_node("todo", todo_node)
    builder.add_node("check", check_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("plan")
    builder.add_conditional_edges(
        "plan",
        after_plan,
        {
            "to_approve": "approve_plan",
            "rejected": END,
        },
    )
    builder.add_conditional_edges(
        "approve_plan",
        after_approve,
        {
            "approved": "todo",
            "rejected": END,
        },
    )
    builder.add_conditional_edges(
        "todo",
        after_todo,
        {
            "continue": "todo",
            "done": "check",
        },
    )
    builder.add_conditional_edges(
        "check",
        after_check,
        {
            "pass": "finalize",
            "retry": "plan",
        },
    )
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
