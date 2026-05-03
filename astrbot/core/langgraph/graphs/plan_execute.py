from __future__ import annotations

import re

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import GraphRunContext, PlanExecuteState

_agent_operator = AgentOperator()

PLANNING_PROMPTS = {
    "low": "请简要列出完成以下任务的关键步骤（1-3步）：\n\n任务：{task}\n\n请按以下格式输出：\n## 执行计划\n1. [步骤1]\n2. [步骤2]\n...",
    "medium": "请为以下任务制定详细的执行计划，包含具体步骤和预期结果：\n\n任务：{task}\n\n请按以下格式输出：\n## 执行计划\n### 步骤1: [标题]\n- 描述: ...\n- 预期输出: ...\n\n### 步骤2: [标题]\n- 描述: ...\n- 预期输出: ...\n...",
    "high": "请为以下任务制定非常详细的执行计划。\n任务：{task}\n请按以下格式输出：\n## 执行计划\n\n### 步骤1: [标题]\n- 描述: ...\n\n### 步骤2: [标题]\n- 描述: ...\n...",
}

_STEP_PATTERN = re.compile(
    r"^(?:\d+[\.\)]\s*|[-*]\s+|#{1,4}\s*步骤\s*\d+\s*[:：]?\s*)", re.UNICODE
)


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


async def generate_plan_node(state: PlanExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {"plan_steps": [], "current_step_index": 0, "step_results": []}

    task = state.get("task", "")
    effort = state.get("planning_effort", "medium")
    planning_prompt = PLANNING_PROMPTS.get(effort, PLANNING_PROMPTS["medium"])

    prompt = planning_prompt.format(task=task)
    agent_state = {
        "system_prompt": "你是一个任务规划助手。请根据任务要求制定结构化的执行计划。",
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
        if not line:
            continue
        m = _STEP_PATTERN.match(line)
        if m:
            desc = line[m.end() :].strip()
            if desc:
                steps.append({"step_id": len(steps) + 1, "description": desc})

    if not steps:
        steps = [{"step_id": 1, "description": task}]

    return {"plan_steps": steps, "current_step_index": 0, "step_results": []}


async def human_approval_node(state: PlanExecuteState, config: RunnableConfig) -> dict:
    import uuid

    plan_steps = state.get("plan_steps", [])
    steps_text = "\n".join(f"  {s['step_id']}. {s['description']}" for s in plan_steps)

    from astrbot.core.langgraph.interaction import CardAction, InteractionCard
    from astrbot.core.langgraph.interaction_manager import get_interaction_manager

    card = InteractionCard(
        interaction_id=f"plan_approve_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title="执行计划审批",
        body=f"以下执行计划已生成，请审批：\n\n{steps_text}",
        actions=[
            CardAction(key="approve", label="批准", style="primary"),
            CardAction(key="reject", label="拒绝", style="danger"),
        ],
    )
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(card, thread_id="", channel="chatui")
    approved = response.action_key == "approve"

    return {"human_approved": approved}


async def execute_step_node(state: PlanExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    plan_steps = state.get("plan_steps", [])
    current_idx = state.get("current_step_index", 0)
    step_results = list(state.get("step_results", []))

    if current_idx >= len(plan_steps):
        return {}

    step = plan_steps[current_idx]
    step_desc = step.get("description", "")

    prompt = (
        f"Execute the following step: {step_desc}\n\n"
        f"Context: This is step {current_idx + 1} of {len(plan_steps)}."
    )
    agent_state = {
        "system_prompt": "You are a task execution assistant. Execute the given step precisely.",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    step_results.append(
        {
            "step_id": step.get("step_id"),
            "description": step_desc,
            "result": result.get("final_text", ""),
        }
    )

    return {
        "current_step_index": current_idx + 1,
        "step_results": step_results,
    }


async def summarize_node(state: PlanExecuteState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    step_results = state.get("step_results", [])
    results_text = "\n\n".join(
        f"Step {r['step_id']}: {r['description']}\nResult: {r['result']}"
        for r in step_results
    )

    prompt = f"Summarize the execution results:\n\n{results_text}"
    agent_state = {
        "system_prompt": "You are a task summary assistant.",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    return {
        "step_results": step_results
        + [
            {
                "step_id": 0,
                "description": "Summary",
                "result": result.get("final_text", ""),
            }
        ]
    }


def should_continue_execution(state: PlanExecuteState) -> str:
    plan_steps = state.get("plan_steps", [])
    current_idx = state.get("current_step_index", 0)
    if current_idx >= len(plan_steps):
        return "summarize"
    return "execute"


def after_approval_router(state: PlanExecuteState) -> str:
    if not state.get("human_approved", False):
        return "reject"
    return "execute"


def build_plan_execute_graph(
    config: dict | None = None, checkpointer=None
) -> StateGraph:
    builder = StateGraph(PlanExecuteState)

    builder.add_node("generate_plan", generate_plan_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("execute_step", execute_step_node)
    builder.add_node("summarize", summarize_node)

    builder.set_entry_point("generate_plan")
    builder.add_edge("generate_plan", "human_approval")
    builder.add_conditional_edges(
        "human_approval",
        after_approval_router,
        {
            "execute": "execute_step",
            "reject": END,
        },
    )
    builder.add_conditional_edges(
        "execute_step",
        should_continue_execution,
        {
            "execute": "execute_step",
            "summarize": "summarize",
        },
    )
    builder.add_edge("summarize", END)

    return builder.compile(checkpointer=checkpointer)
