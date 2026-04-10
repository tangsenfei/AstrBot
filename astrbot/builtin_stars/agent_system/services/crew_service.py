"""
智能体管理模块 - Crew 服务

提供 Crew 的 CRUD 操作、执行、测试、模板等功能
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

from ..models import Crew, CrewTask, ProcessType, AgentTask, TaskStatus


class CrewService:
    """Crew 管理服务"""

    def __init__(self, db: "Database", context: "Context | None" = None):
        self.db = db
        self._context = context

    @property
    def context(self) -> "Context | None":
        """获取 Context 实例"""
        return self._context

    def get_crews(self, enabled_only: bool = False) -> list[Crew]:
        """获取 Crew 列表

        Args:
            enabled_only: 是否只返回启用的 Crew

        Returns:
            Crew 列表
        """
        crews = []

        if enabled_only:
            rows = self.db.select_all(
                "crews",
                where="enabled = ?",
                where_params=(1,),
                order_by="created_at DESC"
            )
        else:
            rows = self.db.select_all("crews", order_by="created_at DESC")

        for row in rows:
            try:
                crew = self._row_to_crew(row)
                crews.append(crew)
            except Exception as e:
                logger.error(f"Failed to parse crew {row.get('id')}: {e}")

        return crews

    def get_crew(self, crew_id: str) -> Crew | None:
        """获取单个 Crew

        Args:
            crew_id: Crew ID

        Returns:
            Crew 对象，不存在则返回 None
        """
        row = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
        if row:
            return self._row_to_crew(row)
        return None

    def create_crew(self, data: dict[str, Any]) -> Crew:
        """创建 Crew

        Args:
            data: Crew 数据
                - name: Crew 名称（必填）
                - description: 描述
                - agents: Agent ID 列表
                - tasks: 任务配置列表
                - process: 执行流程类型 (sequential/hierarchical)
                - manager_llm: Manager LLM 配置（Hierarchical 模式需要）
                - memory: 是否启用记忆
                - cache: 是否启用缓存
                - max_rpm: 每分钟最大请求数
                - share_agent_output: 是否共享 Agent 输出
                - verbose: 是否详细输出
                - enabled: 是否启用
                - metadata: 元数据

        Returns:
            创建的 Crew 对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("Crew 名称不能为空")

        # 生成 ID
        crew_id = data.get("id") or f"crew_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_crew(crew_id)
        if existing:
            raise ValueError(f"Crew ID '{crew_id}' 已存在")

        # 验证 process 类型
        process = ProcessType.SEQUENTIAL
        if data.get("process"):
            try:
                process = ProcessType(data["process"])
            except ValueError:
                raise ValueError(f"无效的 process 值: {data['process']}")

        # 验证 Hierarchical 模式需要 manager_llm
        if process == ProcessType.HIERARCHICAL and not data.get("manager_llm"):
            raise ValueError("Hierarchical 模式需要配置 manager_llm")

        # 验证关联的 Agent 是否存在
        agents = data.get("agents", [])
        if agents:
            for agent_id in agents:
                agent = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
                if not agent:
                    raise ValueError(f"Agent '{agent_id}' 不存在")

        # 创建 CrewTask 记录
        task_ids = []
        tasks_data = data.get("tasks", [])
        for task_data in tasks_data:
            if isinstance(task_data, dict):
                task_id = task_data.get("id") or f"task_{uuid.uuid4().hex[:8]}"

                # 验证 agent_id 是否存在
                if task_data.get("agent_id"):
                    agent = self.db.select_one("agents", where="id = ?", where_params=(task_data["agent_id"],))
                    if not agent:
                        raise ValueError(f"任务关联的 Agent '{task_data['agent_id']}' 不存在")

                task_record = {
                    "id": task_id,
                    "name": task_data.get("name", ""),
                    "description": task_data.get("description", ""),
                    "expected_output": task_data.get("expected_output", ""),
                    "agent_id": task_data.get("agent_id"),
                    "tools": task_data.get("tools", []),
                    "context": task_data.get("context", []),
                    "async_execution": task_data.get("async_execution", False),
                    "config": task_data.get("config", {}),
                }
                self.db.insert("crew_tasks", task_record)
                task_ids.append(task_id)

        # 处理 manager_llm 字段（可能是 dict 或 string）
        manager_llm = data.get("manager_llm")
        if isinstance(manager_llm, dict):
            manager_llm = json.dumps(manager_llm, ensure_ascii=False)

        now = datetime.now()
        crew_data = {
            "id": crew_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "agents": agents,
            "tasks": task_ids,
            "process": process.value,
            "manager_llm": manager_llm,
            "memory": data.get("memory", False),
            "cache": data.get("cache", True),
            "max_rpm": data.get("max_rpm"),
            "share_agent_output": data.get("share_agent_output", True),
            "verbose": data.get("verbose", False),
            "enabled": data.get("enabled", True),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("crews", crew_data)

        logger.info(f"Created crew: {crew_id}")
        return self._row_to_crew(crew_data)

    def update_crew(self, crew_id: str, data: dict[str, Any]) -> Crew | None:
        """更新 Crew

        Args:
            crew_id: Crew ID
            data: 更新数据

        Returns:
            更新后的 Crew 对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找 Crew
        row = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
        if not row:
            return None

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = [
            "name", "description", "agents", "tasks",
            "process", "manager_llm", "memory", "cache",
            "max_rpm", "share_agent_output", "verbose",
            "enabled", "metadata"
        ]

        for field in updatable_fields:
            if field in data:
                # 特殊处理 process
                if field == "process":
                    try:
                        process = ProcessType(data["process"])
                        update_data[field] = process.value
                    except ValueError:
                        raise ValueError(f"无效的 process 值: {data['process']}")
                # 特殊处理 manager_llm（可能是 dict）
                elif field == "manager_llm" and isinstance(data[field], dict):
                    update_data[field] = json.dumps(data[field], ensure_ascii=False)
                else:
                    update_data[field] = data[field]

        # 验证 Hierarchical 模式需要 manager_llm
        new_process = data.get("process") or row.get("process")
        new_manager_llm = data.get("manager_llm") if "manager_llm" in data else row.get("manager_llm")
        if new_process == "hierarchical" and not new_manager_llm:
            raise ValueError("Hierarchical 模式需要配置 manager_llm")

        # 验证关联的 Agent 是否存在
        if "agents" in data and data["agents"]:
            for agent_id in data["agents"]:
                agent = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
                if not agent:
                    raise ValueError(f"Agent '{agent_id}' 不存在")

        # 更新任务
        if "tasks" in data:
            # 删除旧任务
            old_task_ids = self._parse_json(row.get("tasks", "[]"))
            for old_task_id in old_task_ids:
                self.db.delete("crew_tasks", where="id = ?", where_params=(old_task_id,))

            # 创建新任务
            task_ids = []
            for task_data in data["tasks"]:
                if isinstance(task_data, dict):
                    task_id = task_data.get("id") or f"task_{uuid.uuid4().hex[:8]}"

                    # 验证 agent_id 是否存在
                    if task_data.get("agent_id"):
                        agent = self.db.select_one("agents", where="id = ?", where_params=(task_data["agent_id"],))
                        if not agent:
                            raise ValueError(f"任务关联的 Agent '{task_data['agent_id']}' 不存在")

                    task_record = {
                        "id": task_id,
                        "name": task_data.get("name", ""),
                        "description": task_data.get("description", ""),
                        "expected_output": task_data.get("expected_output", ""),
                        "agent_id": task_data.get("agent_id"),
                        "tools": task_data.get("tools", []),
                        "context": task_data.get("context", []),
                        "async_execution": task_data.get("async_execution", False),
                        "config": task_data.get("config", {}),
                    }
                    self.db.insert("crew_tasks", task_record)
                    task_ids.append(task_id)

            update_data["tasks"] = task_ids

        # 更新数据库
        self.db.update(
            "crews",
            update_data,
            where="id = ?",
            where_params=(crew_id,)
        )

        logger.info(f"Updated crew: {crew_id}")
        return self.get_crew(crew_id)

    def delete_crew(self, crew_id: str) -> bool:
        """删除 Crew

        Args:
            crew_id: Crew ID

        Returns:
            是否删除成功
        """
        # 查找 Crew
        row = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
        if not row:
            return False

        # 检查是否有正在执行的任务
        running_tasks = self.db.select_all(
            "agent_tasks",
            where="crew_id = ? AND status IN (?, ?)",
            where_params=(crew_id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
        )
        if running_tasks:
            raise ValueError(f"Crew '{crew_id}' 有 {len(running_tasks)} 个正在执行的任务，无法删除")

        # 删除关联的任务
        task_ids = self._parse_json(row.get("tasks", "[]"))
        for task_id in task_ids:
            self.db.delete("crew_tasks", where="id = ?", where_params=(task_id,))

        # 删除 Crew
        self.db.delete("crews", where="id = ?", where_params=(crew_id,))
        logger.info(f"Deleted crew: {crew_id}")
        return True

    async def execute_crew(self, crew_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """执行 Crew 任务

        Args:
            crew_id: Crew ID
            input_data: 输入数据

        Returns:
            执行结果

        Raises:
            ValueError: Crew 不存在或配置错误
        """
        crew = self.get_crew(crew_id)
        if not crew:
            raise ValueError(f"Crew '{crew_id}' 不存在")

        if not crew.enabled:
            raise ValueError(f"Crew '{crew_id}' 未启用")

        if not crew.agents:
            raise ValueError(f"Crew '{crew_id}' 没有配置 Agent")

        # 创建 AgentTask 记录
        task_id = f"task_exec_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        agent_task_data = {
            "id": task_id,
            "crew_id": crew_id,
            "flow_id": None,
            "name": f"执行 Crew: {crew.name}",
            "description": input_data.get("description", ""),
            "status": TaskStatus.RUNNING.value,
            "progress": 0,
            "input": input_data,
            "output": {},
            "result": None,
            "error": None,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "started_at": now.isoformat(),
            "completed_at": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        self.db.insert("agent_tasks", agent_task_data)

        result = {
            "task_id": task_id,
            "crew_id": crew_id,
            "crew_name": crew.name,
            "status": TaskStatus.RUNNING.value,
            "success": False,
            "output": None,
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
            # 获取任务详情
            tasks = self._get_crew_tasks(crew.tasks)

            # 根据 process 类型执行
            if crew.process == ProcessType.SEQUENTIAL:
                execution_result = await self._execute_sequential(crew, tasks, input_data)
            else:
                execution_result = await self._execute_hierarchical(crew, tasks, input_data)

            result["success"] = True
            result["output"] = execution_result

            # 更新任务状态
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 100,
                    "output": execution_result,
                    "result": json.dumps(execution_result, ensure_ascii=False),
                    "completed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(task_id,)
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Crew execution failed: {crew_id} - {e}")

            # 更新任务状态为失败
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.FAILED.value,
                    "error": str(e),
                    "completed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(task_id,)
            )

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        result["status"] = TaskStatus.COMPLETED.value if result["success"] else TaskStatus.FAILED.value

        return result

    async def test_crew(self, crew_id: str) -> dict[str, Any]:
        """测试 Crew

        Args:
            crew_id: Crew ID

        Returns:
            测试结果

        Raises:
            ValueError: Crew 不存在或配置错误
        """
        crew = self.get_crew(crew_id)
        if not crew:
            raise ValueError(f"Crew '{crew_id}' 不存在")

        result = {
            "crew_id": crew_id,
            "crew_name": crew.name,
            "success": True,
            "errors": [],
            "warnings": [],
            "checks": {
                "agents": False,
                "tasks": False,
                "process": False,
                "llm": False,
            },
        }

        # 检查 Agent 配置
        if not crew.agents:
            result["errors"].append("Crew 没有配置任何 Agent")
            result["success"] = False
        else:
            # 验证每个 Agent 是否存在
            missing_agents = []
            for agent_id in crew.agents:
                agent = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
                if not agent:
                    missing_agents.append(agent_id)

            if missing_agents:
                result["errors"].append(f"以下 Agent 不存在: {', '.join(missing_agents)}")
                result["success"] = False
            else:
                result["checks"]["agents"] = True

        # 检查任务配置
        if not crew.tasks:
            result["warnings"].append("Crew 没有配置任何任务")
        else:
            tasks = self._get_crew_tasks(crew.tasks)

            # 检查任务依赖
            task_ids = set(t.id for t in tasks)
            for task in tasks:
                for context_id in task.context:
                    if context_id not in task_ids:
                        result["warnings"].append(f"任务 '{task.name}' 依赖的任务 '{context_id}' 不存在")

            # 检查任务的 Agent 分配
            for task in tasks:
                if task.agent_id and task.agent_id not in crew.agents:
                    result["warnings"].append(f"任务 '{task.name}' 的 Agent '{task.agent_id}' 不在 Crew 的 Agent 列表中")

            result["checks"]["tasks"] = True

        # 检查 process 配置
        if crew.process == ProcessType.HIERARCHICAL:
            if not crew.manager_llm:
                result["errors"].append("Hierarchical 模式需要配置 manager_llm")
                result["success"] = False
            else:
                result["checks"]["process"] = True
        else:
            result["checks"]["process"] = True

        # 检查 LLM 配置
        if self._context:
            # 检查 Agent 的 LLM 配置
            for agent_id in crew.agents:
                agent_row = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
                if agent_row:
                    provider_id = agent_row.get("provider_id")
                    if not provider_id:
                        result["warnings"].append(f"Agent '{agent_id}' 未配置 LLM 提供商")
        else:
            result["warnings"].append("Context 未初始化，无法验证 LLM 配置")

        result["checks"]["llm"] = True

        return result

    def get_templates(self) -> list[dict[str, Any]]:
        """获取 Crew 模板列表

        Returns:
            模板列表
        """
        templates = [
            {
                "id": "template_research_team",
                "name": "研究团队",
                "description": "一个协作研究团队，包含研究员、分析师和撰稿人",
                "category": "research",
                "agents": [],
                "tasks": [
                    {
                        "id": "task_research",
                        "name": "资料收集",
                        "description": "收集相关主题的研究资料",
                        "expected_output": "整理好的资料清单",
                        "agent_id": None,
                        "tools": [],
                        "context": [],
                        "async_execution": False,
                    },
                    {
                        "id": "task_analyze",
                        "name": "分析整理",
                        "description": "分析收集的资料，提取关键信息",
                        "expected_output": "分析报告",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_research"],
                        "async_execution": False,
                    },
                    {
                        "id": "task_write",
                        "name": "撰写报告",
                        "description": "基于分析结果撰写最终报告",
                        "expected_output": "完整的研究报告",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_analyze"],
                        "async_execution": False,
                    },
                ],
                "process": "sequential",
                "memory": True,
                "cache": True,
                "share_agent_output": True,
            },
            {
                "id": "template_content_team",
                "name": "内容创作团队",
                "description": "一个内容创作团队，包含策划、撰稿和编辑",
                "category": "content",
                "agents": [],
                "tasks": [
                    {
                        "id": "task_plan",
                        "name": "内容策划",
                        "description": "制定内容创作计划和大纲",
                        "expected_output": "内容大纲和创作计划",
                        "agent_id": None,
                        "tools": [],
                        "context": [],
                        "async_execution": False,
                    },
                    {
                        "id": "task_draft",
                        "name": "初稿撰写",
                        "description": "根据大纲撰写内容初稿",
                        "expected_output": "内容初稿",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_plan"],
                        "async_execution": False,
                    },
                    {
                        "id": "task_edit",
                        "name": "编辑润色",
                        "description": "编辑和润色内容",
                        "expected_output": "最终内容",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_draft"],
                        "async_execution": False,
                    },
                ],
                "process": "sequential",
                "memory": False,
                "cache": True,
                "share_agent_output": True,
            },
            {
                "id": "template_dev_team",
                "name": "开发团队",
                "description": "一个软件开发团队，包含架构师、开发者和测试工程师",
                "category": "development",
                "agents": [],
                "tasks": [
                    {
                        "id": "task_design",
                        "name": "架构设计",
                        "description": "设计系统架构和技术方案",
                        "expected_output": "架构设计文档",
                        "agent_id": None,
                        "tools": [],
                        "context": [],
                        "async_execution": False,
                    },
                    {
                        "id": "task_implement",
                        "name": "代码实现",
                        "description": "根据设计实现功能代码",
                        "expected_output": "功能代码",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_design"],
                        "async_execution": False,
                    },
                    {
                        "id": "task_test",
                        "name": "测试验证",
                        "description": "编写测试用例并验证功能",
                        "expected_output": "测试报告",
                        "agent_id": None,
                        "tools": [],
                        "context": ["task_implement"],
                        "async_execution": False,
                    },
                ],
                "process": "sequential",
                "memory": True,
                "cache": True,
                "share_agent_output": True,
            },
            {
                "id": "template_hierarchical_team",
                "name": "层级管理团队",
                "description": "一个由 Manager 统筹协调的团队，适用于复杂任务",
                "category": "management",
                "agents": [],
                "tasks": [
                    {
                        "id": "task_main",
                        "name": "主任务",
                        "description": "需要协调多个 Agent 完成的复杂任务",
                        "expected_output": "任务完成结果",
                        "agent_id": None,
                        "tools": [],
                        "context": [],
                        "async_execution": False,
                    },
                ],
                "process": "hierarchical",
                "manager_llm": "gpt-4",
                "memory": True,
                "cache": True,
                "share_agent_output": True,
            },
        ]

        return templates

    # ==================== 私有方法 ====================

    def _row_to_crew(self, row: dict[str, Any]) -> Crew:
        """将数据库行转换为 Crew 对象"""
        return Crew(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            agents=self._parse_json(row.get("agents", "[]")),
            tasks=self._parse_json(row.get("tasks", "[]")),
            process=ProcessType(row.get("process", "sequential")),
            manager_llm=row.get("manager_llm"),
            memory=bool(row.get("memory", 0)),
            cache=bool(row.get("cache", 1)),
            max_rpm=row.get("max_rpm"),
            share_agent_output=bool(row.get("share_agent_output", 1)),
            verbose=bool(row.get("verbose", 0)),
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

    def _get_crew_tasks(self, task_ids: list[str]) -> list[CrewTask]:
        """获取 Crew 的任务列表

        Args:
            task_ids: 任务 ID 列表

        Returns:
            CrewTask 列表
        """
        tasks = []
        for task_id in task_ids:
            row = self.db.select_one("crew_tasks", where="id = ?", where_params=(task_id,))
            if row:
                tasks.append(self._row_to_crew_task(row))
        return tasks

    def _row_to_crew_task(self, row: dict[str, Any]) -> CrewTask:
        """将数据库行转换为 CrewTask 对象"""
        return CrewTask(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            expected_output=row.get("expected_output", ""),
            agent_id=row.get("agent_id"),
            tools=self._parse_json(row.get("tools", "[]")),
            context=self._parse_json(row.get("context", "[]")),
            async_execution=bool(row.get("async_execution", 0)),
            config=self._parse_json(row.get("config", "{}")),
        )

    async def _execute_sequential(
        self,
        crew: Crew,
        tasks: list[CrewTask],
        input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """串行执行任务

        Args:
            crew: Crew 对象
            tasks: 任务列表
            input_data: 输入数据

        Returns:
            执行结果
        """
        results = {}
        context_data = {}

        for task in tasks:
            # 获取上下文数据
            task_context = {}
            for context_id in task.context:
                if context_id in context_data:
                    task_context[context_id] = context_data[context_id]

            # 执行任务
            task_result = await self._execute_single_task(
                crew, task, input_data, task_context
            )

            results[task.id] = task_result
            context_data[task.id] = task_result

        return {
            "process": "sequential",
            "tasks": results,
            "final_output": list(results.values())[-1] if results else None,
        }

    async def _execute_hierarchical(
        self,
        crew: Crew,
        tasks: list[CrewTask],
        input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """层级执行任务（由 Manager 分配）

        Args:
            crew: Crew 对象
            tasks: 任务列表
            input_data: 输入数据

        Returns:
            执行结果
        """
        # TODO: 实现真正的 Hierarchical 执行逻辑
        # 目前使用简化的串行执行
        results = {}
        context_data = {}

        for task in tasks:
            task_context = {}
            for context_id in task.context:
                if context_id in context_data:
                    task_context[context_id] = context_data[context_id]

            task_result = await self._execute_single_task(
                crew, task, input_data, task_context
            )

            results[task.id] = task_result
            context_data[task.id] = task_result

        return {
            "process": "hierarchical",
            "manager_llm": crew.manager_llm,
            "tasks": results,
            "final_output": list(results.values())[-1] if results else None,
        }

    async def _execute_single_task(
        self,
        crew: Crew,
        task: CrewTask,
        input_data: dict[str, Any],
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """执行单个任务

        Args:
            crew: Crew 对象
            task: 任务对象
            input_data: 输入数据
            context: 上下文数据

        Returns:
            任务执行结果
        """
        result = {
            "task_id": task.id,
            "task_name": task.name,
            "success": False,
            "output": None,
            "error": None,
        }

        try:
            # 获取负责的 Agent
            agent_id = task.agent_id
            if not agent_id and crew.agents:
                agent_id = crew.agents[0]  # 默认使用第一个 Agent

            if not agent_id:
                raise ValueError(f"任务 '{task.name}' 没有分配 Agent")

            # 获取 Agent 配置
            agent_row = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
            if not agent_row:
                raise ValueError(f"Agent '{agent_id}' 不存在")

            # 检查是否配置了 LLM 提供商
            provider_id = agent_row.get("provider_id")
            if not provider_id:
                raise ValueError(f"Agent '{agent_id}' 未配置 LLM 提供商")

            # 检查 Context 是否可用
            if not self._context:
                raise ValueError("Context 未初始化，无法执行任务")

            # 获取 Provider
            provider = self._context.get_provider_by_id(provider_id)
            if not provider:
                raise ValueError(f"LLM 提供商 '{provider_id}' 不存在")

            # 构建提示
            prompt = self._build_task_prompt(task, input_data, context)

            # 调用 LLM
            llm_response = await provider.text_chat(
                prompt=prompt,
                system_prompt=None,
                contexts=[],
                func_tool=None,
            )

            result["success"] = True
            result["output"] = llm_response.completion_text

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Task execution failed: {task.id} - {e}")

        return result

    def _build_task_prompt(
        self,
        task: CrewTask,
        input_data: dict[str, Any],
        context: dict[str, Any]
    ) -> str:
        """构建任务提示

        Args:
            task: 任务对象
            input_data: 输入数据
            context: 上下文数据

        Returns:
            提示字符串
        """
        parts = []

        # 任务描述
        if task.description:
            parts.append(f"任务: {task.description}")

        # 预期输出
        if task.expected_output:
            parts.append(f"\n预期输出: {task.expected_output}")

        # 输入数据
        if input_data:
            input_str = json.dumps(input_data, ensure_ascii=False, indent=2)
            parts.append(f"\n输入数据:\n{input_str}")

        # 上下文数据
        if context:
            parts.append("\n上下文信息:")
            for ctx_id, ctx_data in context.items():
                if isinstance(ctx_data, dict) and ctx_data.get("output"):
                    parts.append(f"- {ctx_data.get('task_name', ctx_id)}: {ctx_data['output']}")
                else:
                    parts.append(f"- {ctx_id}: {ctx_data}")

        return "\n".join(parts)
