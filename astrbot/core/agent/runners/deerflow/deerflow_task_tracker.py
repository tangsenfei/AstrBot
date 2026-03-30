"""
DeerFlow Task Tracker - 任务追踪模块

追踪 DeerFlow 的任务拆解情况，支持人工介入调整和执行进展监控
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from astrbot.core.agent.runners.deerflow.deerflow_api_client import DeerFlowAPIClient


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskItem:
    """任务项数据类"""
    content: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskItem":
        """从字典创建"""
        return cls(
            content=data.get("content", ""),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskPlan:
    """任务计划数据类"""
    thread_id: str
    tasks: list[TaskItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_plan_mode: bool = False
    
    @property
    def total_tasks(self) -> int:
        return len(self.tasks)
    
    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
    
    @property
    def pending_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
    
    @property
    def in_progress_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
    
    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "thread_id": self.thread_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_plan_mode": self.is_plan_mode,
            "summary": {
                "total": self.total_tasks,
                "completed": self.completed_tasks,
                "pending": self.pending_tasks,
                "in_progress": self.in_progress_tasks,
                "progress_percentage": round(self.progress_percentage, 2),
            },
        }


class DeerFlowTaskTracker:
    """DeerFlow 任务追踪器
    
    追踪 DeerFlow 的任务拆解情况，支持人工介入调整和执行进展监控
    """
    
    def __init__(
        self,
        api_client: "DeerFlowAPIClient",
        storage_path: str | Path | None = None,
    ) -> None:
        self.api_client = api_client
        self.storage_path = Path(storage_path) if storage_path else None
        self._plans: dict[str, TaskPlan] = {}
        self._lock = asyncio.Lock()
    
    async def get_task_plan(self, thread_id: str) -> TaskPlan | None:
        """获取指定线程的任务计划
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            任务计划，如果不存在返回 None
        """
        async with self._lock:
            if thread_id in self._plans:
                return self._plans[thread_id]
            
            plan = await self._load_plan_from_storage(thread_id)
            if plan:
                self._plans[thread_id] = plan
            return plan
    
    async def fetch_tasks_from_deerflow(self, thread_id: str) -> TaskPlan:
        """从 DeerFlow 获取任务列表
        
        通过 LangGraph API 获取当前线程的状态，提取 todos
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            任务计划
        """
        try:
            state = await self.api_client.get_thread_state(thread_id)
            
            todos = state.get("todos", [])
            is_plan_mode = state.get("configurable", {}).get("is_plan_mode", False)
            
            tasks = []
            for todo in todos:
                task = TaskItem(
                    content=todo.get("content", ""),
                    status=TaskStatus(todo.get("status", "pending")),
                    metadata={"original_todo": todo},
                )
                tasks.append(task)
            
            plan = TaskPlan(
                thread_id=thread_id,
                tasks=tasks,
                is_plan_mode=is_plan_mode,
            )
            
            async with self._lock:
                self._plans[thread_id] = plan
            
            await self._save_plan_to_storage(plan)
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to fetch tasks from DeerFlow: {e}")
            raise
    
    async def update_task_status(
        self,
        thread_id: str,
        task_index: int,
        new_status: TaskStatus,
        error_message: str | None = None,
    ) -> TaskItem | None:
        """更新任务状态
        
        Args:
            thread_id: 线程 ID
            task_index: 任务索引
            new_status: 新状态
            error_message: 错误信息（可选）
            
        Returns:
            更新后的任务项
        """
        async with self._lock:
            plan = self._plans.get(thread_id)
            if not plan or task_index >= len(plan.tasks):
                return None
            
            task = plan.tasks[task_index]
            task.status = new_status
            task.updated_at = datetime.now()
            task.error_message = error_message
            
            if new_status == TaskStatus.IN_PROGRESS:
                task.started_at = datetime.now()
            elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = datetime.now()
            
            plan.updated_at = datetime.now()
            
            await self._save_plan_to_storage(plan)
            
            return task
    
    async def add_task(
        self,
        thread_id: str,
        content: str,
        position: int | None = None,
    ) -> TaskItem:
        """添加新任务
        
        Args:
            thread_id: 线程 ID
            content: 任务内容
            position: 插入位置（可选，默认添加到末尾）
            
        Returns:
            新添加的任务项
        """
        async with self._lock:
            plan = self._plans.get(thread_id)
            if not plan:
                plan = TaskPlan(thread_id=thread_id)
                self._plans[thread_id] = plan
            
            task = TaskItem(content=content)
            
            if position is not None and 0 <= position <= len(plan.tasks):
                plan.tasks.insert(position, task)
            else:
                plan.tasks.append(task)
            
            plan.updated_at = datetime.now()
            
            await self._save_plan_to_storage(plan)
            
            return task
    
    async def remove_task(self, thread_id: str, task_index: int) -> bool:
        """删除任务
        
        Args:
            thread_id: 线程 ID
            task_index: 任务索引
            
        Returns:
            是否删除成功
        """
        async with self._lock:
            plan = self._plans.get(thread_id)
            if not plan or task_index >= len(plan.tasks):
                return False
            
            plan.tasks.pop(task_index)
            plan.updated_at = datetime.now()
            
            await self._save_plan_to_storage(plan)
            
            return True
    
    async def reorder_tasks(
        self,
        thread_id: str,
        new_order: list[int],
    ) -> bool:
        """重新排序任务
        
        Args:
            thread_id: 线程 ID
            new_order: 新的索引顺序
            
        Returns:
            是否排序成功
        """
        async with self._lock:
            plan = self._plans.get(thread_id)
            if not plan or len(new_order) != len(plan.tasks):
                return False
            
            try:
                plan.tasks = [plan.tasks[i] for i in new_order]
                plan.updated_at = datetime.now()
                await self._save_plan_to_storage(plan)
                return True
            except (IndexError, ValueError):
                return False
    
    async def sync_tasks_to_deerflow(self, thread_id: str) -> bool:
        """将任务同步回 DeerFlow
        
        通过调用 DeerFlow 的 write_todos 工具更新任务列表
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            是否同步成功
        """
        async with self._lock:
            plan = self._plans.get(thread_id)
            if not plan:
                return False
            
            try:
                todos = [
                    {
                        "content": task.content,
                        "status": task.status.value,
                    }
                    for task in plan.tasks
                ]
                
                result = await self.api_client.invoke_tool(
                    thread_id=thread_id,
                    tool_name="write_todos",
                    tool_args={"todos": todos},
                )
                
                logger.info(f"Synced tasks to DeerFlow for thread {thread_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to sync tasks to DeerFlow: {e}")
                return False
    
    async def get_progress_report(self, thread_id: str) -> dict[str, Any]:
        """获取任务进度报告
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            进度报告字典
        """
        plan = await self.get_task_plan(thread_id)
        if not plan:
            return {"error": "Task plan not found"}
        
        return {
            "thread_id": thread_id,
            "total_tasks": plan.total_tasks,
            "completed": plan.completed_tasks,
            "pending": plan.pending_tasks,
            "in_progress": plan.in_progress_tasks,
            "progress_percentage": round(plan.progress_percentage, 2),
            "tasks": [
                {
                    "index": i,
                    "content": task.content,
                    "status": task.status.value,
                }
                for i, task in enumerate(plan.tasks)
            ],
            "updated_at": plan.updated_at.isoformat(),
        }
    
    async def watch_task_progress(
        self,
        thread_id: str,
        callback: callable,
        interval: float = 5.0,
    ) -> None:
        """监控任务进度变化
        
        Args:
            thread_id: 线程 ID
            callback: 进度变化回调函数
            interval: 轮询间隔（秒）
        """
        last_plan = None
        
        while True:
            try:
                plan = await self.fetch_tasks_from_deerflow(thread_id)
                
                if last_plan is None or plan.updated_at > last_plan.updated_at:
                    await callback(plan)
                    last_plan = plan
                
                if plan.completed_tasks == plan.total_tasks and plan.total_tasks > 0:
                    logger.info(f"All tasks completed for thread {thread_id}")
                    break
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching task progress: {e}")
                await asyncio.sleep(interval)
    
    async def _save_plan_to_storage(self, plan: TaskPlan) -> None:
        """保存任务计划到存储"""
        if not self.storage_path:
            return
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        plan_file = self.storage_path / f"{plan.thread_id}.json"
        
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)
    
    async def _load_plan_from_storage(self, thread_id: str) -> TaskPlan | None:
        """从存储加载任务计划"""
        if not self.storage_path:
            return None
        
        plan_file = self.storage_path / f"{thread_id}.json"
        
        if not plan_file.exists():
            return None
        
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return TaskPlan(
                thread_id=data["thread_id"],
                tasks=[TaskItem.from_dict(t) for t in data.get("tasks", [])],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                is_plan_mode=data.get("is_plan_mode", False),
            )
        except Exception as e:
            logger.error(f"Failed to load plan from storage: {e}")
            return None


class TaskInterventionManager:
    """任务人工介入管理器
    
    提供人工介入调整任务的能力
    """
    
    def __init__(self, task_tracker: DeerFlowTaskTracker) -> None:
        self.task_tracker = task_tracker
        self._intervention_queue: asyncio.Queue = asyncio.Queue()
        self._pending_interventions: dict[str, asyncio.Event] = {}
    
    async def request_intervention(
        self,
        thread_id: str,
        intervention_type: str,
        data: dict[str, Any],
    ) -> str:
        """请求人工介入
        
        Args:
            thread_id: 线程 ID
            intervention_type: 介入类型 (approve, modify, cancel, add, remove)
            data: 介入数据
            
        Returns:
            介入请求 ID
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        intervention = {
            "request_id": request_id,
            "thread_id": thread_id,
            "type": intervention_type,
            "data": data,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        
        await self._intervention_queue.put(intervention)
        self._pending_interventions[request_id] = asyncio.Event()
        
        logger.info(f"Intervention requested: {request_id} for thread {thread_id}")
        return request_id
    
    async def approve_intervention(
        self,
        request_id: str,
        approved: bool,
        modifications: dict[str, Any] | None = None,
    ) -> bool:
        """审批人工介入请求
        
        Args:
            request_id: 介入请求 ID
            approved: 是否批准
            modifications: 修改内容（可选）
            
        Returns:
            是否处理成功
        """
        if request_id not in self._pending_interventions:
            return False
        
        event = self._pending_interventions[request_id]
        event.set()
        
        return approved
    
    async def get_pending_interventions(self) -> list[dict[str, Any]]:
        """获取待处理的人工介入请求"""
        interventions = []
        temp_queue = asyncio.Queue()
        
        while not self._intervention_queue.empty():
            intervention = await self._intervention_queue.get()
            if intervention["status"] == "pending":
                interventions.append(intervention)
            await temp_queue.put(intervention)
        
        while not temp_queue.empty():
            await self._intervention_queue.put(await temp_queue.get())
        
        return interventions
    
    async def modify_task_content(
        self,
        thread_id: str,
        task_index: int,
        new_content: str,
    ) -> bool:
        """修改任务内容
        
        Args:
            thread_id: 线程 ID
            task_index: 任务索引
            new_content: 新内容
            
        Returns:
            是否修改成功
        """
        plan = await self.task_tracker.get_task_plan(thread_id)
        if not plan or task_index >= len(plan.tasks):
            return False
        
        plan.tasks[task_index].content = new_content
        plan.tasks[task_index].updated_at = datetime.now()
        plan.updated_at = datetime.now()
        
        return await self.task_tracker.sync_tasks_to_deerflow(thread_id)
    
    async def split_task(
        self,
        thread_id: str,
        task_index: int,
        subtasks: list[str],
    ) -> bool:
        """拆分任务为多个子任务
        
        Args:
            thread_id: 线程 ID
            task_index: 任务索引
            subtasks: 子任务内容列表
            
        Returns:
            是否拆分成功
        """
        async with self.task_tracker._lock:
            plan = self.task_tracker._plans.get(thread_id)
            if not plan or task_index >= len(plan.tasks):
                return False
            
            original_task = plan.tasks[task_index]
            
            new_tasks = [
                TaskItem(
                    content=content,
                    status=TaskStatus.PENDING,
                    metadata={"parent_task": original_task.content},
                )
                for content in subtasks
            ]
            
            plan.tasks.pop(task_index)
            for i, new_task in enumerate(new_tasks):
                plan.tasks.insert(task_index + i, new_task)
            
            plan.updated_at = datetime.now()
            
            return await self.task_tracker.sync_tasks_to_deerflow(thread_id)
    
    async def merge_tasks(
        self,
        thread_id: str,
        task_indices: list[int],
        merged_content: str,
    ) -> bool:
        """合并多个任务
        
        Args:
            thread_id: 线程 ID
            task_indices: 要合并的任务索引列表
            merged_content: 合并后的内容
            
        Returns:
            是否合并成功
        """
        async with self.task_tracker._lock:
            plan = self.task_tracker._plans.get(thread_id)
            if not plan:
                return False
            
            valid_indices = [i for i in task_indices if 0 <= i < len(plan.tasks)]
            if not valid_indices:
                return False
            
            min_index = min(valid_indices)
            
            merged_task = TaskItem(
                content=merged_content,
                status=TaskStatus.PENDING,
                metadata={
                    "merged_from": [plan.tasks[i].content for i in valid_indices],
                },
            )
            
            for i in sorted(valid_indices, reverse=True):
                plan.tasks.pop(i)
            
            plan.tasks.insert(min_index, merged_task)
            plan.updated_at = datetime.now()
            
            return await self.task_tracker.sync_tasks_to_deerflow(thread_id)
