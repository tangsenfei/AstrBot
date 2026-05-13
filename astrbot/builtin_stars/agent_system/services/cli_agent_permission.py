"""Three-level permission resolver for CLI agent requests."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PermissionRequest:
    kind: str
    title: str
    body: str = ""
    raw_input: dict[str, Any] = field(default_factory=dict)
    client_id: str = ""


class PermissionResolver:
    _waiters: dict[str, asyncio.Future] = {}

    def __init__(self, db, *, auto_approve: bool = False) -> None:
        self.db = db
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._auto_approve = auto_approve

    async def resolve(
        self,
        session_id: str,
        request: PermissionRequest,
        *,
        timeout_seconds: float | None = 120,
        on_created: Callable[[dict[str, Any]], None] | None = None,
        on_timeout: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        if self._auto_approve:
            return "approved"
        cache_key = self._build_cache_key(request)
        cached = self._cache.get(cache_key)
        if cached:
            self._cache.move_to_end(cache_key)
            return cached

        permission_id = self._create_db_request(session_id, request, cache_key)
        if on_created:
            on_created(
                {
                    "type": "permission",
                    "permission_id": permission_id,
                    "id": permission_id,
                    "title": request.title,
                    "body": request.body,
                    "payload": request.raw_input,
                }
            )
        future = asyncio.get_running_loop().create_future()
        self._waiters[permission_id] = future
        try:
            if timeout_seconds and timeout_seconds > 0:
                decision_payload = await asyncio.wait_for(
                    future, timeout=timeout_seconds
                )
            else:
                decision_payload = await future
        except asyncio.TimeoutError:
            payload = self._resolve_timeout(session_id, permission_id)
            if on_timeout:
                on_timeout(payload)
            return "denied"
        finally:
            self._waiters.pop(permission_id, None)
        decision = str(decision_payload.get("decision") or "")
        resolved = (
            "approved"
            if decision.startswith("allow") or decision in {"approve", "approved"}
            else "denied"
        )
        if decision == "allow_always":
            self._cache[cache_key] = resolved
            if len(self._cache) > 500:
                self._cache.popitem(last=False)
        return resolved

    @classmethod
    def respond_permission(
        cls, db, permission_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = db.select_one(
            "cli_agent_permissions",
            where="id = ?",
            where_params=(permission_id,),
        )
        if not row:
            raise ValueError(f"权限请求 '{permission_id}' 不存在")
        decision = str(data.get("decision") or data.get("action") or "deny")
        payload = {
            "decision": decision,
            "field_values": data.get("field_values") or {},
            "responded_at": cls._now(),
        }
        db.update(
            "cli_agent_permissions",
            {
                "status": "resolved",
                "decision": decision,
                "responded_at": payload["responded_at"],
            },
            where="id = ?",
            where_params=(permission_id,),
        )
        waiter = cls._waiters.pop(permission_id, None)
        if waiter and not waiter.done():
            waiter.set_result(payload)
        db.insert(
            "cli_agent_events",
            {
                "id": f"clie_{uuid.uuid4().hex[:12]}",
                "session_id": row["session_id"],
                "event_type": "permission_resolved",
                "payload": payload,
                "created_at": cls._now(),
            },
        )
        return payload

    def _resolve_timeout(self, session_id: str, permission_id: str) -> dict[str, Any]:
        payload = {
            "type": "permission_timeout",
            "permission_id": permission_id,
            "id": permission_id,
            "message": "权限请求超时，已自动拒绝",
            "decision": "timeout",
            "responded_at": self._now(),
        }
        self.db.update(
            "cli_agent_permissions",
            {
                "status": "resolved",
                "decision": "timeout",
                "responded_at": payload["responded_at"],
            },
            where="id = ?",
            where_params=(permission_id,),
        )
        self.db.insert(
            "cli_agent_events",
            {
                "id": f"clie_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "event_type": "permission_resolved",
                "payload": payload,
                "created_at": self._now(),
            },
        )
        return payload

    def _create_db_request(
        self, session_id: str, request: PermissionRequest, cache_key: str
    ) -> str:
        permission_id = f"clip_{uuid.uuid4().hex[:12]}"
        now = self._now()
        self.db.insert(
            "cli_agent_permissions",
            {
                "id": permission_id,
                "session_id": session_id,
                "client_id": request.client_id,
                "request_key": cache_key,
                "cache_key": cache_key,
                "title": request.title,
                "body": request.body,
                "payload": request.raw_input,
                "status": "pending",
                "decision": "",
                "created_at": now,
                "responded_at": None,
            },
        )
        self.db.insert(
            "cli_agent_events",
            {
                "id": f"clie_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "event_type": "permission",
                "payload": {
                    "permission_id": permission_id,
                    "cache_key": cache_key,
                    "kind": request.kind,
                    "title": request.title,
                    "body": request.body,
                    **request.raw_input,
                },
                "created_at": now,
            },
        )
        return permission_id

    @staticmethod
    def _build_cache_key(request: PermissionRequest) -> str:
        parts = [request.kind, request.title]
        raw = request.raw_input or {}
        for field_name in ("command", "path", "file_path"):
            if field_name in raw:
                parts.append(f"{field_name}={raw[field_name]}")
        return ":".join(parts)

    @staticmethod
    def from_acp(client_id: str, params: dict[str, Any]) -> PermissionRequest:
        raw = (
            params.get("rawInput")
            if isinstance(params.get("rawInput"), dict)
            else params
        )
        tool_call = (
            params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
        )
        title = params.get("title") or tool_call.get("name") or "CLI Agent 权限请求"
        body = (
            params.get("body")
            or params.get("description")
            or json.dumps(params, ensure_ascii=False)
        )
        return PermissionRequest(
            kind=str(params.get("kind") or params.get("type") or "permission"),
            title=str(title),
            body=str(body),
            raw_input=dict(raw or {}),
            client_id=client_id,
        )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()
