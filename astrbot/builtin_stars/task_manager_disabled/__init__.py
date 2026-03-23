# Task Manager Plugin - 异步任务管理插件
# 支持 DeerFlow 2.0 集成，实现复杂任务的异步执行、进度推送、断点恢复

from .star import TaskManagerStar
from .task_manager import TaskManager
from .task_analyzer import TaskAnalyzer
from .deerflow_integration import DeerFlowIntegration
from .progress_pusher import ProgressPusher
from .checkpoint_manager import CheckpointManager
from .models import Task, TaskStatus, TaskPlan, ExecutionMode

__all__ = [
    "TaskManagerStar",
    "TaskManager",
    "TaskAnalyzer",
    "DeerFlowIntegration",
    "ProgressPusher",
    "CheckpointManager",
    "Task",
    "TaskStatus",
    "TaskPlan",
    "ExecutionMode",
]