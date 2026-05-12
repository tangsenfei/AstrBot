"""Meeting workspace service.

Independent Meeting module used by the top-level Meeting tab. It deliberately
does not reuse the legacy roundtables data model, but it reuses agents,
LangGraph execution, shared tool execution, and HITL primitives.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from astrbot.core import logger

from ..models import Meeting, MeetingArtifact, MeetingEvent, MeetingStatus, TaskStatus
from .agent_service import AgentService
from .hitl_service import HITLService
from .task_service import TaskService

MEETING_ASSISTANT_ID = "agent_meeting_assistant"

MEETING_TYPES: list[dict[str, str]] = [
    {
        "type": "exploration",
        "name": "发散探索会",
        "description": "用于头脑风暴、机会发现、创意生成，产出候选想法池和初步分组。",
        "output": "候选想法池、主题分组、值得继续验证的方向",
    },
    {
        "type": "diagnosis",
        "name": "诊断分析会",
        "description": "用于问题定位、根因分析、现状拆解，产出问题结构和待验证项。",
        "output": "问题结构、关键原因、证据缺口、待验证项",
    },
    {
        "type": "solution_design",
        "name": "方案设计会",
        "description": "用于从目标和约束生成可执行方案，产出 1-3 套可落地方案。",
        "output": "方案草案、执行路径、资源需求、风险预案",
    },
    {
        "type": "review_decision",
        "name": "评审决策会",
        "description": "用于评审已有方案、文档、计划或候选项，产出结论和修改要求。",
        "output": "评审结论、决策依据、修改要求、责任人",
    },
    {
        "type": "alignment_debate",
        "name": "对齐辩论会",
        "description": "用于多方观点冲突、路线分歧、优先级不一致，产出共识和分歧清单。",
        "output": "共识、分歧保留项、裁决路径、下一步行动",
    },
    {
        "type": "retrospective",
        "name": "复盘改进会",
        "description": "用于项目、迭代或事件结束后的总结，产出复盘报告和改进行动项。",
        "output": "复盘报告、经验沉淀、改进行动项",
    },
]


class MeetingService:
    def __init__(self, db, context=None) -> None:
        self.db = db
        self.context = context
        self.agent_service = AgentService(db, context)
        self.task_service = TaskService(db)

    def list_types(self) -> list[dict[str, str]]:
        return MEETING_TYPES

    def list_meetings(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        filters = filters or {}
        conditions = ["1=1"]
        params: list[Any] = []
        for key, column in (("status", "status"), ("meeting_type", "meeting_type")):
            value = filters.get(key)
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)
        q = str(filters.get("q") or "").strip()
        if q:
            conditions.append("(name LIKE ? OR goal LIKE ? OR expected_output LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

        page = max(1, int(filters.get("page") or 1))
        page_size = max(1, min(100, int(filters.get("page_size") or 50)))
        where = " AND ".join(conditions)
        total = self.db.execute(
            f"SELECT COUNT(*) AS count FROM meetings WHERE {where}",
            tuple(params),
        ).fetchone()["count"]
        rows = self.db.execute(
            f"""
            SELECT * FROM meetings
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size, (page - 1) * page_size]),
        ).fetchall()
        hitl_cards_by_meeting = self._pending_hitl_cards_by_meeting()
        return {
            "meetings": [
                self._enrich_meeting(
                    self._row_to_meeting(dict(row)).to_dict(),
                    cards_by_meeting=hitl_cards_by_meeting,
                )
                for row in rows
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def list_meeting_summaries(self, meeting_ids: list[str]) -> list[dict[str, Any]]:
        ids = [
            str(meeting_id).strip()
            for meeting_id in meeting_ids
            if str(meeting_id).strip()
        ]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.execute(
            f"""
            SELECT *
            FROM meetings
            WHERE id IN ({placeholders})
            """,
            tuple(ids),
        ).fetchall()
        hitl_cards_by_meeting = self._pending_hitl_cards_by_meeting()
        by_id = {
            row["id"]: self._enrich_meeting(
                self._row_to_meeting(dict(row)).to_dict(),
                cards_by_meeting=hitl_cards_by_meeting,
            )
            for row in rows
        }
        return [by_id[meeting_id] for meeting_id in ids if meeting_id in by_id]

    def create_meeting(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        goal = str(data.get("goal") or "").strip()
        if not name:
            raise ValueError("会议名称不能为空")
        if not goal:
            raise ValueError("会议目标不能为空")
        meeting_type = str(data.get("meeting_type") or "solution_design")
        if meeting_type not in {item["type"] for item in MEETING_TYPES}:
            meeting_type = "solution_design"

        assistant = self.agent_service.ensure_meeting_assistant()
        if assistant is None:
            raise ValueError("会议助手不可用，请先检查智能体初始化状态")

        now = datetime.now()
        meeting = Meeting(
            id=data.get("id") or f"meeting_{uuid.uuid4().hex[:12]}",
            name=name,
            goal=goal,
            meeting_type=meeting_type,
            expected_output=str(data.get("expected_output") or ""),
            participants=[str(x) for x in (data.get("participants") or []) if x],
            materials=dict(data.get("materials") or {}),
            settings=self._default_settings(data.get("settings")),
            status=MeetingStatus.PENDING,
            stage="goal",
            progress=0,
            assistant_agent_id=assistant.id,
            created_at=now,
            updated_at=now,
        )
        self.db.insert("meetings", meeting.to_dict())
        self.add_event(
            meeting.id,
            "phase",
            role="system",
            speaker="会议助理",
            content="会议已创建，等待开始。",
            payload={"stage": "goal", "progress": 0},
        )
        return self.get_meeting(meeting.id)

    def update_meeting(self, meeting_id: str, data: dict[str, Any]) -> dict[str, Any]:
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"会议 '{meeting_id}' 不存在")
        if meeting["status"] == MeetingStatus.RUNNING.value:
            raise ValueError("会议进行中不可编辑基础配置")

        updates: dict[str, Any] = {"updated_at": datetime.now().isoformat()}
        for key in (
            "name",
            "goal",
            "meeting_type",
            "expected_output",
            "participants",
            "materials",
            "settings",
        ):
            if key in data:
                updates[key] = data[key]
        if "meeting_type" in updates and updates["meeting_type"] not in {
            item["type"] for item in MEETING_TYPES
        }:
            updates["meeting_type"] = "solution_design"
        self.db.update("meetings", updates, where="id = ?", where_params=(meeting_id,))
        return self.get_meeting(meeting_id)

    def get_meeting_summary(
        self, meeting_id: str, *, enrich: bool = True
    ) -> dict[str, Any]:
        row = self.db.select_one("meetings", where="id = ?", where_params=(meeting_id,))
        if not row:
            raise ValueError(f"会议 '{meeting_id}' 不存在")
        data = self._row_to_meeting(row).to_dict()
        return self._enrich_meeting(data) if enrich else data

    def get_meeting_status(self, meeting_id: str) -> dict[str, Any]:
        row = self.db.select_one("meetings", where="id = ?", where_params=(meeting_id,))
        if not row:
            raise ValueError(f"会议 '{meeting_id}' 不存在")
        return {
            "id": row.get("id"),
            "status": row.get("status", ""),
            "stage": row.get("stage", "goal"),
            "progress": int(row.get("progress") or 0),
            "current_round": int(row.get("current_round") or 0),
            "current_speaker": row.get("current_speaker", ""),
            "total_tokens": int(row.get("total_tokens") or 0),
            "input_tokens": int(row.get("input_tokens") or 0),
            "output_tokens": int(row.get("output_tokens") or 0),
            "updated_at": row.get("updated_at"),
        }

    def get_meeting(
        self, meeting_id: str, *, include_events: bool = False, events_limit: int = 500
    ) -> dict[str, Any]:
        data = self.get_meeting_summary(meeting_id)
        data["artifacts"] = self.list_artifacts(meeting_id)
        if include_events:
            data["events"] = self.list_events(meeting_id, limit=events_limit, tail=True)
        return data

    async def start_meeting(
        self,
        meeting_id: str,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        meeting = self.get_meeting_summary(meeting_id)
        if meeting["status"] == MeetingStatus.RUNNING.value:
            return {
                "meeting_id": meeting_id,
                "started": False,
                "message": "会议已在进行中",
            }

        assistant = self.agent_service.ensure_meeting_assistant()
        if assistant is None:
            raise ValueError("会议助手不可用")

        now = datetime.now().isoformat()
        task = self.task_service.create_task(
            task_id=f"task_meeting_{uuid.uuid4().hex[:10]}",
            name=f"Meeting: {meeting['name']}",
            description=meeting["goal"],
            task_type="meeting",
            meeting_id=meeting_id,
            input_data={"meeting_id": meeting_id, "goal": meeting["goal"]},
            category="meeting",
            thread_id=f"meeting:{meeting_id}",
        )
        self.db.update(
            "meetings",
            {
                "status": MeetingStatus.RUNNING.value,
                "stage": "goal",
                "progress": 5,
                "current_speaker": "会议助理",
                "task_id": task.id,
                "started_at": now,
                "updated_at": now,
            },
            where="id = ?",
            where_params=(meeting_id,),
        )
        self.db.update(
            "agent_tasks",
            {"status": TaskStatus.RUNNING.value, "started_at": now, "updated_at": now},
            where="id = ?",
            where_params=(task.id,),
        )
        self.add_event(
            meeting_id,
            "phase",
            role="system",
            speaker="会议助理",
            content="会议开始，会议助理正在确认目标。",
            payload={"stage": "goal", "progress": 5},
        )

        await self._run_meeting_graph(meeting_id, task.id, event_sink=event_sink)
        return {"meeting_id": meeting_id, "started": True, "task_id": task.id}

    async def _run_meeting_graph(
        self,
        meeting_id: str,
        task_id: str,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
        from astrbot.core.langgraph.graphs.meeting import build_meeting_graph
        from astrbot.core.langgraph.state import GraphRunContext, StreamEvent

        try:
            meeting = self.get_meeting_summary(meeting_id)
            assistant = self.agent_service.get_agent(meeting["assistant_agent_id"])
            if assistant is None:
                raise ValueError("会议助手不存在")
            participants = [
                agent
                for agent in self._get_agents(meeting["participants"])
                if agent.id != assistant.id
            ]
            provider = self._resolve_provider(assistant.provider_id)

            def stream_writer(event: StreamEvent):
                if event_sink:
                    event_sink(event)
                else:
                    self._handle_graph_event(meeting_id, event)

            run_ctx = GraphRunContext(
                provider=provider,
                tool_executor=FunctionToolExecutor(),
                hooks=None,
                astr_event=self.context,
                config={"streaming_response": True},
                writer=stream_writer,
            )
            state_input = {
                "meeting_id": meeting_id,
                "task_id": task_id,
                "topic": meeting["goal"],
                "goal": meeting["goal"],
                "expected_output": meeting["expected_output"],
                "meeting_type": meeting["meeting_type"],
                "materials": meeting["materials"],
                "settings": meeting["settings"],
                "participants": [
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "role": agent.name,
                        "system_prompt": self._participant_prompt(agent, meeting),
                        "provider_id": agent.provider_id,
                    }
                    for agent in participants
                ],
                "host": {
                    "id": assistant.id,
                    "name": assistant.name,
                    "system_prompt": self._assistant_prompt(assistant, meeting),
                    "provider_id": assistant.provider_id,
                },
                "strategy": meeting["meeting_type"],
                "max_rounds": int(meeting["settings"].get("rounds") or 2),
                "current_round": 0,
                "round_results": [],
                "messages": [],
                "system_prompt": "",
                "user_prompt": "",
                "session_id": meeting_id,
                "provider_id": assistant.provider_id,
            }
            graph = build_meeting_graph(strategy=meeting["meeting_type"])
            final_state = await graph.ainvoke(
                state_input,
                config={
                    "configurable": {
                        "thread_id": f"meeting:{meeting_id}",
                        "run_ctx": run_ctx,
                    }
                },
            )
            minutes = final_state.get("final_minutes", "") if final_state else ""
            report = final_state.get("deliverable_output", "") if final_state else ""
            result = {
                "minutes": minutes,
                "report": report,
                "round_results": final_state.get("round_results", [])
                if final_state
                else [],
                "completed_at": datetime.now().isoformat(),
            }
            if minutes:
                self.add_artifact(meeting_id, "会议纪要", "minutes", minutes)
            if report:
                self.add_artifact(meeting_id, "会议报告", "report", report)
            completed_at = datetime.now().isoformat()
            self.db.update(
                "meetings",
                {
                    "status": MeetingStatus.COMPLETED.value,
                    "stage": "completed",
                    "progress": 100,
                    "current_speaker": "已完成",
                    "result": result,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
                where="id = ?",
                where_params=(meeting_id,),
            )
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 100,
                    "result": minutes or report,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
                where="id = ?",
                where_params=(task_id,),
            )
            self.add_event(
                meeting_id,
                "phase",
                role="system",
                speaker="会议助理",
                content="会议结束，会议纪要和会议报告已生成。",
                payload={"stage": "completed", "progress": 100},
            )
        except Exception as e:
            logger.error(f"Meeting execution failed: {meeting_id}: {e}", exc_info=True)
            failed_at = datetime.now().isoformat()
            self.db.update(
                "meetings",
                {
                    "status": MeetingStatus.FAILED.value,
                    "stage": "failed",
                    "current_speaker": "执行失败",
                    "result": {"error": str(e), "failed_at": failed_at},
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                },
                where="id = ?",
                where_params=(meeting_id,),
            )
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.FAILED.value,
                    "error": str(e),
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                },
                where="id = ?",
                where_params=(task_id,),
            )
            self.add_event(
                meeting_id,
                "error",
                role="system",
                speaker="会议助理",
                content=str(e),
                payload={"message": str(e)},
            )

    def submit_input(self, meeting_id: str, text: str) -> dict[str, Any]:
        meeting = self.get_meeting_status(meeting_id)
        if not text.strip():
            raise ValueError("发言内容不能为空")
        event = self.add_event(
            meeting_id,
            "user_message",
            role="user",
            speaker="用户",
            round=int(meeting.get("current_round") or 0),
            content=text.strip(),
            payload={"inject": "next_host_turn"},
        )
        return event

    async def respond_hitl(
        self, meeting_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        interaction_id = str(data.get("interaction_id") or "")
        if not interaction_id:
            raise ValueError("缺少 interaction_id")
        hitl_service = HITLService(self.db)
        result = await hitl_service.respond(
            interaction_id,
            data.get("action_key", "confirm"),
            data.get("field_values", {}),
        )
        current = self.get_meeting_status(meeting_id)
        if current.get("status") not in {
            MeetingStatus.COMPLETED.value,
            MeetingStatus.FAILED.value,
            MeetingStatus.CANCELLED.value,
        }:
            next_status = (
                MeetingStatus.CANCELLED.value
                if result.get("action_key") == "cancel"
                else MeetingStatus.RUNNING.value
            )
            self.db.update(
                "meetings",
                {"status": next_status, "updated_at": datetime.now().isoformat()},
                where="id = ?",
                where_params=(meeting_id,),
            )
        return result

    def continue_meeting(self, meeting_id: str, data: dict[str, Any]) -> dict[str, Any]:
        meeting = self.get_meeting(meeting_id)
        if meeting["status"] not in {
            MeetingStatus.COMPLETED.value,
            MeetingStatus.FAILED.value,
        }:
            raise ValueError("只有已结束或失败的会议可以续会")
        review = str(data.get("review_comment") or "").strip()
        extra_topic = str(data.get("additional_topic") or "").strip()
        if not review and not extra_topic:
            raise ValueError("请提供续会意见或追加议题")
        settings = dict(meeting.get("settings") or {})
        settings["rounds"] = max(1, int(data.get("additional_rounds") or 1))
        continuations = list(settings.get("continuations") or [])
        continuations.append(
            {
                "review_comment": review,
                "additional_topic": extra_topic,
                "created_at": datetime.now().isoformat(),
            }
        )
        settings["continuations"] = continuations
        goal = meeting["goal"]
        if extra_topic:
            goal = f"{goal}\n\n续会追加议题：{extra_topic}"
        self.db.update(
            "meetings",
            {
                "goal": goal,
                "settings": settings,
                "status": MeetingStatus.PENDING.value,
                "stage": "goal",
                "progress": 0,
                "current_round": 0,
                "current_speaker": "",
                "completed_at": None,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(meeting_id,),
        )
        self.add_event(
            meeting_id,
            "user_message",
            role="user",
            speaker="用户",
            content=f"续会意见：{review or '无'}"
            + (f"\n追加议题：{extra_topic}" if extra_topic else ""),
            payload={"continuation": True},
        )
        return self.get_meeting(meeting_id)

    def list_events(
        self,
        meeting_id: str,
        limit: int | None = None,
        after_seq: int | None = None,
        *,
        tail: bool = False,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [meeting_id]
        where = "meeting_id = ?"
        if after_seq:
            where += " AND rowid > ?"
            params.append(int(after_seq))
        limit_sql = ""
        if limit:
            limit_sql = " LIMIT ?"
            params.append(max(1, min(5000, int(limit))))
        order = "DESC" if tail and not after_seq else "ASC"
        rows = self.db.execute(
            f"SELECT rowid AS seq, * FROM meeting_events WHERE {where} ORDER BY rowid {order}{limit_sql}",
            tuple(params),
        ).fetchall()
        if order == "DESC":
            rows = list(reversed(rows))
        events = []
        for row in rows:
            item = self._row_to_event(dict(row)).to_dict()
            item["seq"] = row["seq"]
            events.append(item)
        return events

    def list_artifacts(self, meeting_id: str) -> list[dict[str, Any]]:
        rows = self.db.select_all(
            "meeting_artifacts",
            where="meeting_id = ?",
            where_params=(meeting_id,),
            order_by="created_at ASC",
        )
        return [self._row_to_artifact(row).to_dict() for row in rows]

    def add_artifact(
        self,
        meeting_id: str,
        title: str,
        artifact_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": f"mart_{uuid.uuid4().hex[:12]}",
            "meeting_id": meeting_id,
            "title": title,
            "artifact_type": artifact_type,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }
        self.db.insert("meeting_artifacts", row)
        self.add_event(
            meeting_id,
            "artifact",
            role="assistant",
            speaker="会议助理",
            content=title,
            payload=row,
        )
        return self._row_to_artifact(row).to_dict()

    def add_event(
        self,
        meeting_id: str,
        event_type: str,
        *,
        role: str = "assistant",
        speaker: str = "",
        round: int = 0,
        content: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": f"mevt_{uuid.uuid4().hex[:12]}",
            "meeting_id": meeting_id,
            "event_type": event_type,
            "role": role,
            "speaker": speaker,
            "round": int(round or 0),
            "content": content,
            "payload": payload or {},
            "created_at": datetime.now().isoformat(),
        }
        self.db.insert("meeting_events", row)
        return self._row_to_event(row).to_dict()

    def _handle_graph_event(self, meeting_id: str, event: dict[str, Any]) -> None:
        data = dict(event.get("data") or {})
        event_type = str(event.get("event") or data.get("event") or "log")
        speaker = (
            data.get("agent_name")
            or data.get("speaker")
            or ("会议助理" if event_type != "user_message" else "用户")
        )
        current_round = int(data.get("round") or 0)

        if event_type in {"text_delta", "reasoning"}:
            return

        if event_type == "token":
            input_t = int(data.get("input") or 0)
            output_t = int(data.get("output") or 0)
            total_t = int(data.get("total") or input_t + output_t)
            meeting = self.db.select_one(
                "meetings", where="id = ?", where_params=(meeting_id,)
            )
            if meeting:
                self.db.update(
                    "meetings",
                    {
                        "input_tokens": int(meeting.get("input_tokens") or 0) + input_t,
                        "output_tokens": int(meeting.get("output_tokens") or 0)
                        + output_t,
                        "total_tokens": int(meeting.get("total_tokens") or 0) + total_t,
                        "updated_at": datetime.now().isoformat(),
                    },
                    where="id = ?",
                    where_params=(meeting_id,),
                )
            return

        content = (
            data.get("text")
            or data.get("content")
            or data.get("delta")
            or data.get("reasoning")
            or data.get("reasoning_content")
            or data.get("thinking")
            or data.get("message")
            or data.get("label")
            or data.get("title")
            or ""
        )
        self.add_event(
            meeting_id,
            event_type,
            role="assistant",
            speaker=speaker,
            round=current_round,
            content=str(content),
            payload=data,
        )
        updates: dict[str, Any] = {"updated_at": datetime.now().isoformat()}
        if speaker:
            updates["current_speaker"] = speaker
        if current_round:
            updates["current_round"] = current_round
        if event_type == "phase":
            if data.get("stage") or data.get("phase"):
                updates["stage"] = data.get("stage") or data.get("phase")
            if data.get("progress") is not None:
                updates["progress"] = int(data.get("progress") or 0)
        if event_type == "interaction":
            updates["status"] = MeetingStatus.WAITING_FEEDBACK.value
        self.db.update("meetings", updates, where="id = ?", where_params=(meeting_id,))

    def recent_user_inputs(
        self, meeting_id: str, after_seq: int = 0
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT rowid AS seq, *
            FROM meeting_events
            WHERE meeting_id = ? AND event_type = 'user_message' AND rowid > ?
            ORDER BY rowid ASC
            """,
            (meeting_id, int(after_seq or 0)),
        ).fetchall()
        result = []
        for row in rows:
            item = self._row_to_event(dict(row)).to_dict()
            item["seq"] = row["seq"]
            result.append(item)
        return result

    def _pending_hitl_cards_by_meeting(self) -> dict[str, list[dict[str, Any]]]:
        cards_by_meeting: dict[str, list[dict[str, Any]]] = {}
        try:
            for card in HITLService(self.db).list_pending():
                meeting_id = (card.get("meta") or {}).get("meeting_id")
                if meeting_id:
                    cards_by_meeting.setdefault(meeting_id, []).append(card)
        except Exception:
            pass
        try:
            from astrbot.core.langgraph.interaction_manager import (
                get_interaction_manager,
            )

            for state in get_interaction_manager().get_pending_interactions():
                card = state.card.to_dict()
                meeting_id = card.get("meta", {}).get("meeting_id")
                if not meeting_id:
                    continue
                if any(
                    existing.get("interaction_id") == card.get("interaction_id")
                    for existing in cards_by_meeting.get(meeting_id, [])
                ):
                    continue
                card["thread_id"] = state.thread_id
                card["channel"] = state.channel
                cards_by_meeting.setdefault(meeting_id, []).append(card)
        except Exception:
            pass
        return cards_by_meeting

    def _enrich_meeting(
        self,
        meeting: dict[str, Any],
        *,
        cards_by_meeting: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        meeting["type_info"] = next(
            (
                item
                for item in MEETING_TYPES
                if item["type"] == meeting.get("meeting_type")
            ),
            None,
        )
        meeting["has_hitl"] = False
        if meeting.get("status") in {
            MeetingStatus.COMPLETED.value,
            MeetingStatus.FAILED.value,
            MeetingStatus.CANCELLED.value,
        }:
            return meeting
        hitl_cards = (
            (cards_by_meeting or {}).get(meeting.get("id", ""), [])
            if cards_by_meeting is not None
            else self._pending_hitl_cards_by_meeting().get(meeting.get("id", ""), [])
        )
        if hitl_cards:
            meeting["has_hitl"] = True
            meeting["active_hitl"] = hitl_cards[0]
        if (
            not meeting.get("has_hitl")
            and meeting.get("status") == MeetingStatus.WAITING_FEEDBACK.value
        ):
            meeting["status"] = MeetingStatus.RUNNING.value
            try:
                self.db.update(
                    "meetings",
                    {
                        "status": MeetingStatus.RUNNING.value,
                        "updated_at": datetime.now().isoformat(),
                    },
                    where="id = ?",
                    where_params=(meeting.get("id"),),
                )
            except Exception:
                pass
        return meeting

    def _assistant_prompt(self, assistant, meeting: dict[str, Any]) -> str:
        type_info = next(
            (
                item
                for item in MEETING_TYPES
                if item["type"] == meeting.get("meeting_type")
            ),
            MEETING_TYPES[2],
        )
        return "\n".join(
            [
                assistant.soul or "",
                "你是 NiceBot Meeting 的唯一会议助理和主持人。",
                f"会议类型：{type_info['name']}。",
                f"主持重点：{type_info['description']}",
                f"目标产出：{type_info['output']}。",
                "你必须按四个阶段推进：会议目标确定、会议材料准备、会议开展、会议结束。",
                "遇到关键信息缺失、目标冲突、决策风险或用户需要确认的事项时，发起人工确认。",
                "用户可能在会议室随时发言，你需要把这些发言纳入后续主持、追问、总结和报告。",
            ]
        )

    def _participant_prompt(self, agent, meeting: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"你正在参加一场由会议助理主持的虚拟会议。会议目标：{meeting['goal']}",
                f"预期产出：{meeting.get('expected_output') or '由会议助理根据会议类型确定'}",
                f"你的角色：{agent.name}",
                agent.soul or "",
                "请围绕会议目标提供专业观点，回应前文讨论，避免偏题。",
            ]
        )

    def _get_agents(self, agent_ids: list[str]):
        agents = []
        for agent_id in agent_ids:
            agent = self.agent_service.get_agent(agent_id)
            if agent:
                agents.append(agent)
        return agents

    def _resolve_provider(self, provider_id: str | None):
        if self.context is None:
            return None
        if provider_id and hasattr(self.context, "get_provider_by_id"):
            provider = self.context.get_provider_by_id(provider_id)
            if provider is not None:
                return provider
        if hasattr(self.context, "get_using_provider"):
            return self.context.get_using_provider(None)
        return None

    @staticmethod
    def _default_settings(raw: Any) -> dict[str, Any]:
        settings = dict(raw or {})
        settings["rounds"] = max(1, min(6, int(settings.get("rounds") or 2)))
        settings.setdefault("require_goal_confirmation", False)
        settings.setdefault("max_user_inputs_per_round", 20)
        return settings

    def _row_to_meeting(self, row: dict[str, Any]) -> Meeting:
        return Meeting(
            id=row["id"],
            name=row["name"],
            goal=row.get("goal", ""),
            meeting_type=row.get("meeting_type", "solution_design"),
            expected_output=row.get("expected_output", ""),
            participants=self._parse_json(row.get("participants"), []),
            materials=self._parse_json(row.get("materials"), {}),
            settings=self._parse_json(row.get("settings"), {}),
            status=MeetingStatus(row.get("status", "pending")),
            stage=row.get("stage", "goal"),
            progress=int(row.get("progress") or 0),
            current_round=int(row.get("current_round") or 0),
            current_speaker=row.get("current_speaker", ""),
            assistant_agent_id=row.get("assistant_agent_id") or MEETING_ASSISTANT_ID,
            result=self._parse_json(row.get("result"), {}),
            task_id=row.get("task_id", ""),
            total_tokens=int(row.get("total_tokens") or 0),
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=datetime.fromisoformat(row["started_at"])
            if row.get("started_at")
            else None,
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row.get("completed_at")
            else None,
        )

    def _row_to_event(self, row: dict[str, Any]) -> MeetingEvent:
        return MeetingEvent(
            id=row["id"],
            meeting_id=row["meeting_id"],
            event_type=row.get("event_type", "log"),
            role=row.get("role", "assistant"),
            speaker=row.get("speaker", ""),
            round=int(row.get("round") or 0),
            content=row.get("content", ""),
            payload=self._parse_json(row.get("payload"), {}),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_artifact(self, row: dict[str, Any]) -> MeetingArtifact:
        return MeetingArtifact(
            id=row["id"],
            meeting_id=row["meeting_id"],
            title=row["title"],
            artifact_type=row.get("artifact_type", "minutes"),
            content=row.get("content", ""),
            metadata=self._parse_json(row.get("metadata"), {}),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback
