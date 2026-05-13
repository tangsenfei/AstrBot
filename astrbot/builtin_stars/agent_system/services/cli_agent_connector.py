"""CLI Agent transport layer: subprocess lifecycle plus NDJSON JSON-RPC."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import json
import os
import platform
import ssl
import subprocess
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import websockets

from astrbot.core import logger

from .acp_protocol import (
    ACP_JSONRPC_VERSION,
    ACP_PROTOCOL_VERSION,
    AcpCapability,
    AcpMethod,
    acp_capabilities,
)
from .cli_agent_detector import _common_windows_paths, resolve_command_path


class AgentDisconnectedError(RuntimeError):
    """Raised when the ACP process disconnects with pending work."""


class AgentSpawnError(RuntimeError):
    """Raised when the ACP process cannot be started."""


@dataclass
class ConnectorConfig:
    executable: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    agent_kind: str = "custom"
    handshake_timeout: float = 60.0
    prompt_timeout: float = 0.0
    external_session_key: str = ""
    location_kind: str = "local"
    transport_kind: str = "acp_stdio"
    relay_url: str = ""
    auth_secret: str = ""
    tls_verify: bool = True
    session_metadata: dict[str, Any] = field(default_factory=dict)


class LineTransport:
    async def send_line(self, raw: str) -> None:
        raise NotImplementedError

    async def recv_line(self) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class ProcessLineTransport(LineTransport):
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process

    async def send_line(self, raw: str) -> None:
        if not self.process.stdin:
            raise AgentDisconnectedError("ACP process stdin is not available")
        self.process.stdin.write(raw.encode("utf-8"))
        await self.process.stdin.drain()

    async def recv_line(self) -> str:
        if not self.process.stdout:
            raise AgentDisconnectedError("ACP process stdout is not available")
        line = await self.process.stdout.readline()
        return line.decode("utf-8", errors="replace") if line else ""

    async def close(self) -> None:
        if self.process.stdin and not self.process.stdin.is_closing():
            self.process.stdin.close()


class WsLineTransport(LineTransport):
    def __init__(self, ws) -> None:
        self.ws = ws

    @classmethod
    async def connect(cls, config: ConnectorConfig) -> WsLineTransport:
        if not config.relay_url:
            raise AgentSpawnError("远程 CLI Agent relay_url 不能为空")
        ssl_context = None
        if config.relay_url.startswith("wss://") and not config.tls_verify:
            ssl_context = ssl._create_unverified_context()
        ws = await websockets.connect(
            config.relay_url,
            ping_interval=30,
            ping_timeout=60,
            max_size=4 * 1024 * 1024,
            ssl=ssl_context,
        )
        nonce = str(int(time.time() * 1000))
        hello = {
            "type": "hello",
            "nonce": nonce,
            "agent_config": {
                "executable": config.executable,
                "args": config.args,
                "cwd": config.cwd,
                "env": config.env,
                "agent_kind": config.agent_kind,
                "handshake_timeout": config.handshake_timeout,
                "prompt_timeout": config.prompt_timeout,
                "session_metadata": config.session_metadata,
            },
        }
        if config.auth_secret:
            hello["signature"] = hmac.new(
                config.auth_secret.encode("utf-8"),
                nonce.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        await ws.send(json.dumps(hello, ensure_ascii=False, separators=(",", ":")))
        return cls(ws)

    async def send_line(self, raw: str) -> None:
        await self.ws.send(raw)

    async def recv_line(self) -> str:
        raw = await self.ws.recv()
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    async def close(self) -> None:
        await self.ws.close()


class CliAgentConnector:
    """Persistent ACP subprocess connector."""

    _cached_shell_env: dict[str, str] | None = None
    _cached_shell_env_loaded_at: float = 0.0
    _shell_env_ttl_seconds = 300.0

    def __init__(self, db=None, client_id: str = "") -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._transport: LineTransport | None = None
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._pending: dict[Any, asyncio.Future] = {}
        self._next_id = 0
        self._notification_handlers: list[Callable[[dict[str, Any]], Any]] = []
        self._disconnect_handler: Callable[[Exception], Any] | None = None
        self._stderr_head: deque[bytes] = deque()
        self._stderr_tail: deque[bytes] = deque()
        self._stderr_head_bytes = 0
        self._stderr_tail_bytes = 0
        self._initialize_result: dict[str, Any] | None = None
        self._session_result: dict[str, Any] = {}
        self._capabilities: dict[str, Any] = {}
        self._config: ConnectorConfig | None = None
        self._db = db
        self._client_id = client_id
        self.external_session_id = ""
        self.is_connected = False

    @property
    def capabilities(self) -> dict[str, Any]:
        return self._capabilities

    @property
    def session_result(self) -> dict[str, Any]:
        return self._session_result

    @property
    def process_id(self) -> int | None:
        return (
            self._process.pid
            if self._process and self._process.returncode is None
            else None
        )

    @property
    def stderr_tail(self) -> str:
        data = b"".join(self._stderr_head)
        if self._stderr_tail:
            data += b"\n...\n" + b"".join(self._stderr_tail)
        return data.decode("utf-8", errors="replace")[-8192:]

    def on_notification(self, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._notification_handlers.append(handler)

    def on_disconnect(self, handler: Callable[[Exception], Any]) -> None:
        self._disconnect_handler = handler

    async def start(self, config: ConnectorConfig) -> dict[str, Any]:
        self._config = config
        await self._spawn_with_retry()
        self._reader_task = asyncio.create_task(self._reader_loop())
        if self._process:
            self._stderr_task = asyncio.create_task(self._stderr_reader())
        try:
            self._initialize_result = await asyncio.wait_for(
                self.send_request(
                    AcpMethod.INITIALIZE,
                    {
                        "clientInfo": {"name": "NiceBot", "version": "4.23.6"},
                        "protocolVersion": ACP_PROTOCOL_VERSION,
                        "clientCapabilities": {
                            "fs": {"readTextFile": True, "writeTextFile": True}
                        },
                    },
                    timeout=config.handshake_timeout,
                ),
                timeout=config.handshake_timeout,
            )
            protocol_version = self._initialize_result.get("protocolVersion")
            if protocol_version not in (None, ACP_PROTOCOL_VERSION):
                logger.warning(
                    f"ACP protocol version mismatch: requested {ACP_PROTOCOL_VERSION}, got {protocol_version}"
                )
            self._capabilities = acp_capabilities(self._initialize_result)
            session_result = None
            if config.external_session_key:
                session_result = await self.load_session(config.external_session_key)
            if not session_result:
                session_result = await self._new_session()
            if isinstance(session_result, dict):
                session_result = self._with_cached_session_metadata(session_result)
                self._session_result = session_result
                self.external_session_id = (
                    session_result.get("sessionId")
                    or session_result.get("session_id")
                    or session_result.get("id")
                    or ""
                )
            self._cache_initialize_result(self._initialize_result, session_result)
            self.is_connected = True
            return self._initialize_result
        except Exception:
            await self.stop()
            raise

    async def send_prompt(self, text: str) -> Any:
        if not self.external_session_id:
            raise AgentDisconnectedError("ACP session is not initialized")
        prompt_payload = {
            "sessionId": self.external_session_id,
            "prompt": [{"type": "text", "text": text}],
        }
        timeout = self._config.prompt_timeout if self._config else 0
        try:
            return await self.send_request(
                AcpMethod.SESSION_PROMPT,
                prompt_payload,
                timeout=timeout,
            )
        except AgentDisconnectedError:
            raise
        except Exception:
            return await self.send_request(
                AcpMethod.SESSION_PROMPT_ALT,
                prompt_payload,
                timeout=timeout,
            )

    async def cancel_prompt(self) -> None:
        if not self.external_session_id:
            return
        await self.send_notification(
            AcpMethod.SESSION_CANCEL,
            {"sessionId": self.external_session_id},
        )

    async def set_model(self, model_id: str) -> Any:
        if not self.external_session_id:
            raise AgentDisconnectedError("ACP session is not initialized")
        return await self.send_request(
            AcpMethod.SET_MODEL,
            {"sessionId": self.external_session_id, "modelId": model_id},
        )

    async def set_mode(self, mode_id: str) -> Any:
        if not self.external_session_id:
            raise AgentDisconnectedError("ACP session is not initialized")
        return await self.send_request(
            AcpMethod.SET_MODE,
            {"sessionId": self.external_session_id, "modeId": mode_id},
        )

    async def load_session(self, external_session_id: str) -> dict[str, Any] | None:
        if not self._capabilities.get(AcpCapability.LOAD_SESSION):
            return None
        config = self._config
        try:
            return await self.send_request(
                AcpMethod.SESSION_LOAD,
                {
                    "sessionId": external_session_id,
                    "cwd": config.cwd if config else "",
                    "mcpServers": [],
                },
                timeout=config.handshake_timeout if config else 60,
            )
        except Exception as exc:
            logger.warning(
                f"ACP session/load failed, falling back to session/new: {exc}"
            )
            return None

    async def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 60.0,
    ) -> Any:
        if not self._transport:
            raise AgentDisconnectedError("ACP process is not running")
        self._next_id += 1
        req_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        try:
            await self._write_json(
                {
                    "jsonrpc": ACP_JSONRPC_VERSION,
                    "id": req_id,
                    "method": method,
                    "params": params or {},
                }
            )
            if timeout and timeout > 0:
                return await asyncio.wait_for(future, timeout=timeout)
            return await future
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise
        finally:
            self._pending.pop(req_id, None)

    async def send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        await self._write_json(
            {"jsonrpc": ACP_JSONRPC_VERSION, "method": method, "params": params or {}}
        )

    async def respond(self, req_id: Any, result: Any) -> None:
        if req_id is None:
            return
        await self._write_json(
            {"jsonrpc": ACP_JSONRPC_VERSION, "id": req_id, "result": result}
        )

    async def stop(self) -> None:
        self.is_connected = False
        process = self._process
        transport = self._transport
        self._process = None
        self._transport = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(AgentDisconnectedError("ACP connector stopped"))
        self._pending.clear()
        if transport:
            try:
                await transport.close()
            except Exception:
                pass
        if process:
            if process.returncode is None:
                if platform.system() == "Windows":
                    try:
                        killer = await asyncio.create_subprocess_exec(
                            "taskkill",
                            "/F",
                            "/PID",
                            str(process.pid),
                            "/T",
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await asyncio.wait_for(killer.wait(), timeout=5)
                    except Exception:
                        process.kill()
                else:
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                pass
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
        self._reader_task = None
        self._stderr_task = None

    async def _new_session(self) -> Any:
        config = self._config
        params = {
            "cwd": config.cwd if config else "",
            "mcpServers": [],
            "additionalDirectories": [],
        }
        if config and config.session_metadata:
            params["_meta"] = config.session_metadata
        try:
            return await self.send_request(
                AcpMethod.SESSION_NEW,
                params,
                timeout=config.handshake_timeout if config else 60,
            )
        except Exception:
            return await self.send_request(
                AcpMethod.SESSION_NEW_ALT,
                params,
                timeout=config.handshake_timeout if config else 60,
            )

    async def _spawn_with_retry(self, max_retries: int = 3) -> None:
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                await self._spawn()
                return
            except Exception as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        raise AgentSpawnError(f"启动失败，已重试 {max_retries} 次: {last_error}")

    async def _spawn(self) -> None:
        config = self._config
        if not config:
            raise AgentSpawnError("客户端未配置连接参数")
        if config.transport_kind == "remote_ws":
            self._transport = await WsLineTransport.connect(config)
            self._process = None
            return
        executable = resolve_command_path(config.executable) or config.executable
        if not executable:
            raise AgentSpawnError("客户端未配置命令或可执行文件路径")
        self._process = await asyncio.create_subprocess_exec(
            executable,
            *[str(arg) for arg in config.args],
            cwd=config.cwd or None,
            env=self._prepare_env(config.env),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._transport = ProcessLineTransport(self._process)

    async def _write_json(self, payload: dict[str, Any]) -> None:
        if not self._transport:
            raise AgentDisconnectedError("ACP process is not running")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        await self._transport.send_line(raw)

    async def _reader_loop(self) -> None:
        assert self._transport
        try:
            while True:
                line = await self._transport.recv_line()
                if not line:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                await self._dispatch(payload)
            await self._handle_disconnect(AgentDisconnectedError("ACP process exited"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_disconnect(exc)

    async def _dispatch(self, payload: dict[str, Any]) -> None:
        if "id" in payload and ("result" in payload or "error" in payload):
            future = self._pending.pop(payload.get("id"), None)
            if future and not future.done():
                if payload.get("error"):
                    future.set_exception(
                        ValueError(json.dumps(payload["error"], ensure_ascii=False))
                    )
                else:
                    future.set_result(payload.get("result"))
            return
        result = None
        for handler in list(self._notification_handlers):
            value = handler(payload)
            if inspect.isawaitable(value):
                value = await value
            if value is not None:
                result = value
        if payload.get("id") is not None:
            if result is None:
                result = {}
            await self.respond(payload.get("id"), result)

    async def _stderr_reader(self) -> None:
        if not self._process or not self._process.stderr:
            return
        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                self._append_stderr(line)
        except asyncio.CancelledError:
            raise

    def _append_stderr(self, line: bytes) -> None:
        if self._stderr_head_bytes < 4096:
            self._stderr_head.append(line)
            self._stderr_head_bytes += len(line)
        self._stderr_tail.append(line)
        self._stderr_tail_bytes += len(line)
        while self._stderr_tail_bytes > 4096 and self._stderr_tail:
            removed = self._stderr_tail.popleft()
            self._stderr_tail_bytes -= len(removed)

    async def _handle_disconnect(self, error: Exception) -> None:
        if not self.is_connected and not self._pending:
            return
        self.is_connected = False
        for future in self._pending.values():
            if not future.done():
                future.set_exception(AgentDisconnectedError(str(error)))
        self._pending.clear()
        if self._disconnect_handler:
            value = self._disconnect_handler(error)
            if inspect.isawaitable(value):
                await value

    def _cache_initialize_result(
        self,
        init_result: dict[str, Any] | None,
        session_result: Any,
    ) -> None:
        if not self._db or not self._client_id or not isinstance(init_result, dict):
            return
        models = {}
        modes = {}
        config_options = {}
        if isinstance(session_result, dict):
            models = session_result.get("models") or {}
            modes = session_result.get("modes") or {}
            config_options = session_result.get("configOptions") or {}
        if not modes and isinstance(init_result.get("availableModes"), list):
            modes = {"availableModes": init_result.get("availableModes")}
        cache_result = {
            "protocol_version": init_result.get("protocolVersion"),
            "agent_info": init_result.get("agentInfo") or {},
            "capabilities": self._capabilities,
            "models": models,
            "modes": modes,
            "config_options": config_options,
            "server_info": init_result.get("serverInfo") or {},
            "checked_at": self._now(),
        }
        self._db.execute(
            """
            INSERT OR REPLACE INTO cli_agent_cache(
                key, value, client_id, created_at, expires_at
            )
            VALUES (?, ?, ?, datetime('now'), datetime('now', '+1 day'))
            """,
            (
                f"init:{self._client_id}",
                json.dumps(cache_result, ensure_ascii=False),
                self._client_id,
            ),
        )
        self._db.commit()

    def _with_cached_session_metadata(
        self, session_result: dict[str, Any]
    ) -> dict[str, Any]:
        cached = self._read_cached_initialize_result()
        if not cached:
            return session_result
        enriched = dict(session_result)
        enriched.setdefault("models", cached.get("models") or {})
        enriched.setdefault("modes", cached.get("modes") or {})
        enriched.setdefault("configOptions", cached.get("config_options") or {})
        return enriched

    def _read_cached_initialize_result(self) -> dict[str, Any]:
        if not self._db or not self._client_id:
            return {}
        row = self._db.select_one(
            "cli_agent_cache",
            where="key = ?",
            where_params=(f"init:{self._client_id}",),
        )
        if not row:
            return {}
        try:
            value = row.get("value")
            return json.loads(value) if value else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _prepare_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
        shell_env = CliAgentConnector._cached_shell_environment()
        process_env = dict(os.environ)
        explicit_env = {str(key): str(value) for key, value in (base_env or {}).items()}
        env = dict(process_env)
        env.update(shell_env)
        if base_env:
            env.update(explicit_env)
        for key in ("FORCE_COLOR", "NO_COLOR", "TERM", "COLORTERM"):
            env.pop(key, None)
        if platform.system() == "Windows":
            path_values = []
            for source in (process_env, shell_env, explicit_env):
                for key, value in source.items():
                    if str(key).upper() == "PATH" and value:
                        path_values.append(str(value))
            path_values.extend(str(path) for path in _common_windows_paths())
            merged_path = CliAgentConnector._merge_path_values(path_values)
            for key in list(env.keys()):
                if str(key).upper() == "PATH":
                    env.pop(key, None)
            if merged_path:
                env["PATH"] = merged_path
            env["PYTHONIOENCODING"] = "utf-8"
            env["CHCP"] = "65001"
        return env

    @classmethod
    def _cached_shell_environment(cls) -> dict[str, str]:
        now = time.monotonic()
        cached_env = getattr(cls, "_cached_shell_env", None)
        loaded_at = float(getattr(cls, "_cached_shell_env_loaded_at", 0.0) or 0.0)
        if (
            cached_env is None
            or now - loaded_at > cls._shell_env_ttl_seconds
        ):
            cls._cached_shell_env = cls._load_shell_env()
            cls._cached_shell_env_loaded_at = now
        return dict(cls._cached_shell_env or {})

    @staticmethod
    def _load_shell_env() -> dict[str, str]:
        if platform.system() == "Windows":
            return CliAgentConnector._load_windows_env()
        shell = os.environ.get("SHELL") or "/bin/bash"
        try:
            result = subprocess.run(
                [shell, "-ilc", "env"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return {}
        if result.returncode != 0:
            return {}
        return CliAgentConnector._parse_env_lines(result.stdout)

    @staticmethod
    def _load_windows_env() -> dict[str, str]:
        env: dict[str, str] = {}
        try:
            import winreg

            registry_paths = [
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                ),
                (winreg.HKEY_CURRENT_USER, "Environment"),
            ]
            for hive, path in registry_paths:
                try:
                    with winreg.OpenKey(hive, path) as key:
                        index = 0
                        while True:
                            try:
                                name, value, _value_type = winreg.EnumValue(key, index)
                            except OSError:
                                break
                            env[str(name)] = os.path.expandvars(str(value))
                            index += 1
                except OSError:
                    continue
        except Exception:
            env = {}

        common_paths = [str(path) for path in _common_windows_paths()]
        current_path = env.get("Path") or env.get("PATH") or os.environ.get("PATH", "")
        path_parts = [part for part in current_path.split(os.pathsep) if part]
        for path in common_paths:
            if path not in path_parts:
                path_parts.append(path)
        if path_parts:
            env["PATH"] = os.pathsep.join(path_parts)
        return env

    @staticmethod
    def _merge_path_values(values: list[str]) -> str:
        seen: set[str] = set()
        merged: list[str] = []
        for value in values:
            for part in str(value or "").split(os.pathsep):
                cleaned = part.strip().strip('"')
                if not cleaned:
                    continue
                key = os.path.normcase(os.path.normpath(cleaned))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(cleaned)
        return os.pathsep.join(merged)

    @staticmethod
    def _parse_env_lines(raw: str) -> dict[str, str]:
        env: dict[str, str] = {}
        for line in str(raw or "").splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key:
                env[key] = value
        return env

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().isoformat()
