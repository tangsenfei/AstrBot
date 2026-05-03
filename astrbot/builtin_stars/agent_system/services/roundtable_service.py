"""
圆桌会议服务

提供圆桌会议的创建、查询、执行等功能
"""
from __future__ import annotations

import json
import random
import string
from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

from ..models import Roundtable, RoundtableStatus

if TYPE_CHECKING:
    from astrbot.core.agent.models import Agent

    from astrbot.core.star.context import Context

    from ..database import AgentDatabase


class RoundtableService:
    """圆桌会议服务"""

    def __init__(self, db: AgentDatabase, context: Context | None = None) -> None:
        self.db = db
        self._context = context

    def get_roundtables(self, status: str | None = None) -> list[Roundtable]:
        """获取圆桌会议列表

        Args:
            status: 状态筛选，None 表示全部

        Returns:
            圆桌会议列表
        """
        if status:
            rows = self.db.select_all(
                "roundtables",
                where="status = ?",
                where_params=(status,),
                order_by="created_at DESC"
            )
        else:
            rows = self.db.select_all(
                "roundtables",
                order_by="created_at DESC"
            )

        return [self._row_to_roundtable(row) for row in rows]

    def get_roundtable(self, roundtable_id: str) -> Roundtable | None:
        """获取单个圆桌会议

        Args:
            roundtable_id: 圆桌会议 ID

        Returns:
            Roundtable 对象，不存在则返回 None
        """
        row = self.db.select_one(
            "roundtables",
            where="id = ?",
            where_params=(roundtable_id,)
        )
        if not row:
            return None
        return self._row_to_roundtable(row)

    def create_roundtable(self, data: dict[str, Any]) -> Roundtable:
        """创建圆桌会议

        Args:
            data: 圆桌会议数据

        Returns:
            创建的 Roundtable 对象
        """
        roundtable_id = f"roundtable_{self._generate_id()}"

        # 兼容前端数据：has_moderator + moderator 映射到 mode + host_agent_id
        has_moderator = data.get("has_moderator", False)
        moderator = data.get("moderator", "")
        mode = "hosted" if has_moderator else "free"
        host_agent_id = moderator if has_moderator else None

        roundtable = Roundtable(
            id=roundtable_id,
            name=data.get("name", ""),
            topic=data.get("topic", ""),
            deliverable=data.get("deliverable", ""),
            mode=mode,
            meeting_type=data.get("meeting_type", "standard"),
            host_agent_id=host_agent_id,
            participants=data.get("participants", []),
            rounds=data.get("rounds", 3),
            config=data.get("config", {}),
            materials=data.get("materials", {}),
            export_format=data.get("export_format", "markdown"),
            preparation_records=data.get("preparation_records", []),
        )

        self.db.insert("roundtables", roundtable.to_dict())
        return roundtable

    def update_roundtable(self, roundtable_id: str, data: dict[str, Any]) -> Roundtable | None:
        """更新圆桌会议

        Args:
            roundtable_id: 圆桌会议 ID
            data: 更新数据

        Returns:
            更新后的 Roundtable 对象，不存在则返回 None
        """
        roundtable = self.get_roundtable(roundtable_id)
        if not roundtable:
            return None

        # 更新字段
        if "name" in data:
            roundtable.name = data["name"]
        if "topic" in data:
            roundtable.topic = data["topic"]
        if "deliverable" in data:
            roundtable.deliverable = data["deliverable"]
        if "mode" in data:
            roundtable.mode = data["mode"]
        if "meeting_type" in data:
            roundtable.meeting_type = data["meeting_type"]
        if "host_agent_id" in data:
            roundtable.host_agent_id = data["host_agent_id"]
        if "participants" in data:
            roundtable.participants = data["participants"]
        if "rounds" in data:
            roundtable.rounds = data["rounds"]
        if "config" in data:
            roundtable.config = data["config"]
        if "materials" in data:
            roundtable.materials = data["materials"]
        if "export_format" in data:
            roundtable.export_format = data["export_format"]
        if "preparation_records" in data:
            roundtable.preparation_records = data["preparation_records"]
        if "status" in data:
            status_val = data["status"]
            if isinstance(status_val, str):
                status_val = RoundtableStatus(status_val)
            roundtable.status = status_val
        if "stage" in data:
            roundtable.stage = data["stage"]
        if "current_round" in data:
            roundtable.current_round = data["current_round"]
        if "current_speaker" in data:
            roundtable.current_speaker = data["current_speaker"]
        if "streaming_content" in data:
            roundtable.streaming_content = data["streaming_content"]
        if "result" in data:
            roundtable.result = data["result"]
        if "discussion_records" in data:
            roundtable.discussion_records = data["discussion_records"]

        roundtable.updated_at = datetime.now()

        self.db.update(
            "roundtables",
            roundtable.to_dict(),
            where="id = ?",
            where_params=(roundtable_id,)
        )
        return roundtable

    def delete_roundtable(self, roundtable_id: str) -> bool:
        """删除圆桌会议

        Args:
            roundtable_id: 圆桌会议 ID

        Returns:
            是否删除成功
        """
        roundtable = self.get_roundtable(roundtable_id)
        if not roundtable:
            return False

        self.db.delete("roundtables", where="id = ?", where_params=(roundtable_id,))
        return True

    async def execute_roundtable(
        self,
        roundtable_id: str,
        input_data: dict[str, Any],
        event_callback: Any = None
    ) -> dict[str, Any]:
        """执行圆桌会议

        通过 LangGraph 会议图驱动多轮讨论，替代原有的策略模式执行。

        Args:
            roundtable_id: 圆桌会议 ID
            input_data: 输入数据（可覆盖 topic/deliverable/rounds）
            event_callback: 事件回调函数，用于 SSE 推送

        Returns:
            执行结果

        Raises:
            ValueError: 圆桌会议不存在或配置错误
        """
        from astrbot.core.langgraph.graphs.meeting import build_meeting_graph
        from astrbot.core.langgraph.state import GraphRunContext, StreamEvent

        from ..models import TaskStatus
        from .task_service import TaskService

        roundtable = self.get_roundtable(roundtable_id)
        if not roundtable:
            raise ValueError(f"圆桌会议 '{roundtable_id}' 不存在")

        if not roundtable.participants:
            raise ValueError(f"圆桌会议 '{roundtable_id}' 没有配置参会者")

        task_service = TaskService(self.db)
        task = task_service.create_task(
            name=f"圆桌会议: {roundtable.name}",
            description=f"主题: {roundtable.topic}, 类型: {roundtable.meeting_type}",
            task_type="meeting",
            meeting_id=roundtable_id,
            input_data=input_data,
        )
        now_iso = datetime.now().isoformat()
        self.db.update(
            "agent_tasks",
            {
                "status": TaskStatus.RUNNING.value,
                "started_at": now_iso,
                "updated_at": now_iso,
            },
            where="id = ?",
            where_params=(task.id,),
        )

        previous_records = list(roundtable.discussion_records or [])
        previous_result = dict(roundtable.result or {})
        is_continuation = bool(previous_records or previous_result.get("discussion_rounds"))

        self.db.update(
            "roundtables",
            {
                "status": RoundtableStatus.RUNNING.value,
                "result": previous_result if is_continuation else {},
                "discussion_records": list(previous_records) if is_continuation else [],
                "current_round": 0,
                "current_speaker": "准备开始",
                "stage": "running",
                "streaming_content": "",
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(roundtable_id,)
        )

        if event_callback:
            event_callback("status", {"status": "running", "stage": "running", "message": "会议进行中"})

        result = {
            "roundtable_id": roundtable_id,
            "roundtable_name": roundtable.name,
            "status": RoundtableStatus.RUNNING.value,
            "success": False,
            "discussion_rounds": [],
            "summary": None,
            "error": None,
            "execution_time_ms": 0,
            "tokens": {
                "input": 0,
                "output": 0,
                "total": 0,
            },
        }

        start_time = datetime.now()

        try:
            topic = input_data.get("topic") or roundtable.topic
            deliverable = input_data.get("deliverable") or roundtable.deliverable
            rounds = input_data.get("rounds") or roundtable.rounds

            logger.info(f"Roundtable execution starting: {roundtable_id}, topic={topic}, rounds={rounds}, type={roundtable.meeting_type}")

            agents = self._get_agents(roundtable.participants)
            if not agents:
                raise ValueError("没有有效的参会 Agent")

            host_agent = None
            if roundtable.host_agent_id:
                host_agent = self._get_agent(roundtable.host_agent_id)
                if not host_agent:
                    raise ValueError(f"主持人 Agent '{roundtable.host_agent_id}' 不存在")

            if event_callback:
                event_callback("agents_info", {
                    "agents": [{"id": a.id, "name": a.name, "role": a.role or "", "goal": a.goal or ""} for a in agents],
                    "host": {"id": host_agent.id, "name": host_agent.name} if host_agent else None
                })

            participants = []
            for agent in agents:
                parts = []
                if agent.role:
                    parts.append(f"你是一个{agent.role}。")
                if topic and deliverable:
                    parts.append(
                        f"你正在参加一场圆桌会议。"
                        f"会议主题：{topic}。"
                        f"会议预期产出：{deliverable}。"
                        f"你的任务是基于你的专业背景，为达成会议产出目标做出贡献，"
                        f"积极回应其他参会者观点，推动讨论深入，而不是单纯追求你个人的固定目标。"
                    )
                elif agent.goal:
                    parts.append(f"你的目标是：{agent.goal}")
                if agent.backstory:
                    parts.append(f"背景：{agent.backstory}")
                participants.append({
                    "id": agent.id,
                    "name": agent.name,
                    "system_prompt": "\n".join(parts),
                    "provider_id": agent.provider_id,
                })

            host_dict = None
            if host_agent:
                host_parts = ["你是这场圆桌会议的主持人。"]
                if host_agent.role:
                    host_parts.append(f"你的角色：{host_agent.role}")
                if topic and deliverable:
                    host_parts.append(f"会议主题：{topic}。预期产出：{deliverable}。")
                host_dict = {
                    "id": host_agent.id,
                    "name": host_agent.name,
                    "system_prompt": "\n".join(host_parts),
                    "provider_id": host_agent.provider_id,
                }

            provider = None
            provider_id = None
            if self._context:
                first_provider_id = agents[0].provider_id if agents else None
                if first_provider_id:
                    provider = self._context.get_provider_by_id(first_provider_id)
                    provider_id = first_provider_id

            from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor

            def stream_writer(event: StreamEvent):
                if not event_callback:
                    return
                evt_type = event.get("event", "")
                data = event.get("data", {})
                agent_name = data.get("agent_name", "")
                current_round = data.get("round", 0)
                if evt_type == "text_delta":
                    if agent_name:
                        self.db.update(
                            "roundtables",
                            {
                                "current_speaker": agent_name,
                                "current_round": current_round,
                                "updated_at": datetime.now().isoformat(),
                            },
                            where="id = ?",
                            where_params=(roundtable_id,),
                        )
                        event_callback("speaker_start", {
                            "speaker": agent_name,
                            "round": current_round,
                        })
                    event_callback("agent_speech_chunk", {
                        "content": data.get("text", ""),
                        "agent_name": agent_name,
                        "round": current_round,
                        "phase": "speech",
                        "streaming": True,
                    })
                elif evt_type == "reasoning":
                    event_callback("agent_thinking", {
                        "content": data.get("text", ""),
                        "agent_name": agent_name,
                        "round": current_round,
                    })
                elif evt_type == "tool_call":
                    event_callback("tool_call", {
                        "name": data.get("name", ""),
                        "agent_name": agent_name,
                        "round": current_round,
                    })
                elif evt_type == "tool_result":
                    event_callback("tool_result", {
                        "name": data.get("name", ""),
                        "content": data.get("content", ""),
                        "agent_name": agent_name,
                        "round": current_round,
                    })
                elif evt_type == "error":
                    event_callback("error", {
                        "message": data.get("message", ""),
                    })

            run_ctx = GraphRunContext(
                provider=provider,
                tool_executor=FunctionToolExecutor(),
                hooks=None,
                astr_event=self._context,
                config={"streaming_response": True},
                writer=stream_writer,
            )

            graph = build_meeting_graph(
                strategy=roundtable.meeting_type or "standard",
            )

            state_input = {
                "topic": topic,
                "participants": participants,
                "host": host_dict,
                "strategy": roundtable.meeting_type or "standard",
                "max_rounds": rounds,
                "current_round": 0,
                "round_results": [],
                "system_prompt": "",
                "user_prompt": "",
                "messages": [],
                "session_id": roundtable_id,
                "provider_id": provider_id,
            }

            thread_id = f"meeting:{roundtable_id}"

            final_state = await graph.ainvoke(
                state_input,
                config={"configurable": {"thread_id": thread_id, "run_ctx": run_ctx}},
            )

            final_minutes = ""
            round_results = []
            deliverable_output = ""
            if final_state:
                logger.info(f"Final state keys: {list(final_state.keys())}, round_results count: {len(final_state.get('round_results', []))}, final_minutes length: {len(final_state.get('final_minutes', ''))}")
                final_minutes = final_state.get("final_minutes", "")
                round_results = final_state.get("round_results", [])
                deliverable_output = final_state.get("deliverable_output", "")
            else:
                logger.warning(f"Final state is None for roundtable {roundtable_id}")

            result["success"] = True
            result["summary"] = final_minutes

            discussion_records = list(previous_records) if is_continuation else []
            for i, rr in enumerate(round_results):
                speaker = ""
                content = rr
                record_type = "speech"
                if rr.startswith("[开场]"):
                    speaker = "主持人"
                    content = rr[len("[开场]"):].strip()
                    record_type = "opening"
                elif rr.startswith("[主持人总结]"):
                    speaker = "主持人"
                    content = rr[len("[主持人总结]"):].strip()
                    record_type = "summary"
                elif rr.startswith("[") and "]" in rr:
                    close_bracket = rr.index("]")
                    speaker = rr[1:close_bracket]
                    content = rr[close_bracket + 1:].strip()
                discussion_records.append({
                    "round": (i // max(len(agents), 1)) + 1,
                    "speaker": speaker,
                    "content": content,
                    "type": record_type,
                })

            structured_rounds = []
            for i, rr in enumerate(round_results):
                speaker = ""
                content = rr
                if rr.startswith("[开场]"):
                    speaker = "主持人"
                    content = rr[len("[开场]"):].strip()
                elif rr.startswith("[主持人总结]"):
                    speaker = "主持人"
                    content = rr[len("[主持人总结]"):].strip()
                elif rr.startswith("[") and "]" in rr:
                    close_bracket = rr.index("]")
                    speaker = rr[1:close_bracket]
                    content = rr[close_bracket + 1:].strip()
                structured_rounds.append({
                    "round": i + 1,
                    "speaker": speaker,
                    "content": content,
                })

            self.db.update(
                "roundtables",
                {
                    "status": RoundtableStatus.COMPLETED.value,
                    "result": {
                        "discussion_rounds": structured_rounds,
                        "summary": final_minutes,
                        "deliverable": deliverable_output or deliverable,
                        "deliverable_description": deliverable,
                        "executed_at": datetime.now().isoformat(),
                    },
                    "discussion_records": discussion_records,
                    "current_round": rounds,
                    "current_speaker": "已完成",
                    "stage": "completed",
                    "streaming_content": "",
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(roundtable_id,)
            )

            completed_at = datetime.now().isoformat()
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 100,
                    "result": final_minutes,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
                where="id = ?",
                where_params=(task.id,),
            )

            if event_callback:
                event_callback("summary", {"content": final_minutes})
                event_callback("status", {"status": "completed", "stage": "completed", "message": "会议结束"})

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Roundtable execution failed: {roundtable_id} - {e}")

            existing_rt = self.get_roundtable(roundtable_id)
            existing_records = existing_rt.discussion_records if existing_rt else []

            self.db.update(
                "roundtables",
                {
                    "status": RoundtableStatus.FAILED.value,
                    "result": {
                        "error": str(e),
                        "executed_at": datetime.now().isoformat(),
                    },
                    "discussion_records": existing_records,
                    "current_speaker": f"错误: {str(e)[:50]}",
                    "stage": "failed",
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(roundtable_id,)
            )

            failed_at = datetime.now().isoformat()
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.FAILED.value,
                    "error": str(e),
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                },
                where="id = ?",
                where_params=(task.id,),
            )

            if event_callback:
                event_callback("error", {"message": str(e)})
                event_callback("status", {"status": "failed", "stage": "failed", "message": str(e)})

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        result["status"] = RoundtableStatus.COMPLETED.value if result["success"] else RoundtableStatus.FAILED.value

        return result

    # ==================== 私有方法 ====================

    def _row_to_roundtable(self, row: dict[str, Any]) -> Roundtable:
        """将数据库行转换为 Roundtable 对象"""
        # 兼容旧数据：mode 映射到 meeting_type
        mode = row.get("mode", "free")
        meeting_type = row.get("meeting_type", "")
        if not meeting_type:
            meeting_type = "standard"
        return Roundtable(
            id=row["id"],
            name=row["name"],
            topic=row.get("topic", ""),
            deliverable=row.get("deliverable", ""),
            mode=mode,
            meeting_type=meeting_type,
            host_agent_id=row.get("host_agent_id"),
            participants=self._parse_json(row.get("participants", "[]")),
            rounds=row.get("rounds", 3),
            config=self._parse_json(row.get("config", "{}")),
            status=RoundtableStatus(row.get("status", "pending")),
            result=self._parse_json(row.get("result", "{}")),
            discussion_records=self._parse_json(row.get("discussion_records", "[]")),
            current_round=row.get("current_round", 0),
            current_speaker=row.get("current_speaker", ""),
            stage=row.get("stage", "pending"),
            streaming_content=row.get("streaming_content", ""),
            materials=self._parse_json(row.get("materials", "{}")),
            export_format=row.get("export_format", "markdown"),
            preparation_records=self._parse_json(row.get("preparation_records", "[]")),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )

    def _parse_json(self, value: str | dict | list | None) -> dict | list:
        """解析 JSON 字符串"""
        if value is None:
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_agent(self, agent_id: str) -> Agent | None:
        """获取单个 Agent"""
        from ..services.agent_service import AgentService
        service = AgentService(self.db, self._context)
        return service.get_agent(agent_id)

    def _get_agents(self, agent_ids: list[str]) -> list[Agent]:
        """获取多个 Agent"""
        agents = []
        for agent_id in agent_ids:
            agent = self._get_agent(agent_id)
            if agent:
                agents.append(agent)
        return agents

    @staticmethod
    def _generate_id(length: int = 8) -> str:
        """生成随机 ID"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
