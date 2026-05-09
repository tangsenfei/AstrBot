import json
from pathlib import Path

import pytest

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services.flow_service import BUILTIN_DAILY_WORK_FLOW_ID, FlowService
from astrbot.builtin_stars.agent_system.services.work_service import WorkService
from astrbot.core.langgraph.graphs.work_task import (
    _build_execute_prompt,
    _collect_executable_steps,
    _fallback_assign_steps,
    _parse_assigned_steps,
    _parse_steps,
    _validate_assigned_steps,
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


def test_builtin_daily_work_flow_schema_v3_exposes_runtime_nodes(work_db: Database):
    flow_service = FlowService(work_db)
    flow_service.ensure_builtin_daily_work_flow()
    flow = flow_service.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)

    assert flow is not None
    assert flow.metadata["schema_version"] == 3
    assert flow.metadata["topology_locked"] is True
    node_ids = {node.id for node in flow.nodes}
    assert {"daily_mode_strategy", "daily_review_gate", "daily_rework_hitl"}.issubset(node_ids)
    validation = flow_service.validate_flow(BUILTIN_DAILY_WORK_FLOW_ID)
    assert validation["success"] is True


def test_builtin_daily_work_flow_locks_topology(work_db: Database):
    flow_service = FlowService(work_db)
    flow_service.ensure_builtin_daily_work_flow()
    flow = flow_service.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)
    assert flow is not None

    data = flow_service._flow_to_definition(flow)
    data["nodes"] = data["nodes"][:-1]

    with pytest.raises(ValueError, match="拓扑已锁定"):
        flow_service.update_flow(BUILTIN_DAILY_WORK_FLOW_ID, data)


def test_work_service_extracts_flow_runtime_config(work_db: Database):
    flow_service = FlowService(work_db)
    flow_service.ensure_builtin_daily_work_flow()
    work_service = WorkService(work_db)
    definition = work_service._get_flow_definition(BUILTIN_DAILY_WORK_FLOW_ID)
    runtime = work_service._extract_work_flow_runtime_config(definition)

    assert runtime["clarification_config"]["template_id"] == "builtin_work_requirement_clarification"
    assert runtime["plan_config"]["task_mode"] == "normal"
    assert runtime["executor_config"]["execute_prompt_template"]
    assert runtime["executor_config"]["executor_agent_id"] == "agent_nicebot_work_executor"
    assert runtime["review_config"]["rework_title"] == "审查未通过"


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
    review_config = json.loads(row["review_config"])
    assert review_config["enabled"] is True
    assert review_config["max_rework"] == 2
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


def test_parse_steps_preserves_deliverable_lines():
    steps = _parse_steps(
        "1. 确定行程框架与核心区域\n"
        "   交付物：3-5天成都旅游行程框架\n"
        "   1.1 根据天数划分每日节奏\n"
    )

    assert steps[0]["deliverable"] == "3-5天成都旅游行程框架"
    assert "交付物：3-5天成都旅游行程框架" in steps[0]["description"]


def test_fallback_assign_steps_quick_mode():
    state = {
        "task_name": "快速任务",
        "task_desc": "快速完成",
        "input": {},
        "executor_config": {},
        "plan_text_full": "1. 确定行程框架\n   交付物：完整攻略框架",
    }
    steps = _fallback_assign_steps([], "quick", state)
    assert len(steps) == 1
    assert steps[0]["depth"] == 1
    assert steps[0]["children"] == []
    assert "确定行程框架" in steps[0]["description"]
    assert "完整攻略框架" in steps[0]["description"]


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


def test_validate_assigned_steps_rejects_collapsed_normal_plan():
    plan_text = (
        "1. 确定行程框架\n"
        "   交付物：3-5天行程框架\n"
        "2. 规划美食体验\n"
        "   交付物：美食清单\n"
        "3. 设计文化路线\n"
        "   交付物：文化景点计划"
    )
    plan_steps = _parse_steps(plan_text)
    assigned = [{"id": "step_1", "title": "成都旅游攻略", "description": "成都旅游攻略", "children": []}]

    assert _validate_assigned_steps(assigned, plan_steps, "normal", plan_text) is False


def test_build_execute_prompt_contains_requirements_plan_and_normal_scope():
    plan_text = (
        "1. 确定行程框架与核心区域\n"
        "   交付物：3-5天成都旅游行程框架\n"
        "   1.1 根据travel_duration划分每日节奏\n"
    )
    steps = _parse_steps(plan_text)
    state = {
        "task_name": "成都旅游攻略",
        "task_desc": "做一份适合首次到成都的攻略",
        "task_mode": "normal",
        "input": {"goal": "交付可直接使用的旅游攻略", "work_context": {"rules": "预算要清楚"}},
        "clarification": {"travel_duration": "3-5天", "interest_focus": ["美食", "文化历史"]},
        "plan_text_full": plan_text,
    }

    prompt = _build_execute_prompt(state, steps, steps[0], [], "normal")

    assert "## 任务需求" in prompt
    assert "做一份适合首次到成都的攻略" in prompt
    assert "3-5天" in prompt
    assert "美食" in prompt
    assert "## 已审批整体计划" in prompt
    assert "3-5天成都旅游行程框架" in prompt
    assert "## 当前负责部分" in prompt
    assert "根据travel_duration划分每日节奏" in prompt


def test_build_execute_prompt_contains_parent_scope_for_deep_step():
    plan_text = (
        "1. 确定行程框架与核心区域\n"
        "   交付物：3-5天成都旅游行程框架\n"
        "   1.1 根据travel_duration划分每日节奏\n"
    )
    steps = _parse_steps(plan_text)
    child = steps[0]["children"][0]
    state = {
        "task_name": "成都旅游攻略",
        "task_desc": "做一份攻略",
        "task_mode": "deep",
        "input": {"goal": "交付攻略"},
        "clarification": {"travel_duration": "3-5天"},
        "plan_text_full": plan_text,
    }

    prompt = _build_execute_prompt(state, steps, child, [], "deep")

    assert "所属父步骤" in prompt
    assert "确定行程框架与核心区域" in prompt
    assert "当前步骤" in prompt
    assert "根据travel_duration划分每日节奏" in prompt


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
