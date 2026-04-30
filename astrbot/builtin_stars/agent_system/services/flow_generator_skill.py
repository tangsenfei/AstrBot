"""
智能体管理模块 - 流程生成技能

提供流程模板管理和自然语言生成流程的能力，可被智能体加载使用
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from astrbot.core import logger

# 布局常量
Y_SPACING = 120
X_SPACING = 220
X_CENTER = 400


class FlowGeneratorSkill:
    """流程生成技能

    根据自然语言描述自动生成流程定义，或从预设模板创建流程。
    生成的流程格式与 FlowCanvas.vue 兼容。
    """

    SKILL_ID = "flow_generator"
    SKILL_NAME = "流程生成"
    SKILL_DESCRIPTION = "根据自然语言描述或模板快速生成流程定义"
    SKILL_CATEGORY = "flow_generation"

    def __init__(self):
        self._templates = self._build_templates()

    # ==================== 公共方法 ====================

    def generate_flow(self, description: str) -> dict[str, Any]:
        """根据自然语言描述生成流程定义

        解析描述中的关键信息，自动选择合适的模板并填充配置。

        Args:
            description: 自然语言描述

        Returns:
            完整的流程定义，包含 nodes 和 edges
        """
        if not description or not description.strip():
            raise ValueError("描述不能为空")

        # 解析描述中的关键信息
        keywords = self._parse_description(description)

        # 选择最匹配的模板
        template_id = self._select_template(keywords)

        # 根据描述中的信息定制模板
        customizations = self._build_customizations(keywords, description)

        return self.create_flow_from_template(template_id, customizations)

    def get_flow_templates(self) -> list[dict[str, Any]]:
        """获取预设的流程模板列表

        Returns:
            模板列表，每个模板包含 id、name、description、preview
        """
        result = []
        for template in self._templates:
            result.append({
                "id": template["id"],
                "name": template["name"],
                "description": template["description"],
                "preview": {
                    "node_count": len(template["nodes"]),
                    "edge_count": len(template["edges"]),
                    "node_types": list({n["type"] for n in template["nodes"]}),
                },
            })
        return result

    def create_flow_from_template(
        self, template_id: str, customizations: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """从模板创建流程

        Args:
            template_id: 模板 ID
            customizations: 定制参数，可覆盖节点标签、配置等

        Returns:
            完整的流程定义，包含 nodes 和 edges

        Raises:
            ValueError: 模板不存在
        """
        template = self._find_template(template_id)
        if not template:
            raise ValueError(f"模板 '{template_id}' 不存在")

        customizations = customizations or {}

        # 深拷贝模板节点和边
        nodes = [self._clone_node(n) for n in template["nodes"]]
        edges = [self._clone_edge(e) for e in template["edges"]]

        # 应用定制：覆盖节点标签
        label_overrides = customizations.get("label_overrides", {})
        for node in nodes:
            if node["id"] in label_overrides:
                node["data"]["label"] = label_overrides[node["id"]]

        # 应用定制：覆盖节点配置
        config_overrides = customizations.get("config_overrides", {})
        for node in nodes:
            if node["id"] in config_overrides:
                node["data"]["config"].update(config_overrides[node["id"]])

        # 重新生成节点 ID 避免冲突
        id_mapping = {}
        for node in nodes:
            old_id = node["id"]
            new_id = f"node-{node['type']}-{uuid.uuid4().hex[:6]}"
            id_mapping[old_id] = new_id
            node["id"] = new_id

        # 更新边中的节点引用
        for edge in edges:
            edge["source"] = id_mapping.get(edge["source"], edge["source"])
            edge["target"] = id_mapping.get(edge["target"], edge["target"])
            edge["id"] = f"edge-{uuid.uuid4().hex[:6]}"

        # 应用定制：流程名称和描述
        flow_name = customizations.get("name", template["name"])
        flow_description = customizations.get(
            "description", template["description"]
        )

        return {
            "name": flow_name,
            "description": flow_description,
            "nodes": nodes,
            "edges": edges,
        }

    # ==================== 模板定义 ====================

    def _build_templates(self) -> list[dict[str, Any]]:
        """构建预设模板列表"""
        return [
            self._template_sequential_crew(),
            self._template_parallel_crews(),
            self._template_conditional_routing(),
            self._template_human_approval(),
            self._template_meeting_flow(),
        ]

    def _template_sequential_crew(self) -> dict[str, Any]:
        """顺序团队执行流程：开始→监听→团队→结束"""
        return {
            "id": "sequential_crew",
            "name": "顺序团队执行",
            "description": "按顺序执行团队任务：开始→监听→团队→结束",
            "nodes": [
                self._make_node("node-start", "start", "开始", X_CENTER, 0),
                self._make_node("node-listen", "listen", "监听", X_CENTER, Y_SPACING),
                self._make_node("node-crew", "crew", "团队", X_CENTER, Y_SPACING * 2, {"crew_id": ""}),
            ],
            "edges": [
                self._make_edge("edge-1", "node-start", "node-listen"),
                self._make_edge("edge-2", "node-listen", "node-crew"),
            ],
        }

    def _template_parallel_crews(self) -> dict[str, Any]:
        """并行团队执行流程：开始→AND→团队1/团队2→AND→结束"""
        x_left = X_CENTER - X_SPACING // 2
        x_right = X_CENTER + X_SPACING // 2
        return {
            "id": "parallel_crews",
            "name": "并行团队执行",
            "description": "并行执行多个团队任务：开始→AND→团队1/团队2→AND→结束",
            "nodes": [
                self._make_node("node-start", "start", "开始", X_CENTER, 0),
                self._make_node("node-and-split", "and", "并行(AND)", X_CENTER, Y_SPACING),
                self._make_node("node-crew-1", "crew", "团队1", x_left, Y_SPACING * 2, {"crew_id": ""}),
                self._make_node("node-crew-2", "crew", "团队2", x_right, Y_SPACING * 2, {"crew_id": ""}),
                self._make_node("node-and-merge", "and", "合并(AND)", X_CENTER, Y_SPACING * 3),
            ],
            "edges": [
                self._make_edge("edge-1", "node-start", "node-and-split"),
                self._make_edge("edge-2", "node-and-split", "node-crew-1"),
                self._make_edge("edge-3", "node-and-split", "node-crew-2"),
                self._make_edge("edge-4", "node-crew-1", "node-and-merge"),
                self._make_edge("edge-5", "node-crew-2", "node-and-merge"),
            ],
        }

    def _template_conditional_routing(self) -> dict[str, Any]:
        """条件路由流程：开始→监听→路由→分支1/分支2→结束"""
        x_left = X_CENTER - X_SPACING // 2
        x_right = X_CENTER + X_SPACING // 2
        return {
            "id": "conditional_routing",
            "name": "条件路由",
            "description": "根据条件选择不同分支执行：开始→监听→路由→分支1/分支2→结束",
            "nodes": [
                self._make_node("node-start", "start", "开始", X_CENTER, 0),
                self._make_node("node-listen", "listen", "监听", X_CENTER, Y_SPACING),
                self._make_node("node-router", "router", "路由", X_CENTER, Y_SPACING * 2, {
                    "conditions": [
                        {"field": "", "operator": "==", "value": "", "target": "node-crew-1", "label": "条件1"},
                        {"field": "", "operator": "==", "value": "", "target": "node-crew-2", "label": "条件2"},
                    ]
                }),
                self._make_node("node-crew-1", "crew", "分支1", x_left, Y_SPACING * 3, {"crew_id": ""}),
                self._make_node("node-crew-2", "crew", "分支2", x_right, Y_SPACING * 3, {"crew_id": ""}),
            ],
            "edges": [
                self._make_edge("edge-1", "node-start", "node-listen"),
                self._make_edge("edge-2", "node-listen", "node-router"),
                self._make_edge("edge-3", "node-router", "node-crew-1", {"label": "条件1"}),
                self._make_edge("edge-4", "node-router", "node-crew-2", {"label": "条件2"}),
            ],
        }

    def _template_human_approval(self) -> dict[str, Any]:
        """人工审批流程：开始→团队→人工→路由→通过/拒绝→结束"""
        x_left = X_CENTER - X_SPACING // 2
        x_right = X_CENTER + X_SPACING // 2
        return {
            "id": "human_approval",
            "name": "人工审批",
            "description": "需要人工审批的流程：开始→团队→人工→路由→通过/拒绝→结束",
            "nodes": [
                self._make_node("node-start", "start", "开始", X_CENTER, 0),
                self._make_node("node-crew", "crew", "团队", X_CENTER, Y_SPACING, {"crew_id": ""}),
                self._make_node("node-human", "human", "人工审批", X_CENTER, Y_SPACING * 2, {
                    "message": "请审核以下内容"
                }),
                self._make_node("node-router", "router", "审批结果", X_CENTER, Y_SPACING * 3, {
                    "conditions": [
                        {"field": "approved", "operator": "==", "value": True, "target": "node-crew-approve", "label": "通过"},
                        {"field": "approved", "operator": "==", "value": False, "target": "node-crew-reject", "label": "拒绝"},
                    ]
                }),
                self._make_node("node-crew-approve", "crew", "通过", x_left, Y_SPACING * 4, {"crew_id": ""}),
                self._make_node("node-crew-reject", "crew", "拒绝", x_right, Y_SPACING * 4, {"crew_id": ""}),
            ],
            "edges": [
                self._make_edge("edge-1", "node-start", "node-crew"),
                self._make_edge("edge-2", "node-crew", "node-human"),
                self._make_edge("edge-3", "node-human", "node-router"),
                self._make_edge("edge-4", "node-router", "node-crew-approve", {"label": "通过"}),
                self._make_edge("edge-5", "node-router", "node-crew-reject", {"label": "拒绝"}),
            ],
        }

    def _template_meeting_flow(self) -> dict[str, Any]:
        """会议流程：开始→监听→团队→人工→结束"""
        return {
            "id": "meeting_flow",
            "name": "会议流程",
            "description": "会议讨论流程：开始→监听→团队→人工→结束",
            "nodes": [
                self._make_node("node-start", "start", "开始", X_CENTER, 0),
                self._make_node("node-listen", "listen", "监听", X_CENTER, Y_SPACING),
                self._make_node("node-crew", "crew", "团队", X_CENTER, Y_SPACING * 2, {"crew_id": ""}),
                self._make_node("node-human", "human", "人工", X_CENTER, Y_SPACING * 3, {
                    "message": "请确认会议结论"
                }),
            ],
            "edges": [
                self._make_edge("edge-1", "node-start", "node-listen"),
                self._make_edge("edge-2", "node-listen", "node-crew"),
                self._make_edge("edge-3", "node-crew", "node-human"),
            ],
        }

    # ==================== 描述解析 ====================

    def _parse_description(self, description: str) -> dict[str, Any]:
        """解析自然语言描述中的关键信息

        Args:
            description: 自然语言描述

        Returns:
            解析出的关键信息字典
        """
        keywords: dict[str, Any] = {
            "has_crew": False,
            "crew_count": 0,
            "has_listen": False,
            "has_router": False,
            "has_human": False,
            "has_parallel": False,
            "has_approval": False,
            "has_meeting": False,
            "conditions": [],
        }

        desc_lower = description.lower()

        # 检测团队相关
        crew_patterns = [
            r"团队", r"crew", r"小组", r"执行.*任务",
            r"处理", r"分析", r"生成", r"编写", r"审核",
        ]
        for pattern in crew_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_crew"] = True
                break

        # 统计团队数量
        crew_count_patterns = [
            (r"两个团队|2个团队|两个小组|2个小组|两个.*crew", 2),
            (r"三个团队|3个团队|三个小组|3个小组", 3),
            (r"多个团队|多个小组|并行.*团队", 2),
        ]
        for pattern, count in crew_count_patterns:
            if re.search(pattern, desc_lower):
                keywords["crew_count"] = count
                break

        if keywords["crew_count"] == 0 and keywords["has_crew"]:
            keywords["crew_count"] = 1

        # 检测监听
        listen_patterns = [r"监听", r"listen", r"触发", r"事件", r"消息"]
        for pattern in listen_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_listen"] = True
                break

        # 检测路由/条件
        router_patterns = [
            r"条件", r"路由", r"router", r"分支", r"判断",
            r"根据.*选择", r"如果.*则", r"根据.*决定",
        ]
        for pattern in router_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_router"] = True
                break

        # 检测人工
        human_patterns = [
            r"人工", r"human", r"审批", r"审核", r"确认",
            r"人工.*介入", r"需要.*确认", r"等待.*审批",
        ]
        for pattern in human_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_human"] = True
                break

        # 检测并行
        parallel_patterns = [
            r"并行", r"parallel", r"同时", r"并发", r"一起",
        ]
        for pattern in parallel_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_parallel"] = True
                break

        # 检测审批
        approval_patterns = [
            r"审批", r"approval", r"批准", r"通过.*拒绝",
            r"同意.*否决", r"审核.*通过",
        ]
        for pattern in approval_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_approval"] = True
                break

        # 检测会议
        meeting_patterns = [
            r"会议", r"meeting", r"讨论", r"圆桌", r"协商",
        ]
        for pattern in meeting_patterns:
            if re.search(pattern, desc_lower):
                keywords["has_meeting"] = True
                break

        return keywords

    def _select_template(self, keywords: dict[str, Any]) -> str:
        """根据解析的关键信息选择最匹配的模板

        Args:
            keywords: 解析出的关键信息

        Returns:
            模板 ID
        """
        # 优先级从高到低匹配
        if keywords["has_approval"]:
            return "human_approval"

        if keywords["has_meeting"] and keywords["has_human"]:
            return "meeting_flow"

        if keywords["has_parallel"] or keywords["crew_count"] >= 2:
            return "parallel_crews"

        if keywords["has_router"]:
            return "conditional_routing"

        if keywords["has_meeting"]:
            return "meeting_flow"

        # 默认使用顺序执行
        return "sequential_crew"

    def _build_customizations(
        self, keywords: dict[str, Any], description: str
    ) -> dict[str, Any]:
        """根据解析信息构建定制参数

        Args:
            keywords: 解析出的关键信息
            description: 原始描述

        Returns:
            定制参数字典
        """
        customizations: dict[str, Any] = {
            "name": self._extract_flow_name(description),
            "description": description,
            "label_overrides": {},
            "config_overrides": {},
        }

        # 如果有监听事件，配置监听节点
        if keywords["has_listen"]:
            event_type = self._extract_event_type(description)
            if event_type:
                customizations["config_overrides"]["node-listen"] = {
                    "event_type": event_type
                }

        return customizations

    def _extract_flow_name(self, description: str) -> str:
        """从描述中提取流程名称

        Args:
            description: 描述文本

        Returns:
            流程名称
        """
        # 尝试匹配引号中的名称
        match = re.search(r"[\"\"'](.+?)[\"\"']", description)
        if match:
            return match.group(1)

        # 截取描述前 20 字符作为名称
        name = description.strip()[:20]
        if len(description.strip()) > 20:
            name += "..."
        return name

    def _extract_event_type(self, description: str) -> str:
        """从描述中提取事件类型

        Args:
            description: 描述文本

        Returns:
            事件类型
        """
        event_map = {
            r"消息": "message",
            r"指令": "command",
            r"定时": "timer",
            r"文件": "file",
            r"webhook": "webhook",
        }
        for pattern, event_type in event_map.items():
            if re.search(pattern, description.lower()):
                return event_type
        return "message"

    # ==================== 辅助方法 ====================

    def _make_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        x: int,
        y: int,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建节点定义

        Args:
            node_id: 节点 ID
            node_type: 节点类型
            label: 节点标签
            x: X 坐标
            y: Y 坐标
            config: 节点配置

        Returns:
            节点字典
        """
        return {
            "id": node_id,
            "type": node_type,
            "position": {"x": x, "y": y},
            "data": {
                "label": label,
                "config": config or {},
            },
        }

    def _make_edge(
        self,
        edge_id: str,
        source: str,
        target: str,
        condition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建边定义

        Args:
            edge_id: 边 ID
            source: 源节点 ID
            target: 目标节点 ID
            condition: 条件配置

        Returns:
            边字典
        """
        return {
            "id": edge_id,
            "source": source,
            "target": target,
            "condition": condition or {},
        }

    def _clone_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """深拷贝节点"""
        return {
            "id": node["id"],
            "type": node["type"],
            "position": dict(node["position"]),
            "data": {
                "label": node["data"]["label"],
                "config": dict(node["data"].get("config", {})),
            },
        }

    def _clone_edge(self, edge: dict[str, Any]) -> dict[str, Any]:
        """深拷贝边"""
        return {
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            "condition": dict(edge.get("condition", {})),
        }

    def _find_template(self, template_id: str) -> dict[str, Any] | None:
        """查找模板

        Args:
            template_id: 模板 ID

        Returns:
            模板字典，不存在则返回 None
        """
        for template in self._templates:
            if template["id"] == template_id:
                return template
        return None

    def to_skill_dict(self) -> dict[str, Any]:
        """将流程生成技能转换为 Skill 模型可用的字典

        Returns:
            技能数据字典
        """
        return {
            "id": self.SKILL_ID,
            "name": self.SKILL_NAME,
            "description": self.SKILL_DESCRIPTION,
            "source": "custom",
            "category": self.SKILL_CATEGORY,
            "tools": [],
            "workflow": {
                "type": "flow_generator",
                "templates": [t["id"] for t in self._templates],
            },
            "disclosure_level": "instructions",
            "version": "1.0.0",
            "enabled": True,
            "metadata": {},
        }
