from __future__ import annotations

import sys
from pathlib import Path


def test_cli_agent_tables_are_created(tmp_path: Path):
    from astrbot.builtin_stars.agent_system.database import Database

    db = Database(tmp_path / "agent.db")
    db.create_tables()

    rows = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    names = {row["name"] for row in rows}

    assert {
        "cli_agent_clients",
        "cli_agent_workspaces",
        "cli_agent_sessions",
        "cli_agent_messages",
        "cli_agent_events",
        "cli_agent_permissions",
    }.issubset(names)


def test_cli_agent_service_creates_client_workspace_and_session(tmp_path: Path):
    from astrbot.builtin_stars.agent_system.database import Database
    from astrbot.builtin_stars.agent_system.services.cli_agent_service import (
        CliAgentService,
    )

    db = Database(tmp_path / "agent.db")
    db.create_tables()
    service = CliAgentService(db)

    client = service.create_client(
        {
            "name": "Claude Local",
            "agent_kind": "claude",
            "location_kind": "local",
            "transport_kind": "acp_stdio",
            "command": "claude",
            "args": ["--experimental-acp"],
            "env": {"ANTHROPIC_BASE_URL": "https://example.test"},
        }
    )
    workspace = service.create_workspace(
        {
            "name": "AstrBot",
            "root_path": str(tmp_path / "workspace"),
            "location_kind": "local",
            "default_client_id": client["id"],
            "description": "NiceBot workspace",
        }
    )
    session = service.create_session(
        {
            "client_id": client["id"],
            "workspace_id": workspace["id"],
            "title": "Implement CLI Agent",
        }
    )

    assert client["name"] == "Claude Local"
    assert client["args"] == ["--experimental-acp"]
    assert client["env"]["ANTHROPIC_BASE_URL"] == "https://example.test"
    assert workspace["path"].endswith("workspace")
    assert workspace["root_path"].endswith("workspace")
    assert workspace["default_client_id"] == client["id"]
    assert workspace["description"] == "NiceBot workspace"
    assert session["client_id"] == client["id"]
    assert session["workspace_id"] == workspace["id"]
    assert service.list_sessions(client_id=client["id"])[0]["id"] == session["id"]


def test_cli_agent_check_reports_missing_command(tmp_path: Path):
    from astrbot.builtin_stars.agent_system.database import Database
    from astrbot.builtin_stars.agent_system.services.cli_agent_service import (
        CliAgentService,
    )

    db = Database(tmp_path / "agent.db")
    db.create_tables()
    service = CliAgentService(db)

    client = service.create_client(
        {
            "name": "Missing Local",
            "agent_kind": "claude",
            "location_kind": "local",
            "transport_kind": "acp_stdio",
            "command": "definitely-not-a-real-cli-agent-command",
        }
    )
    result = service.check_client(client["id"])

    assert result["available"] is False
    assert result["status"] == "unavailable"
    assert "not found" in result["message"].lower()


def test_cli_agent_acp_clients_get_default_bridge_command(tmp_path: Path):
    from astrbot.builtin_stars.agent_system.database import Database
    from astrbot.builtin_stars.agent_system.services.cli_agent_service import (
        CliAgentService,
    )

    db = Database(tmp_path / "agent.db")
    db.create_tables()
    service = CliAgentService(db)

    client = service.create_client(
        {
            "name": "Claude ACP",
            "agent_kind": "claude",
            "location_kind": "local",
            "transport_kind": "acp_stdio",
        }
    )

    assert client["command"] == "npx"
    assert client["args"] == ["-y", "@agentclientprotocol/claude-agent-acp"]


def test_cli_agent_service_rejects_native_stdio(tmp_path: Path):
    from astrbot.builtin_stars.agent_system.database import Database
    from astrbot.builtin_stars.agent_system.services.cli_agent_service import (
        CliAgentService,
    )

    db = Database(tmp_path / "agent.db")
    db.create_tables()
    service = CliAgentService(db)

    try:
        service.create_client(
            {
                "name": "Echo Local",
                "agent_kind": "custom",
                "location_kind": "local",
                "transport_kind": "native_stdio",
                "command": sys.executable,
                "args": [
                    "-c",
                    "import sys; print('CLI:' + sys.stdin.read().strip().upper())",
                ],
            }
        )
    except ValueError as exc:
        assert "transport_kind" in str(exc)
    else:
        raise AssertionError("native_stdio should be rejected")
