from __future__ import annotations

import json
import re

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()

MAX_RETRY_LOOPS = 100


class TaskExecuteState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    todo_steps: list[dict]
    current_step_index: int
    pending_input: str
    cancelled: bool
    final_summary: str
    planning_enabled: bool
    human_approved: bool
    reject_feedback: str
    retry_count: int
    tokens: dict


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


async def plan_node(state: TaskExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    pending = state.get("pending_input", "")
    reject_feedback = state.get("reject_feedback", "")
    retry_count = state.get("retry_count", 0)

    extra = ""
    if pending:
        extra = f"\n\n[用户补充要求]\n{pending}"
    if reject_feedback:
        extra += f"\n\n[驳回重生成 - 第{retry_count}次修改]\n驳回意见：{reject_feedback}\n请根据驳回意见重新生成步骤。"

    prompt = (
        "请将以下任务拆解为具体的执行步骤（3-7步）。"
        "每个步骤用祈使句描述，并给出进行时态（activeForm）。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}{extra}\n\n"
        "请按以下 JSON 格式输出步骤列表：\n"
        '```json\n{"steps": [{"content": "分析现有架构", "activeForm": "正在分析现有架构", "dependencies": []}]}\n```'
    )
    agent_state = {
        "system_prompt": "你是一个任务规划助手。请将任务拆解为可执行的步骤。严格按 JSON 格式输出。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )

    plan_text = result.get("final_text", "")
    steps = _parse_steps(plan_text)
    if not steps:
        steps = [
            {
                "content": task_desc or task_name,
                "activeForm": f"正在执行{task_name}",
                "dependencies": [],
                "status": "pending",
                "result": "",
            }
        ]

    tokens = _accumulate_tokens(state, result)

    return {
        "todo_steps": steps,
        "current_step_index": 0,
        "pending_input": "",
        "reject_feedback": "",
        "tokens": tokens,
    }


async def approve_plan_node(
    state: TaskExecuteState, config: RunnableConfig
) -> dict:
    from astrbot.core.langgraph.interaction import CardAction, InteractionCard
    from astrbot.core.langgraph.interaction_manager import get_interaction_manager

    run_ctx = _get_run_ctx(config)
    writer = getattr(run_ctx, "writer", None) if run_ctx else None

    plan_steps = state.get("todo_steps", [])
    retry_count = state.get("retry_count", 0)

    steps_text = "\n".join(
        f"  {i + 1}. {s.get('content', s.get('description', ''))}"
        for i, s in enumerate(plan_steps)
    )

    title = "执行计划审批"
    if retry_count > 0:
        title = f"执行计划审批（第 {retry_count} 次修改）"

    card = InteractionCard(
        interaction_id=f"plan_approve_{state.get('task_id', '')}",
        type="plan_approval",
        title=title,
        body=f"以下执行计划已生成，请审批：\n\n{steps_text}",
        fields=[
            {
                "key": "feedback",
                "label": "修改意见",
                "field_type": "textarea",
                "required": False,
            }
        ],
        actions=[
            CardAction(key="approve", label="通过", style="primary"),
            CardAction(key="modify", label="修改", style="default"),
            CardAction(key="reject", label="取消", style="danger"),
        ],
    )
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(
        card,
        thread_id="",
        channel="chatui",
        channel_extra={"writer": writer},
    )

    action_key = response.action_key
    if action_key == "approve":
        return {
            "human_approved": True,
            "reject_feedback": "",
            "retry_count": 0,
        }
    elif action_key == "modify":
        feedback = response.field_values.get("feedback", "") or "需要修改方案"
        return {
            "human_approved": False,
            "reject_feedback": feedback,
            "retry_count": retry_count + 1,
        }
    else:
        return {
            "human_approved": False,
            "reject_feedback": "cancelled",
            "retry_count": 0,
        }


async def todo_node(state: TaskExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    steps = state.get("todo_steps", [])
    if not steps:
        return {}

    current = None
    current_idx = 0
    for i, step in enumerate(steps):
        if step.get("status") == "pending":
            deps = step.get("dependencies", [])
            blocked = False
            for dep_id in deps:
                if isinstance(dep_id, int) and 0 <= dep_id - 1 < len(steps):
                    dep_status = steps[dep_id - 1].get("status", "")
                    if dep_status == "failed":
                        blocked = True
                        break
            if blocked:
                continue
            current = step
            current_idx = i
            step["status"] = "in_progress"
            break

    if current is None:
        return {}

    step_content = current.get("content", "")
    step_active = current.get("activeForm", step_content)
    pending = state.get("pending_input", "")
    task_name = state.get("task_name", "")

    completed_summary = ""
    done_steps = [s for s in steps if s.get("status") == "completed"]
    if done_steps:
        completed_summary = "\n".join(
            f"- {s.get('content', '')}: {s.get('result', '')[:200]}"
            for s in done_steps[-3:]
        )
        completed_summary = f"\n\n已完成步骤：\n{completed_summary}"

    context_parts = [
        f"执行以下任务步骤（{current_idx + 1}/{len(steps)}）：{step_content}",
        f"任务名称：{task_name}",
    ]
    if pending:
        context_parts.insert(0, f"[用户最新要求]\n{pending}\n\n请优先考虑上述要求。")
    if completed_summary:
        context_parts.append(completed_summary)
    prompt = "\n\n".join(context_parts)

    agent_state = {
        "system_prompt": f"你是任务执行助手。{step_active}。完成后简要报告结果。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )

    current["status"] = "completed"
    current["result"] = result.get("final_text", "")
    tokens = _accumulate_tokens(state, result)

    return {
        "todo_steps": steps,
        "current_step_index": current_idx + 1,
        "pending_input": "",
        "tokens": tokens,
    }


async def check_node(state: TaskExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {"cancelled": False}

    steps = state.get("todo_steps", [])
    task_name = state.get("task_name", "")
    results_text = "\n\n".join(
        f"Step {i + 1}: {s.get('content', '')}\nResult: {s.get('result', '')}"
        for i, s in enumerate(steps)
        if s.get("status") == "completed"
    )

    prompt = (
        f"请评估以下任务执行结果是否符合要求：\n\n"
        f"任务：{task_name}\n\n"
        f"执行结果：\n{results_text}\n\n"
        "判断：结果是否完整达成了任务目标？\n"
        "回复 PASS 表示通过，回复 RETRY 表示需要重新执行（附简要原因）。"
    )
    agent_state = {
        "system_prompt": "你是一个质量验证助手。请评估任务执行结果。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )

    check_text = result.get("final_text", "").strip().upper()
    passed = "PASS" in check_text and "RETRY" not in check_text
    tokens = _accumulate_tokens(state, result)

    return {"cancelled": not passed, "tokens": tokens}


async def finalize_node(
    state: TaskExecuteState, config: RunnableConfig
) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    steps = state.get("todo_steps", [])
    task_name = state.get("task_name", "")
    summary_text = "\n".join(
        f"- {s.get('content', '')}: {s.get('result', '')[:300]}"
        for s in steps
        if s.get("status") == "completed"
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
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )

    return {"final_summary": result.get("final_text", ""), "cancelled": False}


async def cancel_node(
    state: TaskExecuteState, config: RunnableConfig
) -> dict:
    return {"cancelled": True}


def after_plan(state: TaskExecuteState) -> str:
    if state.get("planning_enabled", False):
        return "approve"
    return "todo"


def after_approval(state: TaskExecuteState) -> str:
    if state.get("human_approved", False):
        return "todo"
    feedback = state.get("reject_feedback", "")
    retry = state.get("retry_count", 0)
    if feedback == "cancelled":
        return "cancel"
    if retry < MAX_RETRY_LOOPS:
        return "retry"
    return "cancel"


def after_todo(state: TaskExecuteState) -> str:
    steps = state.get("todo_steps", [])
    all_done = all(
        s.get("status") in ("completed", "failed") for s in steps
    )
    if all_done:
        return "check"
    return "todo"


def after_check(state: TaskExecuteState) -> str:
    if state.get("cancelled", False):
        return "retry"
    return "finalize"


def _parse_steps(text: str) -> list[dict]:
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            steps = data.get("steps", [])
            for s in steps:
                s.setdefault("status", "pending")
                s.setdefault("activeForm", s.get("content", ""))
                s.setdefault("dependencies", [])
                s.setdefault("result", "")
            return steps
        except json.JSONDecodeError:
            pass

    steps = []
    for line in text.split("\n"):
        line = line.strip()
        if line and (
            line[0].isdigit()
            or line.startswith("- ")
            or line.startswith("* ")
        ):
            desc = line.lstrip("0123456789.-*) ").strip()
            if desc:
                steps.append({
                    "content": desc,
                    "activeForm": f"正在{desc[:30]}",
                    "dependencies": [],
                    "status": "pending",
                    "result": "",
                })
    return steps


def _accumulate_tokens(state: dict, result: dict) -> dict:
    current = dict(state.get("tokens") or {})
    stats = result.get("stats", {})
    usage = stats.get("token_usage", {})
    current.setdefault("input", 0)
    current.setdefault("output", 0)
    current.setdefault("total", 0)
    current["input"] += usage.get("input", usage.get("prompt_tokens", 0))
    current["output"] += usage.get("output", usage.get("completion_tokens", 0))
    current["total"] += usage.get("total", usage.get("total_tokens", 0))
    return current


def build_task_graph(
    config: dict | None = None, checkpointer=None
) -> StateGraph:
    builder = StateGraph(TaskExecuteState)

    builder.add_node("plan", plan_node)
    builder.add_node("approve_plan", approve_plan_node)
    builder.add_node("todo", todo_node)
    builder.add_node("check", check_node)
    builder.add_node("finalize", finalize_node)
    builder.add_node("cancel", cancel_node)

    builder.set_entry_point("plan")
    builder.add_conditional_edges("plan", after_plan, {
        "approve": "approve_plan",
        "todo": "todo",
    })
    builder.add_conditional_edges("approve_plan", after_approval, {
        "todo": "todo",
        "cancel": "cancel",
        "retry": "plan",
    })
    builder.add_conditional_edges("todo", after_todo, {
        "todo": "todo",
        "check": "check",
    })
    builder.add_conditional_edges("check", after_check, {
        "finalize": "finalize",
        "retry": "plan",
    })
    builder.add_edge("finalize", END)
    builder.add_edge("cancel", END)

    return builder.compile(checkpointer=checkpointer)
