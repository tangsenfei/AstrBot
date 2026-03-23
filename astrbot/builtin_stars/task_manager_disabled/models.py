from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_SUBAGENT = "waiting_subagent"
    CHECKPOINT = "checkpoint"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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