"""Remote CLI Agent relay over transparent ACP NDJSON WebSocket."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import platform
from typing import Any

from .cli_agent_connector import CliAgentConnector, ConnectorConfig


class RelayAuthError(RuntimeError):
    """Raised when a relay connection fails authentication."""


class RelayServer:
    """Remote host relay that bridges WebSocket lines to a local ACP subprocess."""

    def __init__(self, shared_secret: str = "", bearer_token: str = "") -> None:
        self.shared_secret = shared_secret
        self.bearer_token = bearer_token

    async def handle_connection(self, ws) -> None:
        process: asyncio.subprocess.Process | None = None
        try:
            hello = await self._read_and_verify_hello(ws)
            config = ConnectorConfig(**(hello.get("agent_config") or {}))
            process = await self._spawn(config)
            tasks = [
                asyncio.create_task(self._pipe_stdout_to_ws(process, ws)),
                asyncio.create_task(self._pipe_ws_to_stdin(ws, process)),
            ]
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
        finally:
            await self._stop_process(process)

    async def _read_and_verify_hello(self, ws) -> dict[str, Any]:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        hello = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if not self._verify_bearer(ws) or not self._verify_hello(hello):
            await ws.close(code=4401, reason="unauthorized")
            raise RelayAuthError("relay auth failed")
        return hello

    def _verify_bearer(self, ws) -> bool:
        if not self.bearer_token:
            return True
        headers = getattr(ws, "request_headers", None)
        if headers is None and getattr(ws, "request", None) is not None:
            headers = getattr(ws.request, "headers", None)
        auth = headers.get("Authorization", "") if headers else ""
        return hmac.compare_digest(auth, f"Bearer {self.bearer_token}")

    def _verify_hello(self, hello: dict[str, Any]) -> bool:
        if not self.shared_secret:
            return True
        nonce = str(hello.get("nonce") or "")
        signature = str(hello.get("signature") or "")
        expected = hmac.new(
            self.shared_secret.encode("utf-8"),
            nonce.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return bool(nonce) and hmac.compare_digest(signature, expected)

    async def _spawn(self, config: ConnectorConfig) -> asyncio.subprocess.Process:
        if not config.executable:
            raise ValueError("远程 CLI Agent 未配置 executable")
        return await asyncio.create_subprocess_exec(
            config.executable,
            *[str(arg) for arg in config.args],
            cwd=config.cwd or None,
            env=CliAgentConnector._prepare_env(config.env),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def _pipe_stdout_to_ws(
        self, process: asyncio.subprocess.Process, ws
    ) -> None:
        assert process.stdout
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await ws.send(line.decode("utf-8", errors="replace"))

    async def _pipe_ws_to_stdin(
        self, ws, process: asyncio.subprocess.Process
    ) -> None:
        assert process.stdin
        async for raw in ws:
            line = (
                raw.decode("utf-8", errors="replace")
                if isinstance(raw, bytes)
                else str(raw)
            )
            if not line.endswith("\n"):
                line += "\n"
            process.stdin.write(line.encode("utf-8"))
            await process.stdin.drain()

    async def _stop_process(self, process: asyncio.subprocess.Process | None) -> None:
        if not process:
            return
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
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
