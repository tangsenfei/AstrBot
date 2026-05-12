"""
智能体管理模块 - Flow 服务

提供 Flow 的 CRUD 操作、验证、模拟、执行等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.langgraph.checkpoint import create_checkpointer
from astrbot.core.langgraph.graphs.workflow import build_workflow_graph
from astrbot.core.langgraph.state import WorkflowState

if TYPE_CHECKING:
    from astrbot.core.star.context import Context

    from ..database import Database

from ..models import Agent as AgentModel
from ..models import (
    AgentType,
    Crew,
    CrewTask,
    Flow,
    FlowEdge,
    FlowNode,
    FlowNodeType,
    PlanningEffort,
    ProcessType,
    TaskStatus,
)

BUILTIN_DAILY_WORK_FLOW_ID = "builtin_nicebot_daily_work_flow"


class FlowService:
    """Flow 管理服务"""

    def __init__(self, db: Database, context: Context | None = None, crew_service=None):
        self.db = db
        self._context = context
        self._crew_service = crew_service

    @property
    def context(self) -> Context | None:
        """获取 Context 实例"""
        return self._context

    def get_flows(self, enabled_only: bool = False) -> list[Flow]:
        """获取 Flow 列表

        Args:
            enabled_only: 是否只返回启用的 Flow

        Returns:
            Flow 列表
        """
        self.ensure_builtin_daily_work_flow()
        flows = []

        if enabled_only:
            rows = self.db.select_all(
                "flows",
                where="enabled = ?",
                where_params=(1,),
                order_by="created_at DESC"
            )
        else:
            rows = self.db.select_all("flows", order_by="created_at DESC")

        for row in rows:
            try:
                flow = self._row_to_flow(row)
                flows.append(flow)
            except Exception as e:
                logger.error(f"Failed to parse flow {row.get('id')}: {e}")

        return flows

    def get_flow(self, flow_id: str) -> Flow | None:
        """获取单个 Flow

        Args:
            flow_id: Flow ID

        Returns:
            Flow 对象，不存在则返回 None
        """
        if flow_id == BUILTIN_DAILY_WORK_FLOW_ID:
            self.ensure_builtin_daily_work_flow()
        row = self.db.select_one("flows", where="id = ?", where_params=(flow_id,))
        if row:
            return self._row_to_flow(row)
        return None

    def create_flow(self, data: dict[str, Any]) -> Flow:
        """创建 Flow

        Args:
            data: Flow 数据
                - name: Flow 名称（必填）
                - description: 描述
                - nodes: 节点列表
                - edges: 边列表
                - enabled: 是否启用
                - metadata: 元数据

        Returns:
            创建的 Flow 对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("Flow 名称不能为空")

        # 生成 ID
        flow_id = data.get("id") or f"flow_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_flow(flow_id)
        if existing:
            raise ValueError(f"Flow ID '{flow_id}' 已存在")

        # 验证节点
        nodes = self._validate_and_parse_nodes(data.get("nodes", []))

        # 验证边
        edges = self._validate_and_parse_edges(data.get("edges", []), nodes)

        now = datetime.now()
        flow_data = {
            "id": flow_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "enabled": data.get("enabled", True),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入 Flow
        self.db.insert("flows", flow_data)

        # 插入节点
        for node in nodes:
            node_data = {
                "id": node.id,
                "flow_id": flow_id,
                "name": node.name,
                "type": node.type.value,
                "config": node.config,
                "position": node.position,
            }
            self.db.insert("flow_nodes", node_data)

        # 插入边
        for edge in edges:
            edge_data = {
                "id": edge.id,
                "flow_id": flow_id,
                "source": edge.source,
                "target": edge.target,
                "condition": edge.condition,
            }
            self.db.insert("flow_edges", edge_data)

        logger.info(f"Created flow: {flow_id}")
        return self.get_flow(flow_id)

    def update_flow(self, flow_id: str, data: dict[str, Any]) -> Flow | None:
        """更新 Flow

        Args:
            flow_id: Flow ID
            data: 更新数据

        Returns:
            更新后的 Flow 对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找 Flow
        row = self.db.select_one("flows", where="id = ?", where_params=(flow_id,))
        if not row:
            return None
        is_builtin = self._is_builtin_row(row)

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = ["name", "description", "enabled", "metadata"]

        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]
        if is_builtin:
            self._validate_builtin_daily_work_flow_update(flow_id, data)
            update_data["enabled"] = 1
            current_metadata = self._parse_json(row.get("metadata", "{}"))
            next_metadata = data.get("metadata") if "metadata" in data else current_metadata
            if not isinstance(next_metadata, dict):
                next_metadata = {}
            update_data["metadata"] = {
                **current_metadata,
                **next_metadata,
                "is_builtin": True,
                "locked": True,
                "non_deletable": True,
                "resettable": True,
                "editable": True,
                "topology_locked": True,
                "allows_cycles": True,
                "schema_version": max(int(current_metadata.get("schema_version") or 0), 6),
            }

        # 更新节点
        if "nodes" in data:
            # 删除旧节点和边
            self.db.delete("flow_edges", where="flow_id = ?", where_params=(flow_id,))
            self.db.delete("flow_nodes", where="flow_id = ?", where_params=(flow_id,))

            # 验证并插入新节点
            nodes = self._validate_and_parse_nodes(data["nodes"])
            for node in nodes:
                node_data = {
                    "id": node.id,
                    "flow_id": flow_id,
                    "name": node.name,
                    "type": node.type.value,
                    "config": node.config,
                    "position": node.position,
                }
                self.db.insert("flow_nodes", node_data)

        # 更新边
        if "edges" in data:
            # 获取当前节点
            current_flow = self.get_flow(flow_id)
            if current_flow:
                nodes = current_flow.nodes
            else:
                nodes = self._validate_and_parse_nodes(data.get("nodes", []))

            # 删除旧边
            self.db.delete("flow_edges", where="flow_id = ?", where_params=(flow_id,))

            # 验证并插入新边
            edges = self._validate_and_parse_edges(data["edges"], nodes)
            for edge in edges:
                edge_data = {
                    "id": edge.id,
                    "flow_id": flow_id,
                    "source": edge.source,
                    "target": edge.target,
                    "condition": edge.condition,
                }
                self.db.insert("flow_edges", edge_data)

        # 更新数据库
        self.db.update(
            "flows",
            update_data,
            where="id = ?",
            where_params=(flow_id,)
        )

        logger.info(f"Updated flow: {flow_id}")
        return self.get_flow(flow_id)

    def delete_flow(self, flow_id: str) -> bool:
        """删除 Flow

        Args:
            flow_id: Flow ID

        Returns:
            是否删除成功
        """
        # 查找 Flow
        row = self.db.select_one("flows", where="id = ?", where_params=(flow_id,))
        if not row:
            return False
        if self._is_builtin_row(row):
            raise ValueError("内置 Flow 不允许删除")

        # 检查是否有正在执行的任务
        running_tasks = self.db.select_all(
            "agent_tasks",
            where="flow_id = ? AND status IN (?, ?)",
            where_params=(flow_id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
        )
        if running_tasks:
            raise ValueError(f"Flow '{flow_id}' 有 {len(running_tasks)} 个正在执行的任务，无法删除")

        # 删除关联的边和节点（外键级联删除）
        self.db.delete("flow_edges", where="flow_id = ?", where_params=(flow_id,))
        self.db.delete("flow_nodes", where="flow_id = ?", where_params=(flow_id,))

        # 删除 Flow
        self.db.delete("flows", where="id = ?", where_params=(flow_id,))
        logger.info(f"Deleted flow: {flow_id}")
        return True

    def ensure_builtin_daily_work_flow(self) -> None:
        existing = self.db.select_one("flows", where="id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
        if existing:
            metadata = self._parse_json(existing.get("metadata", "{}"))
            if not isinstance(metadata, dict):
                metadata = {}
            upgraded = {
                **metadata,
                "is_builtin": True,
                "locked": True,
                "non_deletable": True,
                "resettable": True,
                "editable": True,
                "kind": "work_daily_task",
                "topology_locked": True,
                "allows_cycles": True,
            }
            if int(upgraded.get("schema_version") or 0) < 6:
                self.reset_builtin_daily_work_flow()
                return
            if upgraded != metadata or not existing.get("enabled"):
                self.db.update(
                    "flows",
                    {"enabled": 1, "metadata": upgraded, "updated_at": datetime.now().isoformat()},
                    where="id = ?",
                    where_params=(BUILTIN_DAILY_WORK_FLOW_ID,),
                )
            node_count = self.db.execute(
                "SELECT COUNT(*) AS count FROM flow_nodes WHERE flow_id = ?",
                (BUILTIN_DAILY_WORK_FLOW_ID,),
            ).fetchone()["count"]
            if node_count == 0:
                self.reset_builtin_daily_work_flow()
            return
        self.reset_builtin_daily_work_flow(create_if_missing=True)

    def reset_builtin_daily_work_flow(self, create_if_missing: bool = False) -> Flow:
        existing = self.db.select_one("flows", where="id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
        now = datetime.now()
        flow_data = {
            "id": BUILTIN_DAILY_WORK_FLOW_ID,
            "name": "NiceBot 日常任务执行流程",
            "description": "Work 日常任务内置流程：需求明确、任务模式策略、任务规划、计划审批、依赖执行、审查分支、返工 HITL 与验收交付。",
            "enabled": 1,
            "metadata": {
                "is_builtin": True,
                "locked": True,
                "non_deletable": True,
                "resettable": True,
                "editable": True,
                "kind": "work_daily_task",
                "schema_version": 6,
                "topology_locked": True,
                "allows_cycles": True,
            },
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        nodes, edges = self._builtin_daily_work_flow_topology()
        if existing:
            nodes = self._merge_builtin_daily_work_nodes(nodes)
            edges = self._merge_builtin_daily_work_edges(edges)
        if existing:
            self.db.delete("flow_edges", where="flow_id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
            self.db.delete("flow_nodes", where="flow_id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
            flow_data["created_at"] = existing.get("created_at") or flow_data["created_at"]
            self.db.update(
                "flows",
                {k: v for k, v in flow_data.items() if k != "id"},
                where="id = ?",
                where_params=(BUILTIN_DAILY_WORK_FLOW_ID,),
            )
        else:
            self.db.insert("flows", flow_data)
        for node in nodes:
            self.db.insert(
                "flow_nodes",
                {
                    "id": node["id"],
                    "flow_id": BUILTIN_DAILY_WORK_FLOW_ID,
                    "name": node["name"],
                    "type": node["type"],
                    "config": node["config"],
                    "position": node["position"],
                },
            )
        for edge in edges:
            self.db.insert(
                "flow_edges",
                {
                    "id": edge["id"],
                    "flow_id": BUILTIN_DAILY_WORK_FLOW_ID,
                    "source": edge["source"],
                    "target": edge["target"],
                    "condition": edge["condition"],
                },
            )
        logger.info("Ensured builtin NiceBot daily work flow")
        flow = self.get_flow(BUILTIN_DAILY_WORK_FLOW_ID)
        if not flow:
            raise ValueError("内置日常任务流程初始化失败")
        return flow

    def _builtin_daily_work_flow_topology(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes = [
            {"id": "daily_start", "name": "开始", "type": "start", "position": {"x": 80, "y": 220}, "config": {}},
            {
                "id": "daily_clarify",
                "name": "需求明确",
                "type": "hitl",
                "position": {"x": 420, "y": 220},
                "config": {
                    "builtin_stage": "clarification",
                    "runtime_config_key": "clarification_config",
                    "agent_id": "agent_nicebot_work_assistant",
                    "template_id": "builtin_work_requirement_clarification",
                    "repeat_until_clear": True,
                    "content_provider_type": "agent",
                    "content_provider_agent_id": "agent_nicebot_work_assistant",
                    "content_system_prompt": "你是 NiceBot Work 任务助手，负责根据用户任务目标生成精准、可操作的需求确认项。你必须只返回合法 JSON，不要输出解释、Markdown 或代码块。",
                    "content_prompt": (
                        "请为 Work 任务生成 2-5 个需求确认项。\n\n"
                        "任务名称：{task_name}\n"
                        "任务描述：{task_desc}\n\n"
                        "工作上下文：\n{work_context}\n\n"
                        "请只返回如下 JSON 对象，不要包含 markdown 代码块：\n"
                        "{\n"
                        '  "confirmation_items": [\n'
                        "    {\n"
                        '      "key": "字段英文key",\n'
                        '      "label": "字段中文标签",\n'
                        '      "description": "为什么需要确认这个信息",\n'
                        '      "field_type": "select 或 multiselect 或 textarea",\n'
                        '      "required": true,\n'
                        '      "recommended": "推荐：结合任务内容给出的默认值",\n'
                        '      "options": ["推荐：选项A", "选项B", "选项C"],\n'
                        '      "allow_custom": true,\n'
                        '      "custom_placeholder": "用户选择自定义时的填写提示"\n'
                        "    }\n"
                        "  ]\n"
                        "}\n\n"
                        "生成要求：\n"
                        "1. 确认项必须贴合任务，不要使用泛化的固定字段。\n"
                        "2. 优先确认会影响交付质量的信息，例如目标对象、范围边界、偏好、约束、交付格式、完成标准。\n"
                        "3. 有明确互斥选项时用 select；可多选维度用 multiselect；需要用户自由描述时用 textarea。\n"
                        "4. select/multiselect 必须提供 3-6 个 options，且至少一个选项以「推荐：」开头。\n"
                        "5. 每个 select/multiselect 都必须设置 allow_custom 为 true。\n"
                        "6. key 使用稳定英文小写蛇形命名。"
                    ),
                },
            },
            {
                "id": "daily_mode_strategy",
                "name": "任务模式策略",
                "type": "router",
                "position": {"x": 760, "y": 220},
                "config": {
                    "builtin_stage": "task_mode_strategy",
                    "runtime_config_key": "plan_config.task_mode",
                    "default_mode": "normal",
                    "modes": {
                        "quick": {"label": "快速", "description": "单执行单元，快速形成可交付结果。", "planning_effort": "low"},
                        "normal": {"label": "常规", "description": "按一级步骤规划执行，二级内容作为检查项或说明。", "planning_effort": "medium"},
                        "deep": {"label": "深度", "description": "按叶子步骤细粒度规划，允许研究、审查、汇报等资源分工。", "planning_effort": "high"},
                    },
                    "conditions": [
                        {"key": "quick", "label": "快速任务", "expression": "plan_config.task_mode == 'quick'"},
                        {"key": "normal", "label": "常规任务", "expression": "plan_config.task_mode == 'normal'"},
                        {"key": "deep", "label": "深度任务", "expression": "plan_config.task_mode == 'deep'"},
                    ],
                },
            },
            {
                "id": "daily_plan",
                "name": "任务规划",
                "type": "agent_task",
                "position": {"x": 1100, "y": 220},
                "config": {
                    "builtin_stage": "plan",
                    "runtime_config_key": "plan_config",
                    "agent_id": "agent_nicebot_work_assistant",
                    "max_depth": 2,
                    "output": "resource_aware_execution_tree",
                    "system_prompt": "你是 NiceBot Work 的资源感知规划智能体。你需要同时完成任务拆解、依赖设计和执行资源分配，并输出可校验的执行树。",
                    "prompt": (
                        "请根据 Work 规划协议输出可审批、可直接落地的执行树。\n\n"
                        "## 任务目标\n"
                        "- 名称：{task_name}\n"
                        "- 描述：{task_desc}\n\n"
                        "## 已确认需求\n"
                        "{clarification}\n\n"
                        "## 工作上下文\n"
                        "{work_context}\n\n"
                        "## 规划要求\n"
                        "- 你必须在规划阶段完成执行资源分配；分配与拆解、依赖设计是一体的。\n"
                        "- 按当前任务模式选择执行粒度，不要先写计划再补执行者。\n"
                        "- 每个执行步骤必须同时给出依赖、执行者、审查者、交付物、验收标准和资源选择理由。\n"
                        "- 依赖只能引用本计划中已经存在的 step_id，不能形成环。\n"
                        "- 输出必须能被系统校验并在人工审批通过后原样执行。\n\n"
                        "{feedback_text}"
                    ),
                },
            },
            {
                "id": "daily_plan_approval",
                "name": "计划审批",
                "type": "hitl",
                "position": {"x": 1440, "y": 220},
                "config": {
                    "builtin_stage": "plan_hitl",
                    "runtime_config_key": "plan_config",
                    "template_id": "builtin_work_plan_approval",
                    "optional_config_key": "plan_config.enabled",
                    "default_enabled": True,
                    "body_template": "请审批以下执行计划：\n\n{plan_body}",
                },
            },
            {
                "id": "daily_execute",
                "name": "依赖执行",
                "type": "agent_task",
                "position": {"x": 1780, "y": 220},
                "config": {
                    "builtin_stage": "execute_dag",
                    "runtime_config_key": "executor_config",
                    "default_agent_id": "agent_nicebot_work_executor",
                    "research_agent_id": "agent_nicebot_research_expert",
                    "system_prompt": "你是 NiceBot Work 执行智能体。当前执行者：{agent_label}。只执行当前步骤，不负责审查自己的结果。",
                    "prompt": "请执行 Work 任务中的当前负责部分。\n\n## 任务需求\n{requirements}\n\n## 已审批整体计划\n{approved_plan}\n\n## 当前负责部分\n{step_scope}\n\n## 执行要求\n1. 先对齐任务需求和已审批整体计划，再完成当前负责部分。\n2. 只执行当前负责部分，不重写整体计划，也不要扩展到未分配步骤。\n3. 输出要能被后续步骤或最终交付复用，保留关键依据、结论和仍不确定的点。\n4. 如果当前负责部分与需求或计划冲突，明确指出冲突并给出最小可行处理。",
                },
            },
            {
                "id": "daily_review_gate",
                "name": "是否启用审查",
                "type": "router",
                "position": {"x": 2120, "y": 120},
                "config": {
                    "builtin_stage": "review_gate",
                    "runtime_config_key": "review_config.enabled",
                    "conditions": [
                        {"key": "enabled", "label": "需要审查", "expression": "review_config.enabled == true", "target": "daily_review"},
                        {"key": "disabled", "label": "跳过审查", "expression": "review_config.enabled == false", "target": "daily_deliver"},
                    ],
                },
            },
            {
                "id": "daily_review",
                "name": "执行审查",
                "type": "review",
                "position": {"x": 2460, "y": 120},
                "config": {
                    "builtin_stage": "review",
                    "runtime_config_key": "review_config",
                    "reviewer_id": "agent_nicebot_work_reviewer",
                    "optional_config_key": "review_config.enabled",
                    "default_enabled": False,
                    "max_rework_config_key": "review_config.max_rework",
                    "default_max_rework": 3,
                    "system_prompt": "你是 NiceBot Work 的审查智能体。只要结果明显未达成目标才判定返工。",
                    "prompt": "请审查以下任务结果是否达成目标。\n\n任务：{task_name}\n\n{work_context}\n\n执行结果：\n{results_text}\n\n如果通过，回复 PASS。需要返工，回复 RETRY 并说明原因。",
                },
            },
            {
                "id": "daily_rework_gate",
                "name": "审查分支判断",
                "type": "router",
                "position": {"x": 2800, "y": 120},
                "config": {
                    "builtin_stage": "review_branch",
                    "runtime_config_key": "review_config",
                    "conditions": [
                        {"key": "pass", "label": "审查通过", "expression": "review_passed == true", "target": "daily_deliver"},
                        {"key": "retry", "label": "未达返工上限", "expression": "review_passed == false && rework_count <= review_config.max_rework", "target": "daily_execute"},
                        {"key": "hitl", "label": "达到返工上限", "expression": "review_passed == false && rework_count > review_config.max_rework", "target": "daily_rework_hitl"},
                    ],
                },
            },
            {
                "id": "daily_rework_hitl",
                "name": "返工人工决策",
                "type": "hitl",
                "position": {"x": 3140, "y": 320},
                "config": {
                    "builtin_stage": "rework_hitl",
                    "runtime_config_key": "review_config",
                    "template_id": "builtin_work_rework_decision",
                    "title": "审查未通过",
                    "body": "任务审查未通过且已达到预设返工次数，请确认是否继续返工或结束任务。",
                },
            },
            {
                "id": "daily_deliver",
                "name": "验收与交付",
                "type": "deliverable",
                "position": {"x": 3480, "y": 120},
                "config": {
                    "builtin_stage": "deliverable",
                    "runtime_config_key": "deliverable_config",
                    "assistant_id": "agent_nicebot_work_assistant",
                    "reporter_id": "agent_nicebot_report_expert",
                    "artifact_type": "markdown",
                    "system_prompt": "你是 NiceBot Work 的汇报专家（{reporter_id}）。请只整理最终交付物，不混入过程日志。",
                    "prompt": "请将以下任务执行结果整理成最终交付物。\n\n任务：{task_name}\n\n{results_text}",
                },
            },
        ]
        edges = [
            {"id": "edge_daily_start_clarify", "source": "daily_start", "target": "daily_clarify", "condition": {}},
            {"id": "edge_daily_clarify_mode", "source": "daily_clarify", "target": "daily_mode_strategy", "condition": {}},
            {"id": "edge_daily_mode_plan", "source": "daily_mode_strategy", "target": "daily_plan", "condition": {"expression": "task_mode in ['quick', 'normal', 'deep']"}},
            {"id": "edge_daily_plan_approval", "source": "daily_plan", "target": "daily_plan_approval", "condition": {}},
            {"id": "edge_daily_approval_execute", "source": "daily_plan_approval", "target": "daily_execute", "condition": {}},
            {"id": "edge_daily_execute_review_gate", "source": "daily_execute", "target": "daily_review_gate", "condition": {}},
            {"id": "edge_daily_review_gate_review", "source": "daily_review_gate", "target": "daily_review", "condition": {"expression": "review_config.enabled == true"}},
            {"id": "edge_daily_review_gate_deliver", "source": "daily_review_gate", "target": "daily_deliver", "condition": {"expression": "review_config.enabled == false"}},
            {"id": "edge_daily_review_branch", "source": "daily_review", "target": "daily_rework_gate", "condition": {}},
            {"id": "edge_daily_branch_retry", "source": "daily_rework_gate", "target": "daily_execute", "condition": {"expression": "review_passed == false && rework_count <= review_config.max_rework"}},
            {"id": "edge_daily_branch_hitl", "source": "daily_rework_gate", "target": "daily_rework_hitl", "condition": {"expression": "review_passed == false && rework_count > review_config.max_rework"}},
            {"id": "edge_daily_branch_deliver", "source": "daily_rework_gate", "target": "daily_deliver", "condition": {"expression": "review_passed == true"}},
            {"id": "edge_daily_rework_hitl_execute", "source": "daily_rework_hitl", "target": "daily_execute", "condition": {"expression": "action == 'retry'"}},
            {"id": "edge_daily_rework_hitl_deliver", "source": "daily_rework_hitl", "target": "daily_deliver", "condition": {"expression": "action in ['finish', 'cancel']"}},
        ]
        return nodes, edges

    def _merge_builtin_daily_work_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current_rows = self.db.select_all("flow_nodes", where="flow_id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
        by_id = {row["id"]: row for row in current_rows}
        by_stage: dict[str, dict[str, Any]] = {}
        for row in current_rows:
            config = self._parse_json(row.get("config", "{}"))
            if isinstance(config, dict) and config.get("builtin_stage"):
                by_stage[str(config["builtin_stage"])] = row

        merged: list[dict[str, Any]] = []
        for node in nodes:
            template = dict(node)
            template_config = dict(template.get("config") or {})
            row = by_id.get(template["id"]) or by_stage.get(str(template_config.get("builtin_stage") or ""))
            if not row:
                merged.append(template)
                continue
            existing_config = self._parse_json(row.get("config", "{}"))
            if not isinstance(existing_config, dict):
                existing_config = {}
            next_config = {**template_config, **existing_config}
            for key in ("builtin_stage", "runtime_config_key"):
                if template_config.get(key):
                    next_config[key] = template_config[key]
            if template_config.get("builtin_stage") == "clarification":
                for key in ("content_system_prompt", "content_prompt"):
                    if template_config.get(key):
                        next_config[key] = template_config[key]
            if template_config.get("conditions") and not existing_config.get("conditions"):
                next_config["conditions"] = template_config["conditions"]
            template["name"] = row.get("name") or template["name"]
            template["config"] = next_config
            merged.append(template)
        return merged

    def _merge_builtin_daily_work_edges(self, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current_rows = self.db.select_all("flow_edges", where="flow_id = ?", where_params=(BUILTIN_DAILY_WORK_FLOW_ID,))
        by_id = {row["id"]: row for row in current_rows}
        merged: list[dict[str, Any]] = []
        for edge in edges:
            template = dict(edge)
            row = by_id.get(template["id"])
            if row:
                condition = self._parse_json(row.get("condition", "{}"))
                if isinstance(condition, dict):
                    template["condition"] = {**(template.get("condition") or {}), **condition}
            merged.append(template)
        return merged

    def _validate_builtin_daily_work_flow_update(self, flow_id: str, data: dict[str, Any]) -> None:
        if flow_id != BUILTIN_DAILY_WORK_FLOW_ID:
            return
        if "nodes" in data:
            current_nodes = self.db.select_all("flow_nodes", where="flow_id = ?", where_params=(flow_id,))
            current_by_id = {row["id"]: row.get("type") for row in current_nodes}
            next_by_id = {node.get("id"): node.get("type", "start") for node in data.get("nodes", []) if isinstance(node, dict)}
            if current_by_id and next_by_id != current_by_id:
                raise ValueError("内置日常任务 Flow 拓扑已锁定，仅允许编辑节点配置、名称和位置")
        if "edges" in data:
            current_edges = self.db.select_all("flow_edges", where="flow_id = ?", where_params=(flow_id,))
            current_topology = {(row["id"], row["source"], row["target"]) for row in current_edges}
            next_topology = {
                (edge.get("id"), edge.get("source"), edge.get("target"))
                for edge in data.get("edges", [])
                if isinstance(edge, dict)
            }
            if current_topology and next_topology != current_topology:
                raise ValueError("内置日常任务 Flow 拓扑已锁定，仅允许编辑边条件配置")

    def _is_builtin_row(self, row: dict[str, Any]) -> bool:
        metadata = self._parse_json(row.get("metadata", "{}"))
        return row.get("id") == BUILTIN_DAILY_WORK_FLOW_ID or bool(isinstance(metadata, dict) and metadata.get("is_builtin"))

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

    def _row_to_agent_model(self, row: dict[str, Any]) -> AgentModel:
        """将数据库行转换为 Agent 数据模型"""
        agent_type_val = row.get("agent_type", "custom")
        if agent_type_val in (None, ""):
            agent_type_val = "custom"

        return AgentModel(
            id=row["id"],
            name=row["name"],
            soul=row.get("soul", ""),
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

    def _get_crew_tasks(self, task_ids: list[str]) -> list[CrewTask]:
        """获取 Crew 的任务列表"""
        tasks = []
        for task_id in task_ids:
            row = self.db.select_one("crew_tasks", where="id = ?", where_params=(task_id,))
            if row:
                tasks.append(CrewTask(
                    id=row["id"],
                    name=row["name"],
                    description=row.get("description", ""),
                    expected_output=row.get("expected_output", ""),
                    agent_id=row.get("agent_id"),
                    tools=self._parse_json(row.get("tools", "[]")),
                    context=self._parse_json(row.get("context", "[]")),
                    async_execution=bool(row.get("async_execution", 0)),
                    config=self._parse_json(row.get("config", "{}")),
                ))
        return tasks

    def validate_flow(self, flow_id: str) -> dict[str, Any]:
        """验证 Flow 配置

        Args:
            flow_id: Flow ID

        Returns:
            验证结果

        Raises:
            ValueError: Flow 不存在
        """
        flow = self.get_flow(flow_id)
        if not flow:
            raise ValueError(f"Flow '{flow_id}' 不存在")

        result = {
            "flow_id": flow_id,
            "flow_name": flow.name,
            "success": True,
            "errors": [],
            "warnings": [],
            "checks": {
                "has_start": False,
                "has_end": False,
                "nodes_connected": False,
                "no_cycles": False,
                "node_configs": False,
            },
        }

        # 检查是否有开始节点
        start_nodes = [n for n in flow.nodes if n.type == FlowNodeType.START]
        if not start_nodes:
            result["errors"].append("Flow 缺少开始节点 (start)")
            result["success"] = False
        elif len(start_nodes) > 1:
            result["warnings"].append(f"Flow 有 {len(start_nodes)} 个开始节点，建议只保留一个")
        else:
            result["checks"]["has_start"] = True

        # 检查节点连接
        node_ids = {n.id for n in flow.nodes}
        {e.source for e in flow.edges}
        target_nodes = {e.target for e in flow.edges}

        # 检查是否有孤立节点
        isolated_nodes = []
        for node in flow.nodes:
            if node.type == FlowNodeType.START:
                # 开始节点应该没有入边
                if node.id in target_nodes:
                    result["warnings"].append(f"开始节点 '{node.name}' 有入边，将被忽略")
            else:
                # 其他节点应该有入边
                if node.id not in target_nodes:
                    isolated_nodes.append(node.name)

        if isolated_nodes:
            result["warnings"].append(f"以下节点没有入边连接: {', '.join(isolated_nodes)}")

        # 检查边的源和目标节点是否存在
        for edge in flow.edges:
            if edge.source not in node_ids:
                result["errors"].append(f"边 '{edge.id}' 的源节点 '{edge.source}' 不存在")
                result["success"] = False
            if edge.target not in node_ids:
                result["errors"].append(f"边 '{edge.id}' 的目标节点 '{edge.target}' 不存在")
                result["success"] = False

        if not result["errors"]:
            result["checks"]["nodes_connected"] = True

        # 检查是否有环。Work 内置流程需要展示真实的审查返工回路，允许显式标记的循环。
        if flow.metadata.get("allows_cycles"):
            result["checks"]["no_cycles"] = True
        elif not self._has_cycle(flow):
            result["checks"]["no_cycles"] = True
        else:
            result["errors"].append("Flow 存在循环依赖")
            result["success"] = False

        # 验证节点配置
        node_config_errors = self._validate_node_configs(flow)
        if node_config_errors:
            result["errors"].extend(node_config_errors)
            result["success"] = False
        else:
            result["checks"]["node_configs"] = True

        # 检查 Crew 节点引用的 Crew 是否存在
        for node in flow.nodes:
            if node.type == FlowNodeType.CREW:
                crew_id = node.config.get("crew_id") or node.config.get("crewName")
                if crew_id:
                    crew = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
                    if not crew:
                        result["warnings"].append(f"节点 '{node.name}' 引用的 Crew '{crew_id}' 不存在")
            elif node.type == FlowNodeType.AGENT_TASK:
                agent_id = node.config.get("agent_id") or node.config.get("default_agent_id")
                crew_id = node.config.get("crew_id")
                if agent_id:
                    agent = self.db.select_one("agents", where="id = ?", where_params=(agent_id,))
                    if not agent:
                        result["warnings"].append(f"节点 '{node.name}' 引用的 Agent '{agent_id}' 不存在")
                if crew_id:
                    crew = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
                    if not crew:
                        result["warnings"].append(f"节点 '{node.name}' 引用的 Crew '{crew_id}' 不存在")
            elif node.type == FlowNodeType.SUB_FLOW:
                sub_flow_id = node.config.get("flow_id")
                if sub_flow_id and not self.db.select_one("flows", where="id = ?", where_params=(sub_flow_id,)):
                    result["warnings"].append(f"节点 '{node.name}' 引用的子流程 '{sub_flow_id}' 不存在")

        return result

    def simulate_flow(self, flow_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """模拟 Flow 执行

        Args:
            flow_id: Flow ID
            input_data: 输入数据

        Returns:
            模拟结果

        Raises:
            ValueError: Flow 不存在或配置错误
        """
        flow = self.get_flow(flow_id)
        if not flow:
            raise ValueError(f"Flow '{flow_id}' 不存在")

        # 先验证 Flow
        validation = self.validate_flow(flow_id)
        if not validation["success"]:
            raise ValueError(f"Flow 验证失败: {'; '.join(validation['errors'])}")

        result = {
            "flow_id": flow_id,
            "flow_name": flow.name,
            "success": True,
            "simulated": True,
            "execution_path": [],
            "node_results": {},
            "final_output": None,
        }

        # 构建执行路径
        execution_order = self._get_execution_order(flow)

        for node in execution_order:
            node_result = {
                "node_id": node.id,
                "node_name": node.name,
                "node_type": node.type.value,
                "status": "simulated",
                "input": input_data,
                "output": f"[模拟输出] {node.name} 执行完成",
            }

            result["execution_path"].append(node.id)
            result["node_results"][node.id] = node_result

            # 更新下一个节点的输入
            input_data = {"previous_output": node_result["output"]}

        if execution_order:
            last_node = execution_order[-1]
            result["final_output"] = result["node_results"][last_node.id]["output"]

        return result

    async def execute_flow(
        self,
        flow_id: str,
        input_data: dict[str, Any],
        stream_callback=None,
    ) -> dict[str, Any]:
        """执行 Flow（使用 LangGraph 工作流图）

        Args:
            flow_id: Flow ID
            input_data: 输入数据
            stream_callback: 可选的流式回调函数

        Returns:
            执行结果

        Raises:
            ValueError: Flow 不存在或配置错误
        """
        flow = self.get_flow(flow_id)
        if not flow:
            raise ValueError(f"Flow '{flow_id}' 不存在")

        if not flow.enabled:
            raise ValueError(f"Flow '{flow_id}' 未启用")

        validation = self.validate_flow(flow_id)
        if not validation["success"]:
            raise ValueError(f"Flow 验证失败: {'; '.join(validation['errors'])}")

        task_id = f"task_flow_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        agent_task_data = {
            "id": task_id,
            "crew_id": None,
            "flow_id": flow_id,
            "name": f"执行 Flow: {flow.name}",
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
            "flow_id": flow_id,
            "flow_name": flow.name,
            "status": TaskStatus.RUNNING.value,
            "success": False,
            "execution_path": [],
            "node_results": {},
            "final_output": None,
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
            flow_def = self._flow_to_definition(flow)
            checkpointer = create_checkpointer()
            graph = build_workflow_graph(flow_def, checkpointer=checkpointer)

            from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
            from astrbot.core.langgraph.state import GraphRunContext

            run_ctx = GraphRunContext(
                provider=None,
                tool_executor=FunctionToolExecutor(),
                hooks=None,
                astr_event=self._context,
                config={"provider_id": input_data.get("provider_id"), "streaming_response": False},
            )

            initial_state = WorkflowState(
                flow_definition=flow_def,
                node_results={},
                current_node_id="",
                system_prompt=input_data.get("system_prompt", ""),
                user_prompt=input_data.get("prompt", ""),
                messages=[],
                session_id=input_data.get("session_id", ""),
                provider_id=input_data.get("provider_id"),
            )

            thread_id = f"workflow:{flow_id}"
            config = {"configurable": {"thread_id": thread_id, "run_ctx": run_ctx}}
            total_nodes = len(flow.nodes)

            async for state_update in graph.astream(initial_state, config=config):
                for node_id, node_output in state_update.items():
                    result["execution_path"].append(node_id)
                    if isinstance(node_output, dict) and "node_results" in node_output:
                        result["node_results"].update(node_output["node_results"])

                completed = len(result["execution_path"])
                progress = int((completed / total_nodes) * 100) if total_nodes > 0 else 100
                self.db.update(
                    "agent_tasks",
                    {"progress": progress, "updated_at": datetime.now().isoformat()},
                    where="id = ?",
                    where_params=(task_id,)
                )

            if result["node_results"]:
                result["success"] = True
                result["final_output"] = result["node_results"]

            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 100,
                    "output": result["node_results"],
                    "result": json.dumps(result["node_results"], ensure_ascii=False),
                    "completed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(task_id,)
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Flow execution failed: {flow_id} - {e}")

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

    # ==================== 私有方法 ====================

    def _flow_to_definition(self, flow: Flow) -> dict[str, Any]:
        """将 Flow 对象转换为 build_workflow_graph 所需的 dict 格式"""
        nodes = []
        for n in flow.nodes:
            nodes.append({
                "id": n.id,
                "name": n.name,
                "type": n.type.value,
                "config": n.config,
                "position": n.position,
            })

        edges = []
        for e in flow.edges:
            edges.append({
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "condition": e.condition,
            })

        return {"nodes": nodes, "edges": edges}

    def _row_to_flow(self, row: dict[str, Any]) -> Flow:
        """将数据库行转换为 Flow 对象"""
        flow_id = row["id"]

        # 获取节点
        node_rows = self.db.select_all(
            "flow_nodes",
            where="flow_id = ?",
            where_params=(flow_id,)
        )
        nodes = [self._row_to_flow_node(n) for n in node_rows]

        # 获取边
        edge_rows = self.db.select_all(
            "flow_edges",
            where="flow_id = ?",
            where_params=(flow_id,)
        )
        edges = [self._row_to_flow_edge(e) for e in edge_rows]

        return Flow(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            nodes=nodes,
            edges=edges,
            enabled=bool(row.get("enabled", 1)),
            metadata=self._parse_json(row.get("metadata", "{}")),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )

    def _row_to_flow_node(self, row: dict[str, Any]) -> FlowNode:
        """将数据库行转换为 FlowNode 对象"""
        return FlowNode(
            id=row["id"],
            name=row["name"],
            type=FlowNodeType(row.get("type", "start")),
            config=self._parse_json(row.get("config", "{}")),
            position=self._parse_json(row.get("position", '{"x": 0, "y": 0}')),
        )

    def _row_to_flow_edge(self, row: dict[str, Any]) -> FlowEdge:
        """将数据库行转换为 FlowEdge 对象"""
        return FlowEdge(
            id=row["id"],
            source=row["source"],
            target=row["target"],
            condition=self._parse_json(row.get("condition", "{}")),
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

    def _validate_and_parse_nodes(self, nodes_data: list) -> list[FlowNode]:
        """验证并解析节点列表"""
        nodes = []
        node_ids = set()

        for node_data in nodes_data:
            if not isinstance(node_data, dict):
                raise ValueError("节点数据必须是字典类型")

            node_id = node_data.get("id")
            if not node_id:
                raise ValueError("节点 ID 不能为空")

            if node_id in node_ids:
                raise ValueError(f"节点 ID '{node_id}' 重复")

            node_ids.add(node_id)

            # 验证节点类型
            node_type = node_data.get("type", "start")
            try:
                FlowNodeType(node_type)
            except ValueError:
                raise ValueError(f"无效的节点类型: {node_type}")

            node = FlowNode(
                id=node_id,
                name=node_data.get("name", node_id),
                type=FlowNodeType(node_type),
                config=node_data.get("config", {}),
                position=node_data.get("position", {"x": 0, "y": 0}),
            )
            nodes.append(node)

        return nodes

    def _validate_and_parse_edges(self, edges_data: list, nodes: list[FlowNode]) -> list[FlowEdge]:
        """验证并解析边列表"""
        edges = []
        edge_ids = set()
        node_ids = {n.id for n in nodes}

        for edge_data in edges_data:
            if not isinstance(edge_data, dict):
                raise ValueError("边数据必须是字典类型")

            edge_id = edge_data.get("id")
            if not edge_id:
                edge_id = f"edge_{uuid.uuid4().hex[:8]}"

            if edge_id in edge_ids:
                raise ValueError(f"边 ID '{edge_id}' 重复")

            edge_ids.add(edge_id)

            source = edge_data.get("source")
            target = edge_data.get("target")

            if not source:
                raise ValueError(f"边 '{edge_id}' 缺少源节点")
            if not target:
                raise ValueError(f"边 '{edge_id}' 缺少目标节点")

            if source not in node_ids:
                raise ValueError(f"边 '{edge_id}' 的源节点 '{source}' 不存在")
            if target not in node_ids:
                raise ValueError(f"边 '{edge_id}' 的目标节点 '{target}' 不存在")

            edge = FlowEdge(
                id=edge_id,
                source=source,
                target=target,
                condition=edge_data.get("condition", {}),
            )
            edges.append(edge)

        return edges

    def _has_cycle(self, flow: Flow) -> bool:
        """检查 Flow 是否有环"""
        # 构建邻接表
        graph = {n.id: [] for n in flow.nodes}
        for edge in flow.edges:
            if edge.source in graph:
                graph[edge.source].append(edge.target)

        # DFS 检测环
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node in flow.nodes:
            if node.id not in visited:
                if dfs(node.id):
                    return True

        return False

    def _validate_node_configs(self, flow: Flow) -> list[str]:
        """验证节点配置"""
        errors = []

        for node in flow.nodes:
            if node.type == FlowNodeType.CREW:
                crew_id = node.config.get("crew_id") or node.config.get("crewName")
                if not crew_id:
                    errors.append(f"Crew 节点 '{node.name}' 缺少 crew_id 配置")

            elif node.type == FlowNodeType.ROUTER:
                conditions = node.config.get("conditions") or node.config.get("branches") or []
                if not conditions:
                    errors.append(f"Router 节点 '{node.name}' 缺少条件配置")

            elif node.type == FlowNodeType.LISTEN:
                event_type = node.config.get("event_type") or node.config.get("eventType")
                if not event_type:
                    errors.append(f"Listen 节点 '{node.name}' 缺少 event_type 配置")
            elif node.type == FlowNodeType.SUB_FLOW:
                if not node.config.get("flow_id"):
                    errors.append(f"子流程节点 '{node.name}' 缺少 flow_id 配置")
            elif node.type == FlowNodeType.HITL:
                if not (node.config.get("template_id") or node.config.get("prompt")):
                    errors.append(f"HITL 节点 '{node.name}' 缺少 template_id 或 prompt 配置")

        return errors

    def _get_execution_order(self, flow: Flow) -> list[FlowNode]:
        """获取节点执行顺序（拓扑排序）"""
        # 构建邻接表和入度表
        node_map = {n.id: n for n in flow.nodes}
        graph = {n.id: [] for n in flow.nodes}
        in_degree = {n.id: 0 for n in flow.nodes}

        for edge in flow.edges:
            if edge.source in graph:
                graph[edge.source].append(edge.target)
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        # 找到所有入度为 0 的节点（开始节点）
        queue = [n_id for n_id, degree in in_degree.items() if degree == 0]
        queue.sort()  # 保证顺序一致

        # 拓扑排序
        result = []
        while queue:
            node_id = queue.pop(0)
            if node_id in node_map:
                result.append(node_map[node_id])

            for neighbor in graph.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    queue.sort()

        return result
