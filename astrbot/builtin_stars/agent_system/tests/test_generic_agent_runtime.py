import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services import (
    skill_service as skill_service_module,
)
from astrbot.builtin_stars.agent_system.services.generic_agent_runtime import (
    GenericAgentRuntimeService,
)


class FastGenericAgentService(GenericAgentRuntimeService):
    def __init__(self, db: Database, root: Path) -> None:
        super().__init__(db)
        self.root = root
        self.active_runs = 0
        self.execution_order: list[str] = []
        (self.root / "source").mkdir(parents=True, exist_ok=True)

    def _data_root(self) -> Path:
        data_root = self.root / "data" / "genericagent"
        data_root.mkdir(parents=True, exist_ok=True)
        return data_root

    def _default_source_path(self) -> Path:
        return self.root / "source"

    async def _execute_run(self, run_id: str) -> None:
        self.active_runs += 1
        assert self.active_runs == 1
        self.execution_order.append(run_id)
        self._update_run(run_id, {"status": "running", "progress": 50})
        self._insert_event(run_id, "process", "fake process started", {})
        await asyncio.sleep(0.02)
        self._update_run(
            run_id,
            {
                "status": "completed",
                "progress": 100,
                "summary": f"completed {run_id}",
                "completed_at": self._now(),
            },
        )
        self._insert_event(run_id, "completed", "fake process completed", {})
        self.active_runs -= 1


class NoWorkerGenericAgentService(FastGenericAgentService):
    def _ensure_worker(self) -> None:
        return


class FakeProviderContext:
    class ProviderManager:
        def get_provider_config_by_id(self, provider_id: str, merged: bool = False):
            if provider_id != "provider-openai":
                return None
            return {
                "proxy": "http://127.0.0.1:7890",
                "timeout": 120,
                "max_retries": 2,
                "custom_headers": {"X-Test": "1"},
            }

    provider_manager = ProviderManager()

    def get_provider_by_id(self, provider_id: str):
        if provider_id != "provider-openai":
            return None
        return type(
            "Provider",
            (),
            {
                "provider_config": {
                    "key": ["sk-test"],
                    "api_base": "https://example.test/v1",
                    "model": "gpt-test",
                    "timeout": 60,
                }
            },
        )()


def make_db(path: Path) -> Database:
    db = Database(path)
    db.create_tables()
    return db


def test_generic_agent_queue_runs_serially(tmp_path: Path):
    async def scenario() -> None:
        db = make_db(tmp_path / "agent.db")
        service = FastGenericAgentService(db, tmp_path)
        first = await service.enqueue_run({"goal": "first"})
        second = await service.enqueue_run({"goal": "second"})

        await service._worker_task

        assert service.execution_order == [first["id"], second["id"]]
        assert service.get_run(first["id"])["status"] == "completed"
        assert service.get_run(second["id"])["status"] == "completed"
        assert service._pending_count() == 0
        assert len(service.list_events(first["id"])) >= 2

        db.close()

    asyncio.run(scenario())


def test_pending_run_can_be_cancelled_without_starting(tmp_path: Path):
    async def scenario() -> None:
        db = make_db(tmp_path / "agent.db")
        service = NoWorkerGenericAgentService(db, tmp_path)
        run = await service.enqueue_run({"goal": "cancel me"})

        cancelled = await service.stop_run(run["id"])

        assert cancelled["status"] == "cancelled"
        assert service._pending_count() == 0
        events = service.list_events(run["id"])
        assert events[-1]["event_type"] == "cancelled"

        db.close()

    asyncio.run(scenario())


def test_stale_running_run_without_pid_is_marked_failed(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    old_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_stale_pidless",
            "source": "manual",
            "goal": "stale",
            "constraints": "",
            "expected_outputs": [],
            "workspace_path": "",
            "parent_task_id": "",
            "status": "running",
            "queue_position": 0,
            "progress": 10,
            "summary": "",
            "artifacts": [],
            "error": "",
            "pid": None,
            "started_at": old_time,
            "completed_at": None,
            "created_at": old_time,
            "updated_at": old_time,
        },
    )

    run = service.get_run("gar_stale_pidless")

    assert run["status"] == "failed"
    assert "进程状态丢失" in run["error"]
    events = service.list_events("gar_stale_pidless")
    assert events[-1]["event_type"] == "error"

    db.close()


def test_tool_policies_filter_generic_agent_tool_schema(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    runtime = tmp_path / "runtime"
    assets = runtime / "assets"
    assets.mkdir(parents=True)
    schema = [
        {"type": "function", "function": {"name": "file_read"}},
        {"type": "function", "function": {"name": "file_write"}},
    ]
    (assets / "tools_schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (assets / "tools_schema_cn.json").write_text(json.dumps(schema), encoding="utf-8")

    service.update_tool_policies(
        {"tools": [{"tool_name": "file_write", "enabled": False}]}
    )
    service._write_filtered_tool_schema(runtime)

    filtered = json.loads((assets / "tools_schema.json").read_text(encoding="utf-8"))
    assert [tool["function"]["name"] for tool in filtered] == ["file_read"]

    db.close()


def test_terminal_output_filters_repeated_working_memory(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    now = service._now()
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_terminal",
            "source": "manual",
            "goal": "terminal",
            "created_at": now,
            "updated_at": now,
        },
    )

    service._record_terminal_output(
        "gar_terminal",
        "\n".join(
            [
                "### [WORKING MEMORY]",
                "<history>",
                "[USER]: hidden prompt",
                "[Agent] repeated summary",
                "</history>",
                "Current turn: 5",
                "[Debug] Current context: 123 chars",
                "Web Execute JS Result: {",
                '  "status": "success"',
                "}",
            ]
        ),
    )

    events = service.list_events("gar_terminal")
    assert len(events) == 1
    assert "WORKING MEMORY" not in events[0]["payload"]["text"]
    assert "Current turn" not in events[0]["payload"]["text"]
    assert "Web Execute JS Result" in events[0]["payload"]["text"]

    db.close()


def test_collect_artifacts_marks_output_txt_as_final_output(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    task_dir = tmp_path / "runtime" / "temp" / "gar_output"
    task_dir.mkdir(parents=True)
    (task_dir / "output.txt").write_text(
        "**Turn 1 ...**\n<summary>plan</summary>\nworking\n"
        "**Turn 2 ...**\n<summary>done</summary>\n最终报告正文",
        encoding="utf-8",
    )
    (task_dir / "report.md").write_text("extra file", encoding="utf-8")

    artifacts = service._collect_artifacts("gar_output", tmp_path / "runtime")
    final = next(item for item in artifacts if item["artifact_type"] == "final_output")

    assert final["name"] == "智能RPA最终输出"
    assert final["content"] == "最终报告正文"
    assert any(item["artifact_type"] == "file" for item in artifacts)

    db.close()


def test_detects_genericagent_task_completion_markers():
    assert GenericAgentRuntimeService._looks_like_completed_task_output(
        "final answer\n[Info] Final response to user.\n"
    )
    assert GenericAgentRuntimeService._looks_like_completed_task_output(
        "final answer\n[ROUND END]\n"
    )
    assert not GenericAgentRuntimeService._looks_like_completed_task_output(
        "still streaming"
    )


def test_recover_interrupted_running_run_from_round_end_output(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    runtime = tmp_path / "data" / "genericagent" / "runtime"
    task_dir = runtime / "temp" / "gar_recovered"
    task_dir.mkdir(parents=True)
    (task_dir / "output.txt").write_text(
        "**Turn 1 ...**\n<summary>done</summary>\n最终报告\n"
        "[Info] Final response to user.\n[ROUND END]\n",
        encoding="utf-8",
    )
    old_time = "2000-01-01T00:00:00"
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_recovered",
            "source": "manual",
            "goal": "recover me",
            "status": "running",
            "pid": None,
            "started_at": old_time,
            "created_at": old_time,
            "updated_at": old_time,
        },
    )

    service._recover_interrupted_runs()

    run = service.get_run("gar_recovered")
    final_artifact = next(
        item for item in run["artifacts"] if item["artifact_type"] == "final_output"
    )

    assert run["status"] == "completed"
    assert run["progress"] == 100
    assert "最终报告" in final_artifact["content"]
    assert any(
        event["event_type"] == "completed" for event in service.list_events(run["id"])
    )

    db.close()


def test_recovery_marks_pidless_running_run_without_final_output_failed(
    tmp_path: Path,
):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    old_time = "2000-01-01T00:00:00"
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_pidless",
            "source": "manual",
            "goal": "still running",
            "status": "running",
            "pid": None,
            "started_at": old_time,
            "created_at": old_time,
            "updated_at": old_time,
        },
    )

    service._recover_interrupted_runs()

    run = service.get_run("gar_pidless")
    assert run["status"] == "failed"
    assert "进程状态丢失" in run["error"]
    assert any(
        event["event_type"] == "error"
        and "进程状态丢失" in event["payload"].get("message", "")
        for event in service.list_events(run["id"])
    )

    db.close()


def test_provider_llm_config_is_saved_without_raw_genericagent_json(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    service.context = FakeProviderContext()

    config = service.update_config(
        {
            "llm_config": {
                "provider_id": "provider-openai",
                "model": {"title": "gpt-override", "value": "gpt-override"},
                "api_mode": "chat_completions",
                "reasoning_effort": "medium",
                "temperature": 0.2,
                "ignored_secret": "nope",
            }
        }
    )
    normalized = service._normalize_llm_config(config["llm_config"])

    assert config["llm_config"] == {
        "provider_id": "provider-openai",
        "model": "gpt-override",
        "api_mode": "chat_completions",
        "reasoning_effort": "medium",
        "temperature": 0.2,
    }
    assert normalized["native_oai_config"]["apikey"] == "sk-test"
    assert normalized["native_oai_config"]["model"] == "gpt-override"
    assert normalized["native_oai_config"]["reasoning_effort"] == "medium"
    assert normalized["native_oai_config"]["proxy"] == "http://127.0.0.1:7890"
    assert normalized["native_oai_config"]["timeout"] == "60"
    assert normalized["native_oai_config"]["read_timeout"] == "60"
    assert normalized["native_oai_config"]["max_retries"] == "2"
    assert normalized["native_oai_config"]["custom_headers"] == {"X-Test": "1"}

    db.close()


def test_error_only_round_end_is_classified_as_llm_failure():
    text = (
        "!!!Error: ConnectionError!!!Error: ConnectionError\n\n"
        "`````\n[Info] Final response to user.\n`````\n\n[ROUND END]"
    )

    assert GenericAgentRuntimeService._looks_like_completed_task_output(text)
    assert GenericAgentRuntimeService._is_error_only_final_output(text)
    assert "LLM 连接失败" in GenericAgentRuntimeService._classify_final_output_error(
        text
    )


def test_recover_interrupted_error_only_output_marks_failed(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    runtime = tmp_path / "data" / "genericagent" / "runtime"
    task_dir = runtime / "temp" / "gar_failed"
    task_dir.mkdir(parents=True)
    (task_dir / "output.txt").write_text(
        "!!!Error: ConnectionError!!!Error: ConnectionError\n"
        "[Info] Final response to user.\n[ROUND END]\n",
        encoding="utf-8",
    )
    old_time = "2000-01-01T00:00:00"
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_failed",
            "source": "manual",
            "goal": "recover failure",
            "status": "running",
            "pid": None,
            "started_at": old_time,
            "created_at": old_time,
            "updated_at": old_time,
        },
    )

    service._recover_interrupted_runs()

    run = service.get_run("gar_failed")
    assert run["status"] == "failed"
    assert "LLM 连接失败" in run["error"]
    assert run["summary"] == ""
    assert not any(item["artifact_type"] == "final_output" for item in run["artifacts"])

    db.close()


def test_completed_error_only_history_is_repaired(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    now = service._now()
    error_output = (
        "!!!Error: ConnectionError!!!Error: ConnectionError\n"
        "[Info] Final response to user.\n[ROUND END]\n"
    )
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_history_error",
            "source": "manual",
            "goal": "history",
            "status": "completed",
            "progress": 100,
            "summary": error_output,
            "artifacts": [
                {
                    "name": "GenericAgent 最终输出",
                    "path": "output.txt",
                    "artifact_type": "final_output",
                    "content": error_output,
                }
            ],
            "created_at": now,
            "updated_at": now,
        },
    )

    run = service.get_run("gar_history_error")

    assert run["status"] == "failed"
    assert "LLM 连接失败" in run["error"]
    assert run["summary"] == ""
    assert run["artifacts"] == []
    assert any(
        event["title"] == "历史运行纠偏为失败"
        for event in service.list_events("gar_history_error")
    )

    db.close()


def test_approve_skill_review_syncs_genericagent_source(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    monkeypatch.setattr(
        skill_service_module.StarTools,
        "get_data_dir",
        lambda name: tmp_path / "data" / name,
    )
    now = service._now()
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_test",
            "source": "manual",
            "goal": "learn",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "generic_agent_skill_reviews",
        {
            "id": "gasr_test",
            "run_id": "gar_test",
            "title": "GenericAgent SOP",
            "description": "review",
            "content": "Use safe workspace constraints.",
            "source_path": "memory/sop.md",
            "status": "pending",
            "synced_skill_id": "",
            "created_at": now,
            "reviewed_at": None,
        },
    )

    review = service.approve_skill_review("gasr_test")
    skill = db.select_one(
        "skills", where="id = ?", where_params=(review["synced_skill_id"],)
    )

    assert review["status"] == "approved"
    assert skill is not None
    assert skill["source"] == "genericagent"
    assert skill["category"] == "genericagent"

    db.close()


def test_reject_skill_review_marks_review_rejected(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    service = NoWorkerGenericAgentService(db, tmp_path)
    now = service._now()
    db.insert(
        "generic_agent_runs",
        {
            "id": "gar_test",
            "source": "manual",
            "goal": "review",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "generic_agent_skill_reviews",
        {
            "id": "gasr_reject",
            "run_id": "gar_test",
            "title": "GenericAgent Draft",
            "description": "review",
            "content": "draft",
            "source_path": "memory/draft.md",
            "status": "pending",
            "synced_skill_id": "",
            "created_at": now,
            "reviewed_at": None,
        },
    )

    review = service.reject_skill_review("gasr_reject")

    assert review["status"] == "rejected"
    assert review["reviewed_at"]

    db.close()
