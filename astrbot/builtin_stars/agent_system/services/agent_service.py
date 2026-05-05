"""
智能体管理模块 - 智能体服务

提供智能体的 CRUD 操作、测试、复制、模板等功能
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

if TYPE_CHECKING:
    from astrbot.core.star.context import Context

    from ..database import Database

from ..models import Agent, PlanningEffort

_agent_operator = AgentOperator()

PLANNING_EFFORT_MAP = {
    "low": {
        "reasoning_effort": "low",
        "max_steps": 5,
        "max_replans": 1,
        "prompt_template": "请简要列出完成以下任务的关键步骤（1-3步）：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n1. [步骤1]\n2. [步骤2]\n...",
    },
    "medium": {
        "reasoning_effort": "medium",
        "max_steps": 15,
        "max_replans": 3,
        "prompt_template": "请为以下任务制定详细的执行计划，包含具体步骤和预期结果：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n### 步骤1: [标题]\n- 描述: ...\n- 预期输出: ...\n\n### 步骤2: [标题]\n- 描述: ...\n- 预期输出: ...\n...",
    },
    "high": {
        "reasoning_effort": "high",
        "max_steps": 30,
        "max_replans": 5,
        "prompt_template": "请为以下任务制定非常详细的执行计划，包含问题分析、信息收集策略、详细执行步骤（含子步骤）、每步预期输出和风险评估：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n\n### 问题分析\n- 核心问题: ...\n- 关键约束: ...\n\n### 信息收集\n- 需要的信息: ...\n- 获取方式: ...\n\n### 执行步骤\n#### 步骤1: [标题]\n- 描述: ...\n- 子步骤:\n  1.1. ...\n  1.2. ...\n- 预期输出: ...\n- 风险: ...\n- 备选方案: ...\n\n#### 步骤2: [标题]\n...\n\n### 总结\n- 预计总步骤数: ...\n- 关键里程碑: ...\n",
    },
}


class _BuiltinMemoryProvider:
    def __init__(self, db):
        self._db = db

    def store(self, agent_id: str, role: str, content: str, summary: str = "", **kwargs) -> None:
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        self._db.insert("agent_memories", {
            "id": memory_id,
            "agent_id": agent_id,
            "role": role,
            "content": content[:2000],
            "summary": summary[:500] if summary else content[:200],
            "scope": kwargs.get("scope", "default"),
            "importance": kwargs.get("importance", 0.5),
        })

    def retrieve(self, agent_id: str, query: str, memory_type: str = "short_term", max_items: int = 20) -> list[dict]:
        if memory_type == "short_term":
            rows = self._db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="created_at DESC",
                limit=max_items,
            )
        else:
            rows = self._db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="importance DESC, created_at DESC",
                limit=max_items,
            )
        memories = []
        for row in reversed(rows):
            memories.append({
                "role": row.get("role", ""),
                "content": row.get("summary") or row.get("content", ""),
            })
        return memories


def _create_mock_event(message: str = "", context=None):
    class MockEvent:
        def __init__(self, msg="", ctx=None):
            self.unified_msg_origin = "agent_test:private:test_session"
            self.message_str = msg
            self.role = "admin"
            self.is_wake = True
            self.is_at_or_wake_command = True
            self._result = None
            self._extras = {}
            self._has_send_oper = False
            self.call_llm = False
            self._temporary_local_files = []
            self.plugins_name = None
            self.context = ctx

            from astrbot.core.platform.message_session import MessageSession
            from astrbot.core.platform.message_type import MessageType
            self.session = MessageSession(
                platform_name="agent_test",
                message_type=MessageType.FRIEND_MESSAGE,
                session_id="test_session",
            )

            from astrbot.core.platform.astrbot_message import (
                AstrBotMessage,
                MessageMember,
            )
            from astrbot.core.platform.message_type import MessageType as MsgType
            from astrbot.core.platform.platform_metadata import PlatformMetadata
            self.platform_meta = PlatformMetadata(name="agent_test", description="Agent Test", id="agent_test")
            self.platform = self.platform_meta

            self.message_obj = AstrBotMessage()
            self.message_obj.message = []
            self.message_obj.message_str = msg
            self.message_obj.session_id = "test_session"
            self.message_obj.self_id = "agent_test"
            self.message_obj.message_id = "test_msg_id"
            self.message_obj.sender = MessageMember(user_id="test_user", nickname="Tester")
            self.message_obj.type = MsgType.FRIEND_MESSAGE
            self.message_obj.raw_message = msg

        def get_result(self): return self._result
        def set_result(self, result): self._result = result
        def clear_result(self): self._result = None
        def stop_event(self): pass
        def continue_event(self): pass
        def is_stopped(self): return False
        def should_call_llm(self, call_llm): self.call_llm = call_llm
        def set_extra(self, key, value): self._extras[key] = value
        def get_extra(self, key=None, default=None):
            if key is None: return self._extras
            return self._extras.get(key, default)
        def clear_extra(self): self._extras = {}
        def get_platform_name(self): return "agent_test"
        def get_platform_id(self): return "agent_test"
        def get_message_str(self): return self.message_str
        def get_session_id(self): return "test_session"
        def get_group_id(self): return ""
        def get_self_id(self): return "agent_test"
        def get_sender_id(self): return "test_user"
        def get_sender_name(self): return "Tester"
        async def send(self, Chain): self._has_send_oper = True
        async def send_streaming(self, generator, use_fallback=False): pass
        async def send_typing(self): pass
        async def stop_typing(self): pass
        def track_temporary_local_file(self, path): self._temporary_local_files.append(path)
        def cleanup_temporary_local_files(self): pass

    return MockEvent(message, ctx=context)


class AgentService:
    """智能体管理服务"""

    def __init__(self, db: Database, context: Context | None = None):
        self.db = db
        self._context = context
        self._memory_provider = None

    @property
    def context(self) -> Context | None:
        """获取 Context 实例"""
        return self._context

    def get_agents(self, category: str | None = None) -> list[Agent]:
        """获取智能体列表

        Args:
            category: 分类筛选（可选，按 metadata.category 筛选）

        Returns:
            智能体列表
        """
        agents = []

        if category:
            # 按分类筛选
            rows = self.db.select_all(
                "agents",
                where="json_extract(metadata, '$.category') = ?",
                where_params=(category,),
                order_by="created_at DESC"
            )
        else:
            rows = self.db.select_all("agents", order_by="created_at DESC")

        for row in rows:
            try:
                agent = self._row_to_agent(row)
                agents.append(agent)
            except Exception as e:
                logger.error(f"Failed to parse agent {row.get('id')}: {e}")

        return agents

    def get_agent(self, agent_id: str) -> Agent | None:
        """获取单个智能体

        Args:
            agent_id: 智能体 ID

        Returns:
            智能体对象，不存在则返回 None
        """
        row = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
        if row:
            return self._row_to_agent(row)
        return None

    def create_agent(self, data: dict[str, Any], skip_skill_validation: bool = False) -> Agent:
        """创建智能体

        Args:
            data: 智能体数据
                - name: 智能体名称（必填）
                - role: 角色定义
                - goal: 目标
                - backstory: 背景故事
                - tools: 工具 ID 列表
                - skills: 技能 ID 列表
                - knowledge_id: 知识库 ID
                - provider_id: LLM 提供商 ID
                - model_name: 模型名称
                - llm_config: LLM 配置
                - memory_config: 记忆配置
                - planning: 是否启用规划
                - planning_effort: 规划努力程度 (low/medium/high)
                - max_iter: 最大迭代次数
                - max_rpm: 每分钟最大请求数
                - verbose: 是否详细输出
                - allow_delegation: 是否允许委托
                - enabled: 是否启用
                - metadata: 元数据

        Returns:
            创建的智能体对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("智能体名称不能为空")

        # 生成 ID
        agent_id = data.get("id") or f"agent_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_agent(agent_id)
        if existing:
            raise ValueError(f"智能体 ID '{agent_id}' 已存在")

        # 验证 planning_effort
        planning_effort = PlanningEffort.MEDIUM
        if data.get("planning_effort"):
            try:
                planning_effort = PlanningEffort(data["planning_effort"])
            except ValueError:
                raise ValueError(f"无效的 planning_effort 值: {data['planning_effort']}")

        # 验证关联的知识库是否存在
        knowledge_id = data.get("knowledge_id")
        if knowledge_id:
            kb = self.db.select_one("knowledge", where="id = ?", where_params=(knowledge_id,))
            if not kb:
                raise ValueError(f"知识库 '{knowledge_id}' 不存在")

        # 验证关联的工具是否存在
        tools = data.get("tools", [])
        if tools:
            for tool_id in tools:
                # 工具可能是内置工具或 MCP 工具，这里只验证自定义工具
                pass  # TODO: 实现工具验证

        # 验证关联的技能是否存在
        skills = data.get("skills", [])
        if skills and not skip_skill_validation:
            for skill_id in skills:
                # 先检查本地数据库
                skill = self.db.select_one("skills", where="id = ?", where_params=(skill_id,))
                if skill:
                    continue
                # 再检查 AstrBot 核心技能
                if skill_id.startswith("astrbot_"):
                    from astrbot.core.skills.skill_manager import SkillManager
                    try:
                        skill_manager = SkillManager()
                        skill_infos = skill_manager.list_skills(active_only=True)
                        found = any(
                            f"astrbot_{si.name.lower().replace('-', '_').replace(' ', '_')}" == skill_id
                            for si in skill_infos
                        )
                        if found:
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to check AstrBot skill: {e}")
                raise ValueError(f"技能 '{skill_id}' 不存在")

        now = datetime.now()
        agent_data = {
            "id": agent_id,
            "name": data["name"],
            "role": data.get("role", ""),
            "goal": data.get("goal", ""),
            "backstory": data.get("backstory", ""),
            "tools": data.get("tools", []),
            "skills": data.get("skills", []),
            "knowledge_id": knowledge_id,
            "provider_id": data.get("provider_id"),
            "model_name": data.get("model_name"),
            "llm_config": data.get("llm_config", {}),
            "memory_config": data.get("memory_config", {}),
            "planning": data.get("planning", False),
            "planning_effort": planning_effort.value,
            "max_iter": data.get("max_iter", 20),
            "max_rpm": data.get("max_rpm"),
            "verbose": data.get("verbose", False),
            "allow_delegation": data.get("allow_delegation", False),
            "enabled": data.get("enabled", True),
            "agent_type": data.get("agent_type", "custom"),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("agents", agent_data)

        logger.info(f"Created agent: {agent_id}")
        return self._row_to_agent(agent_data)

    def import_agents(self, agents_data: list[dict[str, Any]]) -> list[Agent]:
        """批量导入智能体

        Args:
            agents_data: 智能体数据列表

        Returns:
            成功导入的智能体列表
        """
        imported = []
        for data in agents_data:
            try:
                if not data.get("name"):
                    logger.warning(f"Skipping agent without name: {data}")
                    continue
                agent_id = data.get("id") or f"agent_{uuid.uuid4().hex[:8]}"
                existing = self.get_agent(agent_id)
                if existing:
                    logger.warning(f"Agent {agent_id} already exists, skipping")
                    continue
                agent = self.create_agent({**data, "id": agent_id})
                imported.append(agent)
            except Exception as e:
                logger.error(f"Failed to import agent: {e}")
        logger.info(f"Imported {len(imported)} agents")
        return imported

    def update_agent(self, agent_id: str, data: dict[str, Any], skip_skill_validation: bool = False) -> Agent | None:
        """更新智能体

        Args:
            agent_id: 智能体 ID
            data: 更新数据

        Returns:
            更新后的智能体对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找智能体
        row = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
        if not row:
            return None

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = [
            "name", "role", "goal", "backstory",
            "tools", "skills", "knowledge_id",
            "provider_id", "model_name", "llm_config",
            "memory_config", "planning", "planning_effort",
            "max_iter", "max_rpm", "verbose",
            "allow_delegation", "enabled", "agent_type", "metadata"
        ]

        for field in updatable_fields:
            if field in data:
                # 特殊处理 planning_effort
                if field == "planning_effort":
                    try:
                        planning_effort = PlanningEffort(data["planning_effort"])
                        update_data[field] = planning_effort.value
                    except ValueError:
                        raise ValueError(f"无效的 planning_effort 值: {data['planning_effort']}")
                else:
                    update_data[field] = data[field]

        # 验证关联的知识库是否存在
        if "knowledge_id" in data and data["knowledge_id"]:
            kb = self.db.select_one("knowledge", where="id = ?", where_params=(data["knowledge_id"],))
            if not kb:
                raise ValueError(f"知识库 '{data['knowledge_id']}' 不存在")

        # 验证关联的技能是否存在
        if "skills" in data and data["skills"] and not skip_skill_validation:
            for skill_id in data["skills"]:
                # 先检查本地数据库
                skill = self.db.select_one("skills", where="id = ?", where_params=(skill_id,))
                if skill:
                    continue
                # 再检查 AstrBot 核心技能
                if skill_id.startswith("astrbot_"):
                    from astrbot.core.skills.skill_manager import SkillManager
                    try:
                        skill_manager = SkillManager()
                        skill_infos = skill_manager.list_skills(active_only=True)
                        found = any(
                            f"astrbot_{si.name.lower().replace('-', '_').replace(' ', '_')}" == skill_id
                            for si in skill_infos
                        )
                        if found:
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to check AstrBot skill: {e}")
                raise ValueError(f"技能 '{skill_id}' 不存在")

        # 更新数据库
        self.db.update(
            "agents",
            update_data,
            where="id = ?",
            where_params=(agent_id,)
        )

        logger.info(f"Updated agent: {agent_id}")
        return self.get_agent(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        """删除智能体

        Args:
            agent_id: 智能体 ID

        Returns:
            是否删除成功
        """
        # 查找智能体
        row = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
        if not row:
            return False

        # 检查是否有关联的 Crew
        crews = self.db.select_all("crews")
        for crew_row in crews:
            agents = self._parse_json(crew_row.get("agents", "[]"))
            if agent_id in agents:
                raise ValueError(f"智能体 '{agent_id}' 正在被 Crew '{crew_row['name']}' 使用，无法删除")

        # 检查是否有关联的子任务
        sub_tasks = self.db.select_all("sub_tasks", where="agent_id = ?", where_params=(agent_id,))
        if sub_tasks:
            raise ValueError(f"智能体 '{agent_id}' 有 {len(sub_tasks)} 个关联的子任务，无法删除")

        # 删除智能体
        self.db.delete("agents", where="id = ?", where_params=(agent_id,))
        logger.info(f"Deleted agent: {agent_id}")
        return True

    async def test_agent(self, agent_id: str, message: str, history: list | None = None) -> dict[str, Any]:
        """测试智能体

        使用 AstrBot Provider 直接调用。

        Args:
            agent_id: 智能体 ID
            message: 测试消息
            history: 对话历史记录

        Returns:
            测试结果

        Raises:
            ValueError: 智能体不存在或配置错误
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"智能体 '{agent_id}' 不存在")

        original_message = message

        result = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "message": message,
            "success": False,
            "response": None,
            "error": None,
            "execution_time_ms": 0,
            "memory_used": 0,
            "planning_steps": None,
            "tokens": {
                "input": 0,
                "output": 0,
                "total": 0,
            },
        }

        start_time = datetime.now()

        try:
            if not agent.provider_id:
                raise ValueError("智能体未配置 LLM 提供商")

            if not self._context:
                raise ValueError("Context 未初始化，无法测试智能体")

            fallback_result = await self._test_agent_with_graph(agent, message, history)
            result.update(fallback_result)

            if agent.memory_config.get("enabled"):
                self._store_memory(agent_id, "user", original_message)
                if result.get("response"):
                    self._store_memory(agent_id, "assistant", result["response"])

        except Exception as e:
            import traceback
            result["error"] = str(e)
            logger.error(f"Agent test failed: {agent_id} - {e}")
            logger.error(f"Agent test traceback: {traceback.format_exc()}")

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)

        return result

    async def _test_agent_with_graph(self, agent: Agent, message: str, history: list | None = None) -> dict[str, Any]:
        provider = self._context.get_provider_by_id(agent.provider_id)
        if not provider:
            raise ValueError(f"LLM 提供商 '{agent.provider_id}' 不存在")

        retrieved_memories = []
        if agent.memory_config.get("enabled"):
            retrieved_memories = self._retrieve_memories(agent.id, message, agent.memory_config)

        system_prompt = self._build_system_prompt(agent, memories=retrieved_memories)

        contexts = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    contexts.append({"role": role, "content": content})

        planning_steps = None
        if agent.planning:
            planning_effort = agent.planning_effort.value if hasattr(agent.planning_effort, "value") else str(agent.planning_effort)
            effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
            planning_prompt = effort_config["prompt_template"].format(message=message)
            try:
                planning_response = await provider.text_chat(
                    prompt=planning_prompt,
                    system_prompt=system_prompt,
                    contexts=contexts,
                )
                planning_steps = planning_response.completion_text
            except Exception as e:
                logger.error(f"Planning failed: {e}")
                planning_steps = None

            if planning_steps:
                contexts.append({
                    "role": "assistant",
                    "content": f"[执行计划]\n{planning_steps}"
                })

        func_tools = []
        if agent.tools and len(agent.tools) > 0:
            func_tools = list(agent.tools)

        session_id = f"test_{agent.id}_{uuid.uuid4().hex[:6]}"

        run_ctx = GraphRunContext(
            provider=provider,
            tool_executor=None,
            hooks=None,
            astr_event=None,
            config={
                "provider_id": agent.provider_id,
                "max_agent_step": 5,
                "tool_call_timeout": 60,
                "streaming_response": False,
            },
        )
        state = AgentGraphState(
            system_prompt=system_prompt,
            user_prompt=message,
            messages=contexts,
            session_id=session_id,
            provider_id=agent.provider_id,
            func_tools=func_tools if func_tools else None,
        )

        result = await _agent_operator.execute(state, run_ctx, write_stream=False)

        final_text = result.get("final_text", "")
        tool_calls = result.get("tool_calls", [])
        tools_used = [tc.get("name", "") for tc in tool_calls if tc.get("name")]
        stats = result.get("stats", {})
        raw_token_usage = stats.get("token_usage", {})
        tokens = {
            "input": raw_token_usage.get("input_other", 0) + raw_token_usage.get("input_cached", 0),
            "input_other": raw_token_usage.get("input_other", 0),
            "input_cached": raw_token_usage.get("input_cached", 0),
            "output": raw_token_usage.get("output", 0),
            "total": raw_token_usage.get("input_other", 0) + raw_token_usage.get("input_cached", 0) + raw_token_usage.get("output", 0),
        }

        return {
            "success": True,
            "response": final_text or "未能获取响应",
            "tools_used": tools_used,
            "planning_steps": planning_steps,
            "tokens": tokens,
            "memory_used": len(retrieved_memories),
        }

    async def test_agent_stream(
        self, agent_id: str, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式测试智能体

        使用 AstrBot Provider 流式调用。

        Args:
            agent_id: 智能体 ID
            message: 测试消息

        Yields:
            流式事件字典，包含 type 和 data 字段
        """
        start_time = datetime.now()
        original_message = message

        try:
            agent = self.get_agent(agent_id)
            if not agent:
                yield {"type": "error", "data": f"智能体 '{agent_id}' 不存在"}
                return

            if not self._context:
                yield {"type": "error", "data": "Context 未初始化"}
                return

            provider_id = agent.provider_id
            if not provider_id:
                yield {"type": "error", "data": "智能体未配置 LLM 提供商"}
                return

            async for event in self._test_agent_stream_with_graph(agent, message):
                yield event

            if agent.memory_config.get("enabled"):
                self._store_memory(agent_id, "user", original_message)

        except Exception as e:
            import traceback
            logger.error(f"Agent stream test failed: {agent_id} - {e}")
            logger.error(f"Agent stream traceback: {traceback.format_exc()}")
            yield {"type": "error", "data": str(e)}

    async def _test_agent_stream_with_graph(self, agent: Agent, message: str) -> AsyncGenerator[dict[str, Any], None]:
        provider = self._context.get_provider_by_id(agent.provider_id)
        if not provider:
            yield {"type": "error", "data": f"提供商 '{agent.provider_id}' 未找到"}
            return

        start_time = datetime.now()

        retrieved_memories = []
        if agent.memory_config.get("enabled"):
            retrieved_memories = self._retrieve_memories(agent.id, message, agent.memory_config)

        system_prompt = self._build_system_prompt(agent, memories=retrieved_memories)

        contexts = []

        planning_steps = None
        if agent.planning:
            planning_effort = agent.planning_effort.value if hasattr(agent.planning_effort, "value") else str(agent.planning_effort)
            effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
            planning_prompt = effort_config["prompt_template"].format(message=message)
            try:
                planning_response = await provider.text_chat(
                    prompt=planning_prompt,
                    system_prompt=system_prompt,
                    contexts=contexts,
                )
                planning_steps = planning_response.completion_text
            except Exception as e:
                logger.error(f"Planning failed: {e}")
                planning_steps = None

            if planning_steps:
                contexts.append({
                    "role": "assistant",
                    "content": f"[执行计划]\n{planning_steps}"
                })
                yield {"type": "planning", "data": planning_steps}

        func_tools = []
        if agent.tools and len(agent.tools) > 0:
            func_tools = list(agent.tools)

        session_id = f"test_{agent.id}_{uuid.uuid4().hex[:6]}"

        import asyncio
        stream_queue: asyncio.Queue = asyncio.Queue()

        def _stream_callback(event):
            stream_queue.put_nowait(event)

        mock_event = self._create_mock_event(message)

        run_ctx = GraphRunContext(
            provider=provider,
            tool_executor=None,
            hooks=None,
            astr_event=mock_event,
            config={
                "provider_id": agent.provider_id,
                "max_agent_step": 5,
                "tool_call_timeout": 60,
                "streaming_response": True,
            },
            writer=_stream_callback,
        )
        state = AgentGraphState(
            system_prompt=system_prompt,
            user_prompt=message,
            messages=contexts,
            session_id=session_id,
            provider_id=agent.provider_id,
            func_tools=func_tools if func_tools else None,
        )

        execute_task = asyncio.create_task(
            _agent_operator.execute(state, run_ctx, write_stream=True)
        )

        try:
            while not execute_task.done() or not stream_queue.empty():
                try:
                    ev = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                event_type = ev.event if hasattr(ev, "event") else ev.get("event", "")
                event_data = ev.data if hasattr(ev, "data") else ev.get("data", {})

                if event_type == "text_delta":
                    yield {"type": "chunk", "data": event_data.get("text", "")}
                elif event_type == "reasoning":
                    yield {"type": "thinking", "data": event_data.get("text", "")}
                elif event_type == "tool_call":
                    yield {"type": "tool_start", "data": {"name": event_data.get("name", ""), "args": event_data.get("args", {}), "id": event_data.get("id", "")}}
                elif event_type == "tool_result":
                    yield {"type": "tool_result", "data": {"name": event_data.get("name", ""), "result": event_data.get("result", event_data.get("content", "")), "id": event_data.get("id", "")}}
                elif event_type == "error":
                    yield {"type": "error", "data": event_data.get("message", str(event_data))}

                await asyncio.sleep(0)

            result = await execute_task
        except Exception as e:
            logger.error(f"Agent stream execute error: {e}", exc_info=True)
            yield {"type": "error", "data": str(e)}
            if not execute_task.done():
                execute_task.cancel()
            return

        if result.get("error"):
            yield {"type": "error", "data": result["error"]}

        final_text = result.get("final_text", "")
        tool_calls = result.get("tool_calls", [])
        tools_used = [tc.get("name", "") for tc in tool_calls if tc.get("name")]
        stats = result.get("stats", {})
        raw_token_usage = stats.get("token_usage", {})
        tokens = {
            "input": raw_token_usage.get("input_other", 0) + raw_token_usage.get("input_cached", 0),
            "input_other": raw_token_usage.get("input_other", 0),
            "input_cached": raw_token_usage.get("input_cached", 0),
            "output": raw_token_usage.get("output", 0),
            "total": raw_token_usage.get("input_other", 0) + raw_token_usage.get("input_cached", 0) + raw_token_usage.get("output", 0),
        }

        end_time = datetime.now()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        yield {
            "type": "done",
            "data": {
                "response": final_text or "未能获取响应",
                "tools_used": tools_used,
                "planning_steps": planning_steps,
                "execution_time_ms": execution_time_ms,
                "tokens": tokens,
                "time_to_first_token": stats.get("time_to_first_token", 0),
            }
        }

    def duplicate_agent(self, agent_id: str) -> Agent:
        """复制智能体

        Args:
            agent_id: 智能体 ID

        Returns:
            复制后的智能体对象

        Raises:
            ValueError: 智能体不存在
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"智能体 '{agent_id}' 不存在")

        # 创建副本数据
        data = agent.to_dict()
        data["id"] = f"agent_{uuid.uuid4().hex[:8]}"
        data["name"] = f"{agent.name} (副本)"
        data.pop("created_at", None)
        data.pop("updated_at", None)

        # 创建新的智能体
        return self.create_agent(data)

    def get_templates(self) -> list[dict[str, Any]]:
        """获取智能体模板列表

        Returns:
            模板列表
        """
        templates = [
            {
                "id": "template_general_assistant",
                "name": "通用助手",
                "description": "一个通用的 AI 助手，可以回答问题、提供建议和执行任务",
                "category": "general",
                "role": "AI 助手",
                "goal": "帮助用户解决问题，提供准确、有用的信息和建议",
                "backstory": "我是一个经过训练的 AI 助手，具有广泛的知识储备和问题解决能力。",
                "tools": [],
                "skills": [],
                "planning": False,
                "max_iter": 20,
            },
            {
                "id": "template_code_expert",
                "name": "代码专家",
                "description": "专注于编程和软件开发的技术专家",
                "category": "development",
                "role": "高级软件工程师",
                "goal": "帮助用户编写、调试和优化代码，解决技术问题",
                "backstory": "我是一名经验丰富的软件工程师，精通多种编程语言和开发框架，擅长代码审查和性能优化。",
                "tools": [],
                "skills": [],
                "planning": True,
                "planning_effort": "high",
                "max_iter": 30,
            },
            {
                "id": "template_data_analyst",
                "name": "数据分析师",
                "description": "专注于数据分析和可视化的专家",
                "category": "analytics",
                "role": "数据分析师",
                "goal": "分析数据，发现模式，提供洞察和建议",
                "backstory": "我是一名专业的数据分析师，擅长统计分析、数据可视化和机器学习。",
                "tools": [],
                "skills": [],
                "planning": True,
                "planning_effort": "medium",
                "max_iter": 25,
            },
            {
                "id": "template_content_writer",
                "name": "内容创作者",
                "description": "专注于内容创作和文案撰写的专家",
                "category": "content",
                "role": "内容创作者",
                "goal": "创作高质量的内容，包括文章、文案、故事等",
                "backstory": "我是一名专业的内容创作者，擅长各种文体的写作，能够根据需求创作引人入胜的内容。",
                "tools": [],
                "skills": [],
                "planning": False,
                "max_iter": 15,
            },
            {
                "id": "template_customer_service",
                "name": "客服助手",
                "description": "专注于客户服务和问题解决的智能客服",
                "category": "service",
                "role": "客户服务代表",
                "goal": "提供优质的客户服务，解答疑问，处理投诉",
                "backstory": "我是一名专业的客户服务代表，具有出色的沟通能力和问题解决能力，始终保持友好和耐心。",
                "tools": [],
                "skills": [],
                "planning": False,
                "max_iter": 20,
            },
            {
                "id": "template_meeting_assistant",
                "name": "会议助手",
                "description": "专业的圆桌会议主持人，负责会议准备、引导讨论、生成纪要和交付物",
                "category": "meeting",
                "role": "圆桌会议主持人",
                "goal": "高效主持圆桌会议，确保讨论聚焦、深入、有产出。在准备阶段收集和整理材料，在会议中引导讨论方向、控制节奏、促进共识，在完成阶段生成高质量的会议纪要和可落地的交付物。",
                "backstory": """你是一位经验丰富的会议主持人，擅长多种会议模式（头脑风暴、议会投票、方案收敛、六顶思考帽等）。

你的核心能力：
1. **会议准备**：根据会议主题和类型，判断需要收集哪些背景资料，引导用户提供关键信息，确保参会者有足够的上下文。你可以使用 web_search 搜索相关资料，使用 fetch_url 获取参考文档内容。
2. **讨论引导**：根据会议模式灵活调整引导策略——头脑风暴时鼓励发散、议会投票时确保公正、方案收敛时推动落地。善于发现讨论中的盲区和共识点。
3. **节奏控制**：合理分配发言时间，避免讨论偏题或陷入僵局，在关键节点及时总结和推进。
4. **产出保障**：确保每次会议都有明确的结论和可执行的交付物。使用 meeting_save_document 保存会议纪要和交付物，使用 meeting_generate_action_items 提炼行动项。

你的原则：
- 不代替参会者思考，而是引导他们深入思考
- 不急于达成共识，确保每个观点都被充分讨论
- 不忽略少数意见，记录不同视角供决策参考
- 每次会议结束时，产出必须包含：结论、行动项、待跟进问题
- 会议结束后，主动使用 meeting_save_document 保存会议纪要""",
                "tools": ["web_search", "fetch_url", "meeting_save_document", "meeting_generate_action_items"],
                "skills": [],
                "planning": True,
                "planning_effort": "high",
                "max_iter": 30,
            },
        ]

        return templates

    def get_providers(self) -> list[dict[str, Any]]:
        """获取可用的 LLM 提供商列表

        Returns:
            提供商列表，包含每个提供商的当前默认模型
        """
        providers = []

        if not self._context:
            logger.warning("Context not initialized, returning empty providers list")
            return providers

        try:
            # 获取所有 Chat Completion 类型的 Provider
            all_providers = self._context.get_all_providers()

            for provider in all_providers:
                meta = provider.meta()
                # 从 provider_config 获取显示名称，如果没有则使用 id
                display_name = provider.provider_config.get("name", meta.id) if hasattr(provider, "provider_config") else meta.id
                providers.append({
                    "id": meta.id,
                    "name": display_name,
                    "model": meta.model,
                    "provider_type": meta.provider_type.value if meta.provider_type else "chat_completion",
                    "is_chat_provider": True,
                })

        except Exception as e:
            logger.error(f"Failed to get providers: {e}")

        return providers

    async def get_provider_models(self, provider_id: str) -> list[str]:
        """获取指定提供商支持的模型列表

        Args:
            provider_id: 提供商 ID

        Returns:
            模型名称列表
        """
        if not self._context:
            logger.warning("Context not initialized, returning empty models list")
            return []

        try:
            provider = self._context.get_provider_by_id(provider_id)
            if not provider:
                logger.warning(f"Provider {provider_id} not found")
                return []

            # 检查是否是 Chat Completion 类型的 Provider
            from astrbot.core.provider.provider import Provider
            if not isinstance(provider, Provider):
                logger.warning(f"Provider {provider_id} is not a chat completion provider")
                return []

            # 调用 provider 的 get_models 方法获取模型列表
            models = await provider.get_models()
            return models

        except Exception as e:
            logger.error(f"Failed to get models for provider {provider_id}: {e}")
            return []

    # ==================== 私有方法 ====================

    MEETING_ASSISTANT_ID = "agent_meeting_assistant"
    WORK_ASSISTANT_ID = "agent_nicebot_work_assistant"
    WORK_EXECUTOR_ID = "agent_nicebot_work_executor"
    WORK_REVIEWER_ID = "agent_nicebot_work_reviewer"
    WORK_RESEARCHER_ID = "agent_nicebot_research_expert"
    WORK_REPORTER_ID = "agent_nicebot_report_expert"

    def get_work_builtin_agent_ids(self) -> dict[str, str]:
        return {
            "assistant": self.WORK_ASSISTANT_ID,
            "executor": self.WORK_EXECUTOR_ID,
            "reviewer": self.WORK_REVIEWER_ID,
            "researcher": self.WORK_RESEARCHER_ID,
            "reporter": self.WORK_REPORTER_ID,
        }

    def _work_builtin_templates(self) -> dict[str, dict[str, Any]]:
        return {
            self.WORK_ASSISTANT_ID: {
                "template_id": "template_nicebot_work_assistant",
                "name": "NiceBot 任务助手",
                "role": "需求澄清、任务规划、执行调度和验收协调者",
                "goal": "把模糊任务转化为清晰需求、可审批计划、可调度的二级任务树，并在最终交付前做验收判断。",
                "backstory": "你是 NiceBot Work 的任务助手，擅长通过少量高价值问题澄清目标，生成依赖明确的执行计划，并为每个子任务选择合适的执行者。",
                "tools": [],
                "skills": [],
                "planning": True,
                "planning_effort": "high",
                "max_iter": 30,
                "metadata": {"category": "work", "work_builtin_role": "assistant"},
            },
            self.WORK_EXECUTOR_ID: {
                "template_id": "template_nicebot_work_executor",
                "name": "通用任务执行智能体",
                "role": "通用任务执行者",
                "goal": "根据已确认的需求、计划和上下文完成普通任务执行，形成可审查的阶段结果。",
                "backstory": "你是稳定、克制的通用执行智能体，专注完成当前步骤，不擅自扩大范围，并明确记录产出依据和未解决问题。",
                "tools": [],
                "skills": [],
                "planning": False,
                "planning_effort": "medium",
                "max_iter": 25,
                "metadata": {"category": "work", "work_builtin_role": "executor"},
            },
            self.WORK_REVIEWER_ID: {
                "template_id": "template_nicebot_work_reviewer",
                "name": "通用任务审查智能体",
                "role": "任务质量审查者",
                "goal": "独立审查执行结果是否满足需求、计划和交付标准，给出通过或返工意见。",
                "backstory": "你是 NiceBot Work 的质量门禁，不参与执行本身，只根据目标、证据和交付标准判断结果是否足够可靠。",
                "tools": [],
                "skills": [],
                "planning": False,
                "planning_effort": "medium",
                "max_iter": 18,
                "metadata": {"category": "work", "work_builtin_role": "reviewer"},
            },
            self.WORK_RESEARCHER_ID: {
                "template_id": "template_nicebot_research_expert",
                "name": "调查专家",
                "role": "信息收集与资料核对专家",
                "goal": "围绕任务目标收集、筛选、核对信息来源，输出结构化资料和关键依据。",
                "backstory": "你擅长快速建立信息地图，区分事实、推断和不确定性，并保留来源线索供后续交付引用。",
                "tools": [],
                "skills": [],
                "planning": False,
                "planning_effort": "medium",
                "max_iter": 25,
                "metadata": {"category": "work", "work_builtin_role": "researcher"},
            },
            self.WORK_REPORTER_ID: {
                "template_id": "template_nicebot_report_expert",
                "name": "汇报专家",
                "role": "交付物撰写与报告整理专家",
                "goal": "把执行结果整理为清晰、完整、可直接使用的最终交付物。",
                "backstory": "你擅长组织结构、突出结论、保留依据，并根据任务场景选择合适的报告表达方式。",
                "tools": [],
                "skills": [],
                "planning": False,
                "planning_effort": "medium",
                "max_iter": 25,
                "metadata": {"category": "work", "work_builtin_role": "reporter"},
            },
        }

    def ensure_work_builtin_agents(self) -> dict[str, Agent]:
        """Ensure NiceBot Work builtin agents exist.

        Builtin agents are editable by users, but their identity is protected and
        can be reset to these defaults.
        """
        ensured: dict[str, Agent] = {}
        for agent_id, template in self._work_builtin_templates().items():
            existing = self.get_agent(agent_id)
            if existing:
                metadata = {
                    **existing.metadata,
                    **template.get("metadata", {}),
                    "is_work_builtin": True,
                    "template_id": template["template_id"],
                    "resettable": True,
                    "non_deletable": True,
                }
                if existing.agent_type.value != "builtin" or existing.metadata != metadata:
                    self.update_agent(agent_id, {"agent_type": "builtin", "metadata": metadata}, skip_skill_validation=True)
                    existing = self.get_agent(agent_id)
                if existing:
                    ensured[agent_id] = existing
                continue
            data = {
                "id": agent_id,
                "name": template["name"],
                "role": template["role"],
                "goal": template["goal"],
                "backstory": template["backstory"],
                "tools": template.get("tools", []),
                "skills": template.get("skills", []),
                "planning": template.get("planning", False),
                "planning_effort": template.get("planning_effort", "medium"),
                "max_iter": template.get("max_iter", 25),
                "enabled": True,
                "agent_type": "builtin",
                "metadata": {
                    **template.get("metadata", {}),
                    "is_work_builtin": True,
                    "template_id": template["template_id"],
                    "resettable": True,
                    "non_deletable": True,
                },
            }
            ensured[agent_id] = self.create_agent(data, skip_skill_validation=True)
        return ensured

    def ensure_meeting_assistant(self) -> Agent | None:
        """确保会议助手 Agent 存在，不存在则自动创建

        Returns:
            会议助手 Agent 对象，创建失败返回 None
        """
        existing = self.get_agent(self.MEETING_ASSISTANT_ID)
        if existing:
            if existing.agent_type.value != "builtin":
                self.update_agent(self.MEETING_ASSISTANT_ID, {
                    "agent_type": "builtin",
                    "metadata": {
                        **existing.metadata,
                        "is_meeting_assistant": True,
                        "template_id": "template_meeting_assistant",
                    },
                })
                existing = self.get_agent(self.MEETING_ASSISTANT_ID)
            return existing

        meeting_template = None
        for t in self.get_templates():
            if t.get("id") == "template_meeting_assistant":
                meeting_template = t
                break

        if not meeting_template:
            logger.warning("Meeting assistant template not found")
            return None

        try:
            agent = self.create_agent({
                "id": self.MEETING_ASSISTANT_ID,
                "name": meeting_template["name"],
                "role": meeting_template["role"],
                "goal": meeting_template["goal"],
                "backstory": meeting_template["backstory"],
                "tools": meeting_template.get("tools", []),
                "skills": meeting_template.get("skills", []),
                "planning": meeting_template.get("planning", False),
                "planning_effort": meeting_template.get("planning_effort", "medium"),
                "max_iter": meeting_template.get("max_iter", 30),
                "enabled": True,
                "agent_type": "builtin",
                "metadata": {
                    "category": "meeting",
                    "is_meeting_assistant": True,
                    "template_id": "template_meeting_assistant",
                },
            })
            logger.info(f"Auto-created meeting assistant agent: {agent.id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create meeting assistant agent: {e}")
            return None

    def get_meeting_assistant(self) -> Agent | None:
        """获取会议助手 Agent

        Returns:
            会议助手 Agent 对象，不存在返回 None
        """
        return self.get_agent(self.MEETING_ASSISTANT_ID)

    def get_builtin_agents(self) -> list[Agent]:
        """获取所有内置 Agent

        Returns:
            内置 Agent 列表
        """
        agents = []
        rows = self.db.select_all(
            "agents",
            where="agent_type IN ('builtin', 'expert')",
            order_by="created_at DESC"
        )
        for row in rows:
            try:
                agents.append(self._row_to_agent(row))
            except Exception as e:
                logger.error(f"Failed to parse builtin agent {row.get('id')}: {e}")
        return agents

    def reset_builtin_agent(self, agent_id: str) -> Agent | None:
        """重置内置/专家 Agent 到初始模板状态

        Args:
            agent_id: 内置/专家 Agent ID

        Returns:
            重置后的 Agent 对象，失败返回 None
        """
        agent = self.get_agent(agent_id)
        if not agent or not agent.is_builtin:
            return None

        template_id = agent.metadata.get("template_id", "")
        template = None
        work_template = next(
            (t for t in self._work_builtin_templates().values() if t.get("template_id") == template_id),
            None,
        )
        if work_template:
            template = work_template

        if not template:
            for t in self.get_templates():
                if t.get("id") == template_id:
                    template = t
                    break

        if not template:
            category_key = agent.metadata.get("category", "")
            if category_key and agent.is_expert:
                experts = self.load_expert_category(category_key)
                for e in experts:
                    if e.get("id") == template_id:
                        template = e
                        break

        if not template:
            logger.warning(f"Template {template_id} not found for builtin agent {agent_id}")
            return None

        try:
            if agent.is_expert and "capabilities" in template:
                self.update_agent(agent_id, {
                    "name": template["name"],
                    "role": template["role"],
                    "goal": template["goal"],
                    "backstory": template["backstory"],
                    "tools": template.get("tools", []),
                    "skills": template.get("skills", []),
                    "planning": template.get("planning", {}).get("enabled", True),
                    "planning_effort": "high" if template.get("planning", {}).get("enabled") else "medium",
                    "max_iter": 30,
                    "enabled": True,
                    "metadata": {
                        **agent.metadata,
                        "capabilities": template.get("capabilities", []),
                        "rules": template.get("rules", []),
                    },
                }, skip_skill_validation=True)
            else:
                self.update_agent(agent_id, {
                    "name": template["name"],
                    "role": template["role"],
                    "goal": template["goal"],
                    "backstory": template["backstory"],
                    "tools": template.get("tools", []),
                    "skills": template.get("skills", []),
                    "planning": template.get("planning", False),
                    "planning_effort": template.get("planning_effort", "medium"),
                    "max_iter": template.get("max_iter", 30),
                    "enabled": True,
                    "metadata": {
                        **agent.metadata,
                        **template.get("metadata", {}),
                        "template_id": template_id,
                        **({"is_work_builtin": True, "resettable": True, "non_deletable": True} if work_template else {}),
                    },
                }, skip_skill_validation=True)
            logger.info(f"Reset builtin agent {agent_id} to template {template_id}")
            return self.get_agent(agent_id)
        except Exception as e:
            logger.error(f"Failed to reset builtin agent {agent_id}: {e}")
            return None

    def load_expert_templates(self) -> dict[str, Any]:
        """加载专家模板数据"""
        templates_dir = Path(__file__).parent.parent / "data" / "expert_templates"
        if not templates_dir.exists():
            logger.warning(f"Expert templates directory not found: {templates_dir}")
            return {"categories": {}, "total": 0}

        index_path = templates_dir / "index.json"
        if not index_path.exists():
            logger.warning("Expert templates index.json not found")
            return {"categories": {}, "total": 0}

        try:
            with open(index_path, encoding="utf-8") as f:
                index_data = json.load(f)
            return index_data
        except Exception as e:
            logger.error(f"Failed to load expert templates index: {e}")
            return {"categories": {}, "total": 0}

    def load_expert_category(self, category_key: str) -> list[dict[str, Any]]:
        """加载指定分类的专家模板"""
        templates_dir = Path(__file__).parent.parent / "data" / "expert_templates"
        cat_path = templates_dir / f"{category_key}.json"
        if not cat_path.exists():
            return []

        try:
            with open(cat_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("experts", [])
        except Exception as e:
            logger.error(f"Failed to load expert category {category_key}: {e}")
            return []

    def get_expert_categories(self) -> list[dict[str, Any]]:
        """获取专家分类列表"""
        index_data = self.load_expert_templates()
        categories = []
        for key, info in index_data.get("categories", {}).items():
            categories.append(info)
        return sorted(categories, key=lambda x: x.get("label", ""))

    def get_experts_by_category(self, category_key: str) -> list[dict[str, Any]]:
        """获取指定分类的专家模板列表"""
        return self.load_expert_category(category_key)

    def create_expert_agent(self, template_id: str, category_key: str, llm_config: dict | None = None) -> Agent | None:
        """从专家模板创建智能体"""
        experts = self.load_expert_category(category_key)
        template = None
        for e in experts:
            if e.get("id") == template_id:
                template = e
                break

        if not template:
            logger.warning(f"Expert template {template_id} not found in category {category_key}")
            return None

        agent_id = f"expert_{uuid.uuid4().hex[:8]}"
        try:
            agent = self.create_agent({
                "id": agent_id,
                "name": template["name"],
                "role": template["role"],
                "goal": template["goal"],
                "backstory": template["backstory"],
                "tools": template.get("tools", []),
                "skills": template.get("skills", []),
                "planning": template.get("planning", {}).get("enabled", True),
                "planning_effort": "high" if template.get("planning", {}).get("enabled") else "medium",
                "max_iter": 30,
                "enabled": True,
                "agent_type": "expert",
                "metadata": {
                    "template_id": template_id,
                    "category": category_key,
                    "en_name": template.get("en_name", ""),
                    "icon": template.get("icon", "mdi-robot"),
                    "emoji": template.get("emoji", ""),
                    "capabilities": template.get("capabilities", []),
                    "rules": template.get("rules", []),
                },
            }, skip_skill_validation=True)

            if llm_config:
                self.update_agent(agent_id, {
                    "provider_id": llm_config.get("provider_id"),
                    "model_name": llm_config.get("model_name"),
                    "llm_config": llm_config.get("llm_config", {}),
                }, skip_skill_validation=True)
                agent = self.get_agent(agent_id)

            logger.info(f"Created expert agent: {agent_id} from template {template_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create expert agent from template {template_id}: {e}")
            return None

    def batch_set_expert_llm(self, provider_id: str | None = None, model_name: str | None = None, llm_config: dict | None = None) -> int:
        """批量设置所有专家智能体的 LLM 配置"""
        experts = []
        rows = self.db.select_all(
            "agents",
            where="agent_type = 'expert'",
            order_by="created_at DESC"
        )
        for row in rows:
            try:
                experts.append(self._row_to_agent(row))
            except Exception as e:
                logger.error(f"Failed to parse expert agent {row.get('id')}: {e}")

        updated = 0
        for expert in experts:
            try:
                update_data = {}
                if provider_id is not None:
                    update_data["provider_id"] = provider_id
                if model_name is not None:
                    update_data["model_name"] = model_name
                if llm_config is not None:
                    update_data["llm_config"] = llm_config
                if update_data:
                    self.update_agent(expert.id, update_data, skip_skill_validation=True)
                    updated += 1
            except Exception as e:
                logger.error(f"Failed to update expert {expert.id} LLM config: {e}")

        logger.info(f"Updated LLM config for {updated}/{len(experts)} expert agents")
        return updated

    def ensure_expert_agents(self) -> int:
        """确保所有专家模板都已创建为智能体，并更新已有专家的模板数据，返回新创建的数量"""
        index_data = self.load_expert_templates()
        categories = index_data.get("categories", {})
        if not categories:
            logger.warning("No expert categories found")
            return 0

        existing_experts = {}
        rows = self.db.select_all("agents", where="agent_type = 'expert'")
        for row in rows:
            try:
                agent = self._row_to_agent(row)
                template_id = agent.metadata.get("template_id", "")
                if template_id:
                    existing_experts[template_id] = agent
            except Exception as e:
                logger.error(f"Failed to parse expert agent {row.get('id')}: {e}")

        created = 0
        updated = 0
        for cat_key, cat_info in categories.items():
            experts = self.load_expert_category(cat_key)
            for template in experts:
                template_id = template.get("id", "")
                if not template_id:
                    continue

                if template_id in existing_experts:
                    existing = existing_experts[template_id]
                    if existing.role != template.get("role", "") or existing.goal != template.get("goal", "") or existing.backstory != template.get("backstory", ""):
                        try:
                            self.update_agent(existing.id, {
                                "name": template["name"],
                                "role": template["role"],
                                "goal": template["goal"],
                                "backstory": template["backstory"],
                                "skills": template.get("skills", []),
                                "metadata": {
                                    **existing.metadata,
                                    "capabilities": template.get("capabilities", []),
                                    "rules": template.get("rules", []),
                                },
                            }, skip_skill_validation=True)
                            updated += 1
                        except Exception as e:
                            logger.error(f"Failed to update expert agent {template_id}: {e}")
                    continue

                try:
                    agent_id = f"expert_{uuid.uuid4().hex[:8]}"
                    self.create_agent({
                        "id": agent_id,
                        "name": template["name"],
                        "role": template["role"],
                        "goal": template["goal"],
                        "backstory": template["backstory"],
                        "tools": template.get("tools", []),
                        "skills": template.get("skills", []),
                        "planning": template.get("planning", {}).get("enabled", True),
                        "planning_effort": "high" if template.get("planning", {}).get("enabled") else "medium",
                        "max_iter": 30,
                        "enabled": True,
                        "agent_type": "expert",
                        "metadata": {
                            "template_id": template_id,
                            "category": cat_key,
                            "en_name": template.get("en_name", ""),
                            "icon": template.get("icon", "mdi-robot"),
                            "emoji": template.get("emoji", ""),
                            "capabilities": template.get("capabilities", []),
                            "rules": template.get("rules", []),
                        },
                    }, skip_skill_validation=True)
                    created += 1
                except Exception as e:
                    logger.error(f"Failed to create expert agent from template {template_id}: {e}")

        if created > 0 or updated > 0:
            logger.info(f"Expert agents: created {created}, updated {updated}")
        else:
            logger.info("All expert agents up to date")
        return created

    def _row_to_agent(self, row: dict[str, Any]) -> Agent:
        """将数据库行转换为 Agent 对象"""
        from astrbot.builtin_stars.agent_system.models import AgentType
        agent_type_val = row.get("agent_type", "custom")
        if agent_type_val in (None, ""):
            is_builtin = bool(row.get("is_builtin", 0))
            agent_type_val = "builtin" if is_builtin else "custom"
        return Agent(
            id=row["id"],
            name=row["name"],
            role=row.get("role", ""),
            goal=row.get("goal", ""),
            backstory=row.get("backstory", ""),
            tools=self._parse_json(row.get("tools", "[]")),
            skills=self._parse_json(row.get("skills", "[]")),
            knowledge_id=row.get("knowledge_id"),
            provider_id=row.get("provider_id"),
            model_name=row.get("model_name"),
            llm_config=self._parse_json(row.get("llm_config", "{}")),
            memory_config=self._parse_json(row.get("memory_config", "{}")),
            planning=bool(row.get("planning", 0)),
            planning_effort=PlanningEffort(row.get("planning_effort", "medium")),
            max_iter=row.get("max_iter", 20),
            max_rpm=row.get("max_rpm"),
            verbose=bool(row.get("verbose", 0)),
            allow_delegation=bool(row.get("allow_delegation", 0)),
            enabled=bool(row.get("enabled", 1)),
            agent_type=AgentType(agent_type_val),
            metadata=self._parse_json(row.get("metadata", "{}")),
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

    def _get_memory_provider(self):
        if self._memory_provider is None:
            try:
                self._memory_provider = _BuiltinMemoryProvider(self.db)
            except Exception:
                self._memory_provider = None
        return self._memory_provider

    def _store_memory(self, agent_id: str, role: str, content: str, summary: str = "") -> None:
        # 防御性检查：content 为 None 或空字符串时不存储
        if not content:
            return
        provider = self._get_memory_provider()
        if provider:
            try:
                provider.store(agent_id, role, content, summary)
                return
            except Exception as e:
                logger.error(f"Memory provider store failed, falling back to builtin: {e}")
        import uuid
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        try:
            self.db.insert("agent_memories", {
                "id": memory_id,
                "agent_id": agent_id,
                "role": role,
                "content": content[:2000],
                "summary": summary[:500] if summary else content[:200],
                "scope": "default",
                "importance": 0.5,
            })
        except Exception as e:
            logger.error(f"Builtin memory store failed: {e}")

    def _retrieve_memories(self, agent_id: str, query: str, memory_config: dict) -> list[dict]:
        provider = self._get_memory_provider()
        if provider:
            try:
                memory_type = memory_config.get("type", "short_term")
                max_messages = memory_config.get("maxMessages", 20)
                return provider.retrieve(agent_id, query, memory_type=memory_type, max_items=max_messages)
            except Exception as e:
                logger.error(f"Memory provider retrieve failed, falling back to builtin: {e}")
        memory_type = memory_config.get("type", "short_term")
        max_messages = memory_config.get("maxMessages", 20)

        if memory_type == "short_term":
            rows = self.db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="created_at DESC",
                limit=max_messages,
            )
        else:
            rows = self.db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="importance DESC, created_at DESC",
                limit=max_messages,
            )

        memories = []
        for row in reversed(rows):
            memories.append({
                "role": row.get("role", ""),
                "content": row.get("summary") or row.get("content", ""),
            })
        return memories

    def _create_mock_event(self, message: str = ""):
        return _create_mock_event(message, context=self._context)

    def _build_system_prompt(self, agent: Agent, memories: list | None = None) -> str:
        """构建智能体的系统提示

        Args:
            agent: 智能体对象
            memories: 记忆列表（可选）

        Returns:
            系统提示字符串
        """
        parts = []

        # 角色定义
        if agent.role:
            parts.append(f"你是一个{agent.role}。")

        # 目标
        if agent.goal:
            parts.append(f"\n你的目标是：{agent.goal}")

        # 背景故事
        if agent.backstory:
            parts.append(f"\n\n背景：{agent.backstory}")

        # 能力说明
        capabilities = []
        if agent.tools:
            capabilities.append(f"你可以使用以下工具：{', '.join(agent.tools)}")
        if agent.skills:
            capabilities.append(f"你具备以下技能：{', '.join(agent.skills)}")

        if capabilities:
            parts.append("\n\n" + "\n".join(capabilities))

        # Planning 指令
        if agent.planning:
            planning_instructions = {
                PlanningEffort.LOW: "在执行任务前，请简要列出1-3个关键步骤。",
                PlanningEffort.MEDIUM: "在执行任务前，请制定详细的执行计划，列出具体步骤和预期结果。",
                PlanningEffort.HIGH: "在执行任务前，请制定非常详细的执行计划，包括：1)问题分析 2)信息收集策略 3)详细执行步骤（含子步骤）4)每步的预期输出 5)风险评估和备选方案。",
            }
            instruction = planning_instructions.get(agent.planning_effort, planning_instructions[PlanningEffort.MEDIUM])
            parts.append(f"\n\n{instruction}")

        # Memory 配置
        if agent.memory_config.get("enabled"):
            parts.append("\n\n你会记住之前的对话内容，并在需要时引用相关记忆。")

        # 记忆上下文
        if memories:
            memory_texts = []
            for mem in memories:
                text = mem.get("summary") or mem.get("content") or ""
                if text:
                    memory_texts.append(text)
            if memory_texts:
                parts.append("\n\n以下是你之前对话的相关记忆：\n" + "\n".join(memory_texts))

        return "\n".join(parts)
