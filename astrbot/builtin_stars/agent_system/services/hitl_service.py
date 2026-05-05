from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from astrbot.core.langgraph.interaction import InteractionCard, InteractionResponse
from astrbot.core.langgraph.interaction_manager import get_interaction_manager


class HITLService:
    """DB-backed HITL facade shared by Work and Chat task surfaces."""

    def __init__(self, db) -> None:
        self.db = db

    def upsert_from_card(
        self,
        card: InteractionCard | dict[str, Any],
        *,
        task_id: str = "",
        session_id: str = "",
        scope: str = "work",
        channel: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = card.to_dict() if hasattr(card, "to_dict") else dict(card)
        interaction_id = payload.get("interaction_id")
        if not interaction_id:
            return {}

        meta = dict(payload.get("meta") or {})
        meta.update(metadata or {})
        task_id = task_id or meta.get("task_id") or payload.get("task_id") or ""
        session_id = session_id or meta.get("session_id") or payload.get("session_id") or ""
        now = datetime.now().isoformat()
        row = {
            "id": interaction_id,
            "task_id": task_id or None,
            "session_id": session_id,
            "scope": scope,
            "interaction_type": payload.get("type", "clarification"),
            "title": payload.get("title", ""),
            "body": payload.get("body", ""),
            "fields": payload.get("fields", []),
            "actions": payload.get("actions", []),
            "status": "pending",
            "response": {},
            "channel": channel,
            "metadata": meta,
            "created_at": now,
            "resolved_at": None,
        }
        if self.db.select_one("hitl_requests", where="id = ?", where_params=(interaction_id,)):
            self.db.update(
                "hitl_requests",
                {k: v for k, v in row.items() if k not in {"id", "created_at"}},
                where="id = ?",
                where_params=(interaction_id,),
            )
        else:
            self.db.insert("hitl_requests", row)
        return self._row_to_card(row)

    def list_pending(self, task_id: str | None = None) -> list[dict[str, Any]]:
        where = "status = 'pending'"
        params: list[Any] = []
        if task_id:
            where += " AND task_id = ?"
            params.append(task_id)
        rows = self.db.select_all(
            "hitl_requests",
            where=where,
            where_params=tuple(params),
            order_by="created_at ASC",
        )
        return [self._row_to_card(row) for row in rows]

    def get(self, interaction_id: str) -> dict[str, Any] | None:
        row = self.db.select_one("hitl_requests", where="id = ?", where_params=(interaction_id,))
        return self._row_to_card(row) if row else None

    async def respond(self, interaction_id: str, action_key: str, field_values: dict[str, Any] | None = None) -> dict[str, Any]:
        row = self.db.select_one("hitl_requests", where="id = ?", where_params=(interaction_id,))
        if not row:
            # Compatibility path for older in-memory cards that have not been persisted yet.
            state = get_interaction_manager().get_pending_interaction(interaction_id)
            if not state:
                raise ValueError(f"交互 '{interaction_id}' 不存在或已处理")
            row = {
                "id": interaction_id,
                "task_id": state.card.meta.get("task_id") or state.thread_id,
                "session_id": state.card.meta.get("session_id", ""),
                "scope": "work",
                "interaction_type": state.card.type,
                "title": state.card.title,
                "body": state.card.body,
                "fields": state.card.to_dict().get("fields", []),
                "actions": state.card.to_dict().get("actions", []),
                "status": "pending",
                "response": {},
                "channel": state.channel,
                "metadata": state.card.meta,
                "created_at": datetime.now().isoformat(),
                "resolved_at": None,
            }
            self.upsert_from_card(state.card, task_id=row["task_id"], channel=state.channel, metadata=state["metadata"])

        if row.get("status") != "pending":
            raise ValueError(f"交互 '{interaction_id}' 已处理")

        field_values = field_values or {}
        response = InteractionResponse(
            interaction_id=interaction_id,
            action_key=action_key,
            field_values=field_values,
            responded_at=time.time(),
        )
        ok = get_interaction_manager().respond(interaction_id, response)
        if not ok:
            # DB remains the source of truth for restored/persisted cards, but a live graph
            # must still be woken by InteractionManager when available.
            state = get_interaction_manager().get_pending_interaction(interaction_id)
            if state and not state.resolved:
                raise ValueError(f"交互 '{interaction_id}' 未能唤醒执行器")

        now = datetime.now().isoformat()
        status = self._resolved_status(action_key)
        self.db.update(
            "hitl_requests",
            {
                "status": status,
                "response": {"action_key": action_key, "field_values": field_values},
                "resolved_at": now,
            },
            where="id = ?",
            where_params=(interaction_id,),
        )

        task_id = row.get("task_id") or ""
        if task_id:
            task_status = "cancelled" if action_key in {"reject", "cancel"} else "running"
            self.db.update(
                "agent_tasks",
                {
                    "status": task_status,
                    "interaction_id": "",
                    "pending_input": "",
                    "updated_at": now,
                    **({"completed_at": now} if task_status == "cancelled" else {}),
                },
                where="id = ?",
                where_params=(task_id,),
            )
            self.db.insert(
                "execution_logs",
                {
                    "id": f"log_hitl_{interaction_id[:16]}",
                    "task_id": task_id,
                    "sub_task_id": None,
                    "agent_id": None,
                    "level": "info",
                    "message": f"HITL 已处理：{action_key}",
                    "data": {
                        "event": "hitl_resolved",
                        "interaction_id": interaction_id,
                        "action_key": action_key,
                        "field_values": field_values,
                    },
                    "created_at": now,
                },
            )
        return {"interaction_id": interaction_id, "action_key": action_key, "status": status, "task_id": task_id}

    @staticmethod
    def _resolved_status(action_key: str) -> str:
        if action_key in {"reject"}:
            return "rejected"
        if action_key in {"cancel"}:
            return "cancelled"
        if action_key in {"modify", "retry"}:
            return "modified"
        return "approved"

    def _row_to_card(self, row: dict[str, Any]) -> dict[str, Any]:
        fields = self._parse_json(row.get("fields"), [])
        actions = self._parse_json(row.get("actions"), [])
        metadata = self._parse_json(row.get("metadata"), {})
        response = self._parse_json(row.get("response"), {})
        return {
            "interaction_id": row.get("id", ""),
            "type": row.get("interaction_type", "clarification"),
            "title": row.get("title", ""),
            "body": row.get("body", ""),
            "fields": fields if isinstance(fields, list) else [],
            "actions": actions if isinstance(actions, list) else [],
            "status": row.get("status", "pending"),
            "response": response if isinstance(response, dict) else {},
            "meta": metadata if isinstance(metadata, dict) else {},
            "task_id": row.get("task_id") or "",
            "session_id": row.get("session_id") or "",
            "channel": row.get("channel") or "",
            "created_at": row.get("created_at"),
            "resolved_at": row.get("resolved_at"),
        }

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback
