from pathlib import Path

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services.task_service import TaskService
from astrbot.builtin_stars.agent_system.services.work_service import WorkService


def make_db(path: Path) -> Database:
    db = Database(path)
    db.create_tables()
    return db


def seed_work_task(db: Database) -> str:
    task_id = "task_timeline"
    TaskService(db).create_task(
        task_id=task_id,
        name="时间线任务",
        description="验证节点聚合",
        task_type="work_task",
        category="work",
        work_scope="daily",
        work_task_kind="workflow",
    )
    return task_id


def insert_log(db: Database, task_id: str, log_id: str, created_at: str, event: str, data: dict) -> None:
    db.insert(
        "execution_logs",
        {
            "id": log_id,
            "task_id": task_id,
            "sub_task_id": None,
            "agent_id": None,
            "level": "info",
            "message": data.get("message") or data.get("title") or event,
            "data": {"event": event, **data},
            "created_at": created_at,
        },
    )


def test_work_timeline_groups_hitl_and_tokens_by_stage(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    task_id = seed_work_task(db)
    db.insert(
        "work_task_steps",
        {
            "id": f"{task_id}:stage_clarify",
            "task_id": task_id,
            "parent_id": None,
            "title": "需求明确",
            "description": "确认需求",
            "status": "done",
            "dependencies": [],
            "executor": "需求确认助手",
            "executor_type": "agent",
            "executor_id": "agent_nicebot_work_assistant",
            "reviewer_id": "",
            "result": "",
            "result_ref": "",
            "depth": 1,
            "sort_order": 0,
            "started_at": "2026-05-09T00:00:00",
            "completed_at": "2026-05-09T00:00:40",
            "updated_at": "2026-05-09T00:00:40",
        },
    )
    insert_log(
        db,
        task_id,
        "log_hitl_call",
        "2026-05-09T00:00:10",
        "interaction",
        {"stage_id": "stage_clarify", "title": "需求确认：攻略", "body": "请确认天数"},
    )
    insert_log(
        db,
        task_id,
        "log_hitl_done",
        "2026-05-09T00:00:40",
        "hitl_resolved",
        {"stage_id": "stage_clarify", "action_key": "confirm", "field_values": {"days": "5天"}},
    )
    insert_log(
        db,
        task_id,
        "log_token",
        "2026-05-09T00:00:41",
        "token",
        {"stage_id": "stage_clarify", "input": 12, "output": 8},
    )

    timeline = WorkService(db).get_task(task_id)["timeline"]
    clarify = next(stage for stage in timeline["stages"] if stage["id"] == "stage_clarify")

    assert clarify["duration_ms"] == 40000
    assert [event["kind"] for event in clarify["events"][:2]] == ["hitl_call", "hitl_result"]
    assert clarify["token_usage"]["total_tokens"] == 20


def test_work_timeline_maps_execution_step_events(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    task_id = seed_work_task(db)
    db.insert(
        "work_task_steps",
        {
            "id": f"{task_id}:step_1",
            "task_id": task_id,
            "parent_id": None,
            "title": "整理景点",
            "description": "整理景点",
            "status": "done",
            "dependencies": [],
            "executor": "研究员",
            "executor_type": "agent",
            "executor_id": "agent_nicebot_work_researcher",
            "reviewer_id": "",
            "result": "景点列表",
            "result_ref": "",
            "depth": 1,
            "sort_order": 0,
            "started_at": "2026-05-09T00:01:00",
            "completed_at": "2026-05-09T00:02:00",
            "updated_at": "2026-05-09T00:02:00",
        },
    )
    insert_log(
        db,
        task_id,
        "log_step_output",
        "2026-05-09T00:01:20",
        "text_delta",
        {
            "stage_id": "stage_execute",
            "step_id": "step_1",
            "agent_id": "agent_nicebot_work_researcher",
            "agent_label": "研究员",
            "text": "完成景点整理",
        },
    )
    insert_log(
        db,
        task_id,
        "log_step_token",
        "2026-05-09T00:01:30",
        "token",
        {"stage_id": "stage_execute", "step_id": "step_1", "input": 100, "output": 50},
    )

    graph = WorkService(db).get_task(task_id)["timeline"]["execution_graph"]
    node = graph[0]

    assert node["id"] == "step_1"
    assert node["duration_ms"] == 60000
    assert node["result"] == "景点列表"
    assert node["events"][0]["content"] == "完成景点整理"
    assert node["token_usage"]["total_tokens"] == 150
