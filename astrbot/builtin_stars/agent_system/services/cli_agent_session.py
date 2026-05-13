"""CLI Agent session FSM with streaming event broadcast."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from astrbot.core import logger

from .acp_protocol import (
    AcpNotification,
    AcpUpdateType,
    extract_acp_text,
    normalize_acp_tool_call,
)
from .cli_agent_connector import CliAgentConnector, ConnectorConfig
from .cli_agent_connector import AgentDisconnectedError
from .cli_agent_permission import PermissionRequest, PermissionResolver


TURN_DRAIN_DELAY_SECONDS = 0.05
MAX_AUTO_RECONNECT_ATTEMPTS = 2
END_TURN_IDLE_TIMEOUT_SECONDS = 15.0


class SessionState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    PROMPTING = "prompting"
    SUSPENDED = "suspended"
    RESUMING = "resuming"
    ERROR = "error"


VALID_TRANSITIONS = {
    SessionState.IDLE: {SessionState.STARTING},
    SessionState.STARTING: {SessionState.ACTIVE, SessionState.ERROR},
    SessionState.ACTIVE: {
        SessionState.PROMPTING,
        SessionState.SUSPENDED,
        SessionState.RESUMING,
        SessionState.IDLE,
    },
    SessionState.PROMPTING: {
        SessionState.ACTIVE,
        SessionState.SUSPENDED,
        SessionState.RESUMING,
        SessionState.ERROR,
        SessionState.IDLE,
    },
    SessionState.SUSPENDED: {
        SessionState.RESUMING,
        SessionState.ERROR,
        SessionState.IDLE,
    },
    SessionState.RESUMING: {SessionState.ACTIVE, SessionState.ERROR},
    SessionState.ERROR: {SessionState.STARTING, SessionState.RESUMING, SessionState.IDLE},
}


class CliAgentSession:
    def __init__(
        self,
        session_id: str,
        connector: CliAgentConnector,
        db,
        config: ConnectorConfig,
        *,
        client_id: str = "",
        permission_policy: str = "ask",
    ) -> None:
        self.session_id = session_id
        self.state = SessionState.IDLE
        self._connector = connector
        self._db = db
        self._config = config
        self._client_id = client_id
        self._permission_policy = permission_policy
        self._permission_resolver = PermissionResolver(
            db, auto_approve=permission_policy == "allow"
        )
        self._subscribers: list[asyncio.Queue] = []
        self._history: list[dict[str, Any]] = []
        self._event_seq = 0
        self._message_buffer: list[str] = []
        self._last_activity = datetime.now()
        self._pending_prompt = ""
        self._recovery_task: asyncio.Task | None = None
        self._recovering = False
        self._turn_finished = False

    @property
    def last_activity(self) -> datetime:
        return self._last_activity

    async def start(self) -> None:
        self._transition(SessionState.STARTING)
        self._connector.on_notification(self._handle_notification)
        self._connector.on_disconnect(self._on_disconnect)
        init_result = await self._connector.start(self._config)
        lifecycle_result = self._build_lifecycle_result(init_result)
        self._db.update(
            "cli_agent_sessions",
            {
                "external_session_key": self._connector.external_session_id,
                "last_error": "",
                "last_heartbeat": self._now(),
                "updated_at": self._now(),
            },
            where="id = ?",
            where_params=(self.session_id,),
        )
        self._emit_nowait(
            {
                "type": "lifecycle",
                "status": "initialized",
                "result": lifecycle_result,
            }
        )
        self._transition(SessionState.ACTIVE)

    async def send_message(self, text: str) -> None:
        content = str(text or "").strip()
        if not content:
            raise ValueError("消息内容不能为空")
        self._transition(SessionState.PROMPTING)
        self._pending_prompt = content
        self._message_buffer = []
        self._turn_finished = False
        self._insert_message("user", content)
        self._insert_event("message", {"role": "user", "content": content})
        self._emit_nowait({"type": "message", "role": "user", "content": content})
        prompt_task = asyncio.create_task(self._connector.send_prompt(content))
        idle_task = asyncio.create_task(self._watch_turn_idle())
        try:
            done, _pending = await asyncio.wait(
                {prompt_task, idle_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if idle_task in done and idle_task.result() == "idle_finish":
                prompt_task.cancel()
                with contextlib.suppress(Exception):
                    await self._connector.cancel_prompt()
                await self._finish_turn({"synthetic": True, "reason": "idle_timeout"})
                return
            result = await prompt_task
            await self._finish_turn(result)
        except AgentDisconnectedError:
            recovery_task = self._recovery_task
            if recovery_task:
                await recovery_task
                return
            await self._auto_recover(AgentDisconnectedError("Agent 进程断连"))
        except Exception as exc:
            self._transition(SessionState.ERROR)
            self._db.update(
                "cli_agent_sessions",
                {"last_error": str(exc), "updated_at": self._now()},
                where="id = ?",
                where_params=(self.session_id,),
            )
            self._emit_nowait(
                {"type": "error", "message": str(exc), "recoverable": True}
            )
            raise
        finally:
            for task in (prompt_task, idle_task):
                if not task.done():
                    task.cancel()
            if not self._recovering:
                self._pending_prompt = ""

    async def stop(self) -> None:
        await self._connector.stop()
        self._transition(SessionState.IDLE)
        self._emit_nowait({"type": "lifecycle", "status": "idle", "reason": "stopped"})

    async def reconnect(self) -> None:
        self._transition(SessionState.RESUMING)
        try:
            await self._connector.start(self._config)
            self._db.update(
                "cli_agent_sessions",
                {
                    "external_session_key": self._connector.external_session_id,
                    "last_error": "",
                    "last_heartbeat": self._now(),
                    "updated_at": self._now(),
                },
                where="id = ?",
                where_params=(self.session_id,),
            )
            self._transition(SessionState.ACTIVE)
            self._emit_nowait({"type": "reconnected"})
        except Exception as exc:
            self._transition(SessionState.ERROR)
            self._emit_nowait({"type": "error", "message": f"重连失败: {exc}"})

    async def set_model(self, model_id: str) -> Any:
        return await self._connector.set_model(model_id)

    async def set_mode(self, mode_id: str) -> Any:
        return await self._connector.set_mode(mode_id)

    def subscribe(
        self, after_seq: int = 0, *, live_only: bool = False
    ) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        if live_only:
            after_seq = self._event_seq
        for event in self._history:
            if int(event.get("seq") or 0) > after_seq:
                queue.put_nowait(event)
        self._subscribers.append(queue)

        async def generator():
            try:
                while True:
                    yield await queue.get()
            finally:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

        return generator()

    @property
    def events(self) -> AsyncIterator[dict[str, Any]]:
        return self.subscribe()

    async def _handle_notification(self, notification: dict[str, Any]) -> Any:
        method = notification.get("method") or ""
        params = notification.get("params") or {}
        self._last_activity = datetime.now()
        if method == AcpNotification.SESSION_UPDATE:
            update = params.get("update") if isinstance(params, dict) else {}
            update_type = (
                update.get("sessionUpdate") if isinstance(update, dict) else None
            )
            if update_type == AcpUpdateType.AGENT_MESSAGE_CHUNK:
                text = extract_acp_text(update.get("content"))
                if text:
                    self._message_buffer.append(text)
                    self._insert_event("message_chunk", {"text": text})
                    self._emit_nowait({"type": "message_chunk", "text": text})
            elif update_type in {
                AcpUpdateType.TOOL_CALL,
                AcpUpdateType.TOOL_CALL_UPDATE,
            }:
                self._insert_event("tool_call", update)
                self._emit_nowait(
                    {
                        "type": "tool_call",
                        **normalize_acp_tool_call(update, created_at=self._now()),
                    }
                )
            else:
                self._insert_event("session_update", params)
                self._emit_nowait({"type": "session_update", "payload": params})
            return None
        if "permission" in method.lower():
            request = PermissionResolver.from_acp(self._client_id, params)
            decision = await self._permission_resolver.resolve(
                self.session_id,
                request,
                timeout_seconds=120,
                on_created=self._emit_nowait,
                on_timeout=self._emit_nowait,
            )
            return {"outcome": "approved" if decision == "approved" else "denied"}
        if method in {"writeTextFile", "fs/write_text_file"}:
            file_path = params.get("path") or params.get("filePath") or ""
            full_path = self._resolve_workspace_path(str(file_path))
            if full_path and await self._confirm_fs_permission(
                "write", full_path, params
            ):
                content = str(params.get("content") or "")
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                return {"ok": True}
            return {"ok": False, "message": f"路径 '{file_path}' 不在工作区范围内"}
        if method in {"readTextFile", "fs/read_text_file"}:
            file_path = params.get("path") or params.get("filePath") or ""
            full_path = self._resolve_workspace_path(str(file_path))
            if (
                full_path
                and full_path.exists()
                and full_path.is_file()
                and await self._confirm_fs_permission("read", full_path, params)
            ):
                return {"content": full_path.read_text(encoding="utf-8")}
            return {"content": ""}
        if method == AcpNotification.END_TURN:
            await self._finish_turn(params)
            return None
        self._insert_event("acp_event", {"method": method, "params": params})
        self._emit_nowait({"type": "acp_event", "method": method, "payload": params})
        return None

    async def _finish_turn(self, result: Any) -> None:
        if self._turn_finished:
            return
        self._turn_finished = True
        await asyncio.sleep(TURN_DRAIN_DELAY_SECONDS)
        output = "".join(self._message_buffer)
        if output:
            self._insert_message("assistant", output)
        self._insert_event("turn_done", {"result": result})
        self._emit_nowait({"type": "turn_done", "result": result})
        self._message_buffer = []
        self._transition(SessionState.ACTIVE)

    async def _on_disconnect(self, error: Exception) -> None:
        if self.state is SessionState.PROMPTING:
            if not self._recovery_task or self._recovery_task.done():
                self._recovery_task = asyncio.create_task(self._auto_recover(error))
        elif self.state is SessionState.ACTIVE:
            self._transition(SessionState.SUSPENDED)
            self._emit_nowait(
                {"type": "disconnected", "message": "Agent 进程断连，可点击重连"}
            )
        elif self.state is SessionState.RESUMING and self._recovering:
            # The recovery task owns retry/failure reporting. Emitting the raw
            # transport error here creates a duplicate user-visible failure.
            return
        else:
            self._transition(SessionState.ERROR)
            self._emit_nowait({"type": "error", "message": str(error)})

    async def _auto_recover(self, error: Exception) -> None:
        if self._recovering:
            return
        self._recovering = True
        try:
            self._emit_nowait(
                {
                    "type": "status",
                    "message": "Agent 进程意外断开，正在自动重连...",
                    "attempt": 0,
                }
            )
            for attempt in range(1, MAX_AUTO_RECONNECT_ATTEMPTS + 1):
                try:
                    self._transition(SessionState.RESUMING)
                    if self._connector.external_session_id:
                        self._config.external_session_key = (
                            self._connector.external_session_id
                        )
                    await self._connector.start(self._config)
                    self._persist_external_session_key()
                    if self._pending_prompt:
                        self._emit_nowait(
                            {"type": "status", "message": "已重连，继续处理..."}
                        )
                        result = await self._connector.send_prompt(
                            self._pending_prompt
                        )
                        await self._finish_turn(result)
                    else:
                        self._transition(SessionState.ACTIVE)
                        self._emit_nowait({"type": "reconnected"})
                    return
                except Exception as exc:
                    logger.warning(
                        f"Auto-reconnect attempt {attempt}/{MAX_AUTO_RECONNECT_ATTEMPTS} "
                        f"failed for session {self.session_id}: {exc}"
                    )
                    if attempt < MAX_AUTO_RECONNECT_ATTEMPTS:
                        backoff = 1 * (2 ** (attempt - 1))
                        self._emit_nowait(
                            {
                                "type": "status",
                                "message": f"重连失败，{backoff}s 后重试 ({attempt}/{MAX_AUTO_RECONNECT_ATTEMPTS})...",
                                "attempt": attempt,
                            }
                        )
                        await asyncio.sleep(backoff)

            self._transition(SessionState.ERROR)
            self._emit_nowait(
                {
                    "type": "error",
                    "message": f"Agent 进程断连且自动恢复失败: {error}",
                    "recoverable": True,
                    "last_prompt": self._pending_prompt,
                }
            )
        finally:
            self._recovering = False

    async def _watch_turn_idle(self) -> str | None:
        while True:
            await asyncio.sleep(END_TURN_IDLE_TIMEOUT_SECONDS)
            idle_seconds = (datetime.now() - self._last_activity).total_seconds()
            if idle_seconds < END_TURN_IDLE_TIMEOUT_SECONDS:
                continue
            if self.state is SessionState.PROMPTING and self._message_buffer:
                logger.warning(
                    f"Session {self.session_id}: no activity for {idle_seconds:.0f}s, "
                    "synthesizing turn_done"
                )
                self._emit_nowait(
                    {
                        "type": "status",
                        "message": "Agent 长时间无响应，自动结束当前回合",
                    }
                )
                return "idle_finish"
            return None

    def _transition(self, next_state: SessionState) -> None:
        if next_state is self.state:
            return
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if next_state not in allowed:
            raise RuntimeError(
                f"Invalid CLI Agent state transition: {self.state.value} -> {next_state.value}"
            )
        self.state = next_state
        self._last_activity = datetime.now()
        self._db.update(
            "cli_agent_sessions",
            {
                "status": next_state.value,
                "last_heartbeat": self._now(),
                "updated_at": self._now(),
            },
            where="id = ?",
            where_params=(self.session_id,),
        )

    def _emit_nowait(self, event: dict[str, Any]) -> None:
        self._event_seq += 1
        payload = {"seq": self._event_seq, "session_id": self.session_id, **event}
        self._history.append(payload)
        if len(self._history) > 2000:
            self._history = self._history[-2000:]
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                logger.warning(
                    f"CLI Agent SSE subscriber queue overflow: {self.session_id}"
                )
            queue.put_nowait(payload)

    def _resolve_workspace_path(self, requested_path: str) -> Path | None:
        if not self._config.cwd or not requested_path:
            return None
        root = Path(self._config.cwd).resolve()
        candidate = Path(requested_path)
        if candidate.is_absolute():
            target = candidate.resolve()
        else:
            target = (root / candidate).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None
        return target

    async def _confirm_fs_permission(
        self, action: str, full_path: Path, params: dict[str, Any]
    ) -> bool:
        if self._permission_policy == "deny":
            return False
        if self._permission_policy == "allow":
            return True
        request = PermissionRequest(
            kind="fs",
            title=f"{action} file",
            body=str(full_path),
            raw_input={**params, "path": str(full_path)},
            client_id=self._client_id,
        )
        decision = await self._permission_resolver.resolve(
            self.session_id,
            request,
            timeout_seconds=120,
            on_created=self._emit_nowait,
            on_timeout=self._emit_nowait,
        )
        return decision == "approved"

    def _persist_external_session_key(self) -> None:
        self._db.update(
            "cli_agent_sessions",
            {
                "external_session_key": self._connector.external_session_id,
                "last_error": "",
                "last_heartbeat": self._now(),
                "updated_at": self._now(),
            },
            where="id = ?",
            where_params=(self.session_id,),
        )

    def _build_lifecycle_result(self, init_result: dict[str, Any]) -> dict[str, Any]:
        result = dict(init_result) if isinstance(init_result, dict) else {}
        session_result = getattr(self._connector, "session_result", {})
        if isinstance(session_result, dict):
            result.setdefault("models", session_result.get("models") or {})
            result.setdefault("modes", session_result.get("modes") or {})
            result.setdefault(
                "configOptions", session_result.get("configOptions") or {}
            )
        return result

    def _insert_message(self, role: str, content: str) -> dict[str, Any]:
        row = {
            "id": f"clim_{uuid.uuid4().hex[:12]}",
            "session_id": self.session_id,
            "role": role,
            "content": content,
            "external_message_id": "",
            "created_at": self._now(),
        }
        self._db.insert("cli_agent_messages", row)
        return row

    def _insert_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": f"clie_{uuid.uuid4().hex[:12]}",
            "session_id": self.session_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": self._now(),
        }
        self._db.insert("cli_agent_events", row)
        return row

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()
