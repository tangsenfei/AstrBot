import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from quart import Quart

from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.routes import meeting as meeting_routes
from astrbot.builtin_stars.agent_system.services.meeting_runtime import MeetingRuntime
from astrbot.builtin_stars.agent_system.services.meeting_service import MeetingService
from astrbot.builtin_stars.agent_system.services.meeting_runtime import (
    persist_graph_event_batch,
)
from astrbot.core.langgraph.graphs import meeting as meeting_graph


def make_db(path: Path) -> Database:
    db = Database(path)
    db.create_tables()
    return db


def seed_meeting(db: Database, meeting_id: str = "meeting_timeline") -> str:
    db.insert(
        "meetings",
        {
            "id": meeting_id,
            "name": "会议模式回归",
            "goal": "验证会议节点展示",
            "meeting_type": "solution_design",
            "expected_output": "",
            "participants": [],
            "materials": {},
            "settings": {"require_goal_confirmation": False, "rounds": 4},
            "status": "running",
            "stage": "goal",
            "progress": 0,
            "current_round": 0,
            "current_speaker": "",
            "assistant_agent_id": "agent_meeting_assistant",
            "result": {},
            "task_id": "task_meeting_timeline",
            "created_at": "2026-05-13T00:00:00",
            "updated_at": "2026-05-13T00:00:00",
        },
    )
    return meeting_id


def seed_meeting_task(db: Database, meeting_id: str, task_id: str = "task_meeting_cancel") -> str:
    now = "2026-05-13T00:00:00"
    db.insert(
        "agent_tasks",
        {
            "id": task_id,
            "meeting_id": meeting_id,
            "name": "Meeting task",
            "description": "meeting",
            "task_type": "meeting",
            "category": "meeting",
            "status": "running",
            "progress": 20,
            "input": {},
            "output": {},
            "thread_id": f"meeting:{meeting_id}",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.update(
        "meetings",
        {"task_id": task_id, "status": "running", "updated_at": now},
        where="id = ?",
        where_params=(meeting_id,),
    )
    return task_id


@pytest.mark.asyncio
async def test_goal_hitl_only_when_explicitly_required(monkeypatch):
    class FailingInteractionManager:
        async def send_and_wait(self, *args, **kwargs):
            raise AssertionError("goal HITL should not be sent implicitly")

    emitted = []
    run_ctx = meeting_graph.GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=emitted.append,
    )
    monkeypatch.setattr(
        meeting_graph,
        "get_interaction_manager",
        lambda: FailingInteractionManager(),
    )

    updates = await meeting_graph._maybe_goal_hitl(
        {
            "settings": {"require_goal_confirmation": False},
            "goal": "讨论一个方案",
            "topic": "讨论一个方案",
            "expected_output": "",
            "strategy": "solution_design",
            "round_results": [],
        },
        run_ctx,
    )

    assert updates == {}
    assert [event["event"] for event in emitted] == []


def test_meeting_router_uses_host_decision_with_max_round_fallback():
    assert (
        meeting_graph.meeting_router(
            {
                "current_round": 1,
                "max_rounds": 4,
                "host_decision": {"action": "finalize"},
            }
        )
        == "finalize"
    )
    assert (
        meeting_graph.meeting_router(
            {
                "current_round": 1,
                "max_rounds": 4,
                "host_decision": {"action": "continue"},
            }
        )
        == "next_agent"
    )
    assert (
        meeting_graph.meeting_router(
            {
                "current_round": 4,
                "max_rounds": 4,
                "host_decision": {"action": "continue"},
            }
        )
        == "next_agent"
    )
    assert (
        meeting_graph.meeting_router(
            {
                "current_round": 5,
                "max_rounds": 4,
                "host_decision": {"action": "continue"},
            }
        )
        == "finalize"
    )


def test_meeting_runtime_persists_agent_call_and_token_events(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    meeting_id = seed_meeting(db)

    persist_graph_event_batch(
        db.db_path,
        meeting_id,
        [
            {
                "event": "agent_call_start",
                "data": {
                    "call_id": "call_1",
                    "agent_id": "agent_meeting_assistant",
                    "agent_label": "会议助理",
                    "agent_name": "会议助理",
                    "round": 1,
                    "input_payload": {"user_prompt": "请主持会议"},
                },
                "node_id": "running",
                "timestamp": 1,
            },
            {
                "event": "token",
                "data": {
                    "call_id": "call_1",
                    "agent_name": "会议助理",
                    "round": 1,
                    "input": 120,
                    "output": 45,
                },
                "node_id": "running",
                "timestamp": 2,
            },
            {
                "event": "agent_call_end",
                "data": {
                    "call_id": "call_1",
                    "agent_name": "会议助理",
                    "round": 1,
                    "agent_call_status": "completed",
                    "duration_ms": 2300,
                },
                "node_id": "running",
                "timestamp": 3,
            },
        ],
    )

    rows = db.select_all("meeting_events", where="meeting_id = ?", where_params=(meeting_id,))
    assert [row["event_type"] for row in rows] == [
        "agent_call_start",
        "token",
        "agent_call_end",
    ]
    updated = db.select_one("meetings", where="id = ?", where_params=(meeting_id,))
    assert updated["input_tokens"] == 120
    assert updated["output_tokens"] == 45
    assert updated["total_tokens"] == 165


@pytest.mark.asyncio
async def test_create_route_auto_starts_created_meeting(monkeypatch):
    app = Quart(__name__)
    started: list[str] = []

    class FakeService:
        def create_meeting(self, data):
            return {"id": "meeting_auto", "status": "pending", **data}

    class FakeRuntime:
        async def start(self, meeting_id, service_factory):
            started.append(meeting_id)
            assert service_factory() is fake_service
            return {"meeting_id": meeting_id, "started": True}

    fake_service = FakeService()
    monkeypatch.setattr(meeting_routes, "_get_meeting_service", lambda: fake_service)
    monkeypatch.setattr(meeting_routes, "_get_meeting_runtime", lambda: FakeRuntime())

    async with app.test_request_context(
        "/meeting/meetings",
        method="POST",
        json={"name": "自动启动会议", "goal": "创建后自动执行"},
    ):
        response = await meeting_routes._create_meeting()

    assert response["status"] == "ok"
    assert started == ["meeting_auto"]


@pytest.mark.asyncio
async def test_continue_route_auto_starts_continued_meeting(monkeypatch):
    app = Quart(__name__)
    started: list[str] = []

    class FakeService:
        def continue_meeting(self, meeting_id, data):
            return {"id": meeting_id, "status": "pending", "settings": data}

    class FakeRuntime:
        async def start(self, meeting_id, service_factory):
            started.append(meeting_id)
            assert service_factory() is fake_service
            return {"meeting_id": meeting_id, "started": True}

    fake_service = FakeService()
    monkeypatch.setattr(meeting_routes, "_get_meeting_service", lambda: fake_service)
    monkeypatch.setattr(meeting_routes, "_get_meeting_runtime", lambda: FakeRuntime())

    async with app.test_request_context(
        "/meeting/meetings/meeting_auto/continue",
        method="POST",
        json={"review_comment": "继续讨论"},
    ):
        response = await meeting_routes._continue_meeting("meeting_auto")

    assert response["status"] == "ok"
    assert started == ["meeting_auto"]


@pytest.mark.asyncio
async def test_meeting_runtime_cancel_updates_service_and_publishes_done():
    runtime = MeetingRuntime()
    meeting_id = "meeting_cancel_runtime"
    task = asyncio.create_task(asyncio.sleep(60))
    runtime._tasks[meeting_id] = task
    queue = runtime.subscribe(meeting_id)

    class FakeService:
        def cancel_meeting(self, cancelled_id):
            assert cancelled_id == meeting_id
            return {"id": cancelled_id, "status": "cancelled"}

    result = await runtime.cancel(meeting_id, lambda: FakeService())

    assert result["status"] == "cancelled"
    assert task.cancelled()
    event = await queue.get()
    assert event["event_type"] == "done"
    assert event["payload"]["status"] == "cancelled"
    runtime.unsubscribe(meeting_id, queue)


def test_meeting_service_cancel_marks_meeting_task_hitl_and_event_cancelled(tmp_path: Path):
    db = make_db(tmp_path / "agent.db")
    meeting_id = seed_meeting(db, "meeting_cancel_service")
    task_id = seed_meeting_task(db, meeting_id)
    db.insert(
        "hitl_requests",
        {
            "id": "hitl_meeting_cancel",
            "task_id": task_id,
            "session_id": meeting_id,
            "scope": "meeting",
            "interaction_type": "confirmation",
            "title": "确认",
            "body": "确认会议",
            "status": "pending",
            "metadata": {"meeting_id": meeting_id},
            "created_at": "2026-05-13T00:00:00",
        },
    )

    result = MeetingService(db).cancel_meeting(meeting_id)

    assert result["status"] == "cancelled"
    assert db.select_one("agent_tasks", where="id = ?", where_params=(task_id,))["status"] == "cancelled"
    assert db.select_one("hitl_requests", where="id = ?", where_params=("hitl_meeting_cancel",))["status"] == "cancelled"
    events = MeetingService(db).list_events(meeting_id)
    assert events[-1]["event_type"] == "phase"
    assert events[-1]["payload"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_run_meeting_graph_does_not_overwrite_cancelled_status(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path / "agent.db")
    meeting_id = seed_meeting(db, "meeting_cancel_race")
    task_id = seed_meeting_task(db, meeting_id)
    service = MeetingService(db)
    monkeypatch.setattr(
        service.agent_service,
        "get_agent",
        lambda agent_id: SimpleNamespace(id=agent_id, name="会议助手", provider_id="provider_1", soul=""),
    )
    monkeypatch.setattr(service, "_resolve_provider", lambda provider_id: SimpleNamespace(id=provider_id))

    class FakeGraph:
        async def ainvoke(self, state_input, config):
            db.update(
                "meetings",
                {"status": "cancelled", "updated_at": "2026-05-13T00:00:01"},
                where="id = ?",
                where_params=(meeting_id,),
            )
            return {
                "final_minutes": "不应写入",
                "deliverable_output": "不应写入",
                "round_results": [],
            }

    monkeypatch.setattr(meeting_graph, "build_meeting_graph", lambda strategy: FakeGraph())

    await service._run_meeting_graph(meeting_id, task_id)

    meeting = db.select_one("meetings", where="id = ?", where_params=(meeting_id,))
    task = db.select_one("agent_tasks", where="id = ?", where_params=(task_id,))
    assert meeting["status"] == "cancelled"
    assert task["status"] == "cancelled"
