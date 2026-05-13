"""CLI Agent discovery helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

BUILTIN_AGENTS: dict[str, dict[str, Any]] = {
    "claude": {
        "name": "Claude Code",
        "binaries": ["claude"],
        "acp_args": ["--experimental-acp"],
        "auth_required": True,
    },
    "codex": {
        "name": "Codex",
        "binaries": ["codex"],
        "acp_args": [],
        "auth_required": True,
    },
    "qwen": {
        "name": "Qwen Code",
        "binaries": ["qwen"],
        "acp_args": ["--acp"],
        "auth_required": True,
    },
    "codebuddy": {
        "name": "CodeBuddy",
        "binaries": ["codebuddy"],
        "acp_args": ["--acp"],
        "auth_required": True,
    },
    "goose": {
        "name": "Goose",
        "binaries": ["goose"],
        "acp_args": ["acp"],
        "auth_required": False,
    },
    "auggie": {
        "name": "Augment Code",
        "binaries": ["auggie"],
        "acp_args": ["--acp"],
        "auth_required": False,
    },
    "kimi": {
        "name": "Kimi CLI",
        "binaries": ["kimi"],
        "acp_args": ["acp"],
        "auth_required": False,
    },
    "opencode": {
        "name": "OpenCode",
        "binaries": ["opencode"],
        "acp_args": ["acp"],
        "auth_required": False,
    },
    "copilot": {
        "name": "GitHub Copilot",
        "binaries": ["copilot"],
        "acp_args": ["--acp", "--stdio"],
        "auth_required": False,
    },
    "qoder": {
        "name": "Qoder CLI",
        "binaries": ["qodercli"],
        "acp_args": ["--acp"],
        "auth_required": False,
    },
    "cursor": {
        "name": "Cursor Agent",
        "binaries": ["agent"],
        "acp_args": ["acp"],
        "auth_required": True,
        "warning": "命令名 agent 可能命中非 Cursor CLI，请确认完整路径。",
    },
    "vibe": {
        "name": "Mistral Vibe",
        "binaries": ["vibe-acp"],
        "acp_args": [],
        "auth_required": False,
    },
    "kiro": {
        "name": "Kiro",
        "binaries": ["kiro-cli"],
        "acp_args": ["acp"],
        "auth_required": True,
    },
    "hermes": {
        "name": "Hermes Agent",
        "binaries": ["hermes"],
        "acp_args": ["acp"],
        "auth_required": True,
    },
    "snow": {
        "name": "Snow CLI",
        "binaries": ["snow"],
        "acp_args": ["--acp"],
        "auth_required": False,
    },
    "droid": {
        "name": "Factory Droid",
        "binaries": ["droid"],
        "acp_args": ["exec", "--output-format", "acp"],
        "auth_required": False,
    },
}


def detect_installed_agents_sync() -> list[dict[str, Any]]:
    """Return detected ACP CLI agents from PATH and common Windows install dirs."""
    extra_paths = _common_windows_paths()
    results = []
    for agent_id, spec in BUILTIN_AGENTS.items():
        detected_path = ""
        command = ""
        for binary in spec["binaries"]:
            detected_path = shutil.which(binary) or _find_in_paths(binary, extra_paths)
            if detected_path:
                command = binary
                break
        results.append(
            {
                "agent_id": agent_id,
                "name": spec["name"],
                "command": command or (spec["binaries"][0] if spec["binaries"] else ""),
                "detected_path": detected_path,
                "acp_args": list(spec.get("acp_args") or []),
                "installed": bool(detected_path),
                "auth_required": bool(spec.get("auth_required", False)),
                "warning": spec.get("warning", "") if detected_path else "",
            }
        )
    return results


async def detect_installed_agents() -> list[dict[str, Any]]:
    """Async wrapper for route handlers."""
    return await asyncio.to_thread(detect_installed_agents_sync)


def default_agent_command(agent_kind: str) -> tuple[str, list[str]]:
    """Return the preferred command/args for a builtin agent."""
    if agent_kind == "claude":
        return "npx", ["-y", "@agentclientprotocol/claude-agent-acp"]
    if agent_kind == "codex":
        return "npx", ["-y", "@zed-industries/codex-acp"]
    spec = BUILTIN_AGENTS.get(agent_kind)
    if not spec:
        return "", []
    return str(spec["binaries"][0]), list(spec.get("acp_args") or [])


def resolve_command_path(command: str) -> str:
    """Resolve a command through PATH plus common Windows shim directories."""
    command = str(command or "").strip()
    if not command:
        return ""
    if any(sep in command for sep in ("/", "\\")):
        return command if Path(command).exists() else ""
    return shutil.which(command) or _find_in_paths(command, _common_windows_paths())


def _find_in_paths(binary: str, paths: list[Path]) -> str:
    candidates = [binary]
    if os.name == "nt" and not Path(binary).suffix:
        candidates.extend([f"{binary}.cmd", f"{binary}.exe", f"{binary}.bat"])
    for base in paths:
        for name in candidates:
            candidate = base / name
            if candidate.exists():
                return str(candidate)
    return ""


def _common_windows_paths() -> list[Path]:
    if os.name != "nt":
        return []
    env = os.environ
    home = Path.home()
    raw_paths = [
        env.get("APPDATA", "") and Path(env["APPDATA"]) / "npm",
        env.get("LOCALAPPDATA", "") and Path(env["LOCALAPPDATA"]) / "pnpm",
        home / ".bun" / "bin",
        home / "scoop" / "shims",
        env.get("SCOOP", "") and Path(env["SCOOP"]) / "shims",
        env.get("ChocolateyInstall", "") and Path(env["ChocolateyInstall"]) / "bin",
        Path("C:/Program Files/nodejs"),
        Path("C:/Program Files (x86)/nodejs"),
        Path("C:/Program Files/Git/cmd"),
        Path("C:/Program Files/Git/bin"),
        Path("C:/Program Files/Git/usr/bin"),
        Path("C:/Program Files (x86)/Git/cmd"),
        Path("C:/Program Files (x86)/Git/bin"),
        Path("C:/Program Files (x86)/Git/usr/bin"),
    ]
    return [path for path in raw_paths if isinstance(path, Path) and path.exists()]
