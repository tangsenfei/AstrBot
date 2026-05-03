from __future__ import annotations

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()


class CrewState(AgentGraphState, total=False):
    crew_name: str
    tasks: list[dict]
    current_task_index: int
    task_results: list[dict]
    process: str


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


async def task_node(state: CrewState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    tasks = state.get("tasks", [])
    current_idx = state.get("current_task_index", 0)
    task_results = list(state.get("task_results", []))

    if current_idx >= len(tasks):
        return {}

    task = tasks[current_idx]
    task_desc = task.get("description", "")
    agent_name = task.get("agent", "")

    context = ""
    if task_results:
        context = "\n\nPrevious task results:\n" + "\n".join(
            f"- {r.get('description', '')}: {r.get('result', '')[:500]}"
            for r in task_results[-3:]
        )

    prompt = f"Execute the following task: {task_desc}{context}"
    system_prompt = (
        f"You are agent '{agent_name}'. Execute your assigned task precisely."
    )

    agent_state = {
        "system_prompt": system_prompt,
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    task_results.append(
        {
            "task_index": current_idx,
            "description": task_desc,
            "agent": agent_name,
            "result": result.get("final_text", ""),
        }
    )

    return {
        "current_task_index": current_idx + 1,
        "task_results": task_results,
    }


def sequential_router(state: CrewState) -> str:
    tasks = state.get("tasks", [])
    current_idx = state.get("current_task_index", 0)
    if current_idx >= len(tasks):
        return "done"
    return "continue"


def build_crew_graph(
    crew_def: dict | None = None, config: dict | None = None, checkpointer=None
) -> StateGraph:
    builder = StateGraph(CrewState)

    builder.add_node("execute_task", task_node)

    builder.set_entry_point("execute_task")
    builder.add_conditional_edges(
        "execute_task",
        sequential_router,
        {
            "continue": "execute_task",
            "done": END,
        },
    )

    return builder.compile(checkpointer=checkpointer)
