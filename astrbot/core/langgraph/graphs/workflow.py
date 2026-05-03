from __future__ import annotations

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import GraphRunContext, WorkflowState

_agent_operator = AgentOperator()


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


async def crew_node(state: WorkflowState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    node_id = state.get("current_node_id", "")
    flow_def = state.get("flow_definition", {})
    nodes = flow_def.get("nodes", [])
    node_config = {}
    for n in nodes:
        if n.get("id") == node_id:
            node_config = n.get("config", {})
            break

    prompt = node_config.get("prompt", f"Execute task for node: {node_id}")
    system_prompt = node_config.get(
        "system_prompt", "You are a task execution assistant."
    )

    agent_state = {
        "system_prompt": system_prompt,
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    node_results = dict(state.get("node_results", {}))
    node_results[node_id] = result.get("final_text", "")
    return {"node_results": node_results}


async def human_node(state: WorkflowState, config: RunnableConfig) -> dict:
    import uuid

    node_id = state.get("current_node_id", "")
    flow_def = state.get("flow_definition", {})
    nodes = flow_def.get("nodes", [])
    node_config = {}
    for n in nodes:
        if n.get("id") == node_id:
            node_config = n.get("config", {})
            break

    prompt = node_config.get("prompt", f"Please provide input for node: {node_id}")

    from astrbot.core.langgraph.interaction import CardAction, InteractionCard
    from astrbot.core.langgraph.interaction_manager import get_interaction_manager

    card = InteractionCard(
        interaction_id=f"workflow_human_{uuid.uuid4().hex[:12]}",
        type="workflow_human",
        title=f"人工节点: {node_id}",
        body=prompt or "请提供输入",
        fields=[
            {
                "key": "user_input",
                "label": "输入",
                "field_type": "textarea",
                "required": True,
            }
        ],
        actions=[
            CardAction(key="submit", label="提交", style="primary"),
            CardAction(key="skip", label="跳过", style="default"),
        ],
    )
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(card, thread_id="", channel="chatui")

    node_results = dict(state.get("node_results", {}))
    if response.action_key == "submit":
        user_input = response.field_values.get("user_input", "")
        node_results[node_id] = f"用户输入: {user_input}"
    else:
        node_results[node_id] = "已跳过"
    return {"node_results": node_results}


async def router_node(state: WorkflowState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    node_id = state.get("current_node_id", "")
    node_results = state.get("node_results", {})

    prompt = (
        f"Based on the current results: {node_results}, "
        f"determine the next path for router node {node_id}."
    )
    agent_state = {
        "system_prompt": "You are a routing assistant. Determine the next path.",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)

    node_results = dict(node_results)
    node_results[node_id] = result.get("final_text", "")
    return {"node_results": node_results}


async def start_node(state: WorkflowState, config: RunnableConfig) -> dict:
    return {}


def build_workflow_graph(
    flow_def: dict | None = None, config: dict | None = None, checkpointer=None
) -> StateGraph:
    if flow_def is None:
        flow_def = (config or {}).get("flow_definition", {})
    builder = StateGraph(WorkflowState)

    nodes = flow_def.get("nodes", [])
    edges = flow_def.get("edges", [])

    for node in nodes:
        node_type = node.get("type", "crew")
        node_id = node.get("id", "")

        if node_type == "start":
            builder.add_node(node_id, start_node)
        elif node_type == "crew":
            builder.add_node(node_id, crew_node)
        elif node_type == "human":
            builder.add_node(node_id, human_node)
        elif node_type == "router":
            builder.add_node(node_id, router_node)
        else:
            builder.add_node(node_id, crew_node)

    start_nodes = [n for n in nodes if n.get("type") == "start"]
    if start_nodes:
        builder.set_entry_point(start_nodes[0]["id"])
    elif nodes:
        builder.set_entry_point(nodes[0]["id"])

    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")

        if not source or not target:
            continue

        if source == "start" and start_nodes:
            source = start_nodes[0]["id"]

        if target == "end":
            builder.add_edge(source, END)
        else:
            builder.add_edge(source, target)

    return builder.compile(checkpointer=checkpointer)
