"""CLI Agent facade service.

This service owns configuration data for local/remote CLI coding agents. The
runtime adapter that starts Claude/Codex processes is intentionally separate so
the management API can be tested without spawning tools.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .acp_protocol import merge_tool_call_update, normalize_acp_tool_call
from .cli_agent_detector import (
    BUILTIN_AGENTS,
    default_agent_command,
    resolve_command_path,
)

VALID_AGENT_KINDS = {*BUILTIN_AGENTS.keys(), "custom"}
VALID_TRANSPORT_KINDS = {"acp_stdio", "remote_ws"}


class CliAgentService:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Clients

    def list_clients(self, include_disabled: bool = False) -> list[dict[str, Any]]:
        self._disable_removed_transports()
        where = "1=1" if include_disabled else "enabled = 1"
        rows = self.db.select_all(
            "cli_agent_clients",
            where=where,
            order_by="updated_at DESC",
        )
        return [self._client_dict(row) for row in rows]

    def create_client(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        agent_kind = str(data.get("agent_kind") or "").strip()
        location_kind = str(data.get("location_kind") or "local").strip()
        transport_kind = str(data.get("transport_kind") or "").strip()
        if not name:
            raise ValueError("CLI Agent 名称不能为空")
        if agent_kind not in VALID_AGENT_KINDS:
            raise ValueError("agent_kind 不合法")
        if location_kind not in {"local", "remote"}:
            raise ValueError("location_kind 必须是 local 或 remote")
        if not transport_kind:
            transport_kind = "remote_ws" if location_kind == "remote" else "acp_stdio"
        if transport_kind not in VALID_TRANSPORT_KINDS:
            raise ValueError("transport_kind 不合法")

        command, args = self._with_default_agent_command(
            agent_kind,
            transport_kind,
            str(data.get("command") or ""),
            data.get("args") or [],
        )
        now = self._now()
        row = {
            "id": data.get("id") or f"cli_{uuid.uuid4().hex[:12]}",
            "name": name,
            "agent_kind": agent_kind,
            "location_kind": location_kind,
            "transport_kind": transport_kind,
            "command": command,
            "args": args,
            "executable_path": str(data.get("executable_path") or ""),
            "remote_url": str(data.get("remote_url") or ""),
            "relay_url": str(data.get("relay_url") or data.get("remote_url") or ""),
            "auth_type": str(data.get("auth_type") or "none"),
            "auth_secret": str(data.get("auth_secret") or ""),
            "env": data.get("env") or {},
            "default_workspace_id": data.get("default_workspace_id"),
            "permission_policy": str(data.get("permission_policy") or "ask"),
            "retry_policy": data.get("retry_policy")
            or {"max_retries": 3, "backoff_ms": 1000},
            "idle_timeout_minutes": int(data.get("idle_timeout_minutes") or 30),
            "enabled": bool(data.get("enabled", True)),
            "status": str(data.get("status") or "unknown"),
            "status_message": str(data.get("status_message") or ""),
            "last_checked_at": data.get("last_checked_at"),
            "created_at": now,
            "updated_at": now,
        }
        self.db.insert("cli_agent_clients", row)
        return self.get_client(row["id"])

    def get_client(self, client_id: str) -> dict[str, Any]:
        row = self.db.select_one(
            "cli_agent_clients",
            where="id = ?",
            where_params=(client_id,),
        )
        if not row:
            raise ValueError(f"CLI Agent '{client_id}' 不存在")
        return self._client_dict(row)

    def update_client(self, client_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_client(client_id)
        allowed = {
            "name",
            "agent_kind",
            "location_kind",
            "transport_kind",
            "command",
            "args",
            "executable_path",
            "remote_url",
            "relay_url",
            "auth_type",
            "auth_secret",
            "env",
            "default_workspace_id",
            "permission_policy",
            "retry_policy",
            "idle_timeout_minutes",
            "enabled",
            "status",
            "status_message",
            "last_checked_at",
        }
        update = {key: data[key] for key in allowed if key in data}
        update["updated_at"] = self._now()
        self.db.update(
            "cli_agent_clients",
            update,
            where="id = ?",
            where_params=(client_id,),
        )
        return self.get_client(client_id)

    def delete_client(self, client_id: str) -> bool:
        row = self.db.select_one(
            "cli_agent_clients",
            where="id = ?",
            where_params=(client_id,),
        )
        if not row:
            return False
        self.db.update(
            "cli_agent_clients",
            {"enabled": 0, "updated_at": self._now()},
            where="id = ?",
            where_params=(client_id,),
        )
        return True

    def check_client(self, client_id: str) -> dict[str, Any]:
        client = self.get_client(client_id)
        if client["location_kind"] == "remote":
            return self._update_check_status(
                client_id, "unknown", "远程检测将在 relay 阶段启用", False
            )

        command = client.get("executable_path") or client.get("command")
        if not command and client.get("transport_kind") == "acp_stdio":
            command, _ = self._with_default_agent_command(
                client.get("agent_kind", ""),
                client.get("transport_kind", ""),
                "",
                client.get("args") or [],
            )
        if not command:
            return self._update_check_status(
                client_id, "unavailable", "local command not configured", False
            )

        found = self._command_exists(command)
        if not found:
            return self._update_check_status(
                client_id, "unavailable", f"local command not found: {command}", False
            )
        return self._update_check_status(
            client_id,
            "available",
            f"local command found: {command}; runtime protocol not verified",
            True,
        )

    # ------------------------------------------------------------------
    # Workspaces

    def list_workspaces(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        where = "1=1" if include_inactive else "status = 'active'"
        rows = self.db.select_all(
            "cli_agent_workspaces",
            where=where,
            order_by="updated_at DESC",
        )
        return [self._workspace_dict(row) for row in rows]

    def create_workspace(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        path = str(data.get("path") or data.get("root_path") or "").strip()
        location_kind = str(data.get("location_kind") or "local").strip()
        if not name:
            raise ValueError("工作区名称不能为空")
        if not path:
            raise ValueError("工作区路径不能为空")
        if location_kind not in {"local", "remote"}:
            raise ValueError("location_kind 必须是 local 或 remote")

        normalized_path = (
            str(Path(path).expanduser()) if location_kind == "local" else path
        )
        now = self._now()
        row = {
            "id": data.get("id") or f"cliw_{uuid.uuid4().hex[:12]}",
            "name": name,
            "path": normalized_path,
            "location_kind": location_kind,
            "remote_client_id": data.get("remote_client_id")
            or data.get("default_client_id"),
            "rules": str(data.get("rules") or data.get("description") or ""),
            "env": data.get("env") or {},
            "status": str(data.get("status") or "active"),
            "created_at": now,
            "updated_at": now,
        }
        self.db.insert("cli_agent_workspaces", row)
        return self.get_workspace(row["id"])

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        row = self.db.select_one(
            "cli_agent_workspaces",
            where="id = ?",
            where_params=(workspace_id,),
        )
        if not row:
            raise ValueError(f"工作区 '{workspace_id}' 不存在")
        return self._workspace_dict(row)

    def update_workspace(
        self, workspace_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self.get_workspace(workspace_id)
        allowed = {
            "name",
            "path",
            "location_kind",
            "remote_client_id",
            "rules",
            "env",
            "status",
        }
        update = {key: data[key] for key in allowed if key in data}
        if "root_path" in data:
            update["path"] = data["root_path"]
        if "default_client_id" in data:
            update["remote_client_id"] = data["default_client_id"]
        if "description" in data:
            update["rules"] = data["description"]
        update["updated_at"] = self._now()
        self.db.update(
            "cli_agent_workspaces",
            update,
            where="id = ?",
            where_params=(workspace_id,),
        )
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        row = self.db.select_one(
            "cli_agent_workspaces",
            where="id = ?",
            where_params=(workspace_id,),
        )
        if not row:
            return False
        self.db.update(
            "cli_agent_workspaces",
            {"status": "archived", "updated_at": self._now()},
            where="id = ?",
            where_params=(workspace_id,),
        )
        return True

    # ------------------------------------------------------------------
    # Sessions

    def list_sessions(
        self,
        *,
        client_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where = ["1=1"]
        params: list[Any] = []
        if client_id:
            where.append("client_id = ?")
            params.append(client_id)
        if workspace_id:
            where.append("workspace_id = ?")
            params.append(workspace_id)
        rows = self.db.select_all(
            "cli_agent_sessions",
            where=" AND ".join(where),
            where_params=tuple(params),
            order_by="updated_at DESC",
        )
        return [self._session_dict(row) for row in rows]

    def create_session(self, data: dict[str, Any]) -> dict[str, Any]:
        client_id = str(data.get("client_id") or "").strip()
        workspace_id = str(data.get("workspace_id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not client_id:
            raise ValueError("client_id 不能为空")
        if not workspace_id:
            raise ValueError("workspace_id 不能为空")
        if not title:
            raise ValueError("会话标题不能为空")
        self.get_client(client_id)
        self.get_workspace(workspace_id)

        now = self._now()
        row = {
            "id": data.get("id") or f"clis_{uuid.uuid4().hex[:12]}",
            "client_id": client_id,
            "workspace_id": workspace_id,
            "title": title,
            "external_session_key": str(data.get("external_session_key") or ""),
            "status": str(data.get("status") or "idle"),
            "total_tokens": int(data.get("total_tokens") or 0),
            "input_tokens": int(data.get("input_tokens") or 0),
            "output_tokens": int(data.get("output_tokens") or 0),
            "last_error": str(data.get("last_error") or ""),
            "last_heartbeat": str(data.get("last_heartbeat") or ""),
            "created_at": now,
            "updated_at": now,
        }
        self.db.insert("cli_agent_sessions", row)
        return self.get_session(row["id"])

    def get_session(self, session_id: str) -> dict[str, Any]:
        row = self.db.select_one(
            "cli_agent_sessions",
            where="id = ?",
            where_params=(session_id,),
        )
        if not row:
            raise ValueError(f"CLI Agent 会话 '{session_id}' 不存在")
        return self._session_dict(row)

    def update_session(self, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_session(session_id)
        allowed = {
            "title",
            "external_session_key",
            "status",
            "total_tokens",
            "input_tokens",
            "output_tokens",
            "last_error",
            "last_heartbeat",
        }
        update = {key: data[key] for key in allowed if key in data}
        update["updated_at"] = self._now()
        self.db.update(
            "cli_agent_sessions",
            update,
            where="id = ?",
            where_params=(session_id,),
        )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        row = self.db.select_one(
            "cli_agent_sessions",
            where="id = ?",
            where_params=(session_id,),
        )
        if not row:
            return False
        self.db.update(
            "cli_agent_sessions",
            {"status": "archived", "updated_at": self._now()},
            where="id = ?",
            where_params=(session_id,),
        )
        return True

    # ------------------------------------------------------------------
    # Messages and local runtime

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        self.get_session(session_id)
        rows = self.db.select_all(
            "cli_agent_messages",
            where="session_id = ?",
            where_params=(session_id,),
            order_by="created_at ASC",
        )
        messages = [dict(row) for row in rows]
        messages.extend(self._tool_messages_from_events(session_id))
        return sorted(
            messages,
            key=lambda item: (
                str(item.get("created_at") or ""),
                0 if item.get("role") == "user" else 1 if item.get("role") == "tool" else 2,
            ),
        )

    def list_events(
        self, session_id: str, after_seq: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        self.get_session(session_id)
        rows = self.db.execute(
            """
            SELECT rowid AS seq, *
            FROM cli_agent_events
            WHERE session_id = ? AND rowid > ?
            ORDER BY rowid ASC
            LIMIT ?
            """,
            (session_id, int(after_seq or 0), max(1, min(2000, int(limit or 500)))),
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._parse_json(item.get("payload"), {})
            events.append(item)
        return events

    def list_permissions(self, session_id: str | None = None) -> list[dict[str, Any]]:
        where = "status = 'pending'"
        params: tuple[Any, ...] = ()
        if session_id:
            where += " AND session_id = ?"
            params = (session_id,)
        rows = self.db.select_all(
            "cli_agent_permissions",
            where=where,
            where_params=params,
            order_by="created_at ASC",
        )
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._parse_json(item.get("payload"), {})
            result.append(item)
        return result

    def respond_permission(
        self, permission_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        from .cli_agent_permission import PermissionResolver

        return PermissionResolver.respond_permission(self.db, permission_id, data)

    async def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        from .cli_agent_orchestrator import get_orchestrator

        runtime = await get_orchestrator(self.db).ensure_session(session_id)
        await runtime.send_message(content)
        return {"status": "accepted", "session_id": session_id}

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        self.get_session(session_id)
        from .cli_agent_orchestrator import get_orchestrator

        await get_orchestrator(self.db).stop_session(session_id)
        self._insert_event(
            session_id, "lifecycle", {"status": "idle", "reason": "stopped"}
        )
        return {"session_id": session_id, "stopped": True}

    def check_all_clients(self) -> list[dict[str, Any]]:
        clients = self.list_clients(include_disabled=False)
        results = []
        for client in clients:
            if client.get("location_kind") == "remote":
                continue
            results.append(self.check_client(client["id"]))
        return results

    def _insert_message(
        self, session_id: str, role: str, content: str
    ) -> dict[str, Any]:
        now = self._now()
        row = {
            "id": f"clim_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "role": role,
            "content": content,
            "external_message_id": "",
            "created_at": now,
        }
        self.db.insert("cli_agent_messages", row)
        return row

    def _insert_event(
        self, session_id: str, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "id": f"clie_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": self._now(),
        }
        self.db.insert("cli_agent_events", row)
        return row

    @staticmethod
    def _with_default_agent_command(
        agent_kind: str, transport_kind: str, command: str, args: Any
    ) -> tuple[str, list[Any]]:
        parsed_args = args if isinstance(args, list) else []
        if transport_kind != "acp_stdio" or command:
            return command, parsed_args
        default_command, default_args = default_agent_command(agent_kind)
        if default_command:
            return default_command, default_args
        return command, parsed_args

    # ------------------------------------------------------------------
    # Helpers

    def _update_check_status(
        self,
        client_id: str,
        status: str,
        message: str,
        available: bool,
    ) -> dict[str, Any]:
        checked_at = self._now()
        self.db.update(
            "cli_agent_clients",
            {
                "status": status,
                "status_message": message,
                "last_checked_at": checked_at,
                "updated_at": checked_at,
            },
            where="id = ?",
            where_params=(client_id,),
        )
        return {
            "client_id": client_id,
            "available": available,
            "status": status,
            "message": message,
            "checked_at": checked_at,
        }

    def _disable_removed_transports(self) -> None:
        placeholders = ",".join("?" for _ in VALID_TRANSPORT_KINDS)
        self.db.execute(
            f"""
            UPDATE cli_agent_clients
            SET
                enabled = 0,
                status = 'unavailable',
                status_message = '已停用旧传输，请重新创建 acp_stdio 或 remote_ws 客户端',
                updated_at = ?
            WHERE enabled = 1
              AND (transport_kind IS NULL OR transport_kind NOT IN ({placeholders}))
            """,
            (self._now(), *VALID_TRANSPORT_KINDS),
        )
        self.db.commit()

    @staticmethod
    def _command_exists(command: str) -> bool:
        command = command.strip()
        if not command:
            return False
        if any(sep in command for sep in ("/", "\\")):
            return Path(command).exists()
        return bool(resolve_command_path(command) or shutil.which(command))

    def _client_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["args"] = self._parse_json(data.get("args"), [])
        data["env"] = self._parse_json(data.get("env"), {})
        data["retry_policy"] = self._parse_json(
            data.get("retry_policy"), {"max_retries": 3, "backoff_ms": 1000}
        )
        data["enabled"] = bool(data.get("enabled"))
        cache = self._read_client_cache(str(data.get("id") or ""))
        if cache:
            data["cached_capabilities"] = cache.get("capabilities") or {}
            data["cached_models"] = cache.get("models") or {}
            data["cached_modes"] = cache.get("modes") or {}
            data["cached_agent_info"] = cache.get("agent_info") or {}
            data["cache_checked_at"] = cache.get("checked_at") or ""
        return data

    def _read_client_cache(self, client_id: str) -> dict[str, Any]:
        if not client_id:
            return {}
        row = self.db.select_one(
            "cli_agent_cache",
            where="key = ?",
            where_params=(f"init:{client_id}",),
        )
        if not row:
            return {}
        return self._parse_json(row.get("value"), {})

    def _tool_messages_from_events(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.db.select_all(
            "cli_agent_events",
            where="session_id = ? AND event_type = 'tool_call'",
            where_params=(session_id,),
            order_by="created_at ASC",
        )
        tool_calls: dict[str, dict[str, Any]] = {}
        created_at_by_id: dict[str, str] = {}
        for row in rows:
            payload = self._parse_json(row.get("payload"), {})
            created_at = str(row.get("created_at") or self._now())
            update = normalize_acp_tool_call(payload, created_at=created_at)
            tool_id = str(update.get("id") or "")
            if not tool_id:
                continue
            tool_calls[tool_id] = merge_tool_call_update(tool_calls.get(tool_id), update)
            created_at_by_id.setdefault(tool_id, created_at)

        result = []
        for tool_id, tool_call in tool_calls.items():
            result.append(
                {
                    "id": f"clit_{tool_id}",
                    "session_id": session_id,
                    "role": "tool",
                    "content": json.dumps(
                        {"type": "tool_call", "tool_calls": [tool_call]},
                        ensure_ascii=False,
                    ),
                    "external_message_id": tool_id,
                    "created_at": created_at_by_id.get(tool_id) or self._now(),
                }
            )
        return result

    def _workspace_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["env"] = self._parse_json(data.get("env"), {})
        data["root_path"] = data.get("path") or ""
        data["default_client_id"] = data.get("remote_client_id")
        data["description"] = data.get("rules") or ""
        return data

    @staticmethod
    def _session_dict(row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if not value:
            return fallback
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()
