from __future__ import annotations

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core import logger
from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import GraphRunContext, MeetingState, StreamEvent

_agent_operator = AgentOperator()

IMPLEMENTED_STRATEGIES = {"standard", "brainstorm", "parliament"}


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


def _wrap_writer(run_ctx: GraphRunContext, agent_name: str, current_round: int):
    original_writer = run_ctx.writer

    def wrapped_writer(event: StreamEvent):
        if original_writer is None:
            return
        data = dict(event.get("data", {}))
        data["agent_name"] = agent_name
        data["round"] = current_round
        original_writer({**event, "data": data})

    return wrapped_writer


async def opening_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    host = state.get("host")
    topic = state.get("topic", "")
    if not host:
        return {"current_round": 1}

    host_name = host.get("name", "主持人")
    current_round = state.get("current_round", 0) + 1
    saved_writer = run_ctx.writer
    run_ctx.writer = _wrap_writer(run_ctx, host_name, current_round)

    host_prompt = f"你是会议主持人。请为以下主题的开场致辞：{topic}"
    agent_state = {
        "system_prompt": host.get("system_prompt", ""),
        "user_prompt": host_prompt,
        "messages": [],
        "provider_id": host.get("provider_id") or state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)
    run_ctx.writer = saved_writer

    opening_text = result.get("final_text", "")
    if result.get("error"):
        opening_text = f"[开场失败: {result['error']}]"
    return {
        "current_round": 1,
        "round_results": state.get("round_results", []) + [f"[开场] {opening_text}"],
    }


async def agent_speak_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    participants = state.get("participants", [])
    current_round = state.get("current_round", 1)
    round_results = list(state.get("round_results", []))

    for participant in participants:
        context = "\n".join(round_results[-5:])
        prompt = (
            f"会议主题: {state.get('topic', '')}\n"
            f"当前轮次: {current_round}\n"
            f"讨论上下文:\n{context}\n\n请发表你的观点。"
        )
        agent_state = {
            "system_prompt": participant.get("system_prompt", ""),
            "user_prompt": prompt,
            "messages": [],
            "provider_id": participant.get("provider_id") or state.get("provider_id"),
            "session_id": state.get("session_id", ""),
        }

        agent_name = participant.get("name", "Agent")
        saved_writer = run_ctx.writer
        run_ctx.writer = _wrap_writer(run_ctx, agent_name, current_round)

        result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)
        run_ctx.writer = saved_writer

        speech = result.get("final_text", "")
        if result.get("error"):
            speech = f"[发言失败: {result['error']}]"
        round_results.append(f"[{participant.get('name', 'Agent')}] {speech}")

    return {
        "round_results": round_results,
        "current_round": current_round + 1,
    }


async def host_integrate_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    host = state.get("host")
    if not host:
        return {}

    round_results = state.get("round_results", [])
    current_round = state.get("current_round", 1)
    recent = "\n".join(round_results[-10:])
    prompt = f"请总结本轮讨论要点：\n{recent}"

    host_name = host.get("name", "主持人")
    saved_writer = run_ctx.writer
    run_ctx.writer = _wrap_writer(run_ctx, host_name, current_round)

    agent_state = {
        "system_prompt": host.get("system_prompt", ""),
        "user_prompt": prompt,
        "messages": [],
        "provider_id": host.get("provider_id") or state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)
    run_ctx.writer = saved_writer

    summary = result.get("final_text", "")
    if result.get("error"):
        summary = f"[总结失败: {result['error']}]"
    return {"round_results": round_results + [f"[主持人总结] {summary}"]}


async def finalize_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    host = state.get("host")
    round_results = state.get("round_results", [])
    all_discussion = "\n".join(round_results)
    topic = state.get("topic", "")

    prompt = f"请根据以下讨论内容，生成会议纪要：\n{all_discussion}"
    system_prompt = (
        host.get("system_prompt", "") if host else "你是一个会议纪要生成助手。"
    )
    provider_id = host.get("provider_id") if host else None
    agent_state = {
        "system_prompt": system_prompt,
        "user_prompt": prompt,
        "messages": [],
        "provider_id": provider_id or state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }

    finalizer_name = host.get("name", "纪要生成") if host else "纪要生成"
    current_round = state.get("current_round", 0)
    saved_writer = run_ctx.writer
    run_ctx.writer = _wrap_writer(run_ctx, finalizer_name, current_round)

    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)
    run_ctx.writer = saved_writer

    final_text = result.get("final_text", "")
    if result.get("error"):
        final_text = f"[纪要生成失败: {result['error']}]"
    logger.info(f"finalize_node: round_results={len(round_results)}, final_text_len={len(final_text)}, error={result.get('error', 'None')}")

    deliverable_prompt = f"根据以下会议讨论内容，生成具体的、可执行的交付物文档：\n\n会议主题：{topic}\n\n讨论内容：\n{all_discussion}\n\n请直接输出交付物内容，不要包含额外的说明。"
    deliverable_state = {
        "system_prompt": system_prompt,
        "user_prompt": deliverable_prompt,
        "messages": [],
        "provider_id": provider_id or state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }

    run_ctx.writer = _wrap_writer(run_ctx, "交付物生成", current_round)
    deliverable_result = await _agent_operator.execute(deliverable_state, run_ctx, write_stream=True)
    run_ctx.writer = saved_writer

    deliverable_text = deliverable_result.get("final_text", "")
    if deliverable_result.get("error"):
        logger.warning(f"Deliverable generation failed: {deliverable_result['error']}")
        deliverable_text = ""

    return {"final_minutes": final_text, "deliverable_output": deliverable_text}


def standard_router(state: MeetingState) -> str:
    current = state.get("current_round", 0)
    if current >= state.get("max_rounds", 3):
        return "finalize"
    return "next_agent"


def brainstorm_router(state: MeetingState) -> str:
    return standard_router(state)


def parliament_router(state: MeetingState) -> str:
    return standard_router(state)


STRATEGY_ROUTERS = {
    "standard": standard_router,
    "brainstorm": brainstorm_router,
    "parliament": parliament_router,
}


def _after_speak_router(state: MeetingState) -> str:
    host = state.get("host")
    if host:
        return "host_integrate"
    router = STRATEGY_ROUTERS.get(state.get("strategy", "standard"), standard_router)
    return router(state)


def build_meeting_graph(
    strategy: str = "standard",
    config: dict | None = None,
    checkpointer=None,
) -> StateGraph:
    if strategy not in STRATEGY_ROUTERS:
        strategy = "standard"

    builder = StateGraph(MeetingState)

    builder.add_node("opening", opening_node)
    builder.add_node("agent_speak", agent_speak_node)
    builder.add_node("host_integrate", host_integrate_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("opening")
    builder.add_edge("opening", "agent_speak")

    router = STRATEGY_ROUTERS[strategy]
    builder.add_conditional_edges(
        "host_integrate",
        router,
        {
            "next_agent": "agent_speak",
            "next_round": "opening",
            "finalize": "finalize",
        },
    )
    builder.add_conditional_edges(
        "agent_speak",
        _after_speak_router,
        {
            "host_integrate": "host_integrate",
            "next_agent": "agent_speak",
            "next_round": "opening",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
