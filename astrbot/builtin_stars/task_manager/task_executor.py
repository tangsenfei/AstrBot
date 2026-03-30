"""
Task Executor - 任务执行器

负责任务的创建、执行、追踪和管理
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from .config_manager import ConfigManager
    from .deerflow_client import DeerFlowClient


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TodoStatus(str, Enum):
    """Todo 状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TodoItem:
    """Todo 项"""
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
class Task:
    """任务"""
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
    def from_dict(cls, data: dict[str, Any]) -> "Task":
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


class TaskExecutor:
    """任务执行器
    
    负责任务的创建、执行、追踪和管理
    """
    
    def __init__(
        self,
        deerflow_client: "DeerFlowClient",
        config_manager: "ConfigManager",
        data_dir: Path | None = None,
    ) -> None:
        self.deerflow_client = deerflow_client
        self.config_manager = config_manager
        self._tasks: dict[str, Task] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._data_dir = data_dir
        self._tasks_file: Path | None = None
        if data_dir:
            self._tasks_file = data_dir / "tasks.json"
            self._load_tasks()
    
    def _load_tasks(self) -> None:
        """从文件加载任务"""
        if not self._tasks_file or not self._tasks_file.exists():
            return
        
        try:
            with open(self._tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for task_data in data.get("tasks", []):
                try:
                    task = Task.from_dict(task_data)
                    self._tasks[task.id] = task
                except Exception as e:
                    logger.warning(f"Failed to load task: {e}")
            
            logger.info(f"Loaded {len(self._tasks)} tasks from {self._tasks_file}")
        except Exception as e:
            logger.error(f"Failed to load tasks file: {e}")
    
    def _save_tasks(self) -> None:
        """保存任务到文件"""
        if not self._tasks_file:
            return
        
        try:
            self._tasks_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "tasks": [task.to_dict() for task in self._tasks.values()],
            }
            
            with open(self._tasks_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved {len(self._tasks)} tasks to {self._tasks_file}")
        except Exception as e:
            logger.error(f"Failed to save tasks file: {e}")
    
    def create_task(
        self,
        title: str,
        description: str,
        model_name: str | None = None,
        is_plan_mode: bool = True,
    ) -> Task:
        """创建新任务
        
        Args:
            title: 任务标题
            description: 任务描述
            model_name: 使用的模型名称
            is_plan_mode: 是否启用计划模式
            
        Returns:
            创建的任务
        """
        task_id = str(uuid.uuid4())
        thread_id = str(uuid.uuid4())
        
        if not model_name:
            model_name = self.config_manager.get_default_model()
        
        task = Task(
            id=task_id,
            title=title,
            description=description,
            thread_id=thread_id,
            model_name=model_name,
            is_plan_mode=is_plan_mode,
        )
        
        self._tasks[task_id] = task
        self._save_tasks()
        logger.info(f"Created task: {task_id} - {title}")
        
        return task
    
    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> list[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """按状态获取任务"""
        return [t for t in self._tasks.values() if t.status == status]
    
    async def start_task(self, task_id: str) -> tuple[bool, str]:
        """启动任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            (是否启动成功, 错误信息)
        """
        task = self.get_task(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return False, "Task not found"
        
        if task.status not in (TaskStatus.PENDING, TaskStatus.PAUSED):
            logger.error(f"Task cannot be started: {task_id}, status: {task.status}")
            return False, f"Task cannot be started in status: {task.status}"
        
        if not self.deerflow_client.is_embedded_mode:
            task.status = TaskStatus.FAILED
            task.error = "DeerFlow 运行时不可用。请确保 DeerFlow 已正确安装并配置。"
            task.updated_at = datetime.now()
            self._save_tasks()
            logger.error(f"DeerFlow runtime not available for task: {task_id}")
            return False, task.error
        
        task.status = TaskStatus.PLANNING
        task.started_at = datetime.now()
        task.updated_at = datetime.now()
        self._save_tasks()
        
        logger.info(f"Starting task execution: {task_id}, thread_id: {task.thread_id}")
        
        async def run_task():
            try:
                logger.info(f"Task {task_id}: starting stream, description: {task.description[:50]}...")
                event_count = 0
                async for event in self.deerflow_client.stream(
                    thread_id=task.thread_id,
                    message=task.description,
                    model_name=task.model_name,
                    is_plan_mode=task.is_plan_mode,
                ):
                    event_count += 1
                    logger.info(f"Task {task_id}: received event {event_count}, type: {event.get('type', 'unknown')}")
                    await self._handle_event(task, event)
                logger.info(f"Task {task_id}: stream ended, total events: {event_count}")
                
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.updated_at = datetime.now()
                self._save_tasks()
                logger.info(f"Task completed: {task_id}")
                
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.updated_at = datetime.now()
                self._save_tasks()
                logger.info(f"Task cancelled: {task_id}")
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.updated_at = datetime.now()
                self._save_tasks()
                logger.error(f"Task failed: {task_id}, error: {e}")
                
            finally:
                self._running_tasks.pop(task_id, None)
        
        self._running_tasks[task_id] = asyncio.create_task(run_task())
        return True, ""
    
    async def _handle_event(self, task: Task, event: dict[str, Any]) -> None:
        """处理 DeerFlow 事件"""
        event_type = event.get("type", "")
        event_data = event.get("data", {})
        logger.debug(f"Task {task.id} received event: {event_type}, data: {event_data}")

        if event_type == "values":
            # 处理状态更新，包含 todos
            todos_data = event_data.get("todos", [])
            if todos_data:
                task.todos = [
                    TodoItem.from_dict(t) if isinstance(t, dict) else TodoItem(id=str(i), content=str(t))
                    for i, t in enumerate(todos_data)
                ]
                task.updated_at = datetime.now()

                # 如果正在规划且有了 todos，转为等待批准
                if task.status == TaskStatus.PLANNING and task.todos:
                    task.status = TaskStatus.WAITING_APPROVAL

                self._save_tasks()
                logger.debug(f"Task {task.id} todos updated: {len(task.todos)} items")

            # 更新任务结果（如果有最终响应）
            messages = event_data.get("messages", [])
            if messages:
                # 获取最后一条 AI 消息作为结果
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("type") == "ai":
                        content = msg.get("content", "")
                        if content and not msg.get("tool_calls"):
                            task.result = content
                            task.updated_at = datetime.now()
                            self._save_tasks()
                            break

        elif event_type == "messages-tuple":
            # 处理消息事件
            msg_type = event_data.get("type", "")

            if msg_type == "ai":
                content = event_data.get("content", "")
                tool_calls = event_data.get("tool_calls", [])

                if content:
                    logger.debug(f"Task {task.id} AI response: {content[:100]}...")

                if tool_calls:
                    logger.debug(f"Task {task.id} tool calls: {[tc.get('name') for tc in tool_calls]}")

                    # 如果调用了 write_todos 工具，说明正在规划
                    for tc in tool_calls:
                        if tc.get("name") == "write_todos":
                            if task.status == TaskStatus.PLANNING:
                                # 保持 PLANNING 状态，等待 values 事件更新 todos
                                pass
                            break

            elif msg_type == "tool":
                tool_name = event_data.get("name", "")
                tool_result = event_data.get("content", "")
                logger.debug(f"Task {task.id} tool result: {tool_name}")

        elif event_type == "end":
            # 流结束
            usage = event_data.get("usage", {})
            logger.info(f"Task {task.id} stream ended. Usage: {usage}")

        elif event_type == "error":
            error_msg = event_data.get("error", "Unknown error")
            logger.error(f"Task {task.id} event error: {error_msg}")
    
    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.EXECUTING:
            return False
        
        running_task = self._running_tasks.get(task_id)
        if running_task:
            running_task.cancel()
        
        task.status = TaskStatus.PAUSED
        task.updated_at = datetime.now()
        self._save_tasks()
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        running_task = self._running_tasks.get(task_id)
        if running_task:
            running_task.cancel()
        
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now()
        self._save_tasks()
        return True
    
    async def approve_plan(self, task_id: str) -> bool:
        """批准任务计划
        
        用户批准后，任务开始执行
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.WAITING_APPROVAL:
            return False
        
        task.status = TaskStatus.EXECUTING
        task.updated_at = datetime.now()
        self._save_tasks()
        
        await self.deerflow_client.update_todos(
            task.thread_id,
            [t.to_dict() for t in task.todos],
        )
        
        return True
    
    async def modify_plan(
        self,
        task_id: str,
        todos: list[dict[str, Any]],
    ) -> bool:
        """修改任务计划
        
        允许用户在批准前修改任务计划
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.WAITING_APPROVAL:
            return False
        
        task.todos = [TodoItem.from_dict(t) for t in todos]
        task.updated_at = datetime.now()
        self._save_tasks()
        
        return True
    
    async def retry_todo(self, task_id: str, todo_id: str) -> bool:
        """重试失败的 Todo"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        for todo in task.todos:
            if todo.id == todo_id and todo.status == TodoStatus.FAILED:
                todo.status = TodoStatus.PENDING
                todo.error = None
                todo.updated_at = datetime.now()
                task.updated_at = datetime.now()
                self._save_tasks()
                return True
        
        return False
    
    async def skip_todo(self, task_id: str, todo_id: str) -> bool:
        """跳过 Todo"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        for todo in task.todos:
            if todo.id == todo_id:
                todo.status = TodoStatus.SKIPPED
                todo.updated_at = datetime.now()
                task.updated_at = datetime.now()
                self._save_tasks()
                return True
        
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
        
        result = self._tasks.pop(task_id, None) is not None
        if result:
            self._save_tasks()
        return result
    
    def get_task_progress(self, task_id: str) -> dict[str, Any]:
        """获取任务进度"""
        task = self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        
        total = len(task.todos)
        completed = sum(1 for t in task.todos if t.status == TodoStatus.COMPLETED)
        failed = sum(1 for t in task.todos if t.status == TodoStatus.FAILED)
        skipped = sum(1 for t in task.todos if t.status == TodoStatus.SKIPPED)
        
        return {
            "task_id": task_id,
            "status": task.status.value,
            "total_todos": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "in_progress": sum(1 for t in task.todos if t.status == TodoStatus.IN_PROGRESS),
            "pending": sum(1 for t in task.todos if t.status == TodoStatus.PENDING),
            "progress_percent": (completed + skipped) / total * 100 if total > 0 else 0,
        }
