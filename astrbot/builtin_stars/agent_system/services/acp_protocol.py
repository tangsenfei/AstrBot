"""Shared ACP constants and helpers for CLI agent integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

ACP_PROTOCOL_VERSION = 1
ACP_JSONRPC_VERSION = "2.0"


class AcpMethod:
    INITIALIZE = "initialize"
    SESSION_NEW = "session/new"
    SESSION_NEW_ALT = "newSession"
    SESSION_LOAD = "session/load"
    SESSION_PROMPT = "session/prompt"
    SESSION_PROMPT_ALT = "prompt"
    SESSION_CANCEL = "session/cancel"
    SESSION_CLOSE = "session/close"
    SET_MODEL = "session/setModel"
    SET_MODE = "session/setMode"
    SET_CONFIG_OPTION = "session/setConfigOption"
    AUTHENTICATE = "authenticate"


class AcpNotification:
    SESSION_UPDATE = "session/update"
    PERMISSION_REQUEST = "permission/request"
    END_TURN = "session/endTurn"


class AcpUpdateType:
    AGENT_MESSAGE_CHUNK = "agent_message_chunk"
    AGENT_THOUGHT_CHUNK = "agent_thought_chunk"
    TOOL_CALL = "tool_call"
    TOOL_CALL_UPDATE = "tool_call_update"
    PLAN = "plan"
    USAGE_UPDATE = "usage_update"
    CONFIG_OPTION_UPDATE = "config_option_update"


class AcpCapability:
    LOAD_SESSION = "loadSession"
    PROMPT_CAPABILITIES = "promptCapabilities"
    MCP_CAPABILITIES = "mcpCapabilities"
    SESSION_CAPABILITIES = "sessionCapabilities"


def extract_acp_text(payload: Any) -> str:
    """Extract user-visible text from common ACP payload shapes."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "".join(extract_acp_text(item) for item in payload)
    if not isinstance(payload, dict):
        return ""

    for key in ("text", "content", "message", "output", "finalText", "final_text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value

    parts: list[str] = []
    for key in ("delta", "contentBlock", "message", "update", "result", "content"):
        text = extract_acp_text(payload.get(key))
        if text:
            parts.append(text)
    return "".join(parts)


def acp_capabilities(initialize_result: dict[str, Any] | None) -> dict[str, Any]:
    """Return capabilities regardless of the server's preferred nesting."""
    if not isinstance(initialize_result, dict):
        return {}
    agent_caps = initialize_result.get("agentCapabilities")
    if isinstance(agent_caps, dict):
        return agent_caps
    agent_info = initialize_result.get("agentInfo")
    if isinstance(agent_info, dict) and isinstance(
        agent_info.get("capabilities"), dict
    ):
        return agent_info["capabilities"]
    caps = initialize_result.get("capabilities")
    return caps if isinstance(caps, dict) else {}


def normalize_acp_tool_call(
    update: dict[str, Any] | None,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Normalize ACP tool_call/tool_call_update payloads for chat rendering."""
    payload = update if isinstance(update, dict) else {}
    tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
    raw_input = (
        payload.get("rawInput")
        or payload.get("input")
        or payload.get("args")
        or tool_call.get("input")
        or tool_call.get("args")
        or {}
    )
    raw_output = (
        payload.get("rawOutput")
        or payload.get("output")
        or payload.get("result")
        or tool_call.get("output")
        or tool_call.get("result")
    )
    if raw_output is None:
        content_text = extract_acp_text(payload.get("content"))
        raw_output = {"output": content_text} if content_text else None

    status = str(payload.get("status") or tool_call.get("status") or "running")
    timestamp = _iso_timestamp(created_at)
    normalized: dict[str, Any] = {
        "id": str(
            payload.get("toolCallId")
            or payload.get("tool_call_id")
            or payload.get("id")
            or tool_call.get("id")
            or ""
        ),
        "name": str(
            payload.get("name")
            or payload.get("toolName")
            or payload.get("title")
            or tool_call.get("name")
            or "tool"
        ),
        "status": status,
        "kind": payload.get("kind") or tool_call.get("kind") or "",
        "args": raw_input if isinstance(raw_input, dict) else {"input": raw_input},
        "result": raw_output,
        "ts": timestamp,
        "raw": payload,
    }
    if not normalized["id"]:
        normalized["id"] = f"{normalized['name']}-{int(timestamp * 1000)}"
    if status in {"completed", "failed", "cancelled", "canceled"}:
        normalized["finished_ts"] = timestamp
    return normalized


def merge_tool_call_update(
    current: dict[str, Any] | None,
    update: dict[str, Any],
) -> dict[str, Any]:
    """Merge a normalized tool update into the current chat tool call state."""
    if not current:
        return dict(update)
    merged = dict(current)
    for key in ("id", "name", "status", "kind", "raw"):
        if update.get(key):
            merged[key] = update[key]
    if update.get("args"):
        merged["args"] = update["args"]
    if update.get("result") is not None:
        merged["result"] = update["result"]
    merged["ts"] = current.get("ts") or update.get("ts")
    if update.get("finished_ts"):
        merged["finished_ts"] = update["finished_ts"]
    return merged


def _iso_timestamp(value: str | None) -> float:
    if not value:
        return datetime.now().timestamp()
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return datetime.now().timestamp()
