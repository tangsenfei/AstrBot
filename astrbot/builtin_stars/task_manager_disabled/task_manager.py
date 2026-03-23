import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable
from astrbot import logger
from .models import Task, TaskStatus, ExecutionMode, TaskProgress
from .deerflow_integration import DeerFlowIntegration
from .task_analyzer import TaskAnalyzer
from .progress_pusher import ProgressDispatcher
from .checkpoint_manager import CheckpointManager


class TaskManager:
    def __init__(
        self,
        platform_manager: Any = None,
        llm_client: Any = None,
        checkpoint_dir: str = "data/task_checkpoints",
    ):
        self.tasks: dict[str, Task] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

        self.deerflow = DeerFlowIntegration()
        self.analyzer = TaskAnalyzer(llm_client=llm_client)
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.progress_dispatcher = ProgressDispatcher()

        self._event_handlers: dict[str, list[Callable]] = {
            "task_created": [],
            "task_started": [],
            "task_progress": [],
            "task_completed": [],
            "task_failed": [],
        }

    async def initialize(self):
        await self.deerflow.initialize()
        logger.info("TaskManager initialized")

    def register_event_handler(self, event: str, handler: Callable):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    async def _emit_event(self, event: str, task: Task, **kwargs):
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(task, **kwargs)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def create_task(
        self,
        user_id: str,
        platform: str,
        query: str,
        task_type: str = "general",
        execution_mode: ExecutionMode = ExecutionMode.STREAM,
        user_config: dict | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())

        async with self._lock:
            task = Task(
                id=task_id,
                user_id=user_id,
                platform=platform,
                query=query,
                task_type=task_type,
                status=TaskStatus.PENDING,
                execution_mode=execution_mode,
            )
            self.tasks[task_id] = task

        await self._emit_event("task_created", task)
        logger.info(f"Task created: {task_id}")

        asyncio.create_task(self._execute_task(task, user_config))

        return task_id

    async def _execute_task(self, task: Task, user_config: dict | None = None):
        task_id = task.id
        try:
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now()
            await self._emit_event("task_started", task)

            progress = TaskProgress(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                stage="analyzing",
                stage_progress=0,
                total_progress=0,
                message="分析任务..."
            )
            await self.progress_dispatcher.dispatch(task_id, progress)

            if not self.deerflow.is_available:
                raise RuntimeError("DeerFlow not available")

            plan = None
            if user_config and user_config.get("use_planner", True):
                plan_result = await self.analyzer.analyze_and_plan(task.query)
                plan = plan_result

            if plan:
                execution_mode = self.analyzer.select_execution_mode(plan)
                subagent_enabled = self.analyzer.should_enable_subagent(plan)
                plan_mode = self.analyzer.should_enable_plan_mode(plan)
            else:
                execution_mode = task.execution_mode.value
                subagent_enabled = True
                plan_mode = False

            progress = TaskProgress(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                stage="executing",
                stage_progress=20,
                total_progress=20,
                message=f"执行模式: {execution_mode}"
            )
            await self.progress_dispatcher.dispatch(task_id, progress)

            async for event in self.deerflow.stream(
                query=task.query,
                thread_id=task_id,
                skills=plan.get("skills") if plan else None,
                subagent_enabled=subagent_enabled,
                plan_mode=plan_mode,
            ):
                await self._handle_deerflow_event(task, event)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()

            progress = TaskProgress(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                stage="completed",
                stage_progress=100,
                total_progress=100,
                message="任务完成"
            )
            await self.progress_dispatcher.dispatch(task_id, progress)
            await self._emit_event("task_completed", task)

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            logger.info(f"Task cancelled: {task_id}")
            raise

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now()
            logger.error(f"Task failed: {task_id}, error: {e}")

            progress = TaskProgress(
                task_id=task_id,
                status=TaskStatus.FAILED,
                stage="failed",
                stage_progress=0,
                total_progress=0,
                message=f"任务失败: {e}"
            )
            await self.progress_dispatcher.dispatch(task_id, progress)
            await self._emit_event("task_failed", task, error=e)

        finally:
            self._running_tasks.pop(task_id, None)
            if task.checkpoint:
                await self.checkpoint_manager.delete(task_id)

    async def _handle_deerflow_event(self, task: Task, event: dict):
        event_type = event.get("type", "")
        data = event.get("data")

        if event_type in ("values", "messages-tuple"):
            progress = TaskProgress(
                task_id=task.id,
                status=TaskStatus.RUNNING,
                stage="processing",
                stage_progress=50,
                total_progress=50,
                message="处理中..."
            )
            await self.progress_dispatcher.dispatch(task.id, progress)

        elif event_type == "subagent_start":
            task.status = TaskStatus.WAITING_SUBAGENT
            progress = TaskProgress(
                task_id=task.id,
                status=TaskStatus.WAITING_SUBAGENT,
                stage=f"subagent:{data}",
                stage_progress=60,
                total_progress=60,
                message="子任务执行中..."
            )
            await self.progress_dispatcher.dispatch(task.id, progress)

        elif event_type == "checkpoint":
            task.status = TaskStatus.CHECKPOINT
            from .models import Checkpoint
            checkpoint = Checkpoint(
                task_id=task.id,
                step=event.get("step", 0),
                state=event.get("state", {}),
            )
            task.checkpoint = checkpoint
            await self.checkpoint_manager.save(task.id, checkpoint)

        elif event_type == "end":
            task.result = data

    async def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    async def list_tasks(
        self,
        user_id: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        tasks = list(self.tasks.values())
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False

        running_task = self._running_tasks.get(task_id)
        if running_task:
            running_task.cancel()
            try:
                await running_task
            except asyncio.CancelledError:
                pass

        if await self.deerflow.cancel_task(task.thread_id):
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            return True
        return False

    async def pause_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        running_task = self._running_tasks.get(task_id)
        if running_task:
            running_task.cancel()
            try:
                await running_task
            except asyncio.CancelledError:
                pass

        task.status = TaskStatus.PAUSED
        task.updated_at = datetime.now()

        if task.checkpoint:
            await self.checkpoint_manager.save(task_id, task.checkpoint)

        logger.info(f"Task paused: {task_id}")
        return True

    async def resume_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False

        if task.checkpoint:
            await self.checkpoint_manager.delete(task_id)

        asyncio.create_task(self._execute_task(task))
        return True

    async def delete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            if task_id in self._running_tasks:
                await self.cancel_task(task_id)
            await self.checkpoint_manager.delete(task_id)
            del self.tasks[task_id]
            logger.info(f"Task deleted: {task_id}")
            return True
        return False

    async def close(self):
        for task_id in list(self._running_tasks.keys()):
            await self.cancel_task(task_id)
        await self.deerflow.close()