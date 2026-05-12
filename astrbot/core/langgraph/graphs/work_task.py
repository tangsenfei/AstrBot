from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from astrbot.core.langgraph.hitl_card_builder import build_hitl_card
from astrbot.core.langgraph.interaction import CardAction, CardField, InteractionCard
from astrbot.core.langgraph.interaction_manager import get_interaction_manager
from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()

_WORK_LLM_ACTIVITY_EVENTS = {"text_delta", "reasoning", "tool_call", "tool_result"}
_WORK_LLM_TEXT_EVENTS = {"text_delta", "reasoning"}
_WORK_LLM_DEFAULT_IDLE_TIMEOUT_SECONDS = 120.0
_WORK_LLM_STREAM_FLUSH_INTERVAL_SECONDS = 0.5
_WORK_LLM_STREAM_FLUSH_CHARS = 1000
_WORK_LLM_AUTO_RETRY_DELAYS_SECONDS = (2.0, 5.0)
_WORK_LLM_TRANSPORT_ERROR_MARKERS = (
    "APIConnectionError",
    "RemoteProtocolError",
    "incomplete chunked read",
    "peer closed connection",
    "Connection error",
)
_WORK_PLAN_AUTO_REPAIR_MAX_ATTEMPTS = 5


class WorkLLMIdleTimeout(RuntimeError):
    pass


class WorkLLMCallError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        diagnostic: dict[str, Any] | None = None,
        partial_text: str = "",
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.diagnostic = diagnostic or {}
        self.partial_text = partial_text

_NODE_STAGE_MAP = {
    "prepare": "stage_clarify",
    "clarify": "stage_clarify",
    "plan": "stage_plan",
    "approve_plan": "stage_plan",
    "execute": "stage_execute",
    "review": "stage_review",
    "rework_hitl": "stage_review",
    "finalize": "stage_deliver",
}

_WORK_AGENT_LABELS = {
    "agent_nicebot_work_assistant": "NiceBot 任务助手",
    "agent_nicebot_work_executor": "通用任务执行智能体",
    "agent_nicebot_work_reviewer": "通用任务审查智能体",
    "agent_nicebot_research_expert": "调查专家",
    "agent_nicebot_report_expert": "汇报专家",
}

_WORK_ROLE_LABELS = {
    "assistant": "NiceBot 任务助手",
    "executor": "通用任务执行智能体",
    "reviewer": "通用任务审查智能体",
    "researcher": "调查专家",
    "reporter": "汇报专家",
}


class WorkTaskState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    work_task_kind: str
    task_mode: str
    executor_config: dict[str, Any]
    plan_config: dict[str, Any]
    review_config: dict[str, Any]
    clarification_config: dict[str, Any]
    input: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    stage_steps: list[dict[str, Any]]
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
    clarification_feedback: str
    interrogation_history: list[dict[str, Any]]
    interrogation_round: int
    interrogation_ready: bool
    interrogation_summary: str
    retry_config: dict[str, Any]


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


def _pause_requested_for_task(task_id: str) -> bool:
    if not task_id:
        return False
    try:
        from astrbot.builtin_stars.agent_system.database import get_database

        db = get_database()
        row = db.select_one("agent_tasks", where="id = ?", where_params=(task_id,))
        return bool(row and row.get("status") == "pause_requested")
    except Exception:
        return False


def _interrupt_if_pause_requested(
    state: WorkTaskState, config: RunnableConfig, node_id: str
) -> None:
    task_id = str(state.get("task_id") or "")
    if not _pause_requested_for_task(task_id):
        return
    run_ctx = _get_run_ctx(config)
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "paused",
            "label": "任务已在安全点暂停",
            "status": "paused",
            "progress": state.get("progress", 0),
        },
        node_id,
    )
    interrupt(
        {
            "type": "work_pause",
            "task_id": task_id,
            "node_id": node_id,
            "message": "任务已在安全点暂停",
        }
    )


def _trace_context(
    node_id: str,
    *,
    stage_id: str | None = None,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "stage_id": stage_id or _NODE_STAGE_MAP.get(node_id, ""),
        "step_id": str(step_id or ""),
        "agent_id": agent_id or "",
        "agent_label": agent_label or agent_id or "",
    }


def _emit(
    run_ctx: GraphRunContext | None,
    event: str,
    data: dict[str, Any],
    node_id: str = "",
    *,
    stage_id: str | None = None,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> None:
    writer = getattr(run_ctx, "writer", None) if run_ctx else None
    if not writer:
        return
    payload = dict(data or {})
    trace = _trace_context(
        node_id,
        stage_id=stage_id or payload.get("stage_id"),
        step_id=step_id if step_id is not None else payload.get("step_id"),
        agent_id=agent_id or payload.get("agent_id"),
        agent_label=agent_label or payload.get("agent_label"),
    )
    for key, value in trace.items():
        if value not in (None, "") and key not in payload:
            payload[key] = value
    writer(
        {"event": event, "data": payload, "timestamp": time.time(), "node_id": node_id}
    )


def _emit_reasoning_from_result(
    run_ctx: GraphRunContext | None,
    result: dict[str, Any],
    node_id: str,
    *,
    agent_id: str | None = None,
    agent_label: str | None = None,
) -> None:
    reasoning_text = str((result or {}).get("reasoning_text") or "").strip()
    if reasoning_text:
        _emit(
            run_ctx,
            "reasoning",
            {"text": reasoning_text},
            node_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )


def _llm_idle_timeout_seconds(*configs: dict[str, Any] | None) -> float:
    for key in ("content_idle_timeout_seconds", "idle_timeout_seconds"):
        for config in configs:
            if not isinstance(config, dict) or key not in config:
                continue
            try:
                value = float(config.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    for key in ("content_timeout_seconds", "timeout_seconds"):
        for config in configs:
            if not isinstance(config, dict) or key not in config:
                continue
            try:
                value = float(config.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    return _WORK_LLM_DEFAULT_IDLE_TIMEOUT_SECONDS


def _emit_token_from_stats(
    run_ctx: GraphRunContext | None,
    stats: dict[str, Any],
    node_id: str,
    *,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
    call_id: str | None = None,
    call_attempt: int | None = None,
) -> None:
    if not isinstance(stats, dict) or not stats:
        return
    tok_usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}
    if not isinstance(tok_usage, dict):
        return
    _emit(
        run_ctx,
        "token",
        {
            "input": tok_usage.get("input", 0),
            "output": tok_usage.get("output", 0),
            **({"call_id": call_id} if call_id else {}),
            **({"call_attempt": call_attempt} if call_attempt is not None else {}),
        },
        node_id,
        step_id=step_id,
        agent_id=agent_id,
        agent_label=agent_label,
        )


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def _work_llm_input_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "system_prompt",
        "user_prompt",
        "messages",
        "compact_context",
        "func_tools",
    )
    return {key: _json_safe(payload.get(key)) for key in allowed_keys if key in payload}


def _provider_diag_value(provider: Any, key: str) -> Any:
    config = getattr(provider, "provider_config", None)
    if isinstance(config, dict):
        return config.get(key)
    return None


def _provider_diagnostics(payload: dict[str, Any], run_ctx: GraphRunContext) -> dict[str, Any]:
    provider_id = str(payload.get("provider_id") or "")
    provider = None
    context = getattr(run_ctx, "astr_event", None)
    context_obj = getattr(context, "context", context)
    if context_obj and provider_id and hasattr(context_obj, "get_provider_by_id"):
        try:
            provider = context_obj.get_provider_by_id(provider_id)
        except Exception:
            provider = None
    if provider is None:
        provider = getattr(run_ctx, "provider", None)
    return {
        "task_id": str((payload.get("trace_context") or {}).get("task_id") or ""),
        "provider_id": provider_id or str(_provider_diag_value(provider, "id") or ""),
        "model": str(payload.get("model") or _provider_diag_value(provider, "model") or ""),
        "api_base": str(_provider_diag_value(provider, "api_base") or ""),
        "streaming": bool((run_ctx.config or {}).get("streaming_response", False)),
        "stream_include_usage": bool(
            _provider_diag_value(provider, "stream_include_usage") is True
        ),
    }


def _is_transport_llm_error(message: str) -> bool:
    text = str(message or "")
    return any(marker in text for marker in _WORK_LLM_TRANSPORT_ERROR_MARKERS)


def _user_facing_llm_error(message: str) -> str:
    text = str(message or "").strip()
    if _is_transport_llm_error(text):
        return f"上游模型流式连接中断：{text}"
    return f"LLM 调用失败：{text}" if text else "LLM 调用失败"


async def _run_work_llm_call(
    payload: dict[str, Any],
    run_ctx: GraphRunContext,
    *,
    node_id: str,
    idle_timeout_seconds: float,
    step_id: Any = None,
    agent_id: str | None = None,
    agent_label: str | None = None,
    stream_text: bool = True,
    stream_reasoning: bool = True,
    max_steps: int | None = None,
) -> dict[str, Any]:
    call_id = uuid.uuid4().hex
    last_activity = time.monotonic()
    call_started_at = last_activity
    activity_event = asyncio.Event()
    text_buffers: dict[str, str] = {"text_delta": "", "reasoning": ""}
    streamed_totals: dict[str, str] = {"text_delta": "", "reasoning": ""}
    last_flush_at = {"text_delta": last_activity, "reasoning": last_activity}
    last_lane = "reasoning"
    token_seen = False
    error_event_seen = False
    chunk_count = 0
    tool_event_count = 0
    attempt = 0
    diagnostic = _provider_diagnostics(payload, run_ctx)

    def emit_agent_call_end(
        status: str,
        *,
        diag: dict[str, Any] | None = None,
        error_message: str = "",
        retryable: bool | None = None,
    ) -> None:
        _emit(
            run_ctx,
            "agent_call_end",
            {
                "call_id": call_id,
                "call_attempt": attempt,
                "agent_call_status": status,
                "duration_ms": int((time.monotonic() - call_started_at) * 1000),
                "diagnostic": diag or {
                    **diagnostic,
                    "node_id": node_id,
                    "step_id": str(step_id or ""),
                    "attempt": attempt,
                    "chunk_count": chunk_count,
                    "tool_event_count": tool_event_count,
                    "output_chars": len(streamed_totals.get("text_delta", "")),
                    "reasoning_chars": len(streamed_totals.get("reasoning", "")),
                },
                **({"message": error_message} if error_message else {}),
                **({"retryable": retryable} if retryable is not None else {}),
            },
            node_id,
            step_id=step_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )

    def mark_activity(event_type: str) -> None:
        nonlocal last_activity
        if event_type in _WORK_LLM_ACTIVITY_EVENTS:
            last_activity = time.monotonic()
            activity_event.set()

    def should_stream_text(event_type: str) -> bool:
        if event_type == "text_delta":
            return stream_text
        if event_type == "reasoning":
            return stream_reasoning
        return False

    def flush_text(event_type: str) -> None:
        text = text_buffers.get(event_type, "")
        if not text:
            return
        text_buffers[event_type] = ""
        last_flush_at[event_type] = time.monotonic()
        streamed_totals[event_type] += text
        _emit(
            run_ctx,
            event_type,
            {
                "text": text,
                "call_id": call_id,
                "call_attempt": attempt,
                "lane": "reasoning" if event_type == "reasoning" else "output",
            },
            node_id,
            step_id=step_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )

    def flush_all_text() -> None:
        for event_type in list(text_buffers):
            flush_text(event_type)

    def throttled_writer(event: dict[str, Any]) -> None:
        nonlocal token_seen, error_event_seen, chunk_count, tool_event_count, last_lane
        event_type = str((event or {}).get("event") or "")
        data = (event or {}).get("data", {}) or {}
        data_dict = data if isinstance(data, dict) else {"value": data}
        mark_activity(event_type)

        if event_type in _WORK_LLM_TEXT_EVENTS:
            text = str(data_dict.get("text") or "")
            if text:
                chunk_count += 1
                last_lane = "reasoning" if event_type == "reasoning" else "output"
            if should_stream_text(event_type):
                text_buffers[event_type] += text
                now = time.monotonic()
                if (
                    len(text_buffers[event_type]) >= _WORK_LLM_STREAM_FLUSH_CHARS
                    or now - last_flush_at[event_type]
                    >= _WORK_LLM_STREAM_FLUSH_INTERVAL_SECONDS
                ):
                    flush_text(event_type)
            return

        flush_all_text()
        if event_type == "token":
            token_seen = True
        elif event_type in {"tool_call", "tool_result"}:
            tool_event_count += 1
            data_dict.setdefault("lane", last_lane or "reasoning")
            if not data_dict.get("tool_call_id"):
                data_dict["tool_call_id"] = data_dict.get("id") or data_dict.get("call_id") or ""
        elif event_type == "error":
            error_event_seen = True
        data_dict["call_id"] = call_id
        data_dict["call_attempt"] = attempt
        if event_type in _WORK_LLM_TEXT_EVENTS:
            data_dict["lane"] = "reasoning" if event_type == "reasoning" else "output"
        _emit(
            run_ctx,
            event_type,
            data_dict,
            node_id,
            step_id=step_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )

    idle_timeout_seconds = max(0.001, float(idle_timeout_seconds or 0))
    timeout_text = f"{idle_timeout_seconds:g}"

    while True:
        attempt += 1
        call_activity_start = chunk_count + tool_event_count
        if attempt == 1:
            _emit(
                run_ctx,
                "agent_call_start",
                {
                    "call_id": call_id,
                    "call_attempt": attempt,
                    "agent_call_status": "running",
                    "provider_id": payload.get("provider_id") or "",
                    "model": payload.get("model") or "",
                    "func_tools": _json_safe(payload.get("func_tools") or []),
                    "input_payload": _work_llm_input_payload(payload),
                },
                node_id,
                step_id=step_id,
                agent_id=agent_id,
                agent_label=agent_label,
            )
        wrapped_ctx = GraphRunContext(
            provider=run_ctx.provider,
            tool_executor=run_ctx.tool_executor,
            hooks=run_ctx.hooks,
            astr_event=run_ctx.astr_event,
            config=run_ctx.config,
            writer=throttled_writer,
            interrupt_event=run_ctx.interrupt_event,
        )
        execute_kwargs: dict[str, Any] = {"write_stream": True}
        if max_steps is not None:
            execute_kwargs["max_steps"] = max_steps
        task = asyncio.create_task(
            _agent_operator.execute(payload, wrapped_ctx, **execute_kwargs)
        )
        try:
            while not task.done():
                activity_event.clear()
                activity_waiter = asyncio.create_task(activity_event.wait())
                done, pending = await asyncio.wait(
                    {task, activity_waiter},
                    timeout=idle_timeout_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for pending_task in pending:
                    if pending_task is not task:
                        pending_task.cancel()
                if task in done:
                    break
                if activity_waiter in done:
                    continue
                if time.monotonic() - last_activity < idle_timeout_seconds:
                    continue
                task.cancel()
                flush_all_text()
                message = f"连续 {timeout_text} 秒无模型或工具输出。"
                diag = {
                    **diagnostic,
                    "node_id": node_id,
                    "step_id": str(step_id or ""),
                    "attempt": attempt,
                    "chunk_count": chunk_count,
                    "tool_event_count": tool_event_count,
                    "output_chars": len(streamed_totals.get("text_delta", "")),
                    "reasoning_chars": len(streamed_totals.get("reasoning", "")),
                    "last_activity_age_seconds": round(
                        time.monotonic() - last_activity, 3
                    ),
                    "exception_type": "WorkLLMIdleTimeout",
                }
                _emit(
                    run_ctx,
                    "error",
                    {
                        "message": message,
                        "diagnostic": diag,
                        "retryable": True,
                        "status": "retryable_failed",
                        "call_id": call_id,
                        "call_attempt": attempt,
                    },
                    node_id,
                    step_id=step_id,
                    agent_id=agent_id,
                    agent_label=agent_label,
                )
                emit_agent_call_end(
                    "retryable_failed",
                    diag=diag,
                    error_message=message,
                    retryable=True,
                )
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise WorkLLMIdleTimeout(message)

            result = await task
        finally:
            flush_all_text()

        result = dict(result or {})
        final_text = str(result.get("final_text") or "")
        if stream_text and final_text and not streamed_totals.get("text_delta"):
            streamed_totals["text_delta"] += final_text
            _emit(
                run_ctx,
                "text_delta",
                {
                    "text": final_text,
                    "call_id": call_id,
                    "call_attempt": attempt,
                    "lane": "output",
                },
                node_id,
                step_id=step_id,
                agent_id=agent_id,
                agent_label=agent_label,
            )
        reasoning_text = str(result.get("reasoning_text") or "")
        if stream_reasoning and reasoning_text and not streamed_totals.get("reasoning"):
            streamed_totals["reasoning"] += reasoning_text
            _emit(
                run_ctx,
                "reasoning",
                {
                    "text": reasoning_text,
                    "call_id": call_id,
                    "call_attempt": attempt,
                    "lane": "reasoning",
                },
                node_id,
                step_id=step_id,
                agent_id=agent_id,
                agent_label=agent_label,
            )
        error_text = str(result.get("error") or "").strip()
        if not error_text:
            break

        had_stream_activity = (chunk_count + tool_event_count) > call_activity_start
        friendly_error = _user_facing_llm_error(error_text)
        diag = {
            **diagnostic,
            "node_id": node_id,
            "step_id": str(step_id or ""),
            "attempt": attempt,
            "chunk_count": chunk_count,
            "tool_event_count": tool_event_count,
            "output_chars": len(streamed_totals.get("text_delta", "")),
            "reasoning_chars": len(streamed_totals.get("reasoning", "")),
            "exception_type": error_text.split(":", 1)[0],
            "had_stream_output": had_stream_activity,
        }
        retryable = _is_transport_llm_error(error_text)
        can_auto_retry = (
            retryable
            and not had_stream_activity
            and attempt <= len(_WORK_LLM_AUTO_RETRY_DELAYS_SECONDS)
        )
        if can_auto_retry:
            delay = _WORK_LLM_AUTO_RETRY_DELAYS_SECONDS[attempt - 1]
            _emit(
                run_ctx,
                "phase",
                {
                    "phase": "llm_auto_retry",
                    "label": f"{friendly_error}，将自动重试第 {attempt + 1} 次",
                    "attempt": attempt + 1,
                    "diagnostic": diag,
                },
                node_id,
                step_id=step_id,
                agent_id=agent_id,
                agent_label=agent_label,
            )
            await asyncio.sleep(delay)
            continue
        _emit(
            run_ctx,
            "error",
            {
                "message": friendly_error,
                "diagnostic": diag,
                "retryable": retryable,
                "status": "retryable_failed" if retryable else "failed",
                "source": "work_llm_call",
                "raw_error_already_emitted": error_event_seen,
                "call_id": call_id,
                "call_attempt": attempt,
            },
            node_id,
            step_id=step_id,
            agent_id=agent_id,
            agent_label=agent_label,
        )
        emit_agent_call_end(
            "retryable_failed" if retryable else "failed",
            diag=diag,
            error_message=friendly_error,
            retryable=retryable,
        )
        raise WorkLLMCallError(
            friendly_error,
            retryable=retryable,
            diagnostic=diag,
            partial_text=streamed_totals.get("text_delta", ""),
        )

    result = dict(result or {})
    result["_work_call_id"] = call_id
    result["_work_call_attempt"] = attempt
    result["_work_streamed_text"] = streamed_totals.get("text_delta", "")
    result["_work_streamed_reasoning"] = streamed_totals.get("reasoning", "")
    result["_work_diagnostic"] = {
        **diagnostic,
        "node_id": node_id,
        "step_id": str(step_id or ""),
        "attempt": attempt,
        "chunk_count": chunk_count,
        "tool_event_count": tool_event_count,
        "output_chars": len(streamed_totals.get("text_delta", "")),
        "reasoning_chars": len(streamed_totals.get("reasoning", "")),
    }
    if not token_seen:
        _emit_token_from_stats(
            run_ctx,
            result.get("stats", {}) if isinstance(result, dict) else {},
            node_id,
            step_id=step_id,
            agent_id=agent_id,
            agent_label=agent_label,
            call_id=call_id,
            call_attempt=attempt,
        )
    emit_agent_call_end("completed")
    return result


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


def _is_agent_id(value: Any) -> bool:
    text = str(value or "")
    return text.startswith(("agent_", "expert_"))


def _work_agent_label(
    state: WorkTaskState, role: str, agent_id: str | None = None
) -> str:
    agent_id = agent_id or _work_agent_id(state, role)
    config = state.get("executor_config", {}) or {}
    label_map = (
        config.get("agent_labels", {}) or config.get("default_agent_labels", {}) or {}
    )
    if agent_id and label_map.get(agent_id):
        return str(label_map[agent_id])
    if agent_id and _WORK_AGENT_LABELS.get(agent_id):
        return _WORK_AGENT_LABELS[agent_id]
    return _WORK_ROLE_LABELS.get(role, "") or agent_id or ""


def _step_agent_label(
    state: WorkTaskState, step: dict[str, Any], role: str = "executor"
) -> str:
    explicit = str(step.get("executor") or step.get("agent_label") or "").strip()
    agent_id = str(
        step.get("executor_id")
        or step.get("agent_id")
        or _work_agent_id(state, role)
        or ""
    ).strip()
    if explicit and not _is_agent_id(explicit):
        return explicit
    return _work_agent_label(state, role, agent_id)


def _render_prompt_template(
    template: Any, variables: dict[str, Any], fallback: str
) -> str:
    text = str(template or "").strip()
    safe_variables = _normalize_variables(variables)
    if not text:
        return _safe_substitute(fallback, safe_variables)
    return _safe_substitute(text, safe_variables)


def _safe_substitute(text: str, variables: dict[str, str]) -> str:
    for key, value in variables.items():
        text = text.replace("{" + key + "}", value)
    return text


def _normalize_variables(variables: dict[str, Any]) -> dict[str, str]:
    return {key: "" if value is None else str(value) for key, value in variables.items()}


def _extract_context_from_run_ctx(run_ctx: GraphRunContext | None) -> Any:
    if run_ctx is None:
        return None
    astr_event = getattr(run_ctx, "astr_event", None)
    if astr_event is None:
        return None
    if hasattr(astr_event, "get_provider_by_id"):
        return astr_event
    return getattr(astr_event, "context", None)


def _dedupe_tools(*tool_groups: Any) -> list[str]:
    tools: list[str] = []
    seen: set[str] = set()
    for group in tool_groups:
        if not group:
            continue
        values = group if isinstance(group, list) else [group]
        for value in values:
            tool = str(value or "").strip()
            if tool and tool not in seen:
                seen.add(tool)
                tools.append(tool)
    return tools


def _compose_agent_node_system_prompt(
    soul: str, node_prompt: str, fallback_prompt: str
) -> str:
    parts = []
    if soul:
        parts.append(f"## 智能体 Soul\n{soul}")
    effective_node_prompt = node_prompt or fallback_prompt
    if effective_node_prompt:
        parts.append(f"## 当前节点要求\n{effective_node_prompt}")
    return "\n\n".join(parts)


def _load_work_agent(agent_id: str):
    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.agent_service import (
            AgentService,
        )

        return AgentService(get_database()).get_agent(agent_id)
    except Exception:
        return None


def _resolve_work_agent_runtime(
    state: WorkTaskState,
    run_ctx: GraphRunContext | None,
    *,
    role: str,
    agent_id: str | None,
    agent_label: str,
    node_config: dict[str, Any] | None = None,
    node_id: str = "",
    step_id: Any = None,
) -> dict[str, Any]:
    resolved_agent_id = str(agent_id or _work_agent_id(state, role) or "").strip()
    node_config = node_config or {}
    agent = _load_work_agent(resolved_agent_id)
    if not agent:
        message = f"智能体「{resolved_agent_id or role}」不存在，请在智能体管理中检查 Work 配置。"
        _emit(
            run_ctx,
            "error",
            {"message": message},
            node_id,
            step_id=step_id,
            agent_id=resolved_agent_id,
            agent_label=agent_label,
        )
        raise RuntimeError(message)

    provider_id = str(agent.provider_id or "").strip()
    if not provider_id:
        message = f"智能体「{agent.name}」未配置 LLM 提供商，请在智能体管理中配置模型后重试。"
        _emit(
            run_ctx,
            "error",
            {"message": message},
            node_id,
            step_id=step_id,
            agent_id=agent.id,
            agent_label=agent_label or agent.name,
        )
        raise RuntimeError(message)

    context = _extract_context_from_run_ctx(run_ctx)
    provider = (
        context.get_provider_by_id(provider_id)
        if context is not None and hasattr(context, "get_provider_by_id")
        else None
    )
    if provider is None:
        message = f"智能体「{agent.name}」配置的 LLM 提供商「{provider_id}」不存在或不可用。"
        _emit(
            run_ctx,
            "error",
            {"message": message},
            node_id,
            step_id=step_id,
            agent_id=agent.id,
            agent_label=agent_label or agent.name,
        )
        raise RuntimeError(message)

    return {
        "agent": agent,
        "agent_id": agent.id,
        "agent_label": agent_label or agent.name,
        "provider_id": provider_id,
        "model": agent.model_name,
        "func_tools": _dedupe_tools(
            agent.tools,
            node_config.get("tools"),
            node_config.get("func_tools"),
        ),
        "soul": agent.soul,
    }


def _normalize_task_mode(value: Any) -> str:
    task_mode = str(value or "normal").strip()
    return task_mode if task_mode in {"quick", "normal", "deep"} else "normal"


def _plan_mode_strategy_text(task_mode: str) -> str:
    strategies = {
        "quick": (
            "快速模式：围绕一个可直接执行的交付单元规划。只生成一个一级执行步骤，"
            "不要生成 children。这个步骤必须包含完整交付目标、验收标准和执行资源。"
        ),
        "normal": (
            "常规模式：按一级步骤规划执行树。一级步骤是执行粒度；如需二级内容，"
            "只作为检查项或说明保存在 children 中，不作为独立执行单元。"
        ),
        "deep": (
            "深度模式：按二级/叶子步骤规划执行树。每个一级步骤必须包含 children，"
            "叶子步骤是执行粒度；可以根据任务需要使用 researcher、executor、reviewer、reporter 等资源分工。"
        ),
    }
    return strategies.get(task_mode, strategies["normal"])


def _format_available_work_resources(state: WorkTaskState) -> str:
    role_names = {
        "assistant": "任务助理，负责规划、协调和修复计划",
        "executor": "执行者，负责完成具体步骤",
        "reviewer": "审查者，负责检查结果是否达标",
        "researcher": "研究员，负责信息收集、检索和分析",
        "reporter": "汇报专家，负责最终交付整理",
    }
    lines = []
    for role, desc in role_names.items():
        agent_id = _work_agent_id(state, role)
        label = _work_agent_label(state, role, agent_id)
        lines.append(f"- {role}: {agent_id}（{label}）- {desc}")
    return "\n".join(lines)


def _build_resource_aware_plan_prompt(
    state: WorkTaskState,
    *,
    validation_errors: list[str] | None = None,
    previous_output: str = "",
) -> str:
    task_mode = _normalize_task_mode(
        state.get("task_mode") or (state.get("plan_config", {}) or {}).get("task_mode")
    )
    plan_config = state.get("plan_config", {}) or {}
    plan_feedback = state.get("plan_feedback", "")
    extra_requirement = str(
        plan_config.get("prompt_template")
        or plan_config.get("prompt")
        or plan_config.get("custom_requirement")
        or ""
    ).strip()
    validation_section = ""
    if validation_errors:
        validation_section = (
            "\n## 校验反馈（必须修复）\n"
            + "\n".join(f"- {error}" for error in validation_errors)
            + "\n\n请只修复上述结构和资源问题，不要改变用户已确认需求。"
        )
    previous_section = ""
    if previous_output:
        previous_section = (
            "\n## 上一次模型输出\n"
            "以下输出未通过校验，只能作为修复参考：\n"
            f"{_clip_context_text(previous_output, 3000)}"
        )
    feedback_section = f"\n## 人工调整意见\n{plan_feedback}" if plan_feedback else ""
    extra_section = f"\n## 节点自定义要求\n{extra_requirement}" if extra_requirement else ""
    return (
        "你正在执行 NiceBot Work 的资源感知规划协议。你的职责不是先写计划再等待系统分配，"
        "而是在规划时同步完成任务拆解、依赖设计和执行资源分配。\n\n"
        f"## 任务目标\n- 任务名称：{state.get('task_name', '')}\n"
        f"- 任务描述：{state.get('task_desc', '')}\n"
        f"- 规划模式：{task_mode}\n\n"
        f"## 已确认需求\n{_clarification_text(state)}\n\n"
        f"## 工作上下文\n{_context_text(state) or '无额外上下文'}\n\n"
        f"## 可用执行资源\n{_format_available_work_resources(state)}\n\n"
        f"## 模式策略\n{_plan_mode_strategy_text(task_mode)}\n"
        f"{feedback_section}{extra_section}{validation_section}{previous_section}\n\n"
        "## 输出契约\n"
        "只返回 JSON，不要使用 Markdown，不要添加解释文字。JSON 格式如下：\n"
        "{\n"
        '  "steps": [\n'
        "    {\n"
        '      "id": "step_1",\n'
        '      "title": "步骤标题",\n'
        '      "description": "步骤说明",\n'
        '      "deliverable": "本步骤交付物",\n'
        '      "acceptance_criteria": ["可检查标准 1"],\n'
        '      "dependencies": [],\n'
        '      "executor_id": "executor",\n'
        '      "reviewer_id": "reviewer",\n'
        '      "resource_rationale": "为什么这个资源适合该步骤",\n'
        '      "children": []\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "## 禁止事项\n"
        "- 不要输出旧版纯文本步骤。\n"
        "- 不要省略 executor_id、deliverable、acceptance_criteria。\n"
        "- dependencies 只能引用同一 JSON 内已经存在或将存在的 step id。\n"
        "- 不要把资源分配留给后续节点。"
    )


def _extract_json_payload(text: str) -> Any:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def _normalize_resource_plan_steps(
    raw_steps: Any,
    state: WorkTaskState,
    *,
    parent_id: str | None = None,
    depth: int = 1,
) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        description = str(item.get("description") or title).strip()
        deliverable = str(
            item.get("deliverable") or item.get("deliverables") or ""
        ).strip()
        executor_id = str(item.get("executor_id") or item.get("executor_role") or "").strip()
        reviewer_id = str(item.get("reviewer_id") or "").strip()
        if executor_id:
            executor_id = _normalize_resource_agent_id(executor_id, state, "executor")
        if reviewer_id:
            reviewer_id = _normalize_resource_agent_id(reviewer_id, state, "reviewer")
        step = {
            "id": step_id,
            "title": title[:80],
            "description": description,
            "status": "pending",
            "dependencies": _string_list(item.get("dependencies")),
            "parent_id": parent_id,
            "depth": depth,
            "sort_order": int(item.get("sort_order") or index),
            "executor": _work_agent_label(state, "executor", executor_id)
            if executor_id
            else "",
            "executor_type": "agent",
            "executor_id": executor_id,
            "reviewer_id": reviewer_id,
            "deliverable": deliverable,
            "acceptance_criteria": _string_list(item.get("acceptance_criteria")),
            "resource_rationale": str(item.get("resource_rationale") or "").strip(),
            "children": [],
        }
        step["children"] = _normalize_resource_plan_steps(
            item.get("children") or [],
            state,
            parent_id=step_id or None,
            depth=depth + 1,
        )
        steps.append(step)
    return steps


def _flatten_work_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for step in steps or []:
        result.append(step)
        result.extend(_flatten_work_steps(step.get("children") or []))
    return result


def _work_agent_exists(agent_id: str, state: WorkTaskState) -> bool:
    value = str(agent_id or "").strip()
    if not value:
        return False
    configured = set((state.get("executor_config", {}) or {}).get("default_agents", {}).values())
    configured.update(_WORK_AGENT_LABELS.keys())
    configured.update(_work_agent_id(state, role) for role in _WORK_ROLE_LABELS)
    if value in configured:
        return True
    return _load_work_agent(value) is not None


def _validate_dependency_graph(flat_steps: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = [str(step.get("id") or "") for step in flat_steps]
    id_set = {step_id for step_id in ids if step_id}
    for step in flat_steps:
        step_id = str(step.get("id") or "")
        for dep_id in step.get("dependencies") or []:
            dep_text = str(dep_id or "")
            if dep_text not in id_set:
                errors.append(f"{step_id} 的依赖 {dep_text} 不存在")
            if dep_text == step_id:
                errors.append(f"{step_id} 不能依赖自身")
    graph = {
        str(step.get("id") or ""): [str(dep) for dep in step.get("dependencies") or []]
        for step in flat_steps
        if step.get("id")
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            errors.append(f"依赖关系存在环：{step_id}")
            return
        visiting.add(step_id)
        for dep_id in graph.get(step_id, []):
            if dep_id in graph:
                visit(dep_id)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in graph:
        visit(step_id)
    return errors


def _validate_resource_plan_steps(
    steps: list[dict[str, Any]], state: WorkTaskState, task_mode: str
) -> list[str]:
    errors: list[str] = []
    if not steps:
        return ["规划输出没有 steps，无法生成可执行树"]
    flat_steps = _flatten_work_steps(steps)
    seen: set[str] = set()
    for step in flat_steps:
        step_id = str(step.get("id") or "").strip()
        if not step_id:
            errors.append("存在缺少 id 的步骤")
        elif step_id in seen:
            errors.append(f"step_id 重复：{step_id}")
        seen.add(step_id)
        if not str(step.get("title") or step.get("description") or "").strip():
            errors.append(f"{step_id or '未知步骤'} 缺少 title/description")
        if not str(step.get("deliverable") or "").strip():
            errors.append(f"{step_id or '未知步骤'} 缺少 deliverable")
        if not step.get("acceptance_criteria"):
            errors.append(f"{step_id or '未知步骤'} 缺少 acceptance_criteria")
    errors.extend(_validate_dependency_graph(flat_steps))
    executable_steps = _collect_executable_steps(steps, task_mode)
    if task_mode == "quick" and len(executable_steps) != 1:
        errors.append("快速模式必须只生成一个执行步骤，且不要生成 children")
    if task_mode == "deep":
        for step in steps:
            if not step.get("children"):
                errors.append(f"深度模式一级步骤 {step.get('id') or ''} 必须包含 children")
    for step in executable_steps:
        step_id = str(step.get("id") or "未知步骤")
        executor_id = str(step.get("executor_id") or "").strip()
        reviewer_id = str(step.get("reviewer_id") or "").strip()
        if not executor_id:
            errors.append(f"{step_id} 缺少 executor_id")
        elif not _work_agent_exists(executor_id, state):
            errors.append(f"{step_id} 的 executor_id 不存在：{executor_id}")
        if reviewer_id and not _work_agent_exists(reviewer_id, state):
            errors.append(f"{step_id} 的 reviewer_id 不存在：{reviewer_id}")
    return errors


def _parse_resource_plan_output(
    text: str, state: WorkTaskState, task_mode: str
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        payload = _extract_json_payload(text)
    except Exception as exc:
        return [], [f"规划输出不是合法 JSON：{exc}"]
    raw_steps = payload.get("steps") if isinstance(payload, dict) else None
    steps = _normalize_resource_plan_steps(raw_steps, state)
    errors = _validate_resource_plan_steps(steps, state, task_mode)
    if not errors:
        steps = _apply_executor_labels(steps, state)
    return steps, errors


async def prepare_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    retry_config = state.get("retry_config", {}) or {}
    review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
    clarification_enabled = (state.get("clarification_config", {}) or {}).get(
        "enabled", False
    )
    stage_steps = [
        {
            "id": "stage_clarify",
            "title": "需求明确",
            "description": "确认任务目标、交付形式和完成标准",
            "status": "running" if clarification_enabled else "done",
            "depth": 1,
            "sort_order": 0,
            "dependencies": [],
            "executor": "需求确认助手",
            "executor_type": "agent",
            "executor_id": _work_agent_id(state, "assistant"),
        },
        {
            "id": "stage_plan",
            "title": "规划",
            "description": "生成资源感知执行计划和依赖关系",
            "status": "running" if not clarification_enabled else "pending",
            "depth": 1,
            "sort_order": 1,
            "dependencies": ["stage_clarify"],
            "executor": "任务规划助手",
            "executor_type": "agent",
            "executor_id": _work_agent_id(state, "assistant"),
        },
        {
            "id": "stage_execute",
            "title": "执行",
            "description": "按前置依赖顺序执行任务",
            "status": "pending",
            "depth": 1,
            "sort_order": 2,
            "dependencies": ["stage_plan"],
            "executor": _work_agent_label(state, "executor"),
            "executor_type": "agent",
            "executor_id": _work_agent_id(state, "executor"),
            "reviewer_id": _work_agent_id(state, "reviewer"),
        },
    ]
    if review_enabled:
        stage_steps.append(
            {
                "id": "stage_review",
                "title": "审查",
                "description": "审查任务结果是否达标",
                "status": "pending",
                "depth": 1,
                "sort_order": 3,
                "dependencies": ["stage_execute"],
                "executor": "任务审查智能体",
                "executor_type": "agent",
                "executor_id": _work_agent_id(state, "reviewer"),
            },
        )
    last_dep = "stage_review" if review_enabled else "stage_execute"
    stage_steps.append(
        {
            "id": "stage_deliver",
            "title": "交付",
            "description": "生成最终交付物",
            "status": "pending",
            "depth": 1,
            "sort_order": len(stage_steps),
            "dependencies": [last_dep],
            "executor": _work_agent_label(state, "reporter"),
            "executor_type": "agent",
            "executor_id": _work_agent_id(state, "reporter"),
        },
    )
    if retry_config:
        stage_steps = state.get("stage_steps") or stage_steps
        target_stage = retry_config.get("stage_id")
        if target_stage:
            stage_steps = _update_stage_status(stage_steps, target_stage, "running")
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "prepare",
            "label": "准备任务上下文",
            "progress": 5,
            "steps": stage_steps,
        },
        "prepare",
    )
    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get(
        "task_mode", "normal"
    )
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    return {
        "stage_steps": stage_steps,
        "plan_steps": state.get("plan_steps", []),
        "step_results": state.get("step_results", []),
        "current_step_index": state.get("current_step_index", 0),
        "rework_count": state.get("rework_count", 0),
        "task_mode": task_mode,
    }


async def clarify_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "clarify")
    run_ctx = _get_run_ctx(config)
    _emit(
        run_ctx,
        "phase",
        {"phase": "clarification", "label": "需求明确", "progress": 8},
        "clarify",
    )

    clarification_config = state.get("clarification_config", {}) or {}
    working_state: WorkTaskState = dict(state)
    interrogation_result = await _run_interrogation_if_needed(
        working_state, clarification_config, run_ctx
    )
    if interrogation_result:
        if interrogation_result.get("interrogation_ready"):
            working_state.update(interrogation_result)
        else:
            return interrogation_result
    content_provider_type = clarification_config.get("content_provider_type", "agent")
    template_id = clarification_config.get(
        "template_id", "builtin_work_requirement_clarification"
    )

    template = _load_hitl_template(template_id)
    content_payload = await _resolve_clarify_content(
        content_provider_type,
        clarification_config,
        working_state,
        run_ctx,
        config,
    )
    clarify_reasoning_text = (
        str(content_payload.pop("_reasoning_text", "") or "")
        if isinstance(content_payload, dict)
        else ""
    )

    card = build_hitl_card(
        template=template,
        template_id=template_id,
        content_payload=content_payload,
        task_id=working_state.get("task_id", ""),
        session_id=working_state.get("session_id", ""),
        interaction_type="clarification",
        meta={"task_id": working_state.get("task_id", ""), "template_id": template_id},
    )
    card.fields.append(
        CardField(
            key="clarify_more_text",
            label="补充信息",
            field_type="textarea",
            required=False,
            description="如需补充或调整需求，请在此填写",
            custom_placeholder="例如：交付时间要求本周内完成、需要包含竞品对比分析...",
        )
    )

    task_name = working_state.get("task_name", "")
    if task_name and not content_payload.get("title"):
        card.title = f"需求确认：{task_name}"
    if (
        not card.body
        or card.body
        == "请确认以下信息。默认已选推荐项，如不合适可改选或填写自定义补充。"
    ):
        card.body = (
            f"任务「{task_name}」开始前，请确认关键需求。\n\n"
            "默认项已按推荐选择；如果不合适，可以改选或在自定义补充中说明。"
        )

    _emit(run_ctx, "interaction", card.to_dict(), "clarify")
    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=working_state.get("task_id", ""),
        channel="chatui",
        channel_extra={"task_id": working_state.get("task_id", ""), "sync_chatui": True},
    )
    if response.action_key == "cancel":
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "cancelled",
                "label": "任务已取消",
                "progress": 8,
                "status": "cancelled",
            },
            "clarify",
        )
        return {"cancelled": True, "clarification_action": "cancel"}
    values = dict(response.field_values or {})
    if response.action_key == "clarify_more":
        feedback = (
            values.pop("clarify_more_text", "") if isinstance(values, dict) else ""
        )
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "clarification_more",
                "label": "已收到补充需求，将重新生成确认卡片",
                "progress": 8,
                "status": "running",
            },
            "clarify",
        )
        return {
            "clarification": values,
            "clarification_feedback": feedback,
            "clarification_action": "clarify_more",
        }
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "clarification_done",
            "label": "需求已明确",
            "progress": 12,
            "status": "running",
        },
        "clarify",
    )
    stages = _update_stage_status(
        list(state.get("stage_steps", [])), "stage_clarify", "done"
    )
    stages = _update_stage_status(stages, "stage_plan", "running")
    _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "clarify")
    return {
        "clarification": values,
        "clarification_action": "confirm",
        "interrogation_history": working_state.get("interrogation_history", []),
        "interrogation_round": working_state.get("interrogation_round", 0),
        "interrogation_ready": working_state.get("interrogation_ready", False),
        "interrogation_summary": working_state.get("interrogation_summary", ""),
        "stage_steps": stages,
    }


async def plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "plan")
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    _emit(
        run_ctx,
        "phase",
        {"phase": "plan", "label": "生成执行计划", "progress": 15},
        "plan",
    )
    plan_config = state.get("plan_config", {}) or {}
    task_mode = _normalize_task_mode(
        state.get("task_mode") or plan_config.get("task_mode")
    )
    plan_agent_id = plan_config.get("agent_id") or _work_agent_id(state, "assistant")
    plan_agent_label = _work_agent_label(state, "assistant", plan_agent_id)
    runtime = _resolve_work_agent_runtime(
        state,
        run_ctx,
        role="assistant",
        agent_id=plan_agent_id,
        agent_label=plan_agent_label,
        node_config=plan_config,
        node_id="plan",
    )
    node_system_prompt = str(
        plan_config.get("system_prompt")
        or "你是 NiceBot Work 的任务规划助手。请把语义规划、依赖设计和资源分配一次性完成，并严格返回 JSON。"
    )
    system_prompt = _compose_agent_node_system_prompt(
        runtime["soul"],
        node_system_prompt,
        "你是 NiceBot Work 的任务规划助手。请把语义规划、依赖设计和资源分配一次性完成，并严格返回 JSON。",
    )
    result: dict[str, Any] = {}
    text = ""
    steps: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    previous_output = ""
    for repair_attempt in range(_WORK_PLAN_AUTO_REPAIR_MAX_ATTEMPTS + 1):
        prompt = _build_resource_aware_plan_prompt(
            state,
            validation_errors=validation_errors if repair_attempt else None,
            previous_output=previous_output if repair_attempt else "",
        )
        if repair_attempt:
            _emit(
                run_ctx,
                "phase",
                {
                    "phase": "plan_auto_repair",
                    "label": f"规划校验未通过，正在自动修复第 {repair_attempt} 次",
                    "attempt": repair_attempt,
                    "errors": validation_errors,
                },
                "plan",
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
            )
        try:
            result = await _run_work_llm_call(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": prompt,
                    "messages": [],
                    "provider_id": runtime["provider_id"],
                    "model": runtime["model"],
                    "func_tools": runtime["func_tools"] or None,
                    "session_id": state.get("session_id", "work"),
                    "trace_context": _trace_context(
                        "plan",
                        agent_id=runtime["agent_id"],
                        agent_label=runtime["agent_label"],
                    ),
                },
                run_ctx,
                node_id="plan",
                idle_timeout_seconds=_llm_idle_timeout_seconds(plan_config),
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
                stream_text=repair_attempt == 0,
                stream_reasoning=True,
            )
        except (WorkLLMIdleTimeout, WorkLLMCallError) as exc:
            stages = _update_stage_status(
                list(state.get("stage_steps", [])), "stage_plan", "failed"
            )
            _emit(
                run_ctx,
                "phase",
                {
                    "phase": "plan_failed",
                    "label": "计划生成失败",
                    "steps": stages,
                    "progress": 25,
                    "status": "failed",
                },
                "plan",
            )
            raise RuntimeError(f"计划生成失败：{exc}") from exc
        text = str(result.get("final_text") or "").strip()
        if result.get("error"):
            text = ""
            validation_errors = [f"计划生成失败：{result.get('error')}"]
        else:
            steps, validation_errors = _parse_resource_plan_output(
                text, state, task_mode
            )
        if not validation_errors:
            _emit(
                run_ctx,
                "phase",
                {
                    "phase": "plan_validation_passed",
                    "label": "规划已通过执行资源校验",
                    "attempt": repair_attempt,
                    "progress": 24,
                },
                "plan",
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
            )
            break
        previous_output = text
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "plan_validation_failed",
                "label": "规划校验未通过",
                "attempt": repair_attempt,
                "errors": validation_errors,
                "progress": 20,
            },
            "plan",
            agent_id=runtime["agent_id"],
            agent_label=runtime["agent_label"],
        )
    if validation_errors:
        message = "规划校验失败，已用完 5 次自动修复：" + "；".join(
            validation_errors
        )
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_plan", "failed"
        )
        _emit(
            run_ctx,
            "error",
            {
                "message": message,
                "status": "retryable_failed",
                "retryable": True,
                "errors": validation_errors,
                "raw_output": _clip_context_text(previous_output, 2000),
            },
            "plan",
            agent_id=runtime["agent_id"],
            agent_label=runtime["agent_label"],
        )
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "plan_auto_repair_exhausted",
                "label": "规划自动修复已达上限",
                "steps": stages,
                "progress": 25,
                "status": "retryable_failed",
            },
            "plan",
        )
        raise WorkLLMCallError(message, retryable=True)
    stages = _update_stage_status(
        list(state.get("stage_steps", [])), "stage_plan", "running"
    )
    plan_display = _format_plan_for_approval(steps)
    _emit(
        run_ctx,
        "phase",
        {"phase": "plan_done", "label": "计划已生成", "steps": stages, "progress": 25},
        "plan",
    )
    return {
        "plan_steps": steps,
        "stage_steps": stages,
        "plan_text_full": plan_display,
        "current_step_index": 0,
        "step_results": [],
        "approval_action": "",
        "plan_feedback": "",
    }


async def approve_plan_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "approve_plan")
    run_ctx = _get_run_ctx(config)
    steps = state.get("plan_steps", [])
    plan_text_full = state.get("plan_text_full", "")
    plan_config = state.get("plan_config", {}) or {}
    if plan_config.get("approval_enabled") is False:
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_plan", "done"
        )
        stages = _update_stage_status(stages, "stage_execute", "running")
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "plan_auto_approved",
                "label": "计划已自动通过",
                "progress": 30,
                "status": "running",
                "steps": stages,
            },
            "approve_plan",
        )
        return {
            "review_passed": False,
            "approval_action": "approve",
            "stage_steps": stages,
            "plan_steps": steps,
        }
    plan_body = (
        _format_plan_for_approval(steps)
        if steps
        else (plan_text_full if plan_text_full else "无计划内容")
    )
    body = _render_prompt_template(
        plan_config.get("approval_body_template"),
        {
            "plan_body": plan_body,
            "task_name": state.get("task_name", ""),
            "task_desc": state.get("task_desc", ""),
        },
        f"请审批以下执行计划：\n\n{plan_body}",
    )
    card = InteractionCard(
        interaction_id=f"work_plan_{uuid.uuid4().hex[:12]}",
        type="plan_approval",
        title=f"执行计划审批：{state.get('task_name', '')}",
        body=body,
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
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_plan", "done"
        )
        stages = _update_stage_status(stages, "stage_execute", "running")
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "plan_approved",
                "label": "计划已批准",
                "progress": 30,
                "status": "running",
                "steps": stages,
            },
            "approve_plan",
        )
        return {
            "review_passed": False,
            "approval_action": "approve",
            "stage_steps": stages,
            "plan_steps": steps,
        }
    if response.action_key == "modify":
        modify_text = (
            response.field_values.get("modify_text")
            or response.field_values.get("feedback")
            or ""
        )
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "plan_revision_requested",
                "label": "已收到调整计划要求，将重新规划",
                "progress": 18,
                "status": "running",
            },
            "approve_plan",
        )
        return {
            "approval_action": "modify",
            "plan_feedback": modify_text,
            "review_passed": False,
        }
    _emit(
        run_ctx,
        "error",
        {"message": "执行计划被拒绝，任务已取消", "status": "cancelled"},
        "approve_plan",
    )
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "cancelled",
            "label": "任务已取消",
            "progress": state.get("progress", 0),
            "status": "cancelled",
        },
        "approve_plan",
    )
    return {
        "review_passed": False,
        "current_step_index": 999999,
        "approval_action": "reject",
        "cancelled": True,
    }


async def execute_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "execute")
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    steps = state.get("plan_steps", [])
    if not steps:
        steps = [
            {
                "id": "step_1",
                "description": state.get("task_desc") or state.get("task_name", ""),
                "status": "pending",
            }
        ]

    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get(
        "task_mode", "normal"
    )
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    executable_steps = _collect_executable_steps(steps, task_mode)
    idx = state.get("current_step_index", 0)
    if idx >= len(executable_steps):
        return {}

    step = dict(executable_steps[idx])
    step["status"] = "running"
    _update_step_in_tree(steps, step["id"], {"status": "running"})
    progress = 30 + int((idx / max(len(executable_steps), 1)) * 45)
    executor = state.get("executor_config", {}) or {}
    agent_id = (
        step.get("executor_id")
        or executor.get("agent_id")
        or _work_agent_id(state, "executor")
    )
    agent_label = _step_agent_label(state, step, "executor")
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "execute",
            "label": step.get("description", ""),
            "steps": steps,
            "progress": progress,
        },
        "execute",
        step_id=step.get("id"),
        agent_id=agent_id,
        agent_label=agent_label,
    )
    step_scope = _step_scope_text(
        state, steps, step, state.get("step_results", []), task_mode
    )
    prompt_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "requirements": _requirement_text(state),
        "approved_plan": _approved_plan_text(state, steps),
        "step_scope": step_scope,
        "task_mode": task_mode,
        "agent_label": agent_label,
    }
    prompt = _render_prompt_template(
        executor.get("execute_prompt_template") or executor.get("prompt"),
        prompt_variables,
        _build_execute_prompt(
            state, steps, step, state.get("step_results", []), task_mode
        ),
    )
    node_system_prompt = _render_prompt_template(
        executor.get("execute_system_prompt") or executor.get("system_prompt"),
        prompt_variables,
        f"你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。只执行当前步骤，不负责审查自己的结果。",
    )
    runtime = _resolve_work_agent_runtime(
        state,
        run_ctx,
        role="executor",
        agent_id=agent_id,
        agent_label=agent_label,
        node_config=executor,
        node_id="execute",
        step_id=step.get("id"),
    )
    system_prompt = _compose_agent_node_system_prompt(
        runtime["soul"],
        node_system_prompt,
        f"你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。只执行当前步骤，不负责审查自己的结果。",
    )
    try:
        result = await _run_work_llm_call(
            {
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "messages": [],
                "compact_context": _compact_execution_context(
                    state, steps, step, state.get("step_results", []), task_mode
                ),
                "provider_id": runtime["provider_id"],
                "model": runtime["model"],
                "func_tools": runtime["func_tools"] or None,
                "session_id": state.get("session_id", "work"),
                "trace_context": _trace_context(
                    "execute",
                    step_id=step.get("id"),
                    agent_id=runtime["agent_id"],
                    agent_label=runtime["agent_label"],
                ),
            },
            run_ctx,
            node_id="execute",
            idle_timeout_seconds=_llm_idle_timeout_seconds(executor),
            step_id=step.get("id"),
            agent_id=runtime["agent_id"],
            agent_label=runtime["agent_label"],
            stream_text=True,
            stream_reasoning=True,
        )
    except (WorkLLMCallError, WorkLLMIdleTimeout) as exc:
        error_message = str(exc)
        step["status"] = "failed"
        updates = {
            "status": "failed",
            "error": error_message,
            "executor": agent_label,
        }
        _update_step_in_tree(steps, step["id"], updates)
        _update_parent_status(steps, step.get("parent_id"))
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "step_failed",
                "label": f"{step['description']} 执行失败，可重试",
                "steps": steps,
                "progress": progress,
                "status": "retryable_failed",
                "retryable": True,
                "error": error_message,
            },
            "execute",
            step_id=step.get("id"),
            agent_id=agent_id,
            agent_label=agent_label,
        )
        raise
    step["status"] = "done"
    step["result"] = result.get("final_text", "")
    updates = {"status": "done", "result": step["result"], "executor": agent_label}
    if task_mode == "normal" and step.get("children"):
        updates["children"] = _children_with_status(step.get("children") or [], "done")
    _update_step_in_tree(steps, step["id"], updates)
    _update_parent_status(steps, step.get("parent_id"))
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "step_done",
            "label": f"{step['description']} 已完成",
            "steps": steps,
            "progress": progress,
        },
        "execute",
        step_id=step.get("id"),
        agent_id=agent_id,
        agent_label=agent_label,
    )
    results = list(state.get("step_results", []))
    results.append(
        {
            "step_id": step.get("id", idx + 1),
            "description": step.get("description", ""),
            "result": step["result"],
            "agent": agent_label,
            "executor_type": step.get("executor_type") or "agent",
            "executor_id": runtime["agent_id"],
            "status": "done",
            "stats": result.get("stats", {}),
        }
    )
    next_idx = idx + 1
    all_done = next_idx >= len(executable_steps)
    result_dict: dict[str, Any] = {
        "plan_steps": steps,
        "step_results": results,
        "current_step_index": next_idx,
    }
    if all_done:
        review_enabled = (state.get("review_config", {}) or {}).get("enabled", False)
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_execute", "done"
        )
        if review_enabled:
            stages = _update_stage_status(stages, "stage_review", "running")
        else:
            stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "execute")
        result_dict["stage_steps"] = stages
    return result_dict


async def review_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "review")
    run_ctx = _get_run_ctx(config)
    review_config = state.get("review_config", {}) or {}
    if not review_config.get("enabled", False):
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_execute", "done"
        )
        stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "review")
        return {"review_passed": True, "stage_steps": stages}
    if run_ctx is None:
        return {"review_passed": True}
    _emit(
        run_ctx,
        "phase",
        {"phase": "review", "label": "审查任务结果", "progress": 82},
        "review",
    )
    results_text = "\n\n".join(
        f"- {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    review_agent_id = review_config.get("reviewer_id") or _work_agent_id(
        state, "reviewer"
    )
    review_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "work_context": _context_text(state),
        "results_text": results_text,
    }
    review_prompt = _render_prompt_template(
        review_config.get("prompt_template") or review_config.get("prompt"),
        review_variables,
        (
            f"请审查以下任务结果是否达成目标。\n\n"
            f"任务：{state.get('task_name', '')}\n\n"
            f"{_context_text(state)}\n\n"
            f"执行结果：\n{results_text}\n\n"
            "如果通过，回复 PASS。需要返工，回复 RETRY 并说明原因。"
        ),
    )
    review_agent_label = _work_agent_label(state, "reviewer", review_agent_id)
    node_review_system_prompt = _render_prompt_template(
        review_config.get("system_prompt"),
        review_variables,
        "你是 NiceBot Work 的审查智能体。只要结果明显未达成目标才判定返工。",
    )
    runtime = _resolve_work_agent_runtime(
        state,
        run_ctx,
        role="reviewer",
        agent_id=review_agent_id,
        agent_label=review_agent_label,
        node_config=review_config,
        node_id="review",
    )
    review_system_prompt = _compose_agent_node_system_prompt(
        runtime["soul"],
        node_review_system_prompt,
        "你是 NiceBot Work 的审查智能体。只要结果明显未达成目标才判定返工。",
    )
    result = await _run_work_llm_call(
        {
            "system_prompt": review_system_prompt,
            "user_prompt": review_prompt,
            "messages": [],
            "provider_id": runtime["provider_id"],
            "model": runtime["model"],
            "func_tools": runtime["func_tools"] or None,
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context(
                "review",
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
            ),
        },
        run_ctx,
        node_id="review",
        idle_timeout_seconds=_llm_idle_timeout_seconds(review_config),
        agent_id=runtime["agent_id"],
        agent_label=runtime["agent_label"],
        stream_text=True,
        stream_reasoning=True,
    )
    text = result.get("final_text", "").upper()
    passed = "PASS" in text and "RETRY" not in text
    rework_count = state.get("rework_count", 0)
    _emit(
        run_ctx,
        "phase",
        {"phase": "review_done", "label": "审查完成", "passed": passed, "progress": 88},
        "review",
    )
    if passed:
        stages = _update_stage_status(
            list(state.get("stage_steps", [])), "stage_review", "done"
        )
        stages = _update_stage_status(stages, "stage_deliver", "running")
        _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "review")
        return {
            "review_passed": True,
            "rework_count": rework_count,
            "stage_steps": stages,
        }
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
    _emit(
        run_ctx,
        "phase",
        {
            "phase": "rework_planned",
            "label": "已加入返工步骤",
            "steps": steps,
            "progress": 70,
        },
        "review",
    )
    return {
        "review_passed": False,
        "rework_count": rework_count + 1,
        "plan_steps": steps,
        "current_step_index": len(steps) - 1,
    }


async def rework_hitl_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "rework_hitl")
    run_ctx = _get_run_ctx(config)
    review_config = state.get("review_config", {}) or {}
    card = InteractionCard(
        interaction_id=f"work_rework_{uuid.uuid4().hex[:12]}",
        type="error_recovery",
        title=str(review_config.get("rework_title") or "审查未通过"),
        body=str(
            review_config.get("rework_body")
            or "任务审查未通过且已达到预设返工次数，请确认是否继续返工或结束任务。"
        ),
        fields=[
            CardField(
                key="guidance", label="返工要求", field_type="textarea", required=False
            )
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
        steps.append(
            {
                "id": len(steps) + 1,
                "description": f"返工：{guidance or '根据审查意见补全任务结果'}",
                "status": "pending",
            }
        )
        return {
            "plan_steps": steps,
            "current_step_index": len(steps) - 1,
            "review_passed": False,
        }
    if response.action_key == "cancel":
        _emit(run_ctx, "error", {"message": "任务已由人工取消"}, "rework_hitl")
    return {"review_passed": True}


async def finalize_node(state: WorkTaskState, config: RunnableConfig) -> dict:
    _interrupt_if_pause_requested(state, config, "finalize")
    run_ctx = _get_run_ctx(config)
    executor = state.get("executor_config", {}) or {}
    results_text = "\n\n".join(
        f"## {r.get('description', '')}\n{r.get('result', '')}"
        for r in state.get("step_results", [])
    )
    if run_ctx is None:
        return {"final_summary": results_text}
    _emit(
        run_ctx,
        "phase",
        {"phase": "finalize", "label": "生成交付物", "progress": 95},
        "finalize",
    )
    reporter_id = _work_agent_id(state, "reporter")
    finalize_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "results_text": results_text,
        "reporter_id": reporter_id,
    }
    finalize_prompt = _render_prompt_template(
        executor.get("finalize_prompt_template") or executor.get("finalize_prompt"),
        finalize_variables,
        f"请将以下任务执行结果整理成最终交付物。\n\n任务：{state.get('task_name', '')}\n\n{results_text}",
    )
    reporter_label = _work_agent_label(state, "reporter", reporter_id)
    node_finalize_system_prompt = _render_prompt_template(
        executor.get("finalize_system_prompt"),
        finalize_variables,
        f"你是 NiceBot Work 的汇报专家（{reporter_id}）。请只整理最终交付物，不混入过程日志。",
    )
    runtime = _resolve_work_agent_runtime(
        state,
        run_ctx,
        role="reporter",
        agent_id=reporter_id,
        agent_label=reporter_label,
        node_config=executor,
        node_id="finalize",
    )
    finalize_system_prompt = _compose_agent_node_system_prompt(
        runtime["soul"],
        node_finalize_system_prompt,
        f"你是 NiceBot Work 的汇报专家（{reporter_id}）。请只整理最终交付物，不混入过程日志。",
    )
    result = await _run_work_llm_call(
        {
            "system_prompt": finalize_system_prompt,
            "user_prompt": finalize_prompt,
            "messages": [],
            "provider_id": runtime["provider_id"],
            "model": runtime["model"],
            "func_tools": runtime["func_tools"] or None,
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context(
                "finalize",
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
            ),
        },
        run_ctx,
        node_id="finalize",
        idle_timeout_seconds=_llm_idle_timeout_seconds(executor),
        agent_id=runtime["agent_id"],
        agent_label=runtime["agent_label"],
        stream_text=True,
        stream_reasoning=True,
    )
    summary = result.get("final_text", "") or results_text
    _emit(
        run_ctx,
        "artifact",
        {
            "title": state.get("task_name", "Work 任务交付物"),
            "artifact_type": executor.get("artifact_type") or "markdown",
            "content": summary,
        },
        "finalize",
    )
    _emit(
        run_ctx,
        "phase",
        {"phase": "completed", "label": "任务完成", "progress": 100},
        "finalize",
    )
    stages = _update_stage_status(
        list(state.get("stage_steps", [])), "stage_deliver", "done"
    )
    _emit(run_ctx, "phase", {"phase": "stage_update", "steps": stages}, "finalize")
    return {"final_summary": summary, "stage_steps": stages}


def route_after_prepare(state: WorkTaskState) -> str:
    retry_config = state.get("retry_config", {}) or {}
    retry_target = retry_config.get("target")
    if retry_target in {"plan", "execute", "review", "finalize"}:
        return retry_target
    clarification_config = state.get("clarification_config", {}) or {}
    if clarification_config.get("enabled", False):
        return "clarify"
    if state.get("cancelled"):
        return "end"
    return "plan"


def route_after_clarify(state: WorkTaskState) -> str:
    if state.get("cancelled") or state.get("clarification_action") == "cancel":
        return "end"
    if state.get("clarification_action") in {"clarify_more", "interrogate_more"}:
        return "clarify"
    return "plan"


def route_after_approval(state: WorkTaskState) -> str:
    if state.get("approval_action") == "modify":
        return "plan"
    if state.get("cancelled"):
        return "end"
    if state.get("current_step_index", 0) >= 999999:
        return "end"
    return "execute"


def route_after_execute(state: WorkTaskState) -> str:
    steps = state.get("plan_steps", [])
    task_mode = state.get("task_mode") or (state.get("plan_config", {}) or {}).get(
        "task_mode", "normal"
    )
    if task_mode not in ("quick", "normal", "deep"):
        task_mode = "normal"
    executable = _collect_executable_steps(steps, task_mode)
    if state.get("current_step_index", 0) >= len(executable):
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


def _append_step_detail(step: dict[str, Any], line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    if text.startswith(("交付物：", "交付物:", "输出：", "输出:")):
        value = text.split("：", 1)[-1] if "：" in text else text.split(":", 1)[-1]
        step["deliverable"] = value.strip()
    desc = str(step.get("description") or "").strip()
    if text not in desc:
        step["description"] = f"{desc}\n{text}".strip() if desc else text


def _parse_steps(text: str) -> list[dict[str, Any]]:
    import re

    parent_steps: list[dict[str, Any]] = []
    child_steps: list[dict[str, Any]] = []
    current_parent_id: str | None = None
    current_child_id: str | None = None
    parent_counter = 0
    child_counter = 0
    main_step_pattern = re.compile(r"^(\d+)[.、)）]\s")
    sub_num_pattern = re.compile(r"^(\d+)\.(\d+)\s")

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_main_step = bool(main_step_pattern.match(stripped))
        sub_num_match = sub_num_pattern.match(stripped)
        is_sub = bool(sub_num_match)

        cleaned = stripped.lstrip("-*0123456789.、)） ").strip()
        if not cleaned:
            continue

        if is_sub and current_parent_id:
            child_counter += 1
            child_id = f"step_{parent_counter}_{child_counter}"
            current_child_id = child_id
            child_steps.append(
                {
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
                }
            )
        elif is_main_step:
            parent_counter += 1
            child_counter = 0
            step_id = f"step_{parent_counter}"
            current_parent_id = step_id
            current_child_id = None
            parent_steps.append(
                {
                    "id": step_id,
                    "title": cleaned[:80],
                    "description": cleaned,
                    "status": "pending",
                    "dependencies": []
                    if not parent_steps
                    else [f"step_{len(parent_steps)}"],
                    "parent_id": None,
                    "depth": 1,
                    "sort_order": parent_counter,
                    "executor_type": "agent",
                    "executor_id": "agent_nicebot_work_executor",
                    "reviewer_id": "agent_nicebot_work_reviewer",
                }
            )
        elif current_child_id:
            for child in child_steps:
                if child.get("id") == current_child_id:
                    _append_step_detail(child, cleaned)
                    break
        elif current_parent_id:
            for parent in parent_steps:
                if parent.get("id") == current_parent_id:
                    _append_step_detail(parent, cleaned)
                    break

    if not parent_steps:
        parent_steps.append(
            {
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
            }
        )

    result = list(parent_steps[:7])
    for ps in result:
        pid = ps["id"]
        children = [cs for cs in child_steps if cs.get("parent_id") == pid][:10]
        ps["children"] = children
    return result


def _normalize_resource_agent_id(
    agent_id: str, state: WorkTaskState, default_role: str
) -> str:
    value = str(agent_id or "").strip()
    role_aliases = {
        "assistant": "assistant",
        "executor": "executor",
        "reviewer": "reviewer",
        "researcher": "researcher",
        "reporter": "reporter",
        "任务助理": "assistant",
        "执行者": "executor",
        "审查者": "reviewer",
        "研究员": "researcher",
        "汇报专家": "reporter",
    }
    if not value:
        return _work_agent_id(state, default_role)
    return _work_agent_id(state, role_aliases[value]) if value in role_aliases else value


def _approved_plan_text(
    state: WorkTaskState, plan_steps: list[dict[str, Any]] | None = None
) -> str:
    text = str(state.get("plan_text_full") or "").strip()
    if text:
        return text
    steps = plan_steps if plan_steps is not None else state.get("plan_steps", [])
    if steps:
        return _format_plan_for_approval(steps).strip()
    return _fallback_plan_text(state)


def _apply_executor_labels(
    steps: list[dict[str, Any]], state: WorkTaskState, role: str = "executor"
) -> list[dict[str, Any]]:
    result = []
    for raw in steps or []:
        step = dict(raw)
        step["executor_id"] = step.get("executor_id") or _work_agent_id(state, role)
        step["executor"] = _step_agent_label(state, step, role)
        step["executor_type"] = step.get("executor_type") or "agent"
        if step.get("reviewer_id") is None:
            step["reviewer_id"] = ""
        step["children"] = _apply_executor_labels(
            step.get("children") or [], state, role
        )
        result.append(step)
    return result


def _update_stage_status(
    steps: list[dict], stage_id: str, new_status: str
) -> list[dict]:
    updated = []
    for s in steps:
        if s.get("id") == stage_id:
            s = dict(s)
            s["status"] = new_status
        updated.append(s)
    return updated


def _collect_executable_steps(
    steps: list[dict[str, Any]], task_mode: str = "deep"
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if task_mode == "normal":
        return [
            step for step in steps if not str(step.get("id") or "").startswith("stage_")
        ]
    for step in steps:
        children = step.get("children", [])
        if children:
            for child in children:
                result.append(child)
        else:
            result.append(step)
    return result


def _find_step_by_id(
    steps: list[dict[str, Any]], step_id: Any
) -> dict[str, Any] | None:
    target = str(step_id or "")
    if not target:
        return None
    for step in steps or []:
        if str(step.get("id") or "") == target:
            return step
        found = _find_step_by_id(step.get("children") or [], target)
        if found:
            return found
    return None


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_format_value(val)}"
            for key, val in value.items()
            if val not in (None, "", [])
        )
    return str(value or "")


def _clip_context_text(text: str, max_chars: int = 1200) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    head_len = max(200, int(max_chars * 0.65))
    tail_len = max(120, max_chars - head_len - 32)
    return (
        value[:head_len].rstrip()
        + "\n...[中间省略，保留关键结尾]...\n"
        + value[-tail_len:].lstrip()
    )


def _summarize_clarify_llm_output(
    text: str, items: list[dict[str, Any]] | None = None
) -> str:
    if items:
        lines = ["LLM 需求确认草案："]
        for item in items[:5]:
            label = item.get("label") or item.get("key") or "确认项"
            recommended = item.get("recommended") or ""
            description = item.get("description") or ""
            suffix = f"：{recommended}" if recommended else ""
            if description and not suffix:
                suffix = f"：{description}"
            lines.append(f"- {label}{suffix}")
        return "\n".join(lines)
    raw = _clip_context_text(text, 1000)
    return f"LLM 需求确认草案（原始输出）：\n{raw}"


def summarize_step_result_for_context(
    item: dict[str, Any], max_chars: int = 1000
) -> str:
    desc = str(item.get("description") or item.get("step_id") or "已完成步骤")
    result = _clip_context_text(str(item.get("result") or ""), max_chars)
    lines = [f"- {desc}"]
    agent = item.get("agent")
    if agent:
        lines.append(f"  执行者：{agent}")
    result_ref = item.get("result_ref") or item.get("artifact_id")
    if result_ref:
        lines.append(f"  结果引用：{result_ref}")
    if result:
        lines.append(f"  摘要：\n{result}")
    return "\n".join(lines)


def _format_completed_result_index(step_results: list[dict[str, Any]]) -> str:
    lines = []
    for item in step_results or []:
        step_id = item.get("step_id") or ""
        desc = item.get("description") or step_id or "已完成步骤"
        agent = item.get("agent") or ""
        status = item.get("status") or "done"
        result_ref = item.get("result_ref") or item.get("artifact_id") or ""
        suffix = f"，结果引用：{result_ref}" if result_ref else ""
        agent_text = f"，执行者：{agent}" if agent else ""
        lines.append(f"- {step_id} {desc}（{status}{agent_text}{suffix}）")
    return "\n".join(lines)


def _requirement_text(state: WorkTaskState) -> str:
    input_data = state.get("input", {}) or {}
    lines = []
    if state.get("task_name"):
        lines.append(f"- 任务名称：{state['task_name']}")
    if state.get("task_desc"):
        lines.append(f"- 任务描述：{state['task_desc']}")
    if input_data.get("goal"):
        lines.append(f"- 交付目标：{input_data['goal']}")
    clarification = _clarification_text(state)
    if clarification:
        lines.append(f"- 人工确认需求：\n{clarification}")
    context = _context_text(state)
    if context:
        lines.append(f"- 工作上下文：\n{context}")
    return "\n".join(lines) or "按任务名称、任务描述和用户确认信息执行。"


def _step_scope_text(
    state: WorkTaskState,
    steps: list[dict[str, Any]],
    step: dict[str, Any],
    step_results: list[dict[str, Any]],
    task_mode: str,
) -> str:
    lines = [f"- 当前模式：{task_mode}"]
    parent = _find_step_by_id(steps, step.get("parent_id"))
    if parent:
        lines.append(
            f"- 所属父步骤：{parent.get('title') or parent.get('description')}"
        )
        parent_desc = str(parent.get("description") or "").strip()
        if parent_desc and parent_desc != (parent.get("title") or ""):
            lines.append(f"  父步骤说明：{parent_desc}")
    lines.append(
        f"- 当前步骤：{step.get('title') or step.get('description') or step.get('id')}"
    )
    description = str(step.get("description") or "").strip()
    if description and description != (step.get("title") or ""):
        lines.append(f"  步骤说明：\n{description}")
    deliverable = step.get("deliverable") or step.get("deliverables")
    if deliverable:
        lines.append(f"  交付物：{_format_value(deliverable)}")
    children = step.get("children") or []
    if children:
        lines.append("  子任务：")
        for child in children:
            lines.append(f"  - {child.get('title') or child.get('description')}")
    dependencies = step.get("dependencies") or []
    if dependencies:
        dep_titles = []
        for dep_id in dependencies:
            dep = _find_step_by_id(steps, dep_id)
            dep_titles.append(
                str(dep.get("title") or dep.get("description") or dep_id)
                if dep
                else str(dep_id)
            )
        lines.append(f"- 前置依赖：{'；'.join(dep_titles)}")
    result_lines = []
    dep_set = {str(dep) for dep in dependencies}
    if dep_set:
        for item in step_results or []:
            item_id = str(item.get("step_id") or "")
            if item_id in dep_set:
                result_lines.append(summarize_step_result_for_context(item))
    if result_lines:
        lines.append("- 前置结果：\n" + "\n".join(result_lines))
    elif step_results:
        lines.append(
            "- 已完成结果索引（当前步骤无显式依赖，不注入完整历史结果）：\n"
            + _format_completed_result_index(step_results)
        )
    return "\n".join(lines)


def _build_execute_prompt(
    state: WorkTaskState,
    steps: list[dict[str, Any]],
    step: dict[str, Any],
    step_results: list[dict[str, Any]],
    task_mode: str,
) -> str:
    return (
        "请执行 Work 任务中的当前负责部分。\n\n"
        f"## 任务需求\n{_requirement_text(state)}\n\n"
        f"## 已审批整体计划\n{_approved_plan_text(state, steps)}\n\n"
        f"## 当前负责部分\n{_step_scope_text(state, steps, step, step_results, task_mode)}\n\n"
        "## 执行要求\n"
        "1. 先对齐任务需求和已审批整体计划，再完成当前负责部分。\n"
        "2. 只执行当前负责部分，不重写整体计划，也不要扩展到未分配步骤。\n"
        "3. 输出要能被后续步骤或最终交付复用，保留关键依据、结论和仍不确定的点。\n"
        "4. 如果当前负责部分与需求或计划冲突，明确指出冲突并给出最小可行处理。"
    )


def _compact_execution_context(
    state: WorkTaskState,
    steps: list[dict[str, Any]],
    step: dict[str, Any],
    step_results: list[dict[str, Any]],
    task_mode: str,
) -> dict[str, Any]:
    return {
        "task_name": state.get("task_name", ""),
        "task_mode": task_mode,
        "current_step_id": step.get("id", ""),
        "requirements": _requirement_text(state),
        "approved_plan": _approved_plan_text(state, steps),
        "step_scope": _step_scope_text(state, steps, step, step_results, task_mode),
        "completed_results_index": _format_completed_result_index(step_results),
    }


def _children_with_status(
    children: list[dict[str, Any]], status: str
) -> list[dict[str, Any]]:
    updated = []
    for child in children or []:
        item = dict(child)
        item["status"] = status
        item["children"] = _children_with_status(item.get("children") or [], status)
        updated.append(item)
    return updated


def _update_step_in_tree(
    steps: list[dict[str, Any]], step_id: str, updates: dict[str, Any]
) -> None:
    for step in steps:
        if step.get("id") == step_id:
            step.update(updates)
            return
        for child in step.get("children", []):
            if child.get("id") == step_id:
                child.update(updates)
                return


def _update_parent_status(steps: list[dict[str, Any]], parent_id: str | None) -> None:
    if not parent_id:
        return
    for step in steps:
        if step.get("id") != parent_id:
            continue
        children = step.get("children", [])
        if not children:
            continue
        all_done = all(c.get("status") in ("done", "completed") for c in children)
        any_failed = any(c.get("status") == "failed" for c in children)
        if any_failed:
            step["status"] = "failed"
        elif all_done:
            step["status"] = "done"
        return


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
    return (
        config.get(f"{role}_agent_id") or defaults.get(role) or fallback.get(role, "")
    )


def _load_hitl_template(template_id: str) -> dict[str, Any] | None:
    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.hitl_template_service import (
            HITLTemplateService,
        )

        db = get_database()
        svc = HITLTemplateService(db)
        row = svc.get_template(template_id)
        if row:
            return row
    except Exception:
        pass
    return None


async def _run_interrogation_if_needed(
    state: WorkTaskState,
    clarification_config: dict[str, Any],
    run_ctx: GraphRunContext | None,
) -> dict[str, Any] | None:
    if not clarification_config.get("interrogation_enabled", False):
        return None
    if state.get("interrogation_ready"):
        return None
    max_rounds = _safe_int(clarification_config.get("interrogation_max_rounds"), 5)
    max_rounds = max(1, min(10, max_rounds))
    history = list(state.get("interrogation_history") or [])
    current_round = _safe_int(state.get("interrogation_round"), len(history))
    if current_round >= max_rounds:
        message = f"需求拷问已达到最大 {max_rounds} 轮，仍未确认需求可执行。"
        _emit(
            run_ctx,
            "error",
            {"message": message, "status": "retryable_failed"},
            "clarify",
        )
        raise RuntimeError(message)
    if run_ctx is None:
        return {"interrogation_ready": True, "interrogation_summary": ""}

    agent_id = (
        clarification_config.get("interrogation_agent_id")
        or clarification_config.get("content_provider_agent_id")
        or "agent_nicebot_work_assistant"
    )
    agent_label = _work_agent_label(state, "assistant", agent_id)
    prompt_variables = {
        "task_name": state.get("task_name", ""),
        "task_desc": state.get("task_desc", ""),
        "work_context": _context_text(state),
        "interrogation_history": _format_interrogation_history(history),
    }
    default_prompt = (
        "请评估以下 Work 任务是否已经具备明确价值和可执行需求。\n\n"
        "任务名称：{task_name}\n"
        "任务描述：{task_desc}\n\n"
        "工作上下文：\n{work_context}\n\n"
        "已完成质询记录：\n{interrogation_history}\n\n"
        "只返回 JSON：\n"
        "{\n"
        '  "status": "ask 或 ready",\n'
        '  "value_assessment": "对需求价值、合理性、风险的简短判断",\n'
        '  "questions": ["还必须追问的问题"],\n'
        '  "summary": "status 为 ready 时给出已明确需求摘要"\n'
        "}"
    )
    node_system_prompt = _render_prompt_template(
        clarification_config.get("interrogation_system_prompt"),
        prompt_variables,
        "你是 NiceBot Work 的需求拷问助手。先判断需求价值、范围和验收标准是否清楚，只返回 JSON。",
    )
    prompt = _render_prompt_template(
        clarification_config.get("interrogation_prompt"),
        prompt_variables,
        default_prompt,
    )
    runtime = _resolve_work_agent_runtime(
        state,
        run_ctx,
        role="assistant",
        agent_id=agent_id,
        agent_label=agent_label,
        node_config=clarification_config,
        node_id="clarify",
    )
    system_prompt = _compose_agent_node_system_prompt(
        runtime["soul"],
        node_system_prompt,
        "你是 NiceBot Work 的需求拷问助手。只返回 JSON。",
    )
    result = await _run_work_llm_call(
        {
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "messages": [],
            "provider_id": runtime["provider_id"],
            "model": runtime["model"],
            "func_tools": runtime["func_tools"] or None,
            "session_id": state.get("session_id", "work"),
            "trace_context": _trace_context(
                "clarify",
                agent_id=runtime["agent_id"],
                agent_label=runtime["agent_label"],
            ),
        },
        run_ctx,
        node_id="clarify",
        idle_timeout_seconds=_llm_idle_timeout_seconds(clarification_config),
        agent_id=runtime["agent_id"],
        agent_label=runtime["agent_label"],
        stream_text=False,
        stream_reasoning=True,
    )
    payload = _parse_interrogation_payload(str(result.get("final_text") or ""))
    if payload.get("status") == "ready":
        summary = str(payload.get("summary") or payload.get("value_assessment") or "")
        _emit(
            run_ctx,
            "phase",
            {
                "phase": "interrogation_ready",
                "label": "需求拷问已完成，进入标准需求确认",
                "progress": 10,
                "status": "running",
            },
            "clarify",
            agent_id=runtime["agent_id"],
            agent_label=runtime["agent_label"],
        )
        return {
            "interrogation_ready": True,
            "interrogation_summary": summary,
            "interrogation_history": history,
            "interrogation_round": current_round,
        }

    questions = _string_list(payload.get("questions"))
    if not questions:
        questions = ["请补充任务价值、目标对象、范围边界和验收标准。"]
    assessment = str(payload.get("value_assessment") or "")
    card = InteractionCard(
        interaction_id=f"work_interrogate_{uuid.uuid4().hex[:12]}",
        type="clarification_interrogation",
        title=f"需求拷问：{state.get('task_name', '')}",
        body=_format_interrogation_body(questions, assessment, current_round + 1, max_rounds),
        fields=[
            CardField(
                key="interrogation_answer",
                label="回答",
                field_type="textarea",
                required=True,
                description="请逐条回应上面的质询问题",
            )
        ],
        actions=[
            CardAction(key="submit", label="提交回答", style="primary"),
            CardAction(key="cancel", label="取消任务", style="danger"),
        ],
        meta={"task_id": state.get("task_id", ""), "round": current_round + 1},
    )
    _emit(run_ctx, "interaction", card.to_dict(), "clarify")
    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=state.get("task_id", ""),
        channel="chatui",
        channel_extra={"task_id": state.get("task_id", ""), "sync_chatui": True},
    )
    if response.action_key == "cancel":
        return {"cancelled": True, "clarification_action": "cancel"}
    values = response.field_values or {}
    answer = str(values.get("interrogation_answer") or "").strip()
    history.append(
        {
            "round": current_round + 1,
            "value_assessment": assessment,
            "questions": questions,
            "answer": answer,
        }
    )
    return {
        "clarification_action": "interrogate_more",
        "interrogation_history": history,
        "interrogation_round": current_round + 1,
        "interrogation_ready": False,
    }


def _parse_interrogation_payload(text: str) -> dict[str, Any]:
    try:
        payload = _extract_json_payload(text)
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _format_interrogation_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "暂无。"
    lines = []
    for item in history:
        questions = "；".join(_string_list(item.get("questions")))
        lines.append(
            f"第 {item.get('round')} 轮：问题：{questions}\n回答：{item.get('answer', '')}"
        )
    return "\n".join(lines)


def _interrogation_summary_text(state: WorkTaskState) -> str:
    summary = str(state.get("interrogation_summary") or "").strip()
    if summary:
        return f"拷问阶段摘要：\n{summary}\n\n"
    history = state.get("interrogation_history") or []
    if history:
        return f"拷问阶段记录：\n{_format_interrogation_history(history)}\n\n"
    return ""


def _format_interrogation_body(
    questions: list[str], assessment: str, round_no: int, max_rounds: int
) -> str:
    lines = [f"第 {round_no}/{max_rounds} 轮质询。"]
    if assessment:
        lines.append(f"\n价值判断：{assessment}")
    lines.append("\n请先回答这些问题，再进入标准需求确认：")
    lines.extend(f"{idx}. {question}" for idx, question in enumerate(questions, 1))
    return "\n".join(lines)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    agent_id = clarification_config.get(
        "content_provider_agent_id", "agent_nicebot_work_assistant"
    )
    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")

    previous = state.get("clarification", {}) or {}
    previous_feedback = state.get("clarification_feedback", "")

    history_context = ""
    if previous:
        history_lines = []
        for k, v in previous.items():
            if k == "clarify_more_text":
                continue
            val_str = "、".join(str(x) for x in v) if isinstance(v, list) else str(v)
            history_lines.append(f"  - {k}: {val_str}")
        history_context = "已提交的需求信息：\n" + "\n".join(history_lines) + "\n\n"
        if previous_feedback:
            history_context += f"用户的补充意见：\n{previous_feedback}\n\n"
        history_context += (
            "请根据以上已提交信息和补充意见，重新生成需求确认卡片。\n"
            "要求：\n"
            "1. 保留之前已提交的选择作为对应字段的推荐/默认值\n"
            "2. 根据补充意见调整或新增确认项\n"
            "3. 对于用户已明确选择的字段，options 中应将该选择标注为推荐\n"
        )

    interrogation_summary = _interrogation_summary_text(state)
    default_prompt = (
        f"请为以下任务生成需求确认项，以 JSON 格式返回。\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}\n\n"
        f"{_context_text(state)}\n\n"
        f"{interrogation_summary}"
        f"{history_context}"
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
        '      "allow_custom": true,\n'
        '      "custom_placeholder": "自定义时填写"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "要求：\n"
        "1. 根据任务内容生成 2-5 个最相关的确认项\n"
        '2. 每个确认项的 options 应包含 3-6 个选项，推荐项以"推荐："开头\n'
        "3. field_type 选择规则：\n"
        "   - select：单选，有明确互斥选项时使用\n"
        "   - multiselect：多选，需要同时选择多个选项时使用（如：关注维度、目标品牌、数据来源）\n"
        "   - textarea：需要自由输入时使用\n"
        "4. 确保推荐项与任务内容相关，不要使用通用默认值\n"
        '5. 当确认项天然需要多选时（如"关注哪些维度""需要哪些数据源"），使用 multiselect\n'
        "6. 每个 select/multiselect 类型字段必须设置 allow_custom 为 true\n"
    )
    prompt_variables = {
        "task_name": task_name,
        "task_desc": task_desc,
        "work_context": _context_text(state),
        "history_context": history_context,
        "interrogation_summary": _interrogation_summary_text(state),
    }
    prompt = _render_prompt_template(
        clarification_config.get("content_prompt"), prompt_variables, default_prompt
    )
    agent_label = _work_agent_label(state, "assistant", agent_id)
    node_system_prompt = _render_prompt_template(
        clarification_config.get("content_system_prompt"),
        prompt_variables,
        "你是 NiceBot Work 任务助手，擅长根据任务内容生成精准的需求确认项。只返回 JSON，不要其他内容。",
    )

    if run_ctx is None:
        return _fallback_clarify_content(state)

    try:
        runtime = _resolve_work_agent_runtime(
            state,
            run_ctx,
            role="assistant",
            agent_id=agent_id,
            agent_label=agent_label,
            node_config=clarification_config,
            node_id="clarify",
        )
        system_prompt = _compose_agent_node_system_prompt(
            runtime["soul"],
            node_system_prompt,
            "你是 NiceBot Work 任务助手，擅长根据任务内容生成精准的需求确认项。只返回 JSON，不要其他内容。",
        )
        result = await _run_work_llm_call(
            {
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "messages": [],
                "provider_id": runtime["provider_id"],
                "model": runtime["model"],
                "func_tools": runtime["func_tools"] or None,
                "session_id": state.get("session_id", "work"),
                "trace_context": _trace_context(
                    "clarify",
                    agent_id=runtime["agent_id"],
                    agent_label=runtime["agent_label"],
                ),
            },
            run_ctx,
            node_id="clarify",
            idle_timeout_seconds=_llm_idle_timeout_seconds(clarification_config),
            agent_id=runtime["agent_id"],
            agent_label=runtime["agent_label"],
            stream_text=False,
            stream_reasoning=True,
        )
        text = result.get("final_text", "").strip()
        call_id = str(result.get("_work_call_id") or "")
        call_attempt = int(result.get("_work_call_attempt") or 1)
        if text:
            items = _parse_confirmation_items(text)
            if items:
                items = _ensure_allow_custom(items)
                _emit(
                    run_ctx,
                    "text_delta",
                    {
                        "text": _summarize_clarify_llm_output(text, items),
                        "call_id": call_id,
                        "call_attempt": call_attempt,
                        "lane": "output",
                    },
                    "clarify",
                    agent_id=agent_id,
                    agent_label=agent_label,
                )
                return {
                    "confirmation_items": items,
                }
            _emit(
                run_ctx,
                "text_delta",
                {
                    "text": _summarize_clarify_llm_output(text),
                    "call_id": call_id,
                    "call_attempt": call_attempt,
                    "lane": "output",
                },
                "clarify",
                agent_id=agent_id,
                agent_label=agent_label,
            )
            _emit(
                run_ctx,
                "error",
                {"message": "需求确认项解析失败，已降级为兜底卡片。"},
                "clarify",
                agent_id=agent_id,
                agent_label=agent_label,
            )
    except WorkLLMIdleTimeout:
        raise

    return _fallback_clarify_content(state)


def _parse_confirmation_items(text: str) -> list[dict[str, Any]]:
    import json

    cleaned = text
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
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
                data = json.loads(cleaned[start : end + 1])
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


def _ensure_allow_custom(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        ft = item.get("field_type", "select")
        if ft in ("select", "multiselect"):
            item["allow_custom"] = True
    return items


def _format_clarification_summary(values: dict[str, Any], card: InteractionCard) -> str:
    if not values:
        return ""
    field_labels: dict[str, str] = {}
    for f in card.fields or []:
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
        context_hint = (
            f"（任务描述：{task_desc[:60]}）"
            if len(task_desc) > 60
            else f"（任务描述：{task_desc}）"
        )

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
                "options": [
                    "推荐：结构化报告",
                    "清单",
                    "步骤方案",
                    "文件",
                    "对话结论",
                    "自定义",
                ],
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
    goal = (
        (state.get("input", {}) or {}).get("goal")
        or state.get("task_desc")
        or state.get("task_name")
        or "完成任务"
    ).strip()
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
        executor_id = step.get("executor_id") or ""
        if executor_id:
            lines.append(f"  执行者：{step.get('executor') or executor_id}")
        reviewer_id = step.get("reviewer_id") or ""
        if reviewer_id:
            lines.append(f"  审查者：{reviewer_id}")
        acceptance = step.get("acceptance_criteria") or []
        if acceptance:
            lines.append(f"  验收标准：{'；'.join(str(item) for item in acceptance)}")
        rationale = step.get("resource_rationale")
        if rationale:
            lines.append(f"  资源理由：{rationale}")
        deps = step.get("dependencies", [])
        if deps:
            dep_labels = [d for d in deps if d.startswith("step_")]
            if dep_labels:
                lines.append(f"  前置：{', '.join(dep_labels)}")
        else:
            lines.append("  前置：无")
        children = step.get("children", [])
        if children:
            lines.append("  子任务：")
            for child in children:
                child_title = child.get("title", child.get("description", ""))[:60]
                child_executor = child.get("executor") or child.get("executor_id") or ""
                child_deliverable = child.get("deliverable") or ""
                suffix_parts = []
                if child_executor:
                    suffix_parts.append(f"执行者：{child_executor}")
                if child_deliverable:
                    suffix_parts.append(f"交付物：{child_deliverable}")
                suffix = f"（{'；'.join(suffix_parts)}）" if suffix_parts else ""
                lines.append(f"    - {child_title}{suffix}")
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
    builder.add_conditional_edges(
        "prepare",
        route_after_prepare,
        {"clarify": "clarify", "plan": "plan", "execute": "execute", "end": END},
    )
    builder.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {"clarify": "clarify", "plan": "plan", "execute": "execute", "end": END},
    )
    builder.add_edge("plan", "approve_plan")
    builder.add_conditional_edges(
        "approve_plan",
        route_after_approval,
        {"plan": "plan", "execute": "execute", "end": END},
    )
    builder.add_conditional_edges(
        "execute", route_after_execute, {"execute": "execute", "review": "review"}
    )
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"execute": "execute", "hitl": "rework_hitl", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "rework_hitl",
        route_after_rework_hitl,
        {"execute": "execute", "finalize": "finalize"},
    )
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
