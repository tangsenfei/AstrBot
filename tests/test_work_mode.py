import json
from pathlib import Path

import pytest

from astrbot.builtin_stars.agent_system.database import Database
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
