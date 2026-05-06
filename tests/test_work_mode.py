import json
from pathlib import Path

import pytest

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services.work_service import WorkService
from astrbot.core.langgraph.graphs.work_task import (
    _collect_executable_steps,
    _fallback_assign_steps,
    _parse_assigned_steps,
    _update_parent_status,
    _update_step_in_tree,
)


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
            "executor_config": {"agent_id": "assistant"},
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
    assert json.loads(row["executor_config"])["agent_id"] == "assistant"
    assert json.loads(row["plan_config"])["enabled"] is False
    assert json.loads(row["review_config"]) == {"enabled": True, "max_rework": 2}
    assert json.loads(row["input"])["work_context"]["rules"] == "保留执行记录。"

    supplemental = service.submit_input(task["id"], "补充：交付物要包含风险清单。")
    assert supplemental["decision"] == "inject_next_llm_call"
    updated = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    assert "风险清单" in updated["pending_input"]
    assert service.get_task(task["id"])["logs"]


@pytest.mark.asyncio
async def test_create_task_default_task_mode_is_normal(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "测试",
        }
    )
    task = await service.create_task(
        {
            "name": "测试任务模式",
            "description": "验证默认 task_mode",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "plan_config": {"enabled": False},
        }
    )
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    plan_config = json.loads(row["plan_config"])
    assert plan_config["task_mode"] == "normal"


@pytest.mark.asyncio
async def test_create_task_invalid_task_mode_normalized(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "测试",
        }
    )
    task = await service.create_task(
        {
            "name": "非法模式测试",
            "description": "验证非法 task_mode 被规范化",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "plan_config": {"enabled": False, "task_mode": "invalid_mode"},
        }
    )
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    plan_config = json.loads(row["plan_config"])
    assert plan_config["task_mode"] == "normal"


@pytest.mark.asyncio
async def test_create_task_quick_mode_persisted(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "测试",
        }
    )
    task = await service.create_task(
        {
            "name": "快速模式测试",
            "description": "验证快速模式",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "plan_config": {"enabled": False, "task_mode": "quick"},
        }
    )
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    plan_config = json.loads(row["plan_config"])
    assert plan_config["task_mode"] == "quick"


@pytest.mark.asyncio
async def test_create_task_deep_mode_persisted(work_db: Database, tmp_path: Path):
    service = WorkService(work_db)
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "测试",
        }
    )
    task = await service.create_task(
        {
            "name": "深度模式测试",
            "description": "验证深度模式",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "plan_config": {"enabled": False, "task_mode": "deep"},
        }
    )
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    plan_config = json.loads(row["plan_config"])
    assert plan_config["task_mode"] == "deep"


def test_parse_assigned_steps_valid_json():
    text = '''```json
[
  {"id": "step_1", "title": "步骤1", "description": "描述1", "depth": 1, "parent_id": null, "dependencies": [], "executor_type": "agent", "executor_id": "agent_nicebot_work_executor", "reviewer_id": "", "status": "pending", "sort_order": 0},
  {"id": "step_1_1", "title": "子步骤1.1", "description": "子描述1.1", "depth": 2, "parent_id": "step_1", "dependencies": [], "executor_type": "agent", "executor_id": "agent_nicebot_work_executor", "reviewer_id": "", "status": "pending", "sort_order": 0},
  {"id": "step_2", "title": "步骤2", "description": "描述2", "depth": 1, "parent_id": null, "dependencies": ["step_1"], "executor_type": "agent", "executor_id": "agent_nicebot_work_executor", "reviewer_id": "", "status": "pending", "sort_order": 1}
]
```'''
    steps = _parse_assigned_steps(text)
    assert len(steps) == 2
    assert steps[0]["id"] == "step_1"
    assert len(steps[0]["children"]) == 1
    assert steps[0]["children"][0]["id"] == "step_1_1"
    assert steps[1]["id"] == "step_2"
    assert steps[1]["dependencies"] == ["step_1"]


def test_parse_assigned_steps_empty_input():
    assert _parse_assigned_steps("") == []
    assert _parse_assigned_steps("not json") == []


def test_fallback_assign_steps_quick_mode():
    state = {"task_name": "快速任务", "task_desc": "快速完成", "input": {}, "executor_config": {}}
    steps = _fallback_assign_steps([], "quick", state)
    assert len(steps) == 1
    assert steps[0]["depth"] == 1
    assert steps[0]["children"] == []


def test_fallback_assign_steps_normal_mode():
    plan_steps = [
        {"id": "step_1", "title": "步骤1", "description": "描述1", "children": [
            {"id": "step_1_1", "title": "子步骤1.1", "description": "子描述1.1"},
        ]},
        {"id": "step_2", "title": "步骤2", "description": "描述2", "children": []},
    ]
    state = {"task_name": "常规任务", "task_desc": "常规完成", "input": {}, "executor_config": {}}
    steps = _fallback_assign_steps(plan_steps, "normal", state)
    assert len(steps) == 2
    assert len(steps[0]["children"]) == 1
    assert steps[0]["children"][0]["depth"] == 2
    assert steps[0]["children"][0]["parent_id"] == "step_1"
    assert len(steps[1]["children"]) == 0


def test_fallback_assign_steps_deep_mode():
    plan_steps = [
        {"id": "step_1", "title": "步骤1", "description": "描述1", "children": [
            {"id": "step_1_1", "title": "子步骤1.1", "description": "子描述1.1"},
            {"id": "step_1_2", "title": "子步骤1.2", "description": "子描述1.2"},
        ]},
        {"id": "step_2", "title": "步骤2", "description": "描述2", "children": []},
    ]
    state = {"task_name": "深度任务", "task_desc": "深度完成", "input": {}, "executor_config": {}}
    steps = _fallback_assign_steps(plan_steps, "deep", state)
    assert len(steps) == 2
    assert len(steps[0]["children"]) == 2
    assert steps[0]["children"][0]["depth"] == 2
    assert len(steps[1]["children"]) == 1
    assert steps[1]["children"][0]["title"].startswith("执行：")


def test_collect_executable_steps():
    steps = [
        {"id": "step_1", "depth": 1, "children": [
            {"id": "step_1_1", "depth": 2},
            {"id": "step_1_2", "depth": 2},
        ]},
        {"id": "step_2", "depth": 1, "children": []},
    ]
    executable = _collect_executable_steps(steps)
    assert len(executable) == 3
    assert executable[0]["id"] == "step_1_1"
    assert executable[1]["id"] == "step_1_2"
    assert executable[2]["id"] == "step_2"


def test_update_step_in_tree():
    steps = [
        {"id": "step_1", "status": "pending", "children": [
            {"id": "step_1_1", "status": "pending"},
        ]},
    ]
    _update_step_in_tree(steps, "step_1_1", {"status": "done", "result": "ok"})
    assert steps[0]["children"][0]["status"] == "done"
    assert steps[0]["children"][0]["result"] == "ok"


def test_update_parent_status_all_done():
    steps = [
        {"id": "step_1", "status": "pending", "children": [
            {"id": "step_1_1", "status": "done"},
            {"id": "step_1_2", "status": "done"},
        ]},
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "done"


def test_update_parent_status_partial():
    steps = [
        {"id": "step_1", "status": "pending", "children": [
            {"id": "step_1_1", "status": "done"},
            {"id": "step_1_2", "status": "pending"},
        ]},
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "pending"


def test_update_parent_status_failed():
    steps = [
        {"id": "step_1", "status": "pending", "children": [
            {"id": "step_1_1", "status": "done"},
            {"id": "step_1_2", "status": "failed"},
        ]},
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "failed"


def test_persist_work_steps_with_parent_id_and_dependencies(work_db: Database):
    from astrbot.core.langgraph.task_center import TaskCenter
    from datetime import datetime

    task_id = "test_persist_task"
    work_db.insert("agent_tasks", {
        "id": task_id,
        "name": "测试任务",
        "task_type": "work_task",
        "status": "running",
        "category": "work",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })

    now = datetime.now().isoformat()
    steps = [
        {"id": "step_1", "title": "步骤1", "description": "描述1", "status": "done", "dependencies": [], "parent_id": None, "depth": 1, "sort_order": 0, "executor_type": "agent", "executor_id": "exec1", "reviewer_id": "rev1"},
        {"id": "step_1_1", "title": "子步骤1.1", "description": "子描述1.1", "status": "running", "dependencies": [], "parent_id": "step_1", "depth": 2, "sort_order": 0, "executor_type": "agent", "executor_id": "exec2", "reviewer_id": ""},
        {"id": "step_2", "title": "步骤2", "description": "描述2", "status": "pending", "dependencies": ["step_1"], "parent_id": None, "depth": 1, "sort_order": 1, "executor_type": "agent", "executor_id": "exec1", "reviewer_id": "rev1"},
    ]
    TaskCenter._persist_work_steps(work_db, task_id, steps, now)

    persisted = work_db.select_all("work_task_steps", where="task_id = ?", where_params=(task_id,), order_by="sort_order ASC")
    assert len(persisted) == 3
    assert persisted[0]["parent_id"] is None
    assert persisted[1]["parent_id"] == f"{task_id}:step_1"
    assert persisted[2]["dependencies"] is not None
