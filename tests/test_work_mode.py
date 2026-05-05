import json
from pathlib import Path

import pytest

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services.flow_service import BUILTIN_DAILY_WORK_FLOW_ID, FlowService
from astrbot.builtin_stars.agent_system.services.hitl_service import HITLService
from astrbot.builtin_stars.agent_system.services.work_service import WorkService
from astrbot.core.langgraph.graphs.work_task import plan_node
from astrbot.core.langgraph.state import GraphRunContext


@pytest.fixture
def work_db(tmp_path: Path):
    db = Database(tmp_path / "agent_system.db")
    db.create_tables()
    try:
        yield db
    finally:
        db.close()


def test_create_project_writes_db_and_rule_files(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    project_dir = tmp_path / "customer-project"

    project = service.create_project(
        {
            "name": "客户交付",
            "directory": str(project_dir),
            "goal": "交付可运行版本",
            "rules": "所有修改必须经过审查。",
        }
    )

    row = work_db.select_one("work_projects", where="id = ?", where_params=(project["id"],))
    assert row is not None
    assert row["goal"] == "交付可运行版本"
    assert row["rules"] == "所有修改必须经过审查。"
    assert (project_dir / ".nicebot" / "goal.md").read_text(encoding="utf-8") == "交付可运行版本"
    assert (project_dir / ".nicebot" / "rules.md").read_text(encoding="utf-8") == "所有修改必须经过审查。"

    updated = service.update_project(project["id"], {"goal": "按里程碑交付", "rules": "先测后交付。"})
    assert updated["goal"] == "按里程碑交付"
    assert (project_dir / ".nicebot" / "goal.md").read_text(encoding="utf-8") == "按里程碑交付"
    assert (project_dir / ".nicebot" / "rules.md").read_text(encoding="utf-8") == "先测后交付。"


def test_daily_dirs_are_created_and_archived(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily_dir = tmp_path / "daily"

    created = service.create_daily_dir(
        {
            "name": "运营日常",
            "directory": str(daily_dir),
            "default_rules": "优先小步快跑。",
        }
    )

    assert daily_dir.exists()
    assert created["default_rules"] == "优先小步快跑。"
    assert any(item["id"] == created["id"] for item in service.list_daily_dirs())

    assert service.delete_daily_dir(created["id"]) is True
    assert all(item["id"] != created["id"] for item in service.list_daily_dirs())


@pytest.mark.asyncio
async def test_create_work_task_persists_scope_configs_and_input(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "保留执行记录。",
        }
    )

    task = await service.create_task(
        {
            "name": "整理日报",
            "description": "汇总今天的关键进展",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "work_task_kind": "single_agent",
            "executor_config": {"agent_id": "assistant", "crew_id": "", "flow_id": ""},
            "plan_config": {"enabled": False},
            "review_config": {"enabled": True, "max_rework": 2},
        }
    )

    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    assert row is not None
    assert row["task_type"] == "work_task"
    assert row["category"] == "work"
    assert row["work_scope"] == "daily"
    assert row["work_daily_dir_id"] == daily["id"]
    assert row["work_task_kind"] == "single_agent"
    assert json.loads(row["executor_config"]) == {"agent_id": "assistant", "crew_id": "", "flow_id": ""}
    assert row["crew_id"] is None
    assert row["flow_id"] is None
    assert json.loads(row["plan_config"]) == {"enabled": False}
    assert json.loads(row["review_config"]) == {"enabled": True, "max_rework": 2}
    assert json.loads(row["input"])["work_context"]["rules"] == "保留执行记录。"

    supplemental = service.submit_input(task["id"], "补充：交付物要包含风险清单。")
    assert supplemental["decision"] == "inject_next_llm_call"
    updated = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    assert "风险清单" in updated["pending_input"]
    assert service.get_task(task["id"])["logs"]

    listed = service.list_tasks({"page_size": 10})["tasks"][0]
    assert listed["id"] == task["id"]
    assert listed["hitl_cards"] == []
    assert "logs" not in listed
    assert "executor_config" not in listed

    work_db.update(
        "agent_tasks",
        {"status": "running", "progress": 100},
        where="id = ?",
        where_params=(task["id"],),
    )
    repaired = service.get_task(task["id"])
    assert repaired["status"] == "completed"
    assert work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))["status"] == "completed"


def test_work_logs_support_append_only_seq_queries(work_db: Database):
    service = WorkService(work_db)
    work_db.insert(
        "agent_tasks",
        {
            "id": "task_logs",
            "name": "日志测试",
            "description": "",
            "task_type": "work_task",
            "created_at": "2026-05-05T00:00:00",
            "updated_at": "2026-05-05T00:00:00",
        },
    )
    service._append_log("task_logs", "info", "第一条", {"event": "phase"})
    service._append_log("task_logs", "info", "第二条", {"event": "text_delta", "text": "第二条"})

    logs = service.get_task_logs("task_logs")
    assert [log["message"] for log in logs] == ["第一条", "第二条"]
    assert logs[0]["seq"] < logs[1]["seq"]
    assert service.get_task_logs("task_logs", after_seq=logs[0]["seq"])[0]["message"] == "第二条"


def test_hitl_service_persists_and_resolves_task_status(work_db: Database):
    work_db.insert(
        "agent_tasks",
        {
            "id": "task_hitl",
            "name": "审批测试",
            "description": "",
            "task_type": "work_task",
            "status": "waiting_feedback",
            "interaction_id": "hitl_plan_1",
            "created_at": "2026-05-05T00:00:00",
            "updated_at": "2026-05-05T00:00:00",
        },
    )
    service = HITLService(work_db)
    service.upsert_from_card(
        {
            "interaction_id": "hitl_plan_1",
            "type": "plan_approval",
            "title": "执行计划审批",
            "body": "计划正文",
            "fields": [{"key": "modify_text", "label": "修改意见", "field_type": "textarea", "required": False}],
            "actions": [{"key": "approve", "label": "批准执行", "style": "primary"}],
            "meta": {"task_id": "task_hitl"},
        },
        task_id="task_hitl",
    )

    assert service.list_pending("task_hitl")[0]["title"] == "执行计划审批"

    import asyncio

    result = asyncio.run(service.respond("hitl_plan_1", "approve", {}))
    assert result["status"] == "approved"
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=("task_hitl",))
    assert row["status"] == "running"
    assert row["interaction_id"] == ""
    assert service.list_pending("task_hitl") == []


def test_builtin_daily_work_flow_is_seeded_and_locked(work_db: Database):
    service = FlowService(work_db)
    flows = [flow.to_dict() for flow in service.get_flows()]
    builtin = next(flow for flow in flows if flow["id"] == BUILTIN_DAILY_WORK_FLOW_ID)
    assert builtin["metadata"]["is_builtin"] is True

    with pytest.raises(ValueError):
        service.delete_flow(BUILTIN_DAILY_WORK_FLOW_ID)


@pytest.mark.asyncio
async def test_plan_node_falls_back_and_emits_when_provider_unavailable():
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={"streaming_response": True},
        writer=events.append,
    )

    result = await plan_node(
        {
            "task_id": "task_plan_test",
            "task_name": "安排日程",
            "task_desc": "为下周会议制定日程安排",
            "plan_config": {"enabled": True, "timeout_seconds": 10},
            "input": {"goal": "产出可确认的日程计划"},
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["plan_steps"]
    assert any(event["event"] == "error" and "计划生成失败" in event["data"]["message"] for event in events)
    assert any(
        event["event"] == "phase" and event["data"].get("phase") == "plan_done"
        for event in events
    )
