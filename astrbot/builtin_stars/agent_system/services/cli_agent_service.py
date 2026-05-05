"""CLI Agent facade service.

This service owns configuration data for local/remote CLI coding agents. The
runtime adapter that starts Claude/Codex processes is intentionally separate so
the management API can be tested without spawning tools.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class CliAgentService:
    _permission_waiters: dict[str, asyncio.Future] = {}

    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Clients

    def list_clients(self, include_disabled: bool = False) -> list[dict[str, Any]]:
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
        if agent_kind not in {"claude", "codex", "qwen", "goose", "opencode", "custom"}:
            raise ValueError("agent_kind 不合法")
        if location_kind not in {"local", "remote"}:
            raise ValueError("location_kind 必须是 local 或 remote")
        if transport_kind not in {"acp_stdio", "native_stdio", "remote_ws", "remote_http_sse"}:
            raise ValueError("transport_kind 不合法")

        command, args = self._with_default_acp_command(
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
            "auth_type": str(data.get("auth_type") or "none"),
            "auth_secret": str(data.get("auth_secret") or ""),
            "env": data.get("env") or {},
            "default_workspace_id": data.get("default_workspace_id"),
            "permission_policy": str(data.get("permission_policy") or "ask"),
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
            "auth_type",
            "auth_secret",
            "env",
            "default_workspace_id",
            "permission_policy",
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
            return self._update_check_status(client_id, "unknown", "远程检测将在 relay 阶段启用", False)

        command = client.get("executable_path") or client.get("command")
        if not command and client.get("transport_kind") == "acp_stdio":
            command, _ = self._with_default_acp_command(
                client.get("agent_kind", ""),
                client.get("transport_kind", ""),
                "",
                client.get("args") or [],
            )
        if not command:
            return self._update_check_status(client_id, "unavailable", "local command not configured", False)

        found = self._command_exists(command)
        if not found:
            return self._update_check_status(client_id, "unavailable", f"local command not found: {command}", False)
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

        normalized_path = str(Path(path).expanduser()) if location_kind == "local" else path
        now = self._now()
        row = {
            "id": data.get("id") or f"cliw_{uuid.uuid4().hex[:12]}",
            "name": name,
            "path": normalized_path,
            "location_kind": location_kind,
            "remote_client_id": data.get("remote_client_id") or data.get("default_client_id"),
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

    def update_workspace(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_workspace(workspace_id)
        allowed = {"name", "path", "location_kind", "remote_client_id", "rules", "env", "status"}
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
        return [dict(row) for row in rows]

    def list_events(self, session_id: str, after_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
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

    def respond_permission(self, permission_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self.db.select_one(
            "cli_agent_permissions",
            where="id = ?",
            where_params=(permission_id,),
        )
        if not row:
            raise ValueError(f"权限请求 '{permission_id}' 不存在")
        decision = data.get("decision") or data.get("action") or "reject"
        payload = {
            "decision": decision,
            "field_values": data.get("field_values") or {},
            "responded_at": self._now(),
        }
        self.db.update(
            "cli_agent_permissions",
            {
                "status": "resolved",
                "decision": decision,
                "responded_at": payload["responded_at"],
            },
            where="id = ?",
            where_params=(permission_id,),
        )
        waiter = self._permission_waiters.pop(permission_id, None)
        if waiter and not waiter.done():
            waiter.set_result(payload)
        self._insert_event(row["session_id"], "permission_resolved", payload)
        return payload

    async def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        content = str(content or "").strip()
        if not content:
            raise ValueError("消息内容不能为空")

        session = self.get_session(session_id)
        client = self.get_client(session["client_id"])
        client["_session_id"] = session_id
        workspace = self.get_workspace(session["workspace_id"])

        user_message = self._insert_message(session_id, "user", content)
        self._insert_event(session_id, "message", {"role": "user", "content": content})
        self.update_session(session_id, {"status": "running"})
        try:
            output = await self._run_client_once(client, workspace, content)
            assistant_message = self._insert_message(session_id, "assistant", output)
            self._insert_event(session_id, "message", {"role": "assistant", "content": output})
            token_stats = self._estimate_tokens(content, output)
            self.update_session(
                session_id,
                {
                    "status": "idle",
                    "total_tokens": int(session.get("total_tokens") or 0) + token_stats["total_tokens"],
                    "input_tokens": int(session.get("input_tokens") or 0) + token_stats["input_tokens"],
                    "output_tokens": int(session.get("output_tokens") or 0) + token_stats["output_tokens"],
                    "last_error": "",
                },
            )
            return {
                "user_message": user_message,
                "assistant_message": assistant_message,
                "token_stats": token_stats,
            }
        except Exception as exc:
            self.update_session(session_id, {"status": "error", "last_error": str(exc)})
            self._insert_event(session_id, "error", {"message": str(exc)})
            raise

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        self.get_session(session_id)
        self.update_session(session_id, {"status": "idle", "last_error": ""})
        self._insert_event(session_id, "lifecycle", {"status": "idle", "reason": "stopped"})
        return {"session_id": session_id, "stopped": True}

    def _insert_message(self, session_id: str, role: str, content: str) -> dict[str, Any]:
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

    def _insert_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": f"clie_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": self._now(),
        }
        self.db.insert("cli_agent_events", row)
        return row

    async def _run_client_once(
        self,
        client: dict[str, Any],
        workspace: dict[str, Any],
        prompt: str,
    ) -> str:
        if client["location_kind"] == "remote":
            raise ValueError("远程 CLI Agent relay 尚未启用")
        if client["transport_kind"] not in {"native_stdio", "acp_stdio"}:
            raise ValueError(f"当前传输类型暂不支持本地直连: {client['transport_kind']}")

        executable = client.get("executable_path") or client.get("command")
        if not executable and client.get("transport_kind") == "acp_stdio":
            executable, args = self._with_default_acp_command(
                client.get("agent_kind", ""),
                client.get("transport_kind", ""),
                "",
                client.get("args") or [],
            )
        if not executable:
            raise ValueError("客户端未配置命令或可执行文件路径")

        args = args if "args" in locals() else client.get("args") or []
        if not isinstance(args, list):
            args = []
        cwd = workspace.get("path") or workspace.get("root_path") or None
        if cwd and not Path(cwd).exists():
            raise ValueError(f"工作区路径不存在: {cwd}")

        env = os.environ.copy()
        configured_env = client.get("env") or {}
        if isinstance(configured_env, dict):
            env.update({str(key): str(value) for key, value in configured_env.items()})

        if client["transport_kind"] == "acp_stdio":
            return await self._run_acp_once(client, workspace, prompt, executable, args, cwd, env)

        process = await asyncio.create_subprocess_exec(
            executable,
            *[str(arg) for arg in args],
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")),
                timeout=180,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ValueError("CLI Agent 执行超时")

        out_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = stderr.decode("utf-8", errors="replace").strip()
        if process.returncode != 0:
            raise ValueError(err_text or f"CLI Agent 退出码: {process.returncode}")
        return out_text or err_text or "(无输出)"

    async def _run_acp_once(
        self,
        client: dict[str, Any],
        workspace: dict[str, Any],
        prompt: str,
        executable: str,
        args: list[Any],
        cwd: str | None,
        env: dict[str, str],
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            executable,
            *[str(arg) for arg in args],
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        next_id = 0
        pending: dict[int, asyncio.Future] = {}
        output_parts: list[str] = []
        external_session_key = ""

        async def send(method: str, params: dict[str, Any] | None = None) -> Any:
            nonlocal next_id
            next_id += 1
            msg_id = next_id
            fut = asyncio.get_running_loop().create_future()
            pending[msg_id] = fut
            assert process.stdin is not None
            payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
            process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            await process.stdin.drain()
            return await asyncio.wait_for(fut, timeout=60)

        async def respond(msg_id: Any, result: Any) -> None:
            if msg_id is None or process.stdin is None:
                return
            process.stdin.write(
                (json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}, ensure_ascii=False) + "\n").encode("utf-8")
            )
            await process.stdin.drain()

        async def reader() -> None:
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                try:
                    payload = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if "id" in payload and ("result" in payload or "error" in payload):
                    fut = pending.pop(int(payload["id"]), None)
                    if fut and not fut.done():
                        if payload.get("error"):
                            fut.set_exception(ValueError(json.dumps(payload["error"], ensure_ascii=False)))
                        else:
                            fut.set_result(payload.get("result"))
                    continue
                method = payload.get("method", "")
                params = payload.get("params") or {}
                self._insert_event(client["_session_id"], self._event_type_from_acp(method, params), params)
                text = self._extract_text_from_payload(params)
                if text:
                    output_parts.append(text)
                if "permission" in method.lower():
                    result = await self._handle_acp_permission(client, payload.get("id"), params)
                    await respond(payload.get("id"), result)
                elif method in {"readTextFile", "fs/read_text_file"}:
                    await respond(payload.get("id"), {"content": ""})
                elif method in {"writeTextFile", "fs/write_text_file"}:
                    await respond(payload.get("id"), {"ok": False, "message": "NiceBot 当前未授权 CLI Agent 直接写文件"})
                elif payload.get("id") is not None:
                    await respond(payload.get("id"), {})

        client = dict(client)
        reader_task = asyncio.create_task(reader())
        try:
            init_result = await send("initialize", {
                "clientInfo": {"name": "NiceBot", "version": "4.23.6"},
                "protocolVersion": 1,
                "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}},
            })
            self._insert_event(client["_session_id"], "lifecycle", {"status": "initialized", "result": init_result})

            session_params = {
                "cwd": cwd or workspace.get("path") or "",
                "mcpServers": [],
                "additionalDirectories": [],
            }
            try:
                session_result = await send("session/new", session_params)
            except Exception:
                session_result = await send("newSession", session_params)
            external_session_key = (
                session_result.get("sessionId")
                or session_result.get("session_id")
                or session_result.get("id")
                or ""
            ) if isinstance(session_result, dict) else ""
            self._insert_event(client["_session_id"], "lifecycle", {"status": "session_started", "external_session_key": external_session_key})

            prompt_payload = {
                "sessionId": external_session_key,
                "prompt": {"type": "text", "text": prompt},
            }
            try:
                prompt_result = await send("session/prompt", prompt_payload)
            except Exception:
                prompt_result = await send("prompt", prompt_payload)
            direct_text = self._extract_text_from_payload(prompt_result)
            if direct_text:
                output_parts.append(direct_text)
            self._insert_event(client["_session_id"], "lifecycle", {"status": "turn_done", "result": prompt_result})
        finally:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            reader_task.cancel()

        stderr = b""
        if process.stderr:
            try:
                stderr = await process.stderr.read()
            except Exception:
                stderr = b""
        err_text = stderr.decode("utf-8", errors="replace").strip()
        if process.returncode not in (0, None) and not output_parts:
            raise ValueError(err_text or f"ACP Agent 退出码: {process.returncode}")
        return "\n".join(part for part in output_parts if part).strip() or err_text or "(ACP 会话无文本输出)"

    async def _handle_acp_permission(self, client: dict[str, Any], request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        permission_id = f"clip_{uuid.uuid4().hex[:12]}"
        now = self._now()
        session_id = client.get("_session_id", "")
        self.db.insert(
            "cli_agent_permissions",
            {
                "id": permission_id,
                "session_id": session_id,
                "client_id": client["id"],
                "request_key": str(request_id or params.get("id") or permission_id),
                "title": params.get("title") or params.get("toolCall", {}).get("name") or "CLI Agent 权限请求",
                "body": params.get("body") or params.get("description") or json.dumps(params, ensure_ascii=False),
                "payload": params,
                "status": "pending",
                "decision": "",
                "created_at": now,
                "responded_at": None,
            },
        )
        self._insert_event(session_id, "permission", {"permission_id": permission_id, **params})
        policy = client.get("permission_policy") or "ask"
        if policy in {"allow", "auto_approve", "yolo"}:
            return {"outcome": "approved"}
        if policy in {"deny", "reject"}:
            return {"outcome": "denied"}
        fut = asyncio.get_running_loop().create_future()
        self._permission_waiters[permission_id] = fut
        try:
            decision = await asyncio.wait_for(fut, timeout=180)
            approved = decision.get("decision") in {"approve", "approved", "allow"}
            return {"outcome": "approved" if approved else "denied"}
        except asyncio.TimeoutError:
            self.respond_permission(permission_id, {"decision": "timeout"})
            return {"outcome": "denied"}

    @staticmethod
    def _event_type_from_acp(method: str, params: dict[str, Any]) -> str:
        lower = method.lower()
        if "permission" in lower:
            return "permission"
        if "tool" in lower:
            return "tool_call" if "result" not in lower else "tool_result"
        if "session" in lower or "update" in lower:
            return "session_update"
        return "acp_event"

    def _extract_text_from_payload(self, payload: Any) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            return "\n".join(filter(None, (self._extract_text_from_payload(item) for item in payload)))
        if not isinstance(payload, dict):
            return ""
        for key in ("text", "content", "message", "output", "finalText", "final_text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        parts = []
        for key in ("delta", "contentBlock", "message", "update", "result"):
            text = self._extract_text_from_payload(payload.get(key))
            if text:
                parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _estimate_tokens(input_text: str, output_text: str) -> dict[str, int]:
        input_tokens = max(1, len(input_text) // 4)
        output_tokens = max(1, len(output_text) // 4)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    @staticmethod
    def _with_default_acp_command(agent_kind: str, transport_kind: str, command: str, args: Any) -> tuple[str, list[Any]]:
        parsed_args = args if isinstance(args, list) else []
        if transport_kind != "acp_stdio" or command:
            return command, parsed_args
        if agent_kind == "claude":
            return "npx", ["-y", "@zed-industries/claude-code-acp"]
        if agent_kind == "codex":
            return "npx", ["-y", "@zed-industries/codex-acp"]
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

    @staticmethod
    def _command_exists(command: str) -> bool:
        command = command.strip()
        if not command:
            return False
        if any(sep in command for sep in ("/", "\\")):
            return Path(command).exists()
        return shutil.which(command) is not None

    def _client_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["args"] = self._parse_json(data.get("args"), [])
        data["env"] = self._parse_json(data.get("env"), {})
        data["enabled"] = bool(data.get("enabled"))
        return data

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
