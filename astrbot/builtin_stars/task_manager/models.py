from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    WAITING_SUBAGENT = "waiting_subagent"
    CHECKPOINT = "checkpoint"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionMode(Enum):
    DIRECT = "direct"
    STREAM = "stream"
    SUBAGENT = "subagent"
    STAGE = "stage"
    STEP = "step"
    HYBRID = "hybrid"


@dataclass
class TaskStage:
    name: str
    description: str
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None


@dataclass
class TaskPlan:
    task_type: str
    stages: list[TaskStage]
    estimated_steps: int = 5
    complexity: str = "medium"
    allow_subagent: bool = True
    max_concurrent_subagents: int = 3


@dataclass
class TaskProgress:
    task_id: str
    status: TaskStatus
    stage: str
    stage_progress: int
    total_progress: int
    message: str
    completed_items: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Checkpoint:
    task_id: str
    step: int
    state: dict
    subagent_results: list[dict] = field(default_factory=list)
    pending_tools: list[str] = field(default_factory=list)
    stage_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TodoItem:
    """DeerFlow Todo 项"""
    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TodoItem":
        return cls(
            id=data["id"],
            content=data["content"],
            status=TodoStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


@dataclass
class DeerFlowTask:
    """DeerFlow 任务"""
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    thread_id: str = ""
    model_name: str | None = None
    is_plan_mode: bool = True
    todos: list[TodoItem] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "thread_id": self.thread_id,
            "model_name": self.model_name,
            "is_plan_mode": self.is_plan_mode,
            "todos": [t.to_dict() for t in self.todos],
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeerFlowTask":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            thread_id=data.get("thread_id", ""),
            model_name=data.get("model_name"),
            is_plan_mode=data.get("is_plan_mode", True),
            todos=[TodoItem.from_dict(t) for t in data.get("todos", [])],
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class LLMProviderConfig:
    """LLM 提供者配置"""
    name: str
    provider_type: str
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] = field(default_factory=list)
    default_model: str | None = None
    is_enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "api_key": "***" if self.api_key else None,
            "base_url": self.base_url,
            "models": self.models,
            "default_model": self.default_model,
            "is_enabled": self.is_enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMProviderConfig":
        return cls(
            name=data.get("name", ""),
            provider_type=data.get("provider_type", ""),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            models=data.get("models", []),
            default_model=data.get("default_model"),
            is_enabled=data.get("is_enabled", True),
        )


@dataclass
class DeerFlowLLMConfig:
    """DeerFlow LLM 配置"""
    provider: str = ""
    model: str = ""
    api_key: str | None = None
    base_url: str | None = None
    thinking_enabled: bool = True
    is_plan_mode: bool = True
    subagent_enabled: bool = False
    subagent_model: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": "***" if self.api_key else None,
            "base_url": self.base_url,
            "thinking_enabled": self.thinking_enabled,
            "is_plan_mode": self.is_plan_mode,
            "subagent_enabled": self.subagent_enabled,
            "subagent_model": self.subagent_model,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeerFlowLLMConfig":
        return cls(
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            thinking_enabled=data.get("thinking_enabled", True),
            is_plan_mode=data.get("is_plan_mode", True),
            subagent_enabled=data.get("subagent_enabled", False),
            subagent_model=data.get("subagent_model"),
        )


@dataclass
class Task:
    id: str
    user_id: str
    platform: str
    query: str
    task_type: str
    status: TaskStatus
    execution_mode: ExecutionMode = ExecutionMode.STREAM
    plan: TaskPlan | None = None
    thread_id: str = ""
    checkpoint: Checkpoint | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform,
            "query": self.query,
            "task_type": self.task_type,
            "status": self.status.value,
            "execution_mode": self.execution_mode.value,
            "plan": {
                "task_type": self.plan.task_type if self.plan else None,
                "stages": [
                    {"name": s.name, "description": s.description, "status": s.status}
                    for s in self.plan.stages
                ] if self.plan else None,
            } if self.plan else None,
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }
