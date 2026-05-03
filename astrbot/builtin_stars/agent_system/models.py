"""
智能体管理模块 - 数据模型定义

使用 dataclass 定义所有数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ==================== 枚举类型 ====================

class ToolSource(Enum):
    """工具来源"""
    BUILTIN = "builtin"
    MCP = "mcp"
    CUSTOM = "custom"
    API_WRAPPER = "api_wrapper"


class SkillSource(Enum):
    """技能来源（CREWAI 已弃用，保留仅用于兼容历史数据）"""
    ASTRBOT = "astrbot"
    CLAUDECODE = "claudcode"
    CREWAI = "crewai"
    CUSTOM = "custom"


class DisclosureLevel(Enum):
    """技能披露级别"""
    METADATA = "metadata"
    INSTRUCTIONS = "instructions"
    RESOURCES = "resources"


class KnowledgeSource(Enum):
    """知识来源类型"""
    TEXT = "text"
    FILE = "file"
    URL = "url"
    DATABASE = "database"


class PlanningEffort(Enum):
    """规划努力程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProcessType(Enum):
    """Crew 执行流程类型"""
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


class FlowNodeType(Enum):
    """流程节点类型"""
    START = "start"
    LISTEN = "listen"
    ROUTER = "router"
    AND = "and"
    OR = "or"
    CREW = "crew"
    HUMAN = "human"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkScope(Enum):
    """Work 模式任务归属"""
    DAILY = "daily"
    PROJECT = "project"


class WorkTaskKind(Enum):
    """Work 模式任务类型"""
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"
    WORKFLOW = "workflow"


class RoundtableStatus(Enum):
    """圆桌会议状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 工具相关模型 ====================

@dataclass
class Tool:
    """工具定义"""
    id: str
    name: str
    description: str
    source: ToolSource
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    return_type: str | None = None
    version: str = "1.0.0"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source.value,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "version": self.version,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tool":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            source=ToolSource(data.get("source", "builtin")),
            parameters=data.get("parameters", {}),
            return_type=data.get("return_type"),
            version=data.get("version", "1.0.0"),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== 技能相关模型 ====================

@dataclass
class Skill:
    """技能定义"""
    id: str
    name: str
    description: str
    source: str = "custom"
    category: str = ""
    tools: list[str] = field(default_factory=list)  # Tool ID 列表
    workflow: dict[str, Any] = field(default_factory=dict)  # JSON 工作流定义
    disclosure_level: DisclosureLevel = DisclosureLevel.METADATA
    version: str = "1.0.0"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "category": self.category,
            "tools": self.tools,
            "workflow": self.workflow,
            "disclosure_level": self.disclosure_level.value,
            "version": self.version,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            source=data.get("source", data.get("category", "custom")),
            category=data.get("category", ""),
            tools=data.get("tools", []),
            workflow=data.get("workflow", {}),
            disclosure_level=DisclosureLevel(data.get("disclosure_level", "metadata")),
            version=data.get("version", "1.0.0"),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== 知识库相关模型 ====================

@dataclass
class Knowledge:
    """知识库定义"""
    id: str
    name: str
    description: str
    collection_name: str
    sources: list[dict[str, Any]] = field(default_factory=list)  # 知识来源列表
    embedder_config: dict[str, Any] = field(default_factory=dict)  # 嵌入模型配置
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "collection_name": self.collection_name,
            "sources": self.sources,
            "embedder_config": self.embedder_config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Knowledge":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            collection_name=data.get("collection_name", ""),
            sources=data.get("sources", []),
            embedder_config=data.get("embedder_config", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== 智能体相关模型 ====================

class AgentType(Enum):
    """智能体类型"""
    BUILTIN = "builtin"
    EXPERT = "expert"
    CUSTOM = "custom"


@dataclass
class Agent:
    """智能体定义"""
    id: str
    name: str
    role: str
    goal: str
    backstory: str
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    knowledge_id: str | None = None
    provider_id: str | None = None
    model_name: str | None = None
    llm_config: dict[str, Any] = field(default_factory=dict)
    memory_config: dict[str, Any] = field(default_factory=dict)
    planning: bool = False
    planning_effort: PlanningEffort = PlanningEffort.MEDIUM
    max_iter: int = 20
    max_rpm: int | None = None
    verbose: bool = False
    allow_delegation: bool = False
    enabled: bool = True
    agent_type: AgentType = AgentType.CUSTOM
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_builtin(self) -> bool:
        return self.agent_type in (AgentType.BUILTIN, AgentType.EXPERT)

    @property
    def is_expert(self) -> bool:
        return self.agent_type == AgentType.EXPERT

    @property
    def is_deletable(self) -> bool:
        return self.agent_type == AgentType.CUSTOM

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": self.tools,
            "skills": self.skills,
            "knowledge_id": self.knowledge_id,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "llm_config": self.llm_config,
            "memory_config": self.memory_config,
            "planning": self.planning,
            "planning_effort": self.planning_effort.value,
            "max_iter": self.max_iter,
            "max_rpm": self.max_rpm,
            "verbose": self.verbose,
            "allow_delegation": self.allow_delegation,
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "is_expert": self.is_expert,
            "agent_type": self.agent_type.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Agent":
        agent_type_val = data.get("agent_type", "custom")
        if agent_type_val == "custom" and data.get("is_builtin", False):
            agent_type_val = "builtin"
        return cls(
            id=data["id"],
            name=data["name"],
            role=data.get("role", ""),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            tools=data.get("tools", []),
            skills=data.get("skills", []),
            knowledge_id=data.get("knowledge_id"),
            provider_id=data.get("provider_id"),
            model_name=data.get("model_name"),
            llm_config=data.get("llm_config", {}),
            memory_config=data.get("memory_config", {}),
            planning=data.get("planning", False),
            planning_effort=PlanningEffort(data.get("planning_effort", "medium")),
            max_iter=data.get("max_iter", 20),
            max_rpm=data.get("max_rpm"),
            verbose=data.get("verbose", False),
            allow_delegation=data.get("allow_delegation", False),
            enabled=data.get("enabled", True),
            agent_type=AgentType(agent_type_val),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== Crew 相关模型 ====================

@dataclass
class CrewTask:
    """Crew 任务定义"""
    id: str
    name: str
    description: str
    expected_output: str
    agent_id: str | None = None
    tools: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)  # 依赖的任务 ID
    async_execution: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_id": self.agent_id,
            "tools": self.tools,
            "context": self.context,
            "async_execution": self.async_execution,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrewTask":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            expected_output=data.get("expected_output", ""),
            agent_id=data.get("agent_id"),
            tools=data.get("tools", []),
            context=data.get("context", []),
            async_execution=data.get("async_execution", False),
            config=data.get("config", {}),
        )


@dataclass
class Crew:
    """Crew 团队定义"""
    id: str
    name: str
    description: str
    agents: list[str] = field(default_factory=list)  # Agent ID 列表
    tasks: list[str] = field(default_factory=list)  # CrewTask ID 列表
    process: ProcessType = ProcessType.SEQUENTIAL
    manager_llm: str | None = None
    memory: bool = False
    cache: bool = True
    max_rpm: int | None = None
    share_agent_output: bool = True
    verbose: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agents": self.agents,
            "tasks": self.tasks,
            "process": self.process.value,
            "manager_llm": self.manager_llm,
            "memory": self.memory,
            "cache": self.cache,
            "max_rpm": self.max_rpm,
            "share_agent_output": self.share_agent_output,
            "verbose": self.verbose,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Crew":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            agents=data.get("agents", []),
            tasks=data.get("tasks", []),
            process=ProcessType(data.get("process", "sequential")),
            manager_llm=data.get("manager_llm"),
            memory=data.get("memory", False),
            cache=data.get("cache", True),
            max_rpm=data.get("max_rpm"),
            share_agent_output=data.get("share_agent_output", True),
            verbose=data.get("verbose", False),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== Flow 相关模型 ====================

@dataclass
class FlowNode:
    """流程节点"""
    id: str
    name: str
    type: FlowNodeType
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "config": self.config,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowNode":
        return cls(
            id=data["id"],
            name=data["name"],
            type=FlowNodeType(data.get("type", "start")),
            config=data.get("config", {}),
            position=data.get("position", {"x": 0, "y": 0}),
        )


@dataclass
class FlowEdge:
    """流程边"""
    id: str
    source: str  # 源节点 ID
    target: str  # 目标节点 ID
    condition: dict[str, Any] = field(default_factory=dict)  # 条件配置

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowEdge":
        return cls(
            id=data["id"],
            source=data["source"],
            target=data["target"],
            condition=data.get("condition", {}),
        )


@dataclass
class Flow:
    """流程定义"""
    id: str
    name: str
    description: str
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Flow":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            nodes=[FlowNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[FlowEdge.from_dict(e) for e in data.get("edges", [])],
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== 任务执行相关模型 ====================

@dataclass
class AgentTask:
    """智能体任务执行记录"""
    id: str
    name: str
    description: str
    crew_id: str | None = None
    flow_id: str | None = None
    meeting_id: str | None = None
    task_type: str = "crew"  # crew/flow/meeting
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    category: str = ""
    work_scope: str = ""
    work_project_id: str | None = None
    work_daily_dir_id: str | None = None
    work_task_kind: str = ""
    executor_config: dict[str, Any] = field(default_factory=dict)
    plan_config: dict[str, Any] = field(default_factory=dict)
    review_config: dict[str, Any] = field(default_factory=dict)
    deliverables: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    thread_id: str = ""
    pending_input: str = ""
    interaction_id: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "crew_id": self.crew_id,
            "flow_id": self.flow_id,
            "meeting_id": self.meeting_id,
            "task_type": self.task_type,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "input": self.input,
            "output": self.output,
            "result": self.result,
            "error": self.error,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "category": self.category,
            "work_scope": self.work_scope,
            "work_project_id": self.work_project_id,
            "work_daily_dir_id": self.work_daily_dir_id,
            "work_task_kind": self.work_task_kind,
            "executor_config": self.executor_config,
            "plan_config": self.plan_config,
            "review_config": self.review_config,
            "deliverables": self.deliverables,
            "steps": self.steps,
            "thread_id": self.thread_id,
            "pending_input": self.pending_input,
            "interaction_id": self.interaction_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTask":
        return cls(
            id=data["id"],
            crew_id=data.get("crew_id"),
            flow_id=data.get("flow_id"),
            meeting_id=data.get("meeting_id"),
            task_type=data.get("task_type", "crew"),
            name=data["name"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            progress=data.get("progress", 0),
            input=data.get("input", {}),
            output=data.get("output", {}),
            result=data.get("result"),
            error=data.get("error"),
            total_tokens=data.get("total_tokens", 0),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            category=data.get("category", ""),
            work_scope=data.get("work_scope", ""),
            work_project_id=data.get("work_project_id"),
            work_daily_dir_id=data.get("work_daily_dir_id"),
            work_task_kind=data.get("work_task_kind", ""),
            executor_config=data.get("executor_config", {}),
            plan_config=data.get("plan_config", {}),
            review_config=data.get("review_config", {}),
            deliverables=data.get("deliverables", []),
            steps=data.get("steps", []),
            thread_id=data.get("thread_id", ""),
            pending_input=data.get("pending_input", ""),
            interaction_id=data.get("interaction_id", ""),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


@dataclass
class SubTask:
    """子任务"""
    id: str
    parent_task_id: str
    agent_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    tokens: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_task_id": self.parent_task_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "input": self.input,
            "output": self.output,
            "result": self.result,
            "error": self.error,
            "tokens": self.tokens,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubTask":
        return cls(
            id=data["id"],
            parent_task_id=data["parent_task_id"],
            agent_id=data["agent_id"],
            name=data["name"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            progress=data.get("progress", 0),
            input=data.get("input", {}),
            output=data.get("output", {}),
            result=data.get("result"),
            error=data.get("error"),
            tokens=data.get("tokens", 0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class ExecutionLog:
    """执行日志"""
    id: str
    task_id: str
    sub_task_id: str | None = None
    agent_id: str | None = None
    level: str = "info"  # debug, info, warning, error
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "sub_task_id": self.sub_task_id,
            "agent_id": self.agent_id,
            "level": self.level,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionLog":
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            sub_task_id=data.get("sub_task_id"),
            agent_id=data.get("agent_id"),
            level=data.get("level", "info"),
            message=data.get("message", ""),
            data=data.get("data", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class TokenStats:
    """Token 统计"""
    id: str
    task_id: str
    agent_id: str | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenStats":
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            agent_id=data.get("agent_id"),
            model_name=data.get("model_name"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class WorkProject:
    """Work 模式项目"""
    id: str
    name: str
    directory: str
    goal: str = ""
    rules: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "directory": self.directory,
            "goal": self.goal,
            "rules": self.rules,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class WorkDailyDir:
    """Work 模式日常任务目录"""
    id: str
    name: str
    directory: str
    default_rules: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "directory": self.directory,
            "default_rules": self.default_rules,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class WorkArtifact:
    """Work 模式任务交付物"""
    id: str
    task_id: str
    title: str
    artifact_type: str = "markdown"
    content: str = ""
    file_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "artifact_type": self.artifact_type,
            "content": self.content,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


# ==================== 圆桌会议相关模型 ====================

@dataclass
class Roundtable:
    """圆桌会议定义"""
    id: str
    name: str
    topic: str
    deliverable: str = ""
    mode: str = "free"  # hosted 或 free（兼容旧数据）
    meeting_type: str = "standard"  # standard/brainstorm/parliament/convergence/six_hat/fishbone/swot/okr/retrospective/interview
    host_agent_id: str | None = None
    participants: list[str] = field(default_factory=list)  # Agent ID 列表
    rounds: int = 3
    config: dict[str, Any] = field(default_factory=dict)
    status: RoundtableStatus = RoundtableStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    discussion_records: list[dict[str, Any]] = field(default_factory=list)  # 实时讨论记录
    current_round: int = 0  # 当前执行轮次
    current_speaker: str = ""  # 当前发言者
    stage: str = "pending"  # 当前阶段: pending/preparing/running/completed/failed
    streaming_content: str = ""  # 当前流式输出的内容
    materials: dict[str, Any] = field(default_factory=dict)  # 会议材料 {type: url/file/manual, content: ...}
    export_format: str = "markdown"  # markdown / word
    preparation_records: list[dict[str, Any]] = field(default_factory=list)  # 准备阶段记录
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "topic": self.topic,
            "deliverable": self.deliverable,
            "mode": self.mode,
            "meeting_type": self.meeting_type,
            "host_agent_id": self.host_agent_id,
            "participants": self.participants,
            "rounds": self.rounds,
            "config": self.config,
            "status": self.status.value,
            "result": self.result,
            "discussion_records": self.discussion_records,
            "current_round": self.current_round,
            "current_speaker": self.current_speaker,
            "stage": self.stage,
            "streaming_content": self.streaming_content,
            "materials": self.materials,
            "export_format": self.export_format,
            "preparation_records": self.preparation_records,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Roundtable":
        # 兼容旧数据：mode 映射到 meeting_type
        mode = data.get("mode", "free")
        meeting_type = data.get("meeting_type", "")
        if not meeting_type:
            # 旧数据迁移：hosted -> standard, free -> standard
            meeting_type = "standard"
        return cls(
            id=data["id"],
            name=data["name"],
            topic=data.get("topic", ""),
            deliverable=data.get("deliverable", ""),
            mode=mode,
            meeting_type=meeting_type,
            host_agent_id=data.get("host_agent_id"),
            participants=data.get("participants", []),
            rounds=data.get("rounds", 3),
            config=data.get("config", {}),
            status=RoundtableStatus(data.get("status", "pending")),
            result=data.get("result", {}),
            discussion_records=data.get("discussion_records", []),
            current_round=data.get("current_round", 0),
            current_speaker=data.get("current_speaker", ""),
            stage=data.get("stage", "pending"),
            streaming_content=data.get("streaming_content", ""),
            materials=data.get("materials", {}),
            export_format=data.get("export_format", "markdown"),
            preparation_records=data.get("preparation_records", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )
