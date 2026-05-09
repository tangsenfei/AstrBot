from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.agent.hooks import BaseAgentRunHooks
from astrbot.core.agent.runners.tool_loop_agent_runner import ToolLoopAgentRunner
from astrbot.core.astr_agent_context import AgentContextWrapper, AstrAgentContext
from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
from astrbot.core.provider.entities import ProviderRequest

from .adapters import resolve_provider, resolve_tools
from .state import AgentGraphResult, AgentGraphState, GraphRunContext, StreamEvent

if TYPE_CHECKING:
    pass


def _normalize_agent_context(run_ctx: GraphRunContext) -> Any:
    """Ensure run_ctx.astr_event can serve as AgentContextWrapper context.

    AgentContextWrapper expects AstrAgentContext (has .event and .context).
    Callers may pass a mock event, a Context, or a plain object directly.
    Wrap non-AstrAgentContext values so .event and .context are always accessible.
    """
    from astrbot.core.astr_agent_context import AstrAgentContext

    raw = run_ctx.astr_event
    if isinstance(raw, AstrAgentContext):
        return raw

    class _AgentCtxCompat:
        __slots__ = ("context", "event", "extra")
        def __init__(self, ctx_val, evt_val):
            self.context = ctx_val
            self.event = evt_val
            self.extra = {}

    if raw is None:
        return _AgentCtxCompat(None, None)

    has_event = hasattr(raw, "unified_msg_origin") or hasattr(raw, "message_str")
    if has_event:
        ctx_obj = run_ctx.astr_event.context if hasattr(run_ctx.astr_event, "context") else None
        if isinstance(ctx_obj, AstrAgentContext):
            return ctx_obj
        return _AgentCtxCompat(ctx_obj, raw)

    return _AgentCtxCompat(raw, None)


class _NoopHooks(BaseAgentRunHooks[AstrAgentContext]):
    pass


class AgentOperator:
    DEFAULT_MAX_STEPS = 30

    async def execute(
        self,
        state: AgentGraphState,
        run_ctx: GraphRunContext,
        *,
        max_steps: int | None = None,
        write_stream: bool = True,
    ) -> AgentGraphResult:
        if max_steps is None:
            max_steps = run_ctx.config.get("max_agent_step", self.DEFAULT_MAX_STEPS)

        provider = resolve_provider(state, run_ctx)
        if provider is None:
            logger.error("AgentOperator: no provider available for execution")
            return AgentGraphResult(
                final_text="",
                tool_calls=[],
                error="No provider available. Please configure a chat provider.",
                stats={},
            )

        try:
            req = ProviderRequest(
                prompt=state.get("user_prompt"),
                system_prompt=state.get("system_prompt"),
                contexts=state.get("messages", []),
                image_urls=state.get("image_urls", []),
                func_tool=resolve_tools(state, run_ctx),
                session_id=state.get("session_id", ""),
                model=state.get("model"),
            )

            runner = ToolLoopAgentRunner()
            astr_agent_ctx = _normalize_agent_context(run_ctx)
            await runner.reset(
                provider=provider,
                request=req,
                run_context=AgentContextWrapper(
                    context=astr_agent_ctx,
                    tool_call_timeout=run_ctx.config.get("tool_call_timeout", 60),
                ),
                tool_executor=run_ctx.tool_executor or FunctionToolExecutor(),
                agent_hooks=run_ctx.hooks or _NoopHooks(),
                streaming=run_ctx.config.get("streaming_response", False),
                enforce_max_turns=run_ctx.config.get("enforce_max_turns", -1),
                tool_schema_mode=run_ctx.config.get("tool_schema_mode", "full"),
                fallback_providers=run_ctx.config.get("fallback_providers", []),
                tool_result_overflow_dir=run_ctx.config.get("tool_result_overflow_dir"),
            )

            tool_calls = []
            final_text = ""
            reasoning_text = ""
            writer = run_ctx.writer

            trace_context = state.get("trace_context", {}) or {}

            async for resp in runner.step_until_done(max_steps):
                event = self._with_trace_context(self._to_stream_event(resp), trace_context)
                if write_stream and writer and event:
                    writer(event)
                if event and event.get("event") == "reasoning":
                    reasoning_text += str((event.get("data") or {}).get("text") or "")

                if resp.type == "tool_call":
                    tool_calls.append(resp.data)
                elif resp.type == "llm_result":
                    chain = resp.data.get("chain")
                    if chain:
                        final_text = chain.get_plain_text(with_other_comps_mark=True)

            if write_stream and writer and runner.stats:
                tok = runner.stats.token_usage
                writer(StreamEvent(
                    event="token",
                    data={
                        "input": getattr(tok, "input", getattr(tok, "prompt_tokens", 0) or 0),
                        "output": getattr(tok, "output", getattr(tok, "completion_tokens", 0) or 0),
                        **trace_context,
                    },
                    timestamp=time.time(),
                    node_id=str(trace_context.get("node_id") or "agent_operator"),
                ))

            return AgentGraphResult(
                final_text=final_text,
                reasoning_text=reasoning_text,
                tool_calls=tool_calls,
                stats=runner.stats.to_dict() if runner.stats else {},
            )
        except Exception as e:
            logger.error(f"AgentOperator execution error: {e}", exc_info=True)
            return AgentGraphResult(
                final_text="",
                tool_calls=[],
                error=str(e),
                stats={},
            )

    @staticmethod
    def _to_stream_event(resp) -> StreamEvent | None:
        if resp.type == "streaming_delta":
            chain = resp.data.get("chain")
            if chain and hasattr(chain, "type") and chain.type == "reasoning":
                return StreamEvent(
                    event="reasoning",
                    data={"text": chain.get_plain_text()},
                    timestamp=time.time(),
                    node_id="",
                )
            return StreamEvent(
                event="text_delta",
                data={"text": chain.get_plain_text() if chain else ""},
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "tool_call":
            chain = resp.data.get("chain")
            tool_info = {}
            if chain and hasattr(chain, "chain"):
                for comp in chain.chain:
                    if hasattr(comp, "data") and isinstance(comp.data, dict):
                        tool_info = comp.data
                        break
            return StreamEvent(
                event="tool_call",
                data=tool_info if tool_info else resp.data,
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "tool_call_result":
            chain = resp.data.get("chain")
            tool_result = {}
            if chain and hasattr(chain, "chain"):
                for comp in chain.chain:
                    if hasattr(comp, "data") and isinstance(comp.data, dict):
                        tool_result = comp.data
                        break
            return StreamEvent(
                event="tool_result",
                data=tool_result if tool_result else resp.data,
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "err":
            return StreamEvent(
                event="error",
                data={"message": str(resp.data)},
                timestamp=time.time(),
                node_id="",
            )
        return None

    @staticmethod
    def _with_trace_context(event: StreamEvent | None, trace_context: dict[str, Any]) -> StreamEvent | None:
        if not event or not trace_context:
            return event
        data = dict(event.get("data") or {})
        for key, value in trace_context.items():
            if value not in (None, "") and key not in data:
                data[key] = value
        node_id = event.get("node_id") or str(trace_context.get("node_id") or "")
        return StreamEvent(event=event["event"], data=data, timestamp=event["timestamp"], node_id=node_id)
