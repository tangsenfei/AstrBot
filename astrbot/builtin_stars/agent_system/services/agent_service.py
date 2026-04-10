"""
智能体管理模块 - 智能体服务

提供智能体的 CRUD 操作、测试、复制、模板等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from ..database import Database
    from astrbot.core.star.context import Context

from ..models import Agent, PlanningEffort


class AgentService:
    """智能体管理服务"""

    def __init__(self, db: "Database", context: "Context | None" = None):
        self.db = db
        self._context = context

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

    def create_agent(self, data: dict[str, Any]) -> Agent:
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
        if skills:
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
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("agents", agent_data)

        logger.info(f"Created agent: {agent_id}")
        return self._row_to_agent(agent_data)

    def update_agent(self, agent_id: str, data: dict[str, Any]) -> Agent | None:
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
            "allow_delegation", "enabled", "metadata"
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
        if "skills" in data and data["skills"]:
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

    async def test_agent(self, agent_id: str, message: str) -> dict[str, Any]:
        """测试智能体

        Args:
            agent_id: 智能体 ID
            message: 测试消息

        Returns:
            测试结果

        Raises:
            ValueError: 智能体不存在或配置错误
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"智能体 '{agent_id}' 不存在")

        result = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "message": message,
            "success": False,
            "response": None,
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
            # 检查是否配置了 LLM 提供商
            if not agent.provider_id:
                raise ValueError("智能体未配置 LLM 提供商")

            # 检查 Context 是否可用
            if not self._context:
                raise ValueError("Context 未初始化，无法测试智能体")

            # 获取 Provider
            provider = self._context.get_provider_by_id(agent.provider_id)
            if not provider:
                raise ValueError(f"LLM 提供商 '{agent.provider_id}' 不存在")

            # 构建系统提示
            system_prompt = self._build_system_prompt(agent)

            # 调用 LLM
            from astrbot.core.provider.entities import ProviderRequest

            request = ProviderRequest(
                prompt=message,
                system_prompt=system_prompt,
                contexts=[],
                image_urls=[],
                func_tool=None,
            )

            llm_response = await provider.text_chat(
                prompt=message,
                system_prompt=system_prompt,
                contexts=[],
                func_tool=None,
            )

            result["success"] = True
            result["response"] = llm_response.completion_text

            # 记录 token 消耗
            if llm_response.usage:
                # TokenUsage 对象使用 input_other/output 或 prompt_tokens/completion_tokens
                result["tokens"]["input"] = getattr(llm_response.usage, 'prompt_tokens', None) or getattr(llm_response.usage, 'input', 0)
                result["tokens"]["output"] = getattr(llm_response.usage, 'completion_tokens', None) or getattr(llm_response.usage, 'output', 0)
                result["tokens"]["total"] = getattr(llm_response.usage, 'total_tokens', None) or getattr(llm_response.usage, 'total', 0)

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Agent test failed: {agent_id} - {e}")

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)

        return result

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
        ]

        return templates

    def get_providers(self) -> list[dict[str, Any]]:
        """获取可用的 LLM 提供商列表

        Returns:
            提供商列表
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
                providers.append({
                    "id": meta.id,
                    "name": meta.name,
                    "model": meta.model_name,
                    "provider_type": meta.provider_type,
                    "is_chat_provider": True,
                })

        except Exception as e:
            logger.error(f"Failed to get providers: {e}")

        return providers

    # ==================== 私有方法 ====================

    def _row_to_agent(self, row: dict[str, Any]) -> Agent:
        """将数据库行转换为 Agent 对象"""
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

    def _build_system_prompt(self, agent: Agent) -> str:
        """构建智能体的系统提示

        Args:
            agent: 智能体对象

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

        return "\n".join(parts)
