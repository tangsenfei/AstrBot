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

from astrbot.builtin_stars.agent_system.services.crewai_integration import (
    CREWAI_AVAILABLE,
    CrewAIAgentFactory,
)

from ..models import Roundtable, RoundtableStatus

if TYPE_CHECKING:
    from ..database import AgentDatabase
    from astrbot.core.context import Context
    from astrbot.core.agent.models import Agent


class RoundtableService:
    """圆桌会议服务"""

    def __init__(self, db: "AgentDatabase", context: "Context | None" = None) -> None:
        self.db = db
        self._context = context
        # 当前执行的会议上下文，用于构建系统提示时弱化固定 goal
        self._current_topic: str = ""
        self._current_deliverable: str = ""

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

        Args:
            roundtable_id: 圆桌会议 ID
            input_data: 输入数据（可覆盖 topic/deliverable/rounds）
            event_callback: 事件回调函数，用于 SSE 推送

        Returns:
            执行结果

        Raises:
            ValueError: 圆桌会议不存在或配置错误
        """
        from .meeting_strategies import get_strategy

        roundtable = self.get_roundtable(roundtable_id)
        if not roundtable:
            raise ValueError(f"圆桌会议 '{roundtable_id}' 不存在")

        if not roundtable.participants:
            raise ValueError(f"圆桌会议 '{roundtable_id}' 没有配置参会者")

        # 初始化执行状态
        # 续会场景：保留之前的讨论记录
        previous_records = list(roundtable.discussion_records or [])
        previous_result = dict(roundtable.result or {})
        is_continuation = bool(previous_records or previous_result.get("discussion_rounds"))

        discussion_records: list[dict[str, Any]] = list(previous_records) if is_continuation else []
        self.db.update(
            "roundtables",
            {
                "status": RoundtableStatus.RUNNING.value,
                "result": previous_result if is_continuation else {},
                "discussion_records": discussion_records,
                "current_round": 0,
                "current_speaker": "准备开始",
                "stage": "running",
                "streaming_content": "",
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(roundtable_id,)
        )

        # 发送准备事件
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
            # 获取实际执行参数（允许输入覆盖）
            topic = input_data.get("topic") or roundtable.topic
            deliverable = input_data.get("deliverable") or roundtable.deliverable
            rounds = input_data.get("rounds") or roundtable.rounds

            # 设置当前会议上下文，用于系统提示构建
            self._current_topic = topic
            self._current_deliverable = deliverable

            logger.info(f"Roundtable execution starting: {roundtable_id}, topic={topic}, rounds={rounds}, type={roundtable.meeting_type}")

            # 获取所有参会 Agent 配置
            agents = self._get_agents(roundtable.participants)
            if not agents:
                raise ValueError("没有有效的参会 Agent")

            logger.info(f"Found {len(agents)} agents for roundtable {roundtable_id}")
            for i, agent in enumerate(agents):
                logger.info(f"  Agent {i+1}: id={agent.id}, name={agent.name}, provider_id={agent.provider_id}")

            # 获取主持人
            host_agent = None
            if roundtable.host_agent_id:
                host_agent = self._get_agent(roundtable.host_agent_id)
                if not host_agent:
                    raise ValueError(f"主持人 Agent '{roundtable.host_agent_id}' 不存在")

            # 发送 agent 信息事件
            if event_callback:
                event_callback("agents_info", {
                    "agents": [{"id": a.id, "name": a.name, "role": a.role or "", "goal": a.goal or ""} for a in agents],
                    "host": {"id": host_agent.id, "name": host_agent.name} if host_agent else None
                })

            # 根据会议类型选择策略执行
            previous_context = []
            if is_continuation and previous_records:
                for record in previous_records:
                    speaker = record.get("speaker", "")
                    content = record.get("content", "")
                    rtype = record.get("type", "speech")
                    if rtype == "opening":
                        previous_context.append(f"【开场】{content}")
                    elif rtype == "summary":
                        previous_context.append(f"【总结】{content}")
                    elif rtype == "vote":
                        previous_context.append(f"【投票】{speaker}: {content}")
                    else:
                        previous_context.append(f"【{speaker}】{content}")

            strategy = get_strategy(roundtable.meeting_type, self)
            strategy_result = await strategy.execute(
                roundtable_id=roundtable_id,
                roundtable=roundtable,
                agents=agents,
                host_agent=host_agent,
                topic=topic,
                deliverable=deliverable,
                rounds=rounds,
                result=result,
                event_callback=event_callback,
                previous_context=previous_context if previous_context else None,
            )

            result["success"] = True
            result["discussion_rounds"] = strategy_result["discussion_rounds"]
            result["summary"] = strategy_result["summary"]

            # 从 discussion_rounds 重建 discussion_records
            rebuilt_records = []
            for r in strategy_result["discussion_rounds"]:
                if r.get("opening"):
                    rebuilt_records.append({
                        "round": r["round"],
                        "speaker": host_agent.name if host_agent else "系统",
                        "content": r["opening"],
                        "type": "opening",
                    })
                for s in r.get("speeches", []):
                    rebuilt_records.append({
                        "round": r["round"],
                        "speaker": s.get("agent_name", ""),
                        "content": s.get("content", ""),
                        "type": s.get("role", "speech"),
                    })
                if r.get("summary"):
                    rebuilt_records.append({
                        "round": r["round"],
                        "speaker": host_agent.name if host_agent else "系统",
                        "content": r["summary"],
                        "type": "summary",
                    })
                if r.get("votes"):
                    for v in r["votes"]:
                        rebuilt_records.append({
                            "round": r["round"],
                            "speaker": v.get("agent_name", ""),
                            "content": f"投票给: {v.get('vote', '')}",
                            "type": "vote",
                        })

            # 续会场景：合并之前的讨论记录
            if is_continuation and previous_records:
                all_records = previous_records + rebuilt_records
            else:
                all_records = rebuilt_records

            # 更新数据库状态为完成
            self.db.update(
                "roundtables",
                {
                    "status": RoundtableStatus.COMPLETED.value,
                    "result": {
                        "discussion_rounds": strategy_result["discussion_rounds"],
                        "summary": strategy_result["summary"],
                        "deliverable": strategy_result.get("deliverable", ""),
                        "executed_at": datetime.now().isoformat(),
                    },
                    "discussion_records": all_records,
                    "current_round": rounds,
                    "current_speaker": "已完成",
                    "stage": "completed",
                    "streaming_content": "",
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(roundtable_id,)
            )

            if event_callback:
                event_callback("summary", {"content": strategy_result["summary"]})
                event_callback("status", {"status": "completed", "stage": "completed", "message": "会议结束"})

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Roundtable execution failed: {roundtable_id} - {e}")

            # 重新加载已有的讨论记录（策略可能已经保存了部分记录）
            existing_rt = self.get_roundtable(roundtable_id)
            existing_records = existing_rt.discussion_records if existing_rt else []

            # 更新状态为失败，但保存已完成的讨论记录
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

            if event_callback:
                event_callback("error", {"message": str(e)})
                event_callback("status", {"status": "failed", "stage": "failed", "message": str(e)})

        finally:
            # 清除会议上下文，避免影响后续非会议调用
            self._current_topic = ""
            self._current_deliverable = ""

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        result["status"] = RoundtableStatus.COMPLETED.value if result["success"] else RoundtableStatus.FAILED.value

        return result

    def _save_discussion_records(self, roundtable_id: str, records: list[dict[str, Any]], current_round: int, current_speaker: str) -> None:
        """保存讨论记录到数据库"""
        try:
            self.db.update(
                "roundtables",
                {
                    "discussion_records": records,
                    "current_round": current_round,
                    "current_speaker": current_speaker,
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(roundtable_id,)
            )
        except Exception as e:
            logger.error(f"Failed to save discussion records: {e}")

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

    def _build_system_prompt(self, agent: Agent) -> str:
        """构建 Agent 系统提示

        在会议场景中，用会议目标临时覆盖固定的个人 goal，
        避免 Agent 只按自己的固定目标发言而脱离会议主题。
        """
        parts = []
        if agent.role:
            parts.append(f"你是一个{agent.role}。")

        # 会议场景中，用会议目标替代固定 goal，弱化个人目标，强化协作目标
        if self._current_topic and self._current_deliverable:
            parts.append(
                f"你正在参加一场圆桌会议。"
                f"会议主题：{self._current_topic}。"
                f"会议预期产出：{self._current_deliverable}。"
                f"你的任务是基于你的专业背景，为达成会议产出目标做出贡献，"
                f"积极回应其他参会者观点，推动讨论深入，而不是单纯追求你个人的固定目标。"
            )
        elif agent.goal:
            parts.append(f"你的目标是：{agent.goal}")

        if agent.backstory:
            parts.append(f"背景：{agent.backstory}")
        return "\n".join(parts)

    def _build_func_tool(self, agent: Agent) -> Any:
        """根据 Agent 配置的工具构建 func_tool

        Args:
            agent: Agent 对象

        Returns:
            ToolSet 对象，或 None
        """
        if not agent.tools or not self._context:
            return None

        try:
            tool_manager = self._context.get_llm_tool_manager()
            if not tool_manager:
                return None

            from astrbot.core.agent.tool import ToolSet
            tool_set = ToolSet()
            for tool_id in agent.tools:
                tool = tool_manager.get_func(tool_id)
                if tool and tool.active:
                    tool_set.add_tool(tool)

            if not tool_set.empty():
                logger.debug(f"Built ToolSet for agent {agent.id} with {len(tool_set.tools)} tools: {agent.tools}")
                return tool_set
        except Exception as e:
            logger.warning(f"Failed to build func_tool for agent {agent.id}: {e}")

        return None

    async def _call_agent(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
        func_tool: Any = None,
    ) -> str:
        """调用 Agent 的 LLM

        优先使用 CrewAI Agent 执行，降级到 AstrBot Provider 直接调用。

        Args:
            agent: Agent 对象
            prompt: 提示词
            tokens_result: 用于累加 token 消耗的字典
            func_tool: 工具集，None 时自动根据 agent.tools 构建

        Returns:
            LLM 响应文本
        """
        if CREWAI_AVAILABLE and self._context:
            try:
                return await self._call_agent_with_crewai(agent, prompt, tokens_result)
            except Exception as e:
                logger.warning(f"CrewAI Agent call failed, falling back to provider: {e}")

        return await self._call_agent_with_provider(agent, prompt, tokens_result, func_tool)

    def _convert_to_agent_model(self, agent: Agent):
        """将 Agent 对象转换为 AgentModel（用于 CrewAI 创建）"""
        from ..models import Agent as AgentModel, AgentType, PlanningEffort

        return AgentModel(
            id=agent.id,
            name=agent.name,
            role=agent.role or agent.name,
            goal=agent.goal or "",
            backstory=agent.backstory or "",
            tools=agent.tools if hasattr(agent, 'tools') else [],
            skills=[],
            knowledge_id=None,
            provider_id=agent.provider_id,
            model_name=agent.model_name if hasattr(agent, 'model_name') else None,
            llm_config=agent.llm_config if hasattr(agent, 'llm_config') else {},
            memory_config=agent.memory_config if hasattr(agent, 'memory_config') else {},
            planning=agent.planning if hasattr(agent, 'planning') else False,
            planning_effort=PlanningEffort(agent.planning_effort) if hasattr(agent, 'planning_effort') and agent.planning_effort else PlanningEffort.MEDIUM,
            max_iter=agent.max_iter if hasattr(agent, 'max_iter') else 20,
            verbose=False,
            allow_delegation=False,
            enabled=True,
            agent_type=AgentType.CUSTOM,
            metadata={},
        )

    async def _call_agent_with_crewai(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
    ) -> str:
        """使用 CrewAI Agent 调用"""
        agent_model = self._convert_to_agent_model(agent)
        crewai_agent = CrewAIAgentFactory.create_agent(agent_model, self._context, disable_planning=True)
        if not crewai_agent:
            raise ValueError(f"无法为 Agent '{agent.id}' 创建 CrewAI Agent")

        output = await crewai_agent.kickoff_async(prompt)

        response_text = ""
        if hasattr(output, 'raw') and output.raw:
            response_text = output.raw
        elif hasattr(output, '__str__'):
            response_text = str(output)

        if hasattr(output, 'token_usage') and output.token_usage:
            tokens_result["input"] += getattr(output.token_usage, 'prompt_tokens', 0) or 0
            tokens_result["output"] += getattr(output.token_usage, 'completion_tokens', 0) or 0
            tokens_result["total"] += getattr(output.token_usage, 'total_tokens', 0) or 0

        return response_text

    async def _call_agent_with_provider(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
        func_tool: Any = None,
    ) -> str:
        """使用 AstrBot Provider 直接调用（降级方案）"""
        if not self._context:
            raise ValueError("Context 未初始化，无法执行圆桌会议")

        provider_id = agent.provider_id
        if not provider_id:
            raise ValueError(f"Agent '{agent.id}' 未配置 LLM 提供商")

        provider = self._context.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"LLM 提供商 '{provider_id}' 不存在")

        system_prompt = self._build_system_prompt(agent)

        if func_tool is None:
            func_tool = self._build_func_tool(agent)

        llm_response = await provider.text_chat(
            prompt=prompt,
            system_prompt=system_prompt if system_prompt else None,
            contexts=[],
            func_tool=func_tool,
        )

        if llm_response.usage:
            tokens_result["input"] += getattr(llm_response.usage, 'prompt_tokens', None) or getattr(llm_response.usage, 'input', 0)
            tokens_result["output"] += getattr(llm_response.usage, 'completion_tokens', None) or getattr(llm_response.usage, 'output', 0)
            tokens_result["total"] += getattr(llm_response.usage, 'total_tokens', None) or getattr(llm_response.usage, 'total', 0)

        return llm_response.completion_text or ""

    async def _call_agent_stream(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
        event_callback: Any = None,
        round_num: int = 0,
        phase: str = "speech",
        func_tool: Any = None,
    ) -> str:
        """流式调用 Agent 的 LLM

        优先使用 CrewAI Agent 执行，降级到 AstrBot Provider 流式调用。

        Args:
            agent: Agent 对象
            prompt: 提示词
            tokens_result: 用于累加 token 消耗的字典
            event_callback: 事件回调函数
            round_num: 当前轮次
            phase: 当前阶段
            func_tool: 工具集

        Returns:
            LLM 响应完整文本
        """
        if CREWAI_AVAILABLE and self._context:
            try:
                return await self._call_agent_stream_with_crewai(
                    agent, prompt, tokens_result, event_callback, round_num, phase
                )
            except Exception as e:
                logger.warning(f"CrewAI Agent stream failed, falling back to provider: {e}")

        return await self._call_agent_stream_with_provider(
            agent, prompt, tokens_result, event_callback, round_num, phase, func_tool
        )

    async def _call_agent_stream_with_crewai(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
        event_callback: Any = None,
        round_num: int = 0,
        phase: str = "speech",
    ) -> str:
        """使用 CrewAI Agent 流式调用

        CrewAI 的 kickoff_async 是非流式调用，无法实现逐字流式输出。
        圆桌会议场景优先使用 Provider 的 text_chat_stream 实现真正的流式输出，
        以便参会人发言内容能实时推送给前端。
        """
        return await self._call_agent_stream_with_provider(
            agent, prompt, tokens_result, event_callback, round_num, phase, None
        )

    async def _call_agent_stream_with_provider(
        self,
        agent: Agent,
        prompt: str,
        tokens_result: dict[str, int],
        event_callback: Any = None,
        round_num: int = 0,
        phase: str = "speech",
        func_tool: Any = None,
    ) -> str:
        """使用 AstrBot Provider 流式调用（降级方案）

        使用 chunk 缓冲机制，将多个小 chunk 合并后批量推送，
        减少高频事件推送导致的 CPU 消耗。
        """
        if not self._context:
            raise ValueError("Context 未初始化，无法执行圆桌会议")

        provider_id = agent.provider_id
        if not provider_id:
            raise ValueError(f"Agent '{agent.id}' 未配置 LLM 提供商")

        provider = self._context.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"LLM 提供商 '{provider_id}' 不存在")

        system_prompt = self._build_system_prompt(agent)

        if func_tool is None:
            func_tool = self._build_func_tool(agent)

        full_text = ""
        chunk_buffer = ""
        thinking_buffer = ""
        CHUNK_FLUSH_SIZE = 6
        THINKING_FLUSH_SIZE = 8
        chunk_count = 0
        thinking_count = 0

        async for llm_response in provider.text_chat_stream(
            prompt=prompt,
            system_prompt=system_prompt if system_prompt else None,
            contexts=[],
            func_tool=func_tool,
        ):
            if llm_response.role == "err":
                if chunk_buffer and event_callback:
                    event_callback("agent_speech_chunk", {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "round": round_num,
                        "phase": phase,
                        "content": chunk_buffer,
                        "streaming": True,
                    })
                    chunk_buffer = ""
                if thinking_buffer and event_callback:
                    event_callback("agent_thinking", {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "round": round_num,
                        "phase": phase,
                        "content": thinking_buffer,
                    })
                    thinking_buffer = ""
                if event_callback:
                    event_callback("error", {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "content": llm_response.completion_text,
                    })
                return full_text

            if llm_response.is_chunk:
                if llm_response.result_chain:
                    for component in llm_response.result_chain.chain:
                        if hasattr(component, 'text') and component.text:
                            chunk = component.text
                            full_text += chunk
                            if event_callback:
                                chunk_buffer += chunk
                                chunk_count += 1
                                if chunk_count >= CHUNK_FLUSH_SIZE:
                                    if thinking_buffer:
                                        event_callback("agent_thinking", {
                                            "agent_id": agent.id,
                                            "agent_name": agent.name,
                                            "round": round_num,
                                            "phase": phase,
                                            "content": thinking_buffer,
                                        })
                                        thinking_buffer = ""
                                        thinking_count = 0
                                    event_callback("agent_speech_chunk", {
                                        "agent_id": agent.id,
                                        "agent_name": agent.name,
                                        "round": round_num,
                                        "phase": phase,
                                        "content": chunk_buffer,
                                        "streaming": True,
                                    })
                                    chunk_buffer = ""
                                    chunk_count = 0

                if llm_response.reasoning_content:
                    if event_callback:
                        thinking_buffer += llm_response.reasoning_content
                        thinking_count += 1
                        if thinking_count >= THINKING_FLUSH_SIZE:
                            if chunk_buffer:
                                event_callback("agent_speech_chunk", {
                                    "agent_id": agent.id,
                                    "agent_name": agent.name,
                                    "round": round_num,
                                    "phase": phase,
                                    "content": chunk_buffer,
                                    "streaming": True,
                                })
                                chunk_buffer = ""
                                chunk_count = 0
                            event_callback("agent_thinking", {
                                "agent_id": agent.id,
                                "agent_name": agent.name,
                                "round": round_num,
                                "phase": phase,
                                "content": thinking_buffer,
                            })
                            thinking_buffer = ""
                            thinking_count = 0
            else:
                if llm_response.result_chain:
                    for component in llm_response.result_chain.chain:
                        if hasattr(component, 'text') and component.text:
                            if not full_text:
                                full_text += component.text

                if llm_response.usage:
                    tokens_result["input"] += getattr(llm_response.usage, 'prompt_tokens', None) or getattr(llm_response.usage, 'input', 0)
                    tokens_result["output"] += getattr(llm_response.usage, 'completion_tokens', None) or getattr(llm_response.usage, 'output', 0)
                    tokens_result["total"] += getattr(llm_response.usage, 'total_tokens', None) or getattr(llm_response.usage, 'total', 0)

        if thinking_buffer and event_callback:
            event_callback("agent_thinking", {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "round": round_num,
                "phase": phase,
                "content": thinking_buffer,
            })

        if chunk_buffer and event_callback:
            event_callback("agent_speech_chunk", {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "round": round_num,
                "phase": phase,
                "content": chunk_buffer,
                "streaming": True,
            })

        if event_callback:
            event_callback("agent_speech", {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "round": round_num,
                "phase": phase,
                "content": full_text,
                "streaming": False,
            })

        return full_text

    async def _call_system_opening(
        self,
        topic: str,
        deliverable: str,
        agents: list[Agent],
        tokens_result: dict[str, int]
    ) -> str:
        """系统开场（无主持人模式）"""
        agent_names = ", ".join([a.name for a in agents])
        prompt = (
            f"你是一场圆桌会议的系统引导者。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"参会者：{agent_names}\n\n"
            f"请作为系统引导者，为这场圆桌会议做一个简短的开场，"
            f"介绍讨论主题、预期产出，并引导各位参会者开始发言。"
            f"请控制在 200 字以内。"
        )
        # 使用第一个 Agent 的 provider 来执行系统引导
        if agents and agents[0].provider_id:
            return await self._call_agent(agents[0], prompt, tokens_result)
        return f"欢迎参加关于「{topic}」的圆桌会议，请各位专家依次发表见解。"

    async def _call_system_summary(
        self,
        topic: str,
        deliverable: str,
        speeches: list[dict[str, Any]],
        round_num: int,
        total_rounds: int,
        tokens_result: dict[str, int]
    ) -> str:
        """系统总结（无主持人模式）"""
        speech_text = "\n".join([f"- {s['agent_name']}：{s['content']}" for s in speeches])
        prompt = (
            f"你是一场圆桌会议的系统引导者。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"当前是第 {round_num}/{total_rounds} 轮讨论。\n\n"
            f"本轮发言：\n{speech_text}\n\n"
            f"请对本轮讨论进行简要总结，并引导下一轮讨论的方向。"
            f"请控制在 200 字以内。"
        )
        if speeches:
            # 使用第一个发言者的 provider
            agent = self._get_agent(speeches[0]["agent_id"])
            if agent and agent.provider_id:
                return await self._call_agent(agent, prompt, tokens_result)
        return f"第 {round_num} 轮讨论结束，请各位继续深入探讨。"

    async def _call_system_final_summary(
        self,
        topic: str,
        deliverable: str,
        discussion_rounds: list[dict[str, Any]],
        tokens_result: dict[str, int]
    ) -> str:
        """系统生成最终会议纪要（无主持人模式）"""
        rounds_text = ""
        for r in discussion_rounds:
            rounds_text += f"\n第 {r['round']} 轮：\n"
            if r.get("opening"):
                rounds_text += f"开场：{r['opening']}\n"
            for s in r.get("speeches", []):
                rounds_text += f"- {s['agent_name']}：{s['content']}\n"
            if r.get("summary"):
                rounds_text += f"总结：{r['summary']}\n"

        prompt = (
            f"你是一场圆桌会议的系统引导者。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n\n"
            f"以下是全部讨论记录：\n{rounds_text}\n\n"
            f"请生成一份完整的会议纪要，包括：\n"
            f"1. 讨论背景与目标\n"
            f"2. 各方主要观点\n"
            f"3. 达成的共识\n"
            f"4. 待进一步讨论的问题\n"
            f"5. 行动建议\n"
        )
        # 尝试使用第一个参会者的 provider
        for r in discussion_rounds:
            for s in r.get("speeches", []):
                agent = self._get_agent(s["agent_id"])
                if agent and agent.provider_id:
                    return await self._call_agent(agent, prompt, tokens_result)
        return "会议纪要生成失败：没有可用的 LLM 提供商。"

    def _build_host_opening_prompt(
        self,
        host: Agent,
        topic: str,
        deliverable: str,
        agents: list[Agent]
    ) -> str:
        """构建主持人开场提示"""
        agent_names = ", ".join([a.name for a in agents if a.id != host.id])
        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"参会者：{agent_names}\n\n"
            f"请作为主持人，为这场圆桌会议做一个简短的开场，"
            f"介绍讨论主题、预期产出，并引导各位参会者开始发言。"
            f"请控制在 200 字以内。"
        )

    def _build_speech_prompt(
        self,
        agent: Agent,
        topic: str,
        deliverable: str,
        context_history: list[str],
        round_num: int
    ) -> str:
        """构建参会者发言提示"""
        context_text = "\n".join(context_history[-6:])  # 最近 6 条上下文，避免信息过载
        return (
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"当前是第 {round_num} 轮讨论。\n\n"
            f"之前的讨论：\n{context_text}\n\n"
            f"【发言要求】\n"
            f"1. 你的发言必须围绕会议主题和预期产出\n"
            f"2. 请回应或补充之前参会者的观点，不要完全自说自话\n"
            f"3. 提出建设性意见，推动讨论向产出目标前进\n"
            f"4. 如果之前的观点有不足，请礼貌地指出并补充\n"
            f"5. 控制在 250 字以内"
        )

    def _build_host_summary_prompt(
        self,
        host: Agent,
        topic: str,
        deliverable: str,
        speeches: list[dict[str, Any]],
        round_num: int,
        total_rounds: int
    ) -> str:
        """构建主持人总结提示"""
        speech_text = "\n".join([f"- {s['agent_name']}：{s['content']}" for s in speeches])
        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"当前是第 {round_num}/{total_rounds} 轮讨论。\n\n"
            f"本轮发言：\n{speech_text}\n\n"
            f"请对本轮讨论进行简要总结，并引导下一轮讨论的方向。"
            f"请控制在 200 字以内。"
        )

    def _build_final_summary_prompt(
        self,
        host: Agent,
        topic: str,
        deliverable: str,
        discussion_rounds: list[dict[str, Any]]
    ) -> str:
        """构建最终会议纪要提示"""
        rounds_text = ""
        for r in discussion_rounds:
            rounds_text += f"\n第 {r['round']} 轮：\n"
            if r.get("opening"):
                rounds_text += f"开场：{r['opening']}\n"
            for s in r.get("speeches", []):
                rounds_text += f"- {s['agent_name']}：{s['content']}\n"
            if r.get("summary"):
                rounds_text += f"总结：{r['summary']}\n"

        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n\n"
            f"以下是全部讨论记录：\n{rounds_text}\n\n"
            f"请生成一份完整的会议纪要，包括：\n"
            f"1. 讨论背景与目标\n"
            f"2. 各方主要观点\n"
            f"3. 达成的共识\n"
            f"4. 待进一步讨论的问题\n"
            f"5. 行动建议\n"
        )

    @staticmethod
    def _generate_id(length: int = 8) -> str:
        """生成随机 ID"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
