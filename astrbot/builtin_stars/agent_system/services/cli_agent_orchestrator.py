"""Singleton orchestrator for CLI agent runtime sessions."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .cli_agent_connector import CliAgentConnector, ConnectorConfig
from .cli_agent_session import CliAgentSession


class CliAgentOrchestrator:
    _instance: CliAgentOrchestrator | None = None

    def __init__(self, db) -> None:
        self.db = db
        self._sessions: dict[str, CliAgentSession] = {}
        self._lock = asyncio.Lock()
        self._max_concurrent = 10
        self._idle_timeout_minutes = 30

    @classmethod
    def get_instance(cls, db=None) -> CliAgentOrchestrator:
        if cls._instance is None:
            if db is None:
                from ..database import get_database

                db = get_database()
            cls._instance = cls(db)
        elif db is not None:
            cls._instance.db = db
        return cls._instance

    async def ensure_session(self, session_id: str) -> CliAgentSession:
        existing = self._sessions.get(session_id)
        if existing:
            return existing
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing:
                return existing
            if len(self._sessions) >= self._max_concurrent:
                raise RuntimeError(f"并发会话数已达上限 ({self._max_concurrent})")
            session_row, client, workspace = self._load_session_config(session_id)
            config = self._build_connector_config(session_row, client, workspace)
            connector = self._build_connector(client)
            runtime = CliAgentSession(
                session_id,
                connector,
                self.db,
                config,
                client_id=client["id"],
                permission_policy=str(client.get("permission_policy") or "ask"),
            )
            await runtime.start()
            self._sessions[session_id] = runtime
            return runtime

    async def stop_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.stop()
        else:
            self.db.update(
                "cli_agent_sessions",
                {"status": "idle", "last_error": "", "updated_at": self._now()},
                where="id = ?",
                where_params=(session_id,),
            )

    async def reconnect_session(self, session_id: str) -> CliAgentSession:
        session = await self.ensure_session(session_id)
        await session.reconnect()
        return session

    async def cleanup_idle(self) -> None:
        cutoff = datetime.now() - timedelta(minutes=self._idle_timeout_minutes)
        stale = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_activity < cutoff
        ]
        for session_id in stale:
            await self.stop_session(session_id)
        self.db.execute(
            "DELETE FROM cli_agent_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')"
        )
        self.db.commit()

    def get_session(self, session_id: str) -> CliAgentSession | None:
        return self._sessions.get(session_id)

    def _load_session_config(
        self, session_id: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        session = self.db.select_one(
            "cli_agent_sessions",
            where="id = ?",
            where_params=(session_id,),
        )
        if not session:
            raise ValueError(f"CLI Agent 会话 '{session_id}' 不存在")
        client = self.db.select_one(
            "cli_agent_clients",
            where="id = ?",
            where_params=(session["client_id"],),
        )
        if not client:
            raise ValueError(f"CLI Agent 客户端 '{session['client_id']}' 不存在")
        workspace = self.db.select_one(
            "cli_agent_workspaces",
            where="id = ?",
            where_params=(session["workspace_id"],),
        )
        if not workspace:
            raise ValueError(f"CLI Agent 工作区 '{session['workspace_id']}' 不存在")
        return dict(session), self._parse_row(client), self._parse_row(workspace)

    def _build_connector(self, client: dict[str, Any]):
        return CliAgentConnector(self.db, client_id=str(client.get("id") or ""))

    def _build_connector_config(
        self,
        session: dict[str, Any],
        client: dict[str, Any],
        workspace: dict[str, Any],
    ) -> ConnectorConfig:
        command = client.get("executable_path") or client.get("command") or ""
        args = client.get("args") if isinstance(client.get("args"), list) else []
        if client.get("transport_kind") == "acp_stdio" and not command:
            command, args = self._default_acp_command(client.get("agent_kind", ""))
        cwd = workspace.get("path") or None
        if cwd and client.get("location_kind") == "local" and not Path(cwd).exists():
            raise ValueError(f"工作区路径不存在: {cwd}")
        retry_policy = client.get("retry_policy")
        idle_timeout = int(
            client.get("idle_timeout_minutes") or self._idle_timeout_minutes
        )
        self._idle_timeout_minutes = idle_timeout
        return ConnectorConfig(
            executable=str(command),
            args=[str(arg) for arg in args],
            cwd=str(cwd) if cwd else None,
            env=client.get("env") if isinstance(client.get("env"), dict) else {},
            agent_kind=str(client.get("agent_kind") or "custom"),
            external_session_key=str(session.get("external_session_key") or ""),
            location_kind=str(client.get("location_kind") or "local"),
            transport_kind=str(client.get("transport_kind") or "acp_stdio"),
            relay_url=str(client.get("relay_url") or client.get("remote_url") or ""),
            auth_secret=str(client.get("auth_secret") or ""),
            prompt_timeout=float((retry_policy or {}).get("prompt_timeout", 0))
            if isinstance(retry_policy, dict)
            else 0,
            session_metadata=self._session_metadata(client),
        )

    @staticmethod
    def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        for key, fallback in {
            "args": [],
            "env": {},
            "retry_policy": {"max_retries": 3, "backoff_ms": 1000},
        }.items():
            value = data.get(key)
            if isinstance(value, str):
                try:
                    data[key] = json.loads(value) if value else fallback
                except json.JSONDecodeError:
                    data[key] = fallback
        return data

    @staticmethod
    def _default_acp_command(agent_kind: str) -> tuple[str, list[str]]:
        if agent_kind == "claude":
            return "npx", ["-y", "@agentclientprotocol/claude-agent-acp"]
        if agent_kind == "codex":
            return "npx", ["-y", "@zed-industries/codex-acp"]
        return "", []

    @staticmethod
    def _session_metadata(client: dict[str, Any]) -> dict[str, Any]:
        if client.get("agent_kind") != "claude":
            return {}
        try:
            from .claudecode_skill_adapter import ClaudeCodeSkillAdapter

            skills = ClaudeCodeSkillAdapter.discover_skills()
            return {
                "nicebot": {
                    "skills": [
                        {
                            "id": skill.id,
                            "name": skill.name,
                            "description": skill.description,
                        }
                        for skill in skills
                    ]
                }
            }
        except Exception:
            return {}

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()


def get_orchestrator(db=None) -> CliAgentOrchestrator:
    return CliAgentOrchestrator.get_instance(db)
