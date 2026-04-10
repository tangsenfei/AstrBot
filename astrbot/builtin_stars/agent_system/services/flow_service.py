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

if TYPE_CHECKING:
    from ..database import Database
    from astrbot.core.star.context import Context

from ..models import (
    Flow, FlowNode, FlowEdge, FlowNodeType,
    AgentTask, TaskStatus
)


class FlowService:
    """Flow 管理服务"""

    def __init__(self, db: "Database", context: "Context | None" = None):
        self.db = db
        self._context = context

    @property
    def context(self) -> "Context | None":
        """获取 Context 实例"""
        return self._context

    def get_flows(self, enabled_only: bool = False) -> list[Flow]:
        """获取 Flow 列表

        Args:
            enabled_only: 是否只返回启用的 Flow

        Returns:
            Flow 列表
        """
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

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = ["name", "description", "enabled", "metadata"]

        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

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
        source_nodes = {e.source for e in flow.edges}
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

        # 检查是否有环
        if not self._has_cycle(flow):
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
                crew_id = node.config.get("crew_id")
                if crew_id:
                    crew = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
                    if not crew:
                        result["warnings"].append(f"节点 '{node.name}' 引用的 Crew '{crew_id}' 不存在")

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

    async def execute_flow(self, flow_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """执行 Flow

        Args:
            flow_id: Flow ID
            input_data: 输入数据

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

        # 验证 Flow
        validation = self.validate_flow(flow_id)
        if not validation["success"]:
            raise ValueError(f"Flow 验证失败: {'; '.join(validation['errors'])}")

        # 创建 AgentTask 记录
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
            # 获取执行顺序
            execution_order = self._get_execution_order(flow)
            total_nodes = len(execution_order)
            current_context = input_data.copy()

            for idx, node in enumerate(execution_order):
                # 更新进度
                progress = int((idx / total_nodes) * 100) if total_nodes > 0 else 100
                self.db.update(
                    "agent_tasks",
                    {"progress": progress, "updated_at": datetime.now().isoformat()},
                    where="id = ?",
                    where_params=(task_id,)
                )

                # 执行节点
                node_result = await self._execute_node(flow, node, current_context)

                result["execution_path"].append(node.id)
                result["node_results"][node.id] = node_result

                # 更新上下文
                if node_result.get("success"):
                    current_context = node_result.get("output", {})
                else:
                    raise Exception(f"节点 '{node.name}' 执行失败: {node_result.get('error')}")

            result["success"] = True
            result["final_output"] = current_context

            # 更新任务状态
            self.db.update(
                "agent_tasks",
                {
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 100,
                    "output": current_context,
                    "result": json.dumps(current_context, ensure_ascii=False),
                    "completed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                where="id = ?",
                where_params=(task_id,)
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Flow execution failed: {flow_id} - {e}")

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

    # ==================== 私有方法 ====================

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
                crew_id = node.config.get("crew_id")
                if not crew_id:
                    errors.append(f"Crew 节点 '{node.name}' 缺少 crew_id 配置")

            elif node.type == FlowNodeType.ROUTER:
                conditions = node.config.get("conditions", [])
                if not conditions:
                    errors.append(f"Router 节点 '{node.name}' 缺少条件配置")

            elif node.type == FlowNodeType.LISTEN:
                event_type = node.config.get("event_type")
                if not event_type:
                    errors.append(f"Listen 节点 '{node.name}' 缺少 event_type 配置")

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

    async def _execute_node(
        self,
        flow: Flow,
        node: FlowNode,
        input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """执行单个节点

        Args:
            flow: Flow 对象
            node: 节点对象
            input_data: 输入数据

        Returns:
            节点执行结果
        """
        result = {
            "node_id": node.id,
            "node_name": node.name,
            "node_type": node.type.value,
            "success": False,
            "input": input_data,
            "output": None,
            "error": None,
        }

        try:
            if node.type == FlowNodeType.START:
                # 开始节点直接传递输入
                result["success"] = True
                result["output"] = input_data

            elif node.type == FlowNodeType.LISTEN:
                # 监听节点等待事件
                result["success"] = True
                result["output"] = {
                    "event_type": node.config.get("event_type"),
                    "data": input_data,
                }

            elif node.type == FlowNodeType.ROUTER:
                # 路由节点根据条件选择分支
                conditions = node.config.get("conditions", [])
                selected_branch = None

                for condition in conditions:
                    if self._evaluate_condition(condition, input_data):
                        selected_branch = condition.get("target")
                        break

                result["success"] = True
                result["output"] = {
                    "selected_branch": selected_branch,
                    "data": input_data,
                }

            elif node.type == FlowNodeType.AND:
                # AND 合并节点：等待所有输入完成
                result["success"] = True
                result["output"] = {
                    "merged": True,
                    "data": input_data,
                }

            elif node.type == FlowNodeType.OR:
                # OR 合并节点：任一输入完成即可
                result["success"] = True
                result["output"] = {
                    "merged": True,
                    "data": input_data,
                }

            elif node.type == FlowNodeType.CREW:
                # Crew 执行节点
                crew_id = node.config.get("crew_id")
                if not crew_id:
                    raise ValueError(f"Crew 节点 '{node.name}' 缺少 crew_id 配置")

                # 获取 Crew
                crew_row = self.db.select_one("crews", where="id = ?", where_params=(crew_id,))
                if not crew_row:
                    raise ValueError(f"Crew '{crew_id}' 不存在")

                # 执行 Crew（简化版，实际应调用 CrewService）
                result["success"] = True
                result["output"] = {
                    "crew_id": crew_id,
                    "result": f"[模拟] Crew {crew_id} 执行完成",
                    "input": input_data,
                }

            elif node.type == FlowNodeType.HUMAN:
                # 人工反馈节点
                result["success"] = True
                result["output"] = {
                    "waiting_for_feedback": True,
                    "message": node.config.get("message", "等待人工反馈"),
                    "data": input_data,
                }

            else:
                raise ValueError(f"未知的节点类型: {node.type}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Node execution failed: {node.id} - {e}")

        return result

    def _evaluate_condition(self, condition: dict[str, Any], data: dict[str, Any]) -> bool:
        """评估条件表达式

        Args:
            condition: 条件配置
            data: 输入数据

        Returns:
            条件是否满足
        """
        # 简化的条件评估逻辑
        # 支持简单的字段比较
        field = condition.get("field")
        operator = condition.get("operator", "==")
        value = condition.get("value")

        if not field:
            return True

        actual_value = data.get(field)

        if operator == "==":
            return actual_value == value
        elif operator == "!=":
            return actual_value != value
        elif operator == ">":
            return actual_value > value
        elif operator == ">=":
            return actual_value >= value
        elif operator == "<":
            return actual_value < value
        elif operator == "<=":
            return actual_value <= value
        elif operator == "contains":
            return value in actual_value if actual_value else False
        elif operator == "in":
            return actual_value in value if value else False

        return True
