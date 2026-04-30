"""
智能体管理模块 - 智能体服务

提供智能体的 CRUD 操作、测试、复制、模板等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator

from astrbot.core import logger

from astrbot.builtin_stars.agent_system.services.crewai_integration import (
    get_memory_provider,
    get_planning_provider,
    CREWAI_AVAILABLE,
    AstrBotLLMAdapter,
    AstrBotToolAdapter,
    CrewAIAgentFactory,
)

if TYPE_CHECKING:
    from ..database import Database
    from astrbot.core.star.context import Context

from ..models import Agent, PlanningEffort


class AgentService:
    """智能体管理服务"""

    def __init__(self, db: "Database", context: "Context | None" = None):
        self.db = db
        self._context = context
        self._memory_provider = None
        self._planning_provider = None

    @property
    def context(self) -> "Context | None":
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

        优先使用 CrewAI Agent 执行，降级到 AstrBot Provider 直接调用。

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

            if CREWAI_AVAILABLE:
                crewai_result = await self._test_agent_with_crewai(agent, message, history)
                result.update(crewai_result)
            else:
                fallback_result = await self._test_agent_with_provider(agent, message, history)
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

    async def _test_agent_with_crewai(self, agent: Agent, message: str, history: list | None = None) -> dict[str, Any]:
        """使用 CrewAI Agent 执行测试"""
        crewai_agent = CrewAIAgentFactory.create_agent(agent, self._context, disable_planning=True)
        if not crewai_agent:
            logger.warning("Failed to create CrewAI Agent, falling back to provider")
            return await self._test_agent_with_provider(agent, message, history)

        try:
            context_str = ""
            if history:
                for msg in history:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role and content:
                        context_str += f"{role}: {content}\n"

            full_message = message
            if context_str:
                full_message = f"对话历史:\n{context_str}\n\n当前问题: {message}"

            output = await crewai_agent.kickoff_async(full_message)

            response_text = ""
            if hasattr(output, 'raw') and output.raw:
                response_text = output.raw
            elif hasattr(output, 'result') and output.result:
                response_text = str(output.result)
            elif hasattr(output, '__str__'):
                response_text = str(output)

            tokens = {"input": 0, "output": 0, "total": 0}
            if hasattr(output, 'token_usage') and output.token_usage:
                tokens["input"] = getattr(output.token_usage, 'prompt_tokens', 0) or 0
                tokens["output"] = getattr(output.token_usage, 'completion_tokens', 0) or 0
                tokens["total"] = getattr(output.token_usage, 'total_tokens', 0) or 0

            tools_used = []
            if hasattr(output, 'tasks_output') and output.tasks_output:
                for task_output in output.tasks_output:
                    if hasattr(task_output, 'tools_used') and task_output.tools_used:
                        for tu in task_output.tools_used:
                            tools_used.append(tu.tool_name if hasattr(tu, 'tool_name') else str(tu))

            planning_steps = None
            if agent.planning and hasattr(crewai_agent, 'planning_config') and crewai_agent.planning_config:
                planning_steps = f"[CrewAI Planning 已启用, effort={getattr(crewai_agent.planning_config, 'planning_effort', 'medium')}]"

            return {
                "success": True,
                "response": response_text,
                "tools_used": tools_used,
                "planning_steps": planning_steps,
                "tokens": tokens,
            }

        except Exception as e:
            logger.error(f"CrewAI Agent execution failed, falling back to provider: {e}")
            return await self._test_agent_with_provider(agent, message, history)

    async def _test_agent_with_provider(self, agent: Agent, message: str, history: list | None = None) -> dict[str, Any]:
        """使用 AstrBot Provider 直接调用（降级方案）"""
        provider = self._context.get_provider_by_id(agent.provider_id)
        if not provider:
            raise ValueError(f"LLM 提供商 '{agent.provider_id}' 不存在")

        retrieved_memories = []
        if agent.memory_config.get("enabled"):
            retrieved_memories = self._retrieve_memories(agent.id, message, agent.memory_config)

        system_prompt = self._build_system_prompt(agent, memories=retrieved_memories)

        func_tool = None
        if agent.tools and len(agent.tools) > 0:
            try:
                tool_manager = self._context.get_llm_tool_manager()
                if tool_manager:
                    from astrbot.core.agent.tool import ToolSet
                    tool_set = ToolSet()
                    for tool_id in agent.tools:
                        tool = tool_manager.get_func(tool_id)
                        if tool:
                            tool_set.add_tool(tool)
                    if not tool_set.empty():
                        func_tool = tool_set
            except Exception as e:
                logger.warning(f"Failed to get tools for agent test: {e}")

        contexts = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    contexts.append({"role": role, "content": content})

        planning_steps = None
        if agent.planning:
            planning_provider = self._get_planning_provider()
            planning_effort = agent.planning_effort.value if hasattr(agent.planning_effort, 'value') else str(agent.planning_effort)
            if planning_provider:
                try:
                    planning_steps = await planning_provider.generate_plan(
                        system_prompt, message, provider, contexts, planning_effort
                    )
                except Exception as e:
                    logger.error(f"Planning provider failed: {e}")
                    planning_steps = None

            if planning_steps is None:
                from ..services.crewai_integration import PLANNING_EFFORT_MAP
                effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
                planning_prompt = effort_config["prompt_template"].format(message=message)
                planning_response = await provider.text_chat(
                    prompt=planning_prompt,
                    system_prompt=system_prompt,
                    contexts=contexts,
                )
                planning_steps = planning_response.completion_text

            if planning_steps:
                contexts.append({
                    "role": "assistant",
                    "content": f"[执行计划]\n{planning_steps}"
                })

        max_steps = 5
        step = 0
        final_response = ""
        tools_used = []
        tokens = {"input": 0, "output": 0, "total": 0}

        mock_event = self._create_mock_event(message)

        while step < max_steps:
            llm_response = await provider.text_chat(
                prompt=message if step == 0 else None,
                system_prompt=system_prompt,
                contexts=contexts,
                func_tool=func_tool,
            )

            if llm_response.usage:
                tokens["input"] += getattr(llm_response.usage, 'prompt_tokens', None) or getattr(llm_response.usage, 'input', 0)
                tokens["output"] += getattr(llm_response.usage, 'completion_tokens', None) or getattr(llm_response.usage, 'output', 0)
                tokens["total"] += getattr(llm_response.usage, 'total_tokens', None) or getattr(llm_response.usage, 'total', 0)

            if llm_response.tools_call_args and llm_response.tools_call_name and func_tool:
                tool_results = []
                tool_call_ids = llm_response.tools_call_ids or [f"call_{i}" for i in range(len(llm_response.tools_call_name))]

                for i, (tool_name, tool_args, tool_id) in enumerate(zip(
                    llm_response.tools_call_name,
                    llm_response.tools_call_args,
                    tool_call_ids
                )):
                    try:
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except json.JSONDecodeError:
                                tool_args = {}

                        if not isinstance(tool_args, dict):
                            tool_args = {}

                        tool = None
                        for t in func_tool.tools:
                            if t.name == tool_name:
                                tool = t
                                break
                        if tool and tool.handler:
                            import inspect
                            sig = inspect.signature(tool.handler)
                            params = list(sig.parameters.keys())

                            if params and params[0] in ('event', 'AstrMessageEvent'):
                                tool_result = await tool.handler(mock_event, **tool_args)
                            else:
                                tool_result = await tool.handler(**tool_args)

                            if tool_result is None:
                                tool_result = ""
                            tool_results.append({
                                "tool_call_id": tool_id,
                                "name": tool_name,
                                "content": str(tool_result)
                            })
                            tools_used.append(tool_name)
                        else:
                            tool_results.append({
                                "tool_call_id": tool_id,
                                "name": tool_name,
                                "content": f"工具 '{tool_name}' 不可用或没有处理器"
                            })
                    except Exception as e:
                        logger.error(f"Tool execution error: {tool_name} - {e}")
                        tool_results.append({
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": f"工具执行错误: {str(e)}"
                        })

                contexts.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": r["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": r["name"],
                            "arguments": json.dumps(
                                llm_response.tools_call_args[i]
                                if isinstance(llm_response.tools_call_args[i], dict)
                                else llm_response.tools_call_args[i],
                                ensure_ascii=False
                            )
                        }
                    } for i, r in enumerate(tool_results)]
                })
                for r in tool_results:
                    contexts.append({
                        "role": "tool",
                        "tool_call_id": r["tool_call_id"],
                        "content": r["content"]
                    })

                step += 1
                message = None
            else:
                final_response = llm_response.completion_text
                break

        if not final_response:
            final_response = llm_response.completion_text if 'llm_response' in dir() else "未能获取响应"

        return {
            "success": True,
            "response": final_response,
            "tools_used": tools_used,
            "planning_steps": planning_steps,
            "tokens": tokens,
            "memory_used": len(retrieved_memories),
        }

    async def test_agent_stream(
        self, agent_id: str, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式测试智能体

        优先使用 CrewAI Agent 执行，降级到 AstrBot Provider 流式调用。

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

            if CREWAI_AVAILABLE:
                async for event in self._test_agent_stream_with_crewai(agent, message):
                    yield event
            else:
                async for event in self._test_agent_stream_with_provider(agent, message):
                    yield event

            if agent.memory_config.get("enabled"):
                self._store_memory(agent_id, "user", original_message)

        except Exception as e:
            import traceback
            logger.error(f"Agent stream test failed: {agent_id} - {e}")
            logger.error(f"Agent stream traceback: {traceback.format_exc()}")
            yield {"type": "error", "data": str(e)}

    async def _test_agent_stream_with_crewai(self, agent: Agent, message: str) -> AsyncGenerator[dict[str, Any], None]:
        """使用 CrewAI Agent 流式执行

        CrewAI 的 kickoff_async 是非流式调用，无法实现逐字输出效果。
        对话场景优先使用 Provider 的 text_chat_stream 实现真正的流式输出。
        """
        async for event in self._test_agent_stream_with_provider(agent, message):
            yield event

    async def _test_agent_stream_with_provider(self, agent: Agent, message: str) -> AsyncGenerator[dict[str, Any], None]:
        """使用 AstrBot Provider 流式调用（降级方案）"""
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
            planning_provider = self._get_planning_provider()
            planning_effort = agent.planning_effort.value if hasattr(agent.planning_effort, 'value') else str(agent.planning_effort)
            if planning_provider:
                try:
                    planning_steps = await planning_provider.generate_plan(
                        system_prompt, message, provider, contexts, planning_effort
                    )
                except Exception as e:
                    logger.error(f"Planning provider failed, falling back to builtin: {e}")
                    planning_steps = None

            if planning_steps is None:
                from ..services.crewai_integration import PLANNING_EFFORT_MAP
                effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
                planning_prompt = effort_config["prompt_template"].format(message=message)
                planning_response = await provider.text_chat(
                    prompt=planning_prompt,
                    system_prompt=system_prompt,
                    contexts=contexts,
                )
                planning_steps = planning_response.completion_text

            if planning_steps:
                contexts.append({
                    "role": "assistant",
                    "content": f"[执行计划]\n{planning_steps}"
                })
                yield {"type": "planning", "data": planning_steps}

        func_tool = None
        if agent.tools and len(agent.tools) > 0:
            try:
                tool_manager = self._context.get_llm_tool_manager()
                if tool_manager:
                    from astrbot.core.agent.tool import ToolSet
                    tool_set = ToolSet()
                    for tool_id in agent.tools:
                        tool = tool_manager.get_func(tool_id)
                        if tool:
                            tool_set.add_tool(tool)
                    if not tool_set.empty():
                        func_tool = tool_set
            except Exception as e:
                logger.warning(f"Failed to get tools for agent stream test: {e}")

        max_steps = 5
        step = 0
        final_response = ""
        tools_used = []

        while step < max_steps:
            full_text = ""
            has_tool_calls = False
            tool_call_data = None
            chunk_buffer = ""
            thinking_buffer = ""
            CHUNK_FLUSH_SIZE = 4
            THINKING_FLUSH_SIZE = 6
            chunk_count = 0
            thinking_count = 0

            async for llm_response in provider.text_chat_stream(
                prompt=message if step == 0 else None,
                system_prompt=system_prompt if system_prompt else None,
                contexts=contexts,
                func_tool=func_tool,
            ):
                if llm_response.role == "err":
                    if chunk_buffer:
                        yield {"type": "chunk", "data": chunk_buffer}
                        chunk_buffer = ""
                    if thinking_buffer:
                        yield {"type": "thinking", "data": thinking_buffer}
                        thinking_buffer = ""
                    yield {"type": "error", "data": llm_response.completion_text}
                    return

                if llm_response.is_chunk:
                    if llm_response.result_chain:
                        for component in llm_response.result_chain.chain:
                            if hasattr(component, 'text') and component.text:
                                chunk = component.text
                                full_text += chunk
                                chunk_buffer += chunk
                                chunk_count += 1
                                if chunk_count >= CHUNK_FLUSH_SIZE:
                                    if thinking_buffer:
                                        yield {"type": "thinking", "data": thinking_buffer}
                                        thinking_buffer = ""
                                        thinking_count = 0
                                    yield {"type": "chunk", "data": chunk_buffer}
                                    chunk_buffer = ""
                                    chunk_count = 0

                    if llm_response.reasoning_content:
                        thinking_buffer += llm_response.reasoning_content
                        thinking_count += 1
                        if thinking_count >= THINKING_FLUSH_SIZE:
                            if chunk_buffer:
                                yield {"type": "chunk", "data": chunk_buffer}
                                chunk_buffer = ""
                                chunk_count = 0
                            yield {"type": "thinking", "data": thinking_buffer}
                            thinking_buffer = ""
                            thinking_count = 0
                else:
                    if llm_response.tools_call_name:
                        has_tool_calls = True
                        tool_call_data = llm_response

                    if llm_response.result_chain:
                        for component in llm_response.result_chain.chain:
                            if hasattr(component, 'text') and component.text:
                                if not full_text:
                                    full_text += component.text

            if thinking_buffer:
                yield {"type": "thinking", "data": thinking_buffer}
            if chunk_buffer:
                yield {"type": "chunk", "data": chunk_buffer}

            if has_tool_calls and tool_call_data and func_tool:
                for tool_name in tool_call_data.tools_call_name:
                    yield {"type": "tool_start", "data": tool_name}

                tool_results = []
                tool_call_ids = tool_call_data.tools_call_ids or [f"call_{i}" for i in range(len(tool_call_data.tools_call_name))]

                mock_event = self._create_mock_event(message)

                for i, (tool_name, tool_args, tool_id) in enumerate(zip(
                    tool_call_data.tools_call_name,
                    tool_call_data.tools_call_args,
                    tool_call_ids
                )):
                    try:
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except json.JSONDecodeError:
                                tool_args = {}

                        if not isinstance(tool_args, dict):
                            tool_args = {}

                        tool = None
                        for t in func_tool.tools:
                            if t.name == tool_name:
                                tool = t
                                break

                        tool_result_str = ""
                        if tool and tool.handler:
                            import inspect
                            sig = inspect.signature(tool.handler)
                            params = list(sig.parameters.keys())

                            if params and params[0] in ('event', 'AstrMessageEvent'):
                                tool_result = await tool.handler(mock_event, **tool_args)
                            else:
                                tool_result = await tool.handler(**tool_args)

                            if tool_result is None:
                                tool_result = ""
                            tool_result_str = str(tool_result)
                            tool_results.append({
                                "tool_call_id": tool_id,
                                "name": tool_name,
                                "content": tool_result_str
                            })
                            tools_used.append(tool_name)
                        else:
                            tool_result_str = f"工具 '{tool_name}' 不可用或没有处理器"
                            tool_results.append({
                                "tool_call_id": tool_id,
                                "name": tool_name,
                                "content": tool_result_str
                            })

                        yield {"type": "tool_result", "data": {"name": tool_name, "result": tool_result_str}}

                    except Exception as e:
                        logger.error(f"Tool execution error: {tool_name} - {e}")
                        error_msg = f"工具执行错误: {str(e)}"
                        tool_results.append({
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": error_msg
                        })
                        yield {"type": "tool_result", "data": {"name": tool_name, "result": error_msg}}

                contexts.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": r["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": r["name"],
                            "arguments": json.dumps(
                                tool_call_data.tools_call_args[i]
                                if isinstance(tool_call_data.tools_call_args[i], dict)
                                else tool_call_data.tools_call_args[i],
                                ensure_ascii=False
                            )
                        }
                    } for i, r in enumerate(tool_results)]
                })
                for r in tool_results:
                    contexts.append({
                        "role": "tool",
                        "tool_call_id": r["tool_call_id"],
                        "content": r["content"]
                    })

                step += 1
                message = None
            else:
                final_response = full_text
                break

        if not final_response:
            final_response = "未能获取响应"

        end_time = datetime.now()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        yield {
            "type": "done",
            "data": {
                "response": final_response,
                "tools_used": tools_used,
                "planning_steps": planning_steps,
                "execution_time_ms": execution_time_ms,
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
            with open(index_path, 'r', encoding='utf-8') as f:
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
            with open(cat_path, 'r', encoding='utf-8') as f:
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
        from astrbot.builtin_stars.agent_system.models import AgentType
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
        if agent_type_val in (None, ''):
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
                self._memory_provider = get_memory_provider(self.db)
            except Exception:
                self._memory_provider = None
        return self._memory_provider

    def _get_planning_provider(self):
        if self._planning_provider is None:
            try:
                self._planning_provider = get_planning_provider()
            except Exception:
                self._planning_provider = None
        return self._planning_provider

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
        from ..services.crewai_integration import _create_mock_event as _create_mock
        return _create_mock(message)

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
