from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GraphRunContext


def resolve_provider(state: dict, run_ctx: GraphRunContext):
    provider_id = state.get("provider_id") or run_ctx.config.get("provider_id")
    if provider_id:
        astr_event = run_ctx.astr_event
        context = _extract_context(astr_event)
        if context is not None:
            provider_manager = context.provider_manager
            if provider_manager and provider_id in provider_manager.inst_map:
                return provider_manager.inst_map[provider_id]

    return run_ctx.provider


def _extract_context(astr_event):
    if astr_event is None:
        return None

    from astrbot.core.star.context import Context

    if isinstance(astr_event, Context):
        return astr_event

    context_attr = getattr(astr_event, "context", None)
    if isinstance(context_attr, Context):
        return context_attr

    if hasattr(astr_event, "context") and hasattr(context_attr, "context"):
        inner_ctx = getattr(context_attr, "context", None)
        if isinstance(inner_ctx, Context):
            return inner_ctx

    return None


def resolve_tools(state: dict, run_ctx: GraphRunContext):
    tool_names = state.get("func_tools")
    if not tool_names:
        return None

    astr_event = run_ctx.astr_event
    context = _extract_context(astr_event)
    if context is None:
        return None

    tool_manager = context.get_llm_tool_manager()
    if tool_manager is None:
        return None

    from astrbot.core.agent.tool import ToolSet

    tool_set = ToolSet()
    for name in tool_names:
        tool = tool_manager.get_func(name)
        if tool:
            tool_set.add_tool(tool)
    return tool_set if not tool_set.empty() else None
