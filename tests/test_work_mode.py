import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from astrbot.builtin_stars.agent_system import database as agent_database
from astrbot.builtin_stars.agent_system.database import Database
from astrbot.builtin_stars.agent_system.services.agent_service import AgentService
from astrbot.builtin_stars.agent_system.services.flow_service import (
    BUILTIN_DAILY_WORK_FLOW_ID,
    FlowService,
)
from astrbot.builtin_stars.agent_system.services.work_config_service import (
    WorkConfigService,
)
from astrbot.builtin_stars.agent_system.services.work_service import WorkService
from astrbot.core.langgraph.graphs import work_task as work_task_module
from astrbot.core.langgraph.graphs.work_task import (
    _build_execute_prompt,
    _collect_executable_steps,
    _parse_steps,
    _step_scope_text,
    _update_parent_status,
    _update_step_in_tree,
    approve_plan_node,
    clarify_node,
    execute_node,
    finalize_node,
    plan_node,
    prepare_node,
    route_after_approval,
    route_after_execute,
)
from astrbot.core.langgraph.interaction import InteractionResponse
from astrbot.core.langgraph.state import GraphRunContext, TaskRecord, TaskStatus


@pytest.fixture
def work_db(tmp_path: Path):
    db = Database(tmp_path / "agent_system.db")
    db.create_tables()
    try:
        yield db
    finally:
        db.close()


def test_agents_schema_migrates_backstory_to_soul_and_removes_legacy_fields(
    tmp_path: Path,
):
    db = Database(tmp_path / "legacy_agent_system.db")
    try:
        db.execute(
            """
            CREATE TABLE agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                goal TEXT,
                backstory TEXT,
                tools TEXT DEFAULT '[]',
                skills TEXT DEFAULT '[]',
                provider_id TEXT,
                model_name TEXT,
                llm_config TEXT DEFAULT '{}',
                memory_config TEXT DEFAULT '{}',
                planning INTEGER DEFAULT 0,
                planning_effort TEXT DEFAULT 'medium',
                max_iter INTEGER DEFAULT 20,
                enabled INTEGER DEFAULT 1,
                agent_type TEXT DEFAULT 'custom',
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = datetime.now().isoformat()
        db.execute(
            """
            INSERT INTO agents (
                id, name, role, goal, backstory, tools, provider_id,
                model_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_legacy",
                "旧智能体",
                "旧角色",
                "旧目标",
                "旧背景会成为 soul",
                '["web_search_tavily"]',
                "provider_a",
                "model_a",
                now,
                now,
            ),
        )
        db.commit()

        db.create_tables()

        columns = [
            row["name"] for row in db.execute("PRAGMA table_info(agents)").fetchall()
        ]
        assert "soul" in columns
        assert "role" not in columns
        assert "goal" not in columns
        assert "backstory" not in columns
        row = db.select_one("agents", where="id = ?", where_params=("agent_legacy",))
        assert row["soul"] == "旧背景会成为 soul"
        assert json.loads(row["tools"]) == ["web_search_tavily"]
        assert row["provider_id"] == "provider_a"
    finally:
        db.close()


def test_agent_service_exposes_soul_without_legacy_identity_fields(work_db: Database):
    service = AgentService(work_db)

    agent = service.create_agent(
        {
            "id": "agent_soul",
            "name": "Soul Agent",
            "soul": "只保留 soul",
            "role": "旧角色不应保存",
            "goal": "旧目标不应保存",
            "backstory": "旧背景不应保存",
        }
    )

    data = agent.to_dict()
    assert data["soul"] == "只保留 soul"
    assert "role" not in data
    assert "goal" not in data
    assert "backstory" not in data

    updated = service.update_agent("agent_soul", {"soul": "更新后的 soul"})
    assert updated is not None
    updated_data = updated.to_dict()
    assert updated_data["soul"] == "更新后的 soul"
    assert "role" not in updated_data
    assert "goal" not in updated_data
    assert "backstory" not in updated_data


@pytest.mark.asyncio
async def test_run_work_llm_call_emits_grouped_agent_call_events(monkeypatch):
    class StreamingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            run_ctx.writer({"event": "reasoning", "data": {"text": "先判断是否需要搜索。"}})
            run_ctx.writer(
                {
                    "event": "tool_call",
                    "data": {"name": "web_search_tavily", "id": "tool_1", "query": "成都旅游"},
                }
            )
            run_ctx.writer(
                {
                    "event": "tool_result",
                    "data": {"name": "web_search_tavily", "id": "tool_1", "result": "搜索结果"},
                }
            )
            run_ctx.writer({"event": "text_delta", "data": {"text": "最终答案"}})
            return {
                "final_text": "最终答案",
                "stats": {"token_usage": {"input": 10, "output": 5}},
            }

    monkeypatch.setattr(work_task_module, "_agent_operator", StreamingOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )

    result = await work_task_module._run_work_llm_call(
        {
            "system_prompt": "系统提示词",
            "user_prompt": "用户提示词",
            "messages": [],
            "provider_id": "provider_a",
            "model": "model_a",
            "func_tools": ["web_search_tavily"],
            "session_id": "work",
            "trace_context": {"task_id": "task_call_group"},
        },
        run_ctx,
        node_id="execute",
        idle_timeout_seconds=10,
        step_id="step_1",
        agent_id="agent_executor",
        agent_label="执行智能体",
    )

    event_types = [event["event"] for event in events]
    assert event_types[0] == "agent_call_start"
    assert event_types[-1] == "agent_call_end"
    call_id = events[0]["data"]["call_id"]
    assert call_id
    assert result["_work_call_id"] == call_id
    for event in events:
        if event["event"] in {
            "agent_call_start",
            "agent_call_end",
            "reasoning",
            "tool_call",
            "tool_result",
            "text_delta",
            "token",
        }:
            assert event["data"]["call_id"] == call_id
    assert events[0]["data"]["input_payload"]["system_prompt"] == "系统提示词"
    assert events[0]["data"]["input_payload"]["func_tools"] == ["web_search_tavily"]
    assert "provider_id" not in events[0]["data"]["input_payload"]
    assert "model" not in events[0]["data"]["input_payload"]
    assert "trace_context" not in events[0]["data"]["input_payload"]
    assert next(event for event in events if event["event"] == "reasoning")["data"][
        "lane"
    ] == "reasoning"
    assert next(event for event in events if event["event"] == "tool_call")["data"][
        "lane"
    ] == "reasoning"
    assert next(event for event in events if event["event"] == "text_delta")["data"][
        "lane"
    ] == "output"
    assert events[-1]["data"]["agent_call_status"] == "completed"


@pytest.mark.asyncio
async def test_prepare_node_omits_assign_stage_for_new_work_flow():
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )

    result = await prepare_node(
        {
            "task_id": "task_no_assign_stage",
            "task_name": "无分配阶段",
            "plan_config": {"enabled": True, "task_mode": "normal"},
            "clarification_config": {"enabled": False},
            "review_config": {"enabled": False},
            "executor_config": {},
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    stage_ids = [step["id"] for step in result["stage_steps"]]
    assert stage_ids == [
        "stage_clarify",
        "stage_plan",
        "stage_execute",
        "stage_deliver",
    ]
    execute_stage = next(
        step for step in result["stage_steps"] if step["id"] == "stage_execute"
    )
    assert execute_stage["dependencies"] == ["stage_plan"]


def test_route_after_approval_goes_directly_to_execute():
    assert route_after_approval({"approval_action": "approve"}) == "execute"


@pytest.mark.asyncio
async def test_plan_node_repairs_resource_aware_plan_before_hitl(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    for agent_id, name in (
        ("agent_nicebot_work_assistant", "任务助手"),
        ("agent_nicebot_work_executor", "执行智能体"),
        ("agent_nicebot_work_reviewer", "审查智能体"),
    ):
        work_db.insert(
            "agents",
            {
                "id": agent_id,
                "name": name,
                "soul": "按资源感知方式工作。",
                "provider_id": "provider_agent",
                "model_name": "model_agent",
                "created_at": now,
                "updated_at": now,
            },
        )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    valid_plan = json.dumps(
        {
            "steps": [
                {
                    "id": "step_1",
                    "title": "完成调研",
                    "description": "收集任务所需资料",
                    "deliverable": "调研摘要",
                    "acceptance_criteria": ["资料来源清楚"],
                    "dependencies": [],
                    "executor_id": "executor",
                    "reviewer_id": "reviewer",
                    "resource_rationale": "需要通用执行者完成信息整理",
                }
            ]
        },
        ensure_ascii=False,
    )

    class RepairingOperator:
        def __init__(self):
            self.calls = []

        async def execute(self, state, run_ctx, write_stream=True):
            self.calls.append(state)
            if len(self.calls) == 1:
                return {
                    "final_text": json.dumps(
                        {
                            "steps": [
                                {
                                    "id": "step_1",
                                    "title": "完成调研",
                                    "description": "收集资料",
                                    "deliverable": "调研摘要",
                                    "acceptance_criteria": ["资料来源清楚"],
                                    "dependencies": [],
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    "stats": {},
                }
            return {"final_text": valid_plan, "stats": {}}

    operator = RepairingOperator()
    monkeypatch.setattr(work_task_module, "_agent_operator", operator)
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    result = await plan_node(
        {
            "task_name": "资源感知规划",
            "task_desc": "规划时完成执行资源分配",
            "session_id": "work",
            "task_mode": "normal",
            "executor_config": {
                "default_agents": {
                    "assistant": "agent_nicebot_work_assistant",
                    "executor": "agent_nicebot_work_executor",
                    "reviewer": "agent_nicebot_work_reviewer",
                }
            },
            "plan_config": {"enabled": True, "task_mode": "normal"},
            "stage_steps": [{"id": "stage_plan", "status": "running"}],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert len(operator.calls) == 2
    first_prompt = operator.calls[0]["user_prompt"]
    assert "资源感知规划协议" in first_prompt
    assert "常规模式" in first_prompt
    assert "executor_id" in first_prompt
    assert result["plan_steps"][0]["executor_id"] == "agent_nicebot_work_executor"
    assert result["plan_steps"][0]["reviewer_id"] == "agent_nicebot_work_reviewer"
    assert any(
        event["data"].get("phase") == "plan_validation_failed" for event in events
    )
    assert any(event["data"].get("phase") == "plan_auto_repair" for event in events)
    assert any(
        event["data"].get("phase") == "plan_validation_passed" for event in events
    )
    assert not any(
        event["event"] == "text_delta"
        and not event["data"].get("call_id")
        for event in events
    )


@pytest.mark.asyncio
async def test_clarify_confirm_does_not_emit_synthetic_llm_output(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeInteractionManager:
        async def send_and_wait(self, card, **kwargs):
            return InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="confirm",
                field_values={"travel_days": "3天"},
                responded_at=0,
            )

    monkeypatch.setattr(
        work_task_module, "get_interaction_manager", lambda: FakeInteractionManager()
    )
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )

    result = await clarify_node(
        {
            "task_id": "task_clarify_no_fake_output",
            "task_name": "成都旅游攻略",
            "task_desc": "做一个成都旅游攻略",
            "clarification_config": {
                "enabled": True,
                "content_provider_type": "static",
                "content_payload": {
                    "confirmation_items": [
                        {
                            "key": "travel_days",
                            "label": "旅行天数",
                            "field_type": "select",
                            "recommended": "3天",
                            "options": ["3天", "4天"],
                        }
                    ]
                },
            },
            "stage_steps": [
                {"id": "stage_clarify", "status": "running"},
                {"id": "stage_plan", "status": "pending"},
            ],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["clarification_action"] == "confirm"
    assert not any(
        event["event"] == "text_delta"
        and "需求已确认" in str(event["data"].get("text") or "")
        for event in events
    )


@pytest.mark.asyncio
async def test_approve_plan_preserves_validated_execution_tree_and_starts_execute(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeInteractionManager:
        async def send_and_wait(self, card, **kwargs):
            assert "执行者" in card.body
            assert "交付物" in card.body
            return InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="approve",
                field_values={},
                responded_at=0,
            )

    monkeypatch.setattr(
        work_task_module, "get_interaction_manager", lambda: FakeInteractionManager()
    )
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )
    validated_steps = [
        {
            "id": "step_1",
            "title": "执行计划",
            "description": "完成任务",
            "deliverable": "交付物",
            "acceptance_criteria": ["可直接使用"],
            "dependencies": [],
            "executor_id": "agent_nicebot_work_executor",
            "reviewer_id": "agent_nicebot_work_reviewer",
        }
    ]

    result = await approve_plan_node(
        {
            "task_id": "task_approve",
            "task_name": "审批资源计划",
            "plan_steps": validated_steps,
            "plan_text_full": "这只是展示文本，不应该被重新解析为旧 Markdown。",
            "stage_steps": [
                {"id": "stage_plan", "status": "running"},
                {"id": "stage_execute", "status": "pending"},
            ],
            "plan_config": {},
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["plan_steps"] == validated_steps
    assert "stage_assign" not in [step["id"] for step in result["stage_steps"]]
    assert next(
        step for step in result["stage_steps"] if step["id"] == "stage_execute"
    )["status"] == "running"


def test_work_config_roundtrip_initializes_daily_defaults(work_db: Database):
    service = WorkConfigService(work_db)

    config = service.get_config()

    assert config["daily"]["clarification"]["standard"]["agent_id"]
    assert "confirmation_items" in config["daily"]["clarification"]["standard"]["prompt"]
    assert config["daily"]["clarification"]["interrogation"]["max_rounds"] == 5
    assert config["daily"]["planning"]["quick"]["agent_id"]
    assert config["daily"]["deliverable"]["reporter_agent_id"]

    updated = service.update_config(
        {
            "daily": {
                "clarification": {
                    "standard": {
                        "agent_id": "agent_custom_clarifier",
                        "system_prompt": "自定义需求确认系统提示词",
                        "prompt": "自定义需求确认用户提示词",
                    },
                    "interrogation": {"max_rounds": 3},
                },
                "planning": {
                    "quick": {
                        "agent_id": "agent_custom_planner",
                        "system_prompt": "快速规划系统提示词",
                        "prompt": "快速规划用户提示词",
                    }
                },
            }
        }
    )

    assert (
        updated["daily"]["clarification"]["standard"]["agent_id"]
        == "agent_custom_clarifier"
    )
    assert updated["daily"]["clarification"]["interrogation"]["max_rounds"] == 3
    assert updated["daily"]["planning"]["quick"]["agent_id"] == "agent_custom_planner"


@pytest.mark.asyncio
async def test_create_task_uses_work_config_as_runtime_source(
    work_db: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    service = WorkService(work_db)
    WorkConfigService(work_db).update_config(
        {
            "daily": {
                "clarification": {
                    "standard": {
                        "agent_id": "agent_config_clarifier",
                        "system_prompt": "配置里的需求确认系统提示词",
                        "prompt": "配置里的需求确认用户提示词",
                    },
                    "interrogation": {
                        "agent_id": "agent_config_interrogator",
                        "system_prompt": "配置里的拷问系统提示词",
                        "prompt": "配置里的拷问用户提示词",
                        "max_rounds": 4,
                    },
                },
                "planning": {
                    "quick": {
                        "agent_id": "agent_config_quick_planner",
                        "system_prompt": "配置里的快速规划系统提示词",
                        "prompt": "配置里的快速规划用户提示词",
                    }
                },
                "deliverable": {
                    "reporter_agent_id": "agent_config_reporter",
                    "system_prompt": "配置里的交付系统提示词",
                    "prompt": "配置里的交付用户提示词",
                    "artifact_type": "markdown",
                },
            }
        }
    )
    daily = service.create_daily_dir(
        {
            "name": "默认池",
            "directory": str(tmp_path / "daily-pool"),
            "default_rules": "测试",
        }
    )
    captured = {}

    async def fake_start(graph_type, graph_config):
        captured["graph_type"] = graph_type
        captured["graph_config"] = graph_config
        return {"started": True, "task_id": graph_config["task_id"]}

    monkeypatch.setattr(service, "_start_task_center_task", fake_start)

    task = await service.create_task(
        {
            "name": "配置来源测试",
            "description": "验证 Work 配置唯一来源",
            "work_scope": "daily",
            "work_daily_dir_id": daily["id"],
            "plan_config": {"task_mode": "quick", "approval_enabled": False},
            "clarification_config": {"interrogation_enabled": True},
        }
    )

    assert captured["graph_type"] == "work_task"
    graph_config = captured["graph_config"]
    assert graph_config["task_id"] == task["id"]
    assert graph_config["plan_config"]["enabled"] is True
    assert graph_config["plan_config"]["approval_enabled"] is False
    assert graph_config["plan_config"]["agent_id"] == "agent_config_quick_planner"
    assert graph_config["plan_config"]["system_prompt"] == "配置里的快速规划系统提示词"
    assert graph_config["plan_config"]["prompt_template"] == "配置里的快速规划用户提示词"
    assert graph_config["clarification_config"]["content_provider_agent_id"] == "agent_config_clarifier"
    assert graph_config["clarification_config"]["interrogation_enabled"] is True
    assert graph_config["clarification_config"]["interrogation_agent_id"] == "agent_config_interrogator"
    assert graph_config["clarification_config"]["interrogation_max_rounds"] == 4
    assert graph_config["executor_config"]["reporter_agent_id"] == "agent_config_reporter"
    row = work_db.select_one("agent_tasks", where="id = ?", where_params=(task["id"],))
    assert json.loads(row["plan_config"])["approval_enabled"] is False


@pytest.mark.asyncio
async def test_approve_plan_auto_approves_when_manual_approval_disabled():
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )
    steps = [
        {
            "id": "step_1",
            "title": "执行计划",
            "description": "完成任务",
            "deliverable": "交付物",
            "acceptance_criteria": ["可直接使用"],
            "dependencies": [],
            "executor_id": "agent_nicebot_work_executor",
        }
    ]

    result = await approve_plan_node(
        {
            "task_id": "task_auto_approve",
            "task_name": "自动审批",
            "plan_steps": steps,
            "stage_steps": [
                {"id": "stage_plan", "status": "running"},
                {"id": "stage_execute", "status": "pending"},
            ],
            "plan_config": {"approval_enabled": False},
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["approval_action"] == "approve"
    assert result["plan_steps"] == steps
    assert next(
        step for step in result["stage_steps"] if step["id"] == "stage_execute"
    )["status"] == "running"
    assert any(
        event["data"].get("phase") == "plan_auto_approved" for event in events
    )
    assert not any(event["event"] == "interaction" for event in events)


@pytest.mark.asyncio
async def test_clarify_interrogation_asks_before_standard_confirmation(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    class FakeInteractionManager:
        async def send_and_wait(self, card, **kwargs):
            captured["card"] = card
            return InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="submit",
                field_values={"interrogation_answer": "目标用户是团队负责人，验收标准是可执行清单。"},
                responded_at=0,
            )

    async def fake_llm_call(*args, **kwargs):
        return {
            "final_text": json.dumps(
                {
                    "status": "ask",
                    "value_assessment": "价值方向可行，但目标用户和验收标准不清楚。",
                    "questions": ["目标用户是谁？", "验收标准是什么？"],
                },
                ensure_ascii=False,
            ),
            "stats": {},
        }

    monkeypatch.setattr(
        work_task_module, "get_interaction_manager", lambda: FakeInteractionManager()
    )
    monkeypatch.setattr(work_task_module, "_run_work_llm_call", fake_llm_call)
    monkeypatch.setattr(
        work_task_module,
        "_resolve_work_agent_runtime",
        lambda *args, **kwargs: {
            "agent_id": "agent_interrogator",
            "agent_label": "拷问助手",
            "provider_id": "provider",
            "model": "model",
            "func_tools": [],
            "soul": "",
        },
    )
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=None,
        config={},
        writer=events.append,
    )

    result = await clarify_node(
        {
            "task_id": "task_interrogate",
            "task_name": "做一份方案",
            "task_desc": "帮我做方案",
            "clarification_config": {
                "enabled": True,
                "interrogation_enabled": True,
                "interrogation_agent_id": "agent_interrogator",
                "interrogation_max_rounds": 5,
            },
            "stage_steps": [{"id": "stage_clarify", "status": "running"}],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert captured["card"].type == "clarification_interrogation"
    assert "目标用户是谁" in captured["card"].body
    assert result["clarification_action"] == "interrogate_more"
    assert result["interrogation_round"] == 1
    assert result["interrogation_history"][0]["answer"].startswith("目标用户")
    assert any(event["event"] == "interaction" for event in events)


def test_work_service_clear_work_history_removes_only_work_runtime_data(
    work_db: Database,
):
    service = WorkService(work_db)
    now = datetime.now().isoformat()
    for table in (
        "work_items",
        "work_runs",
        "work_run_nodes",
        "work_events",
        "work_os_artifacts",
    ):
        work_db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY)")
        work_db.insert(table, {"id": f"{table}_old"})
    work_db.insert(
        "agent_tasks",
        {
            "id": "work_task_1",
            "name": "旧 Work",
            "task_type": "work_task",
            "category": "work",
            "status": "failed",
            "created_at": now,
            "updated_at": now,
        },
    )
    work_db.insert(
        "agent_tasks",
        {
            "id": "meeting_task_1",
            "name": "会议任务",
            "task_type": "meeting_task",
            "category": "meeting",
            "status": "completed",
            "created_at": now,
            "updated_at": now,
        },
    )
    work_db.insert(
        "execution_logs",
        {
            "id": "log_work_1",
            "task_id": "work_task_1",
            "level": "info",
            "message": "旧日志",
            "created_at": now,
        },
    )
    work_db.insert(
        "work_task_steps",
        {
            "id": "work_task_1:step_1",
            "task_id": "work_task_1",
            "title": "旧步骤",
            "updated_at": now,
        },
    )
    work_db.insert(
        "work_artifacts",
        {
            "id": "artifact_work_1",
            "task_id": "work_task_1",
            "title": "旧交付物",
            "created_at": now,
        },
    )
    work_db.insert(
        "hitl_requests",
        {
            "id": "hitl_work_1",
            "task_id": "work_task_1",
            "scope": "work",
            "interaction_type": "plan_approval",
            "title": "旧审批",
            "status": "pending",
            "created_at": now,
        },
    )

    result = service.clear_work_history()
    result_again = service.clear_work_history()

    assert result["deleted_tasks"] == 1
    assert result_again["deleted_tasks"] == 0
    assert result["deleted_work_os_rows"] == 5
    assert result_again["deleted_work_os_rows"] == 0
    assert (
        work_db.select_one("agent_tasks", where="id = ?", where_params=("work_task_1",))
        is None
    )
    assert (
        work_db.select_one(
            "agent_tasks", where="id = ?", where_params=("meeting_task_1",)
        )
        is not None
    )
    assert (
        work_db.select_all(
            "execution_logs", where="task_id = ?", where_params=("work_task_1",)
        )
        == []
    )
    assert (
        work_db.select_all(
            "work_task_steps", where="task_id = ?", where_params=("work_task_1",)
        )
        == []
    )
    assert (
        work_db.select_all(
            "work_artifacts", where="task_id = ?", where_params=("work_task_1",)
        )
        == []
    )
    assert (
        work_db.select_all(
            "hitl_requests", where="task_id = ?", where_params=("work_task_1",)
        )
        == []
    )
    for table in (
        "work_items",
        "work_runs",
        "work_run_nodes",
        "work_events",
        "work_os_artifacts",
    ):
        assert work_db.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
            "count"
        ] == 0


@pytest.mark.asyncio
async def test_work_service_pause_resume_and_terminate_controls_task(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    now = datetime.now().isoformat()
    work_db.insert(
        "agent_tasks",
        {
            "id": "work_control_1",
            "name": "可控 Work",
            "task_type": "work_task",
            "category": "work",
            "status": "running",
            "thread_id": "work:control",
            "created_at": now,
            "updated_at": now,
        },
    )
    calls: list[tuple[str, str, object]] = []

    class FakeTaskCenter:
        async def request_pause_task(self, task_id: str):
            calls.append(("pause", task_id, None))

        async def resume_task(self, task_id: str, resume_value):
            calls.append(("resume", task_id, resume_value))

        async def cancel_task(self, task_id: str):
            calls.append(("terminate", task_id, None))

    monkeypatch.setattr(
        "astrbot.core.langgraph.task_tools.get_task_center",
        lambda: FakeTaskCenter(),
    )

    service = WorkService(work_db)
    paused_request = await service.pause_task("work_control_1")

    assert paused_request["status"] == "pause_requested"
    assert calls == [("pause", "work_control_1", None)]
    assert work_db.select_one(
        "agent_tasks", where="id = ?", where_params=("work_control_1",)
    )["status"] == "pause_requested"

    work_db.update(
        "agent_tasks",
        {"status": "paused"},
        where="id = ?",
        where_params=("work_control_1",),
    )
    resumed = await service.resume_task("work_control_1")

    assert resumed["status"] == "running"
    assert calls[-1] == ("resume", "work_control_1", {"action": "resume"})

    terminated = await service.terminate_task("work_control_1")

    assert terminated["status"] == "cancelled"
    assert calls[-1] == ("terminate", "work_control_1", None)
    logs = work_db.select_all(
        "execution_logs", where="task_id = ?", where_params=("work_control_1",)
    )
    assert any(
        (json.loads(log["data"]) if isinstance(log["data"], str) else log["data"]).get(
            "event"
        )
        == "terminated_by_user"
        for log in logs
    )


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

    row = work_db.select_one(
        "work_projects", where="id = ?", where_params=(project["id"],)
    )
    assert row is not None
    assert row["goal"] == "交付可运行版本"
    assert row["rules"] == "所有修改必须经过审查。"
    assert (project_dir / ".nicebot" / "goal.md").read_text(
        encoding="utf-8"
    ) == "交付可运行版本"
    assert (project_dir / ".nicebot" / "rules.md").read_text(
        encoding="utf-8"
    ) == "所有修改必须经过审查。"

    updated = service.update_project(
        project["id"], {"goal": "按里程碑交付", "rules": "先测后交付。"}
    )
    assert updated["goal"] == "按里程碑交付"
    assert (project_dir / ".nicebot" / "goal.md").read_text(
        encoding="utf-8"
    ) == "按里程碑交付"
    assert (project_dir / ".nicebot" / "rules.md").read_text(
        encoding="utf-8"
    ) == "先测后交付。"


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
async def test_work_task_center_context_includes_tool_event(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, object] = {}

    class FakeContext:
        def get_config(self, umo=None):
            return {"umo": umo, "provider_settings": {}}

    class FakeTaskRecord:
        task_id = "task_record_1"
        thread_id = "thread_1"

    class FakeTaskCenter:
        async def create_task(self, task_type, config, session_id, run_ctx):
            captured["task_type"] = task_type
            captured["config"] = config
            captured["session_id"] = session_id
            captured["run_ctx"] = run_ctx
            return FakeTaskRecord()

    monkeypatch.setattr(
        "astrbot.core.langgraph.task_tools.get_task_center",
        lambda: FakeTaskCenter(),
    )
    context = FakeContext()
    service = WorkService(work_db, context=context)

    result = await service._start_task_center_task(
        "work_task",
        {
            "task_id": "work_1",
            "thread_id": "thread_1",
            "task_name": "工具上下文验收",
            "description": "需要本地工具可以拿到 event 和 Context",
        },
    )

    assert result["started"] is True
    run_ctx = captured["run_ctx"]
    astr_event = run_ctx.astr_event
    event = getattr(astr_event, "event", astr_event)
    assert getattr(astr_event, "context", None) is context
    assert event.unified_msg_origin == "nicebot_work:FriendMessage:work_1"
    assert "工具上下文验收" in event.message_str
    assert "需要本地工具可以拿到 event 和 Context" in event.message_str
    assert event.role == "admin"
    assert event.get_sender_id() == "nicebot_work"


@pytest.mark.asyncio
async def test_plan_node_fails_without_fallback_card_on_llm_error(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "任务助手",
            "soul": "负责规划。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class FailingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            return {"final_text": "", "error": "peer closed connection", "stats": {}}

    monkeypatch.setattr(work_task_module, "_agent_operator", FailingOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    with pytest.raises(RuntimeError, match="peer closed connection"):
        await plan_node(
            {
                "task_name": "成都旅游攻略",
                "task_desc": "成都旅游攻略",
                "session_id": "work",
                "plan_config": {"enabled": True},
                "stage_steps": [
                    {"id": "stage_plan", "status": "running"},
                    {"id": "stage_execute", "status": "pending"},
                ],
            },
            {"configurable": {"run_ctx": run_ctx}},
        )

    assert not any(
        event["event"] == "text_delta" and "明确任务目标和约束" in str(event["data"])
        for event in events
    )
    assert any(
        event["event"] == "error"
        and "peer closed connection" in event["data"].get("message", "")
        for event in events
    )
    assert any(
        event["event"] == "phase"
        and event["data"].get("phase") == "plan_failed"
        for event in events
    )


@pytest.mark.asyncio
async def test_plan_node_uses_idle_timeout_instead_of_total_timeout(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "任务助手",
            "soul": "负责规划。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class SlowStreamingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            plan_json = json.dumps(
                {
                    "steps": [
                        {
                            "id": "step_1",
                            "title": "调研",
                            "description": "收集资料",
                            "deliverable": "资料",
                            "acceptance_criteria": ["资料完整"],
                            "dependencies": [],
                            "executor_id": "executor",
                            "reviewer_id": "reviewer",
                            "resource_rationale": "通用执行者可完成资料整理",
                        },
                        {
                            "id": "step_2",
                            "title": "输出",
                            "description": "形成报告",
                            "deliverable": "报告",
                            "acceptance_criteria": ["报告可直接使用"],
                            "dependencies": ["step_1"],
                            "executor_id": "executor",
                            "reviewer_id": "reviewer",
                            "resource_rationale": "通用执行者可完成内容输出",
                        },
                    ]
                },
                ensure_ascii=False,
            )
            run_ctx.writer(
                {
                    "event": "text_delta",
                    "data": {"text": plan_json[: len(plan_json) // 2]},
                    "timestamp": 0,
                    "node_id": "plan",
                }
            )
            await asyncio.sleep(0.03)
            run_ctx.writer(
                {
                    "event": "text_delta",
                    "data": {"text": plan_json[len(plan_json) // 2 :]},
                    "timestamp": 0,
                    "node_id": "plan",
                }
            )
            return {
                "final_text": plan_json,
                "stats": {},
            }

    monkeypatch.setattr(work_task_module, "_agent_operator", SlowStreamingOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    result = await plan_node(
        {
            "task_name": "成都旅游攻略",
            "task_desc": "成都旅游攻略",
            "session_id": "work",
            "plan_config": {
                "enabled": True,
                "timeout_seconds": 0.01,
                "idle_timeout_seconds": 1,
            },
            "stage_steps": [
                {"id": "stage_plan", "status": "running"},
                {"id": "stage_execute", "status": "pending"},
            ],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert "调研" in result["plan_text_full"]
    assert any(
        event["event"] == "text_delta"
        and "调研" in event["data"].get("text", "")
        for event in events
    )
    assert not any(
        event["event"] == "error"
        and "超过" in event["data"].get("message", "")
        for event in events
    )


@pytest.mark.asyncio
async def test_plan_node_fails_after_idle_timeout_without_activity(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "任务助手",
            "soul": "负责规划。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class HangingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            await asyncio.sleep(1)
            return {"final_text": "不应返回", "stats": {}}

    monkeypatch.setattr(work_task_module, "_agent_operator", HangingOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    with pytest.raises(RuntimeError, match="连续 0.05 秒无模型或工具输出"):
        await plan_node(
            {
                "task_name": "成都旅游攻略",
                "task_desc": "成都旅游攻略",
                "session_id": "work",
                "plan_config": {"enabled": True, "idle_timeout_seconds": 0.05},
                "stage_steps": [
                    {"id": "stage_plan", "status": "running"},
                    {"id": "stage_execute", "status": "pending"},
                ],
            },
            {"configurable": {"run_ctx": run_ctx}},
        )

    assert any(
        event["event"] == "error"
        and "连续 0.05 秒无模型或工具输出" in event["data"].get("message", "")
        for event in events
    )


@pytest.mark.asyncio
async def test_clarify_content_forwards_tool_events_without_streaming_text(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "任务助手",
            "soul": "负责需求明确。",
            "tools": '["web_search_tavily"]',
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class ToolCallingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            assert write_stream is True
            run_ctx.writer(
                {
                    "event": "tool_call",
                    "data": {
                        "event": "tool_call",
                        "name": "web_search_tavily",
                        "query": "成都旅游攻略",
                        "stage_id": "stage_clarify",
                    },
                    "timestamp": 0,
                    "node_id": "clarify",
                }
            )
            run_ctx.writer(
                {
                    "event": "text_delta",
                    "data": {"event": "text_delta", "text": "不应被透传"},
                    "timestamp": 0,
                    "node_id": "clarify",
                }
            )
            run_ctx.writer(
                {
                    "event": "tool_result",
                    "data": {
                        "event": "tool_result",
                        "name": "web_search_tavily",
                        "result": "搜索结果",
                        "stage_id": "stage_clarify",
                    },
                    "timestamp": 0,
                    "node_id": "clarify",
                }
            )
            return {
                "final_text": json.dumps(
                    {
                        "confirmation_items": [
                            {
                                "key": "days",
                                "label": "旅行天数",
                                "field_type": "select",
                                "recommended": "推荐：3天",
                                "options": ["推荐：3天", "4天", "5天"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                "stats": {},
            }

    monkeypatch.setattr(work_task_module, "_agent_operator", ToolCallingOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    content = await work_task_module._agent_clarify_content(
        {"content_provider_agent_id": "agent_nicebot_work_assistant"},
        {
            "task_name": "成都旅游攻略",
            "task_desc": "成都旅游攻略",
            "session_id": "work",
        },
        run_ctx,
    )

    assert content["confirmation_items"][0]["key"] == "days"
    event_names = [event["event"] for event in events]
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert not any(
        event["event"] == "text_delta"
        and event["data"].get("text") == "不应被透传"
        for event in events
    )


def test_builtin_daily_work_flow_schema_v3_exposes_runtime_nodes(work_db: Database):
    flow_service = FlowService(work_db)
    flow_service.ensure_builtin_daily_work_flow()
    flow = flow_service.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)

    assert flow is not None
    assert flow.metadata["schema_version"] == 6
    assert flow.metadata["topology_locked"] is True
    node_ids = {node.id for node in flow.nodes}
    assert {"daily_mode_strategy", "daily_review_gate", "daily_rework_hitl"}.issubset(
        node_ids
    )
    validation = flow_service.validate_flow(BUILTIN_DAILY_WORK_FLOW_ID)
    assert validation["success"] is True


def test_builtin_daily_work_flow_upgrade_refreshes_clarification_prompt(
    work_db: Database,
):
    flow_service = FlowService(work_db)
    flow_service.reset_builtin_daily_work_flow()

    flow = flow_service.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)
    metadata = dict(flow.metadata)
    metadata["schema_version"] = 4
    work_db.update(
        "flows",
        {"metadata": metadata},
        where="id = ?",
        where_params=(BUILTIN_DAILY_WORK_FLOW_ID,),
    )
    old_config = next(node.config for node in flow.nodes if node.id == "daily_clarify")
    old_config["content_prompt"] = "请返回 confirmation_items JSON。"
    work_db.update(
        "flow_nodes",
        {"config": old_config},
        where="id = ? AND flow_id = ?",
        where_params=("daily_clarify", BUILTIN_DAILY_WORK_FLOW_ID),
    )

    flow_service.ensure_builtin_daily_work_flow()
    upgraded = flow_service.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)
    clarify = next(node for node in upgraded.nodes if node.id == "daily_clarify")
    plan = next(node for node in upgraded.nodes if node.id == "daily_plan")
    execute = next(node for node in upgraded.nodes if node.id == "daily_execute")

    assert upgraded.metadata["schema_version"] == 6
    assert '"confirmation_items"' in clarify.config["content_prompt"]
    assert "不要使用泛化的固定字段" in clarify.config["content_prompt"]
    assert plan.config["output"] == "resource_aware_execution_tree"
    assert "资源感知规划智能体" in plan.config["system_prompt"]
    assert "执行资源分配" in plan.config["prompt"]
    assert "assignment_system_prompt" not in execute.config


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

    assert (
        runtime["clarification_config"]["template_id"]
        == "builtin_work_requirement_clarification"
    )
    assert '"confirmation_items"' in runtime["clarification_config"]["content_prompt"]
    assert "不要使用泛化的固定字段" in runtime["clarification_config"]["content_prompt"]
    assert runtime["plan_config"]["task_mode"] == "normal"
    assert runtime["plan_config"]["output"] == "resource_aware_execution_tree"
    assert "执行资源分配" in runtime["plan_config"]["prompt_template"]
    assert runtime["executor_config"]["execute_prompt_template"]
    assert (
        runtime["executor_config"]["executor_agent_id"] == "agent_nicebot_work_executor"
    )
    assert "assignment_system_prompt" not in runtime["executor_config"]
    assert runtime["review_config"]["rework_title"] == "审查未通过"


@pytest.mark.asyncio
async def test_create_work_task_persists_scope_configs_and_input(
    work_db: Database, tmp_path: Path
):
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
    plan_config = json.loads(row["plan_config"])
    assert plan_config["enabled"] is True
    assert plan_config["approval_enabled"] is False
    review_config = json.loads(row["review_config"])
    assert review_config["enabled"] is True
    assert review_config["max_rework"] == 2
    assert json.loads(row["input"])["work_context"]["rules"] == "保留执行记录。"

    supplemental = service.submit_input(task["id"], "补充：交付物要包含风险清单。")
    assert supplemental["decision"] == "inject_next_llm_call"
    updated = work_db.select_one(
        "agent_tasks", where="id = ?", where_params=(task["id"],)
    )
    assert "风险清单" in updated["pending_input"]
    assert service.get_task(task["id"])["logs"]


@pytest.mark.asyncio
async def test_create_task_default_task_mode_is_normal(
    work_db: Database, tmp_path: Path
):
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
async def test_create_task_invalid_task_mode_normalized(
    work_db: Database, tmp_path: Path
):
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


def test_parse_steps_preserves_deliverable_lines():
    steps = _parse_steps(
        "1. 确定行程框架与核心区域\n"
        "   交付物：3-5天成都旅游行程框架\n"
        "   1.1 根据天数划分每日节奏\n"
    )

    assert steps[0]["deliverable"] == "3-5天成都旅游行程框架"
    assert "交付物：3-5天成都旅游行程框架" in steps[0]["description"]


def test_collect_executable_steps():
    steps = [
        {
            "id": "step_1",
            "depth": 1,
            "children": [
                {"id": "step_1_1", "depth": 2},
                {"id": "step_1_2", "depth": 2},
            ],
        },
        {"id": "step_2", "depth": 1, "children": []},
    ]
    executable = _collect_executable_steps(steps)
    assert len(executable) == 3
    assert executable[0]["id"] == "step_1_1"
    assert executable[1]["id"] == "step_1_2"
    assert executable[2]["id"] == "step_2"


def test_route_after_execute_uses_task_mode_for_normal_parent_steps():
    steps = [
        {
            "id": "step_1",
            "depth": 1,
            "children": [
                {"id": "step_1_1", "depth": 2},
                {"id": "step_1_2", "depth": 2},
            ],
        },
        {"id": "step_2", "depth": 1, "children": []},
    ]

    assert (
        route_after_execute(
            {
                "task_mode": "normal",
                "plan_config": {"task_mode": "normal"},
                "plan_steps": steps,
                "current_step_index": 2,
            }
        )
        == "review"
    )


@pytest.mark.asyncio
async def test_clarify_node_emits_llm_draft_before_hitl(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "需求助手",
            "soul": "先理解需求再生成确认项。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class CapturingOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            return {
                "final_text": json.dumps(
                    {
                        "confirmation_items": [
                            {
                                "key": "scope",
                                "label": "任务范围",
                                "description": "确认任务范围",
                                "field_type": "select",
                                "required": True,
                                "recommended": "推荐：当前范围",
                                "options": ["推荐：当前范围", "扩大范围", "缩小范围"],
                                "allow_custom": True,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                "reasoning_text": "我先判断任务范围。",
                "stats": {},
            }

    class FakeInteractionManager:
        async def send_and_wait(self, card, **kwargs):
            assert card.fields[0].key == "scope"
            return InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="confirm",
                field_values={"scope": "推荐：当前范围"},
                responded_at=0,
            )

    monkeypatch.setattr(work_task_module, "_agent_operator", CapturingOperator())
    monkeypatch.setattr(
        work_task_module, "get_interaction_manager", lambda: FakeInteractionManager()
    )
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    await clarify_node(
        {
            "task_id": "task_clarify",
            "session_id": "session_clarify",
            "task_name": "验收任务",
            "task_desc": "检查需求明确节点",
            "clarification_config": {
                "enabled": True,
                "content_provider_type": "agent",
                "content_provider_agent_id": "agent_nicebot_work_assistant",
            },
            "executor_config": {
                "default_agents": {"assistant": "agent_nicebot_work_assistant"}
            },
            "stage_steps": [],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    text_idx = next(
        idx
        for idx, event in enumerate(events)
        if event["event"] == "text_delta"
        and "需求确认草案" in event["data"].get("text", "")
    )
    hitl_idx = next(idx for idx, event in enumerate(events) if event["event"] == "interaction")
    assert text_idx < hitl_idx


@pytest.mark.asyncio
async def test_clarify_node_exposes_parse_failure_before_fallback_card(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_work_assistant",
            "name": "需求助手",
            "soul": "先理解需求再生成确认项。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class BadJsonOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            return {"final_text": "我理解这是一次验收任务，但这里不是 JSON。", "stats": {}}

    class FakeInteractionManager:
        async def send_and_wait(self, card, **kwargs):
            assert card.fields
            return InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="confirm",
                field_values={field.key: field.recommended or "确认" for field in card.fields},
                responded_at=0,
            )

    monkeypatch.setattr(work_task_module, "_agent_operator", BadJsonOperator())
    monkeypatch.setattr(
        work_task_module, "get_interaction_manager", lambda: FakeInteractionManager()
    )
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    await clarify_node(
        {
            "task_id": "task_bad_clarify",
            "session_id": "session_bad_clarify",
            "task_name": "验收任务",
            "task_desc": "检查兜底提示",
            "clarification_config": {
                "enabled": True,
                "content_provider_type": "agent",
                "content_provider_agent_id": "agent_nicebot_work_assistant",
            },
            "executor_config": {
                "default_agents": {"assistant": "agent_nicebot_work_assistant"}
            },
            "stage_steps": [],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    error_idx = next(
        idx
        for idx, event in enumerate(events)
        if event["event"] == "error"
        and "需求确认项解析失败" in event["data"].get("message", "")
    )
    hitl_idx = next(idx for idx, event in enumerate(events) if event["event"] == "interaction")
    assert error_idx < hitl_idx
    assert any(
        event["event"] == "text_delta"
        and "不是 JSON" in event["data"].get("text", "")
        for event in events
    )


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
        "input": {
            "goal": "交付可直接使用的旅游攻略",
            "work_context": {"rules": "预算要清楚"},
        },
        "clarification": {
            "travel_duration": "3-5天",
            "interest_focus": ["美食", "文化历史"],
        },
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


def test_step_scope_uses_explicit_dependencies_without_recent_result_fallback():
    steps = [
        {"id": "step_1", "title": "前置一", "description": "前置一"},
        {"id": "step_2", "title": "前置二", "description": "前置二"},
        {
            "id": "step_3",
            "title": "当前",
            "description": "当前",
            "dependencies": ["step_1"],
        },
    ]
    scope = _step_scope_text(
        {},
        steps,
        steps[2],
        [
            {"step_id": "step_1", "description": "前置一", "result": "应该出现"},
            {"step_id": "step_2", "description": "前置二", "result": "不应该出现"},
        ],
        "normal",
    )

    assert "应该出现" in scope
    assert "不应该出现" not in scope


def test_step_scope_without_dependencies_uses_result_index_not_full_recent_results():
    steps = [{"id": "step_3", "title": "当前", "description": "当前"}]
    long_result = "A" * 1400 + "关键结尾"
    scope = _step_scope_text(
        {},
        steps,
        steps[0],
        [
            {"step_id": "step_1", "description": "前置一", "result": "完整旧结果"},
            {"step_id": "step_2", "description": "前置二", "result": long_result},
        ],
        "normal",
    )

    assert "已完成结果索引" in scope
    assert "完整旧结果" not in scope
    assert long_result not in scope


@pytest.mark.asyncio
async def test_execute_node_requires_agent_llm_without_provider_fallback(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_no_llm",
            "name": "无模型智能体",
            "soul": "只能在配置了 LLM 后执行。",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FailingOperator:
        called = False

        async def execute(self, *args, **kwargs):
            self.called = True
            raise AssertionError("agent without provider must not call LLM")

    operator = FailingOperator()
    monkeypatch.setattr(work_task_module, "_agent_operator", operator)
    events = []
    run_ctx = GraphRunContext(
        provider=object(),
        tool_executor=None,
        hooks=None,
        astr_event=object(),
        config={},
        writer=events.append,
    )

    with pytest.raises(RuntimeError, match="未配置 LLM 提供商"):
        await execute_node(
            {
                "task_name": "测试任务",
                "task_desc": "验证不兜底 provider",
                "task_mode": "quick",
                "executor_config": {"default_agents": {"executor": "agent_no_llm"}},
                "plan_config": {"task_mode": "quick"},
                "plan_steps": [
                    {
                        "id": "step_1",
                        "description": "执行一步",
                        "status": "pending",
                        "executor_id": "agent_no_llm",
                    }
                ],
                "stage_steps": [],
                "step_results": [],
                "current_step_index": 0,
            },
            {"configurable": {"run_ctx": run_ctx}},
        )

    assert operator.called is False
    error_events = [event for event in events if event["event"] == "error"]
    assert error_events
    assert "无模型智能体" in error_events[-1]["data"]["message"]
    assert "未配置 LLM 提供商" in error_events[-1]["data"]["message"]


@pytest.mark.asyncio
async def test_execute_node_merges_agent_soul_tools_and_node_prompt(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_runtime",
            "name": "融合智能体",
            "soul": "这是智能体 soul。",
            "tools": ["web_search_tavily"],
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class CapturingOperator:
        def __init__(self):
            self.calls = []

        async def execute(self, state, run_ctx, write_stream=True):
            self.calls.append((state, run_ctx, write_stream))
            return {"final_text": "执行完成", "stats": {}}

    operator = CapturingOperator()
    monkeypatch.setattr(work_task_module, "_agent_operator", operator)
    events = []
    run_ctx = GraphRunContext(
        provider=object(),
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    result = await execute_node(
        {
            "task_name": "测试任务",
            "task_desc": "验证配置融合",
            "task_mode": "quick",
            "executor_config": {
                "default_agents": {"executor": "agent_runtime"},
                "execute_system_prompt": "节点要求：保持精简。",
                "tools": ["node_extra_tool", "web_search_tavily"],
            },
            "plan_config": {"task_mode": "quick"},
            "plan_steps": [
                {
                    "id": "step_1",
                    "description": "执行一步",
                    "status": "pending",
                    "executor_id": "agent_runtime",
                }
            ],
            "stage_steps": [],
            "step_results": [],
            "current_step_index": 0,
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["step_results"][0]["result"] == "执行完成"
    assert len(operator.calls) == 1
    state, _, write_stream = operator.calls[0]
    assert write_stream is True
    assert state["provider_id"] == "provider_agent"
    assert state["model"] == "model_agent"
    assert state["func_tools"] == ["web_search_tavily", "node_extra_tool"]
    assert state["messages"] == []
    assert state["compact_context"]["current_step_id"] == "step_1"
    assert "这是智能体 soul。" in state["system_prompt"]
    assert "节点要求：保持精简。" in state["system_prompt"]


@pytest.mark.asyncio
async def test_run_work_llm_call_retries_connection_error_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
):
    class FlakyOperator:
        def __init__(self):
            self.calls = 0

        async def execute(self, state, run_ctx, write_stream=True):
            self.calls += 1
            if self.calls == 1:
                return {
                    "final_text": "",
                    "error": "APIConnectionError: Connection error.",
                    "stats": {},
                }
            return {"final_text": "重试成功", "stats": {}}

    operator = FlakyOperator()
    monkeypatch.setattr(work_task_module, "_agent_operator", operator)
    monkeypatch.setattr(work_task_module, "_WORK_LLM_AUTO_RETRY_DELAYS_SECONDS", (0,))
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=object(),
        config={},
        writer=events.append,
    )

    result = await work_task_module._run_work_llm_call(
        {
            "provider_id": "provider_a",
            "model": "model_a",
            "trace_context": {"node_id": "plan"},
        },
        run_ctx,
        node_id="plan",
        idle_timeout_seconds=1,
    )

    assert operator.calls == 2
    assert result["final_text"] == "重试成功"
    assert any(
        event["event"] == "phase"
        and event["data"].get("phase") == "llm_auto_retry"
        for event in events
    )


@pytest.mark.asyncio
async def test_execute_node_stream_error_after_partial_output_marks_step_failed(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_runtime",
            "name": "执行智能体",
            "soul": "执行任务。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class BrokenStreamOperator:
        async def execute(self, state, run_ctx, write_stream=True):
            run_ctx.writer(
                {
                    "event": "text_delta",
                    "data": {"text": "已经输出一部分"},
                    "node_id": "execute",
                }
            )
            return {
                "final_text": "",
                "error": "RemoteProtocolError: peer closed connection without sending complete message body (incomplete chunked read)",
                "stats": {},
            }

    monkeypatch.setattr(work_task_module, "_agent_operator", BrokenStreamOperator())
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )
    state = {
        "task_name": "执行失败验收",
        "task_desc": "验证错误后不标记完成",
        "task_mode": "quick",
        "executor_config": {"default_agents": {"executor": "agent_runtime"}},
        "plan_config": {"task_mode": "quick"},
        "plan_steps": [
            {
                "id": "step_1",
                "description": "执行一步",
                "status": "pending",
                "executor_id": "agent_runtime",
            }
        ],
        "stage_steps": [],
        "step_results": [],
        "current_step_index": 0,
    }

    with pytest.raises(work_task_module.WorkLLMCallError):
        await execute_node(state, {"configurable": {"run_ctx": run_ctx}})

    phase_events = [event for event in events if event["event"] == "phase"]
    assert any(
        event["data"].get("phase") == "step_failed"
        and event["data"].get("status") == "retryable_failed"
        for event in phase_events
    )
    assert state["plan_steps"][0]["status"] != "done"


@pytest.mark.asyncio
async def test_finalize_node_sends_all_step_results(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(agent_database, "_db", work_db)
    now = datetime.now().isoformat()
    work_db.insert(
        "agents",
        {
            "id": "agent_nicebot_report_expert",
            "name": "汇报专家",
            "soul": "整理全部执行结果。",
            "provider_id": "provider_agent",
            "model_name": "model_agent",
            "created_at": now,
            "updated_at": now,
        },
    )

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object() if provider_id == "provider_agent" else None

    class CapturingOperator:
        def __init__(self):
            self.calls = []

        async def execute(self, state, run_ctx, write_stream=True):
            self.calls.append(state)
            return {"final_text": "最终交付", "stats": {}}

    operator = CapturingOperator()
    monkeypatch.setattr(work_task_module, "_agent_operator", operator)
    events = []
    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=FakeContext(),
        config={},
        writer=events.append,
    )

    result = await finalize_node(
        {
            "task_name": "交付验收",
            "executor_config": {
                "default_agents": {"reporter": "agent_nicebot_report_expert"}
            },
            "stage_steps": [],
            "step_results": [
                {"step_id": "step_1", "description": "第一步", "result": "结果一"},
                {"step_id": "step_2", "description": "第二步", "result": "结果二"},
                {"step_id": "step_3", "description": "第三步", "result": "结果三"},
            ],
        },
        {"configurable": {"run_ctx": run_ctx}},
    )

    assert result["final_summary"] == "最终交付"
    prompt = operator.calls[0]["user_prompt"]
    assert "结果一" in prompt
    assert "结果二" in prompt
    assert "结果三" in prompt


def test_update_step_in_tree():
    steps = [
        {
            "id": "step_1",
            "status": "pending",
            "children": [
                {"id": "step_1_1", "status": "pending"},
            ],
        },
    ]
    _update_step_in_tree(steps, "step_1_1", {"status": "done", "result": "ok"})
    assert steps[0]["children"][0]["status"] == "done"
    assert steps[0]["children"][0]["result"] == "ok"


def test_update_parent_status_all_done():
    steps = [
        {
            "id": "step_1",
            "status": "pending",
            "children": [
                {"id": "step_1_1", "status": "done"},
                {"id": "step_1_2", "status": "done"},
            ],
        },
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "done"


def test_update_parent_status_partial():
    steps = [
        {
            "id": "step_1",
            "status": "pending",
            "children": [
                {"id": "step_1_1", "status": "done"},
                {"id": "step_1_2", "status": "pending"},
            ],
        },
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "pending"


def test_update_parent_status_failed():
    steps = [
        {
            "id": "step_1",
            "status": "pending",
            "children": [
                {"id": "step_1_1", "status": "done"},
                {"id": "step_1_2", "status": "failed"},
            ],
        },
    ]
    _update_parent_status(steps, "step_1")
    assert steps[0]["status"] == "failed"


def test_persist_work_steps_with_parent_id_and_dependencies(work_db: Database):
    from astrbot.core.langgraph.task_center import TaskCenter

    task_id = "test_persist_task"
    work_db.insert(
        "agent_tasks",
        {
            "id": task_id,
            "name": "测试任务",
            "task_type": "work_task",
            "status": "running",
            "category": "work",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    )

    now = datetime.now().isoformat()
    steps = [
        {
            "id": "step_1",
            "title": "步骤1",
            "description": "描述1",
            "status": "done",
            "dependencies": [],
            "parent_id": None,
            "depth": 1,
            "sort_order": 0,
            "executor_type": "agent",
            "executor_id": "exec1",
            "reviewer_id": "rev1",
        },
        {
            "id": "step_1_1",
            "title": "子步骤1.1",
            "description": "子描述1.1",
            "status": "running",
            "dependencies": [],
            "parent_id": "step_1",
            "depth": 2,
            "sort_order": 0,
            "executor_type": "agent",
            "executor_id": "exec2",
            "reviewer_id": "",
        },
        {
            "id": "step_2",
            "title": "步骤2",
            "description": "描述2",
            "status": "pending",
            "dependencies": ["step_1"],
            "parent_id": None,
            "depth": 1,
            "sort_order": 1,
            "executor_type": "agent",
            "executor_id": "exec1",
            "reviewer_id": "rev1",
        },
    ]
    TaskCenter._persist_work_steps(work_db, task_id, steps, now)

    persisted = work_db.select_all(
        "work_task_steps",
        where="task_id = ?",
        where_params=(task_id,),
        order_by="sort_order ASC",
    )
    assert len(persisted) == 3
    assert persisted[0]["parent_id"] is None
    assert persisted[1]["parent_id"] == f"{task_id}:step_1"
    assert persisted[2]["dependencies"] is not None


@pytest.mark.asyncio
async def test_work_service_retry_execute_step_reuses_completed_dependencies(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    service = WorkService(work_db)
    task_id = "task_retry_execute"
    now = datetime.now().isoformat()
    work_db.insert(
        "agent_tasks",
        {
            "id": task_id,
            "name": "重试执行节点",
            "description": "验证节点重试",
            "task_type": "work_task",
            "status": "retryable_failed",
            "progress": 60,
            "input": {},
            "steps": [],
            "executor_config": {},
            "plan_config": {"enabled": True, "task_mode": "normal"},
            "review_config": {"enabled": False},
            "thread_id": "work:task_retry_execute",
            "category": "work",
            "work_scope": "daily",
            "work_task_kind": "workflow",
            "created_at": now,
            "updated_at": now,
        },
    )
    for step in (
        {
            "id": f"{task_id}:step_1",
            "title": "已完成步骤",
            "description": "已完成步骤",
            "status": "done",
            "dependencies": [],
            "result": "前置结果",
            "sort_order": 0,
        },
        {
            "id": f"{task_id}:step_2",
            "title": "失败步骤",
            "description": "失败步骤",
            "status": "failed",
            "dependencies": [f"{task_id}:step_1"],
            "result": "坏结果",
            "sort_order": 1,
        },
    ):
        work_db.insert(
            "work_task_steps",
            {
                **step,
                "task_id": task_id,
                "parent_id": None,
                "depth": 1,
                "updated_at": now,
            },
        )

    captured = {}

    async def fake_start(graph_type, graph_config):
        captured["graph_type"] = graph_type
        captured["graph_config"] = graph_config
        return {"started": True, "task_id": task_id, "thread_id": graph_config["thread_id"]}

    monkeypatch.setattr(service, "_start_task_center_task", fake_start)

    result = await service.retry_node(task_id, "step_2")

    assert result["status"] == "running"
    assert captured["graph_type"] == "work_task"
    config = captured["graph_config"]
    assert config["retry_config"]["target"] == "execute"
    assert config["retry_config"]["step_id"] == "step_2"
    assert config["current_step_index"] == 1
    assert config["step_results"][0]["result"] == "前置结果"
    assert config["plan_steps"][1]["status"] == "pending"
    assert "result" not in config["plan_steps"][1]


def test_task_center_coalesces_llm_stream_events_as_logs(
    work_db: Database, monkeypatch: pytest.MonkeyPatch
):
    from astrbot.core.langgraph.task_center import TaskCenter

    monkeypatch.setattr(agent_database, "_db", work_db)
    task_id = "test_stream_task"
    now = datetime.now().isoformat()
    work_db.insert(
        "agent_tasks",
        {
            "id": task_id,
            "name": "流式任务",
            "task_type": "work_task",
            "status": "running",
            "category": "work",
            "thread_id": "session:test_stream_task",
            "created_at": now,
            "updated_at": now,
        },
    )
    task = TaskRecord(
        task_id=task_id,
        task_type="work_task",
        session_id="session",
        thread_id="session:test_stream_task",
        status=TaskStatus.RUNNING,
        config={},
        hitl_context=None,
        result=None,
        error=None,
        created_at=0,
        updated_at=0,
    )
    center = TaskCenter(None)

    asyncio.run(
        center._persist_stream_event(
            task,
            {
                "event": "text_delta",
                "data": {
                    "stage_id": "stage_execute",
                    "step_id": "step_1",
                    "agent_id": "agent_1",
                    "agent_label": "执行者",
                    "text": "以下是",
                },
                "timestamp": 0,
                "node_id": "",
            },
        )
    )
    asyncio.run(
        center._persist_stream_event(
            task,
            {
                "event": "text_delta",
                "data": {
                    "stage_id": "stage_execute",
                    "step_id": "step_1",
                    "agent_id": "agent_1",
                    "agent_label": "执行者",
                    "text": "完整输出",
                },
                "timestamp": 0,
                "node_id": "",
            },
        )
    )
    asyncio.run(
        center._persist_stream_event(
            task,
            {
                "event": "reasoning",
                "data": {
                    "stage_id": "stage_execute",
                    "step_id": "step_1",
                    "agent_id": "agent_1",
                    "agent_label": "执行者",
                    "text": "思考",
                },
                "timestamp": 0,
                "node_id": "",
            },
        )
    )
    asyncio.run(
        center._persist_stream_event(
            task,
            {
                "event": "reasoning",
                "data": {
                    "stage_id": "stage_execute",
                    "step_id": "step_1",
                    "agent_id": "agent_1",
                    "agent_label": "执行者",
                    "text": "过程",
                },
                "timestamp": 0,
                "node_id": "",
            },
        )
    )
    asyncio.run(
        center._persist_stream_event(
            task,
            {
                "event": "token",
                "data": {"input": 10, "output": 20, "total": 30},
                "timestamp": 0,
                "node_id": "",
            },
        )
    )

    logs = [
        dict(row)
        for row in work_db.execute(
            "SELECT * FROM execution_logs WHERE task_id = ? ORDER BY rowid ASC",
            (task_id,),
        ).fetchall()
    ]
    events = [json.loads(row["data"])["event"] for row in logs]
    assert events == ["text_delta", "reasoning"]
    assert logs[0]["message"] == "以下是完整输出"
    assert json.loads(logs[0]["data"])["text"] == "以下是完整输出"
    assert json.loads(logs[1]["data"])["text"] == "思考过程"
    token_rows = work_db.select_all(
        "token_stats", where="task_id = ?", where_params=(task_id,)
    )
    assert len(token_rows) == 1
    assert token_rows[0]["total_tokens"] == 30
    task_row = work_db.select_one(
        "agent_tasks", where="id = ?", where_params=(task_id,)
    )
    assert task_row["input_tokens"] == 10
    assert task_row["output_tokens"] == 20
    assert task_row["total_tokens"] == 30
