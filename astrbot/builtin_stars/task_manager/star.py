import uuid
from typing import Any
from astrbot.api.star import Star, register
from astrbot.core.agent.tool import FunctionTool
from .task_manager import TaskManager
from .models import Task, TaskStatus, ExecutionMode


class TaskManagerStar(Star):
    def __init__(self, context: Any):
        super().__init__(context)
        self.task_manager = TaskManager(
            platform_manager=getattr(context, "platform_manager", None),
            llm_client=getattr(context, "llm_client", None),
        )

    async def initialize(self) -> None:
        await self.task_manager.initialize()
        self._register_handlers()
        self.context.logger.info("TaskManager Star initialized")

    def _register_handlers(self):
        async def on_task_created(task: Task):
            self.context.logger.info(f"Task created: {task.id}")

        async def on_task_completed(task: Task):
            self.context.logger.info(f"Task completed: {task.id}")

        async def on_task_failed(task: Task, error: Exception):
            self.context.logger.error(f"Task failed: {task.id}, error: {error}")

        self.task_manager.register_event_handler("task_created", on_task_created)
        self.task_manager.register_event_handler("task_completed", on_task_completed)
        self.task_manager.register_event_handler("task_failed", on_task_failed)

    @register("create_async_task")
    class CreateAsyncTaskTool(FunctionTool):
        name = "create_async_task"
        description = "创建异步任务来处理复杂研究任务"

        parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "任务描述"
                },
                "task_type": {
                    "type": "string",
                    "enum": ["research", "report", "analysis", "coding", "general"],
                    "default": "general",
                    "description": "任务类型"
                },
                "use_planner": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否使用任务规划器"
                },
                "enable_subagent": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否启用子Agent"
                }
            },
            "required": ["query"]
        }

        async def execute(
            self,
            query: str,
            task_type: str = "general",
            use_planner: bool = True,
            enable_subagent: bool = True,
            **kwargs
        ):
            session = self.context.context
            user_id = session.user_id if hasattr(session, "user_id") else "unknown"
            platform = session.platform if hasattr(session, "platform") else "unknown"

            task_id = await self.task_manager.create_task(
                user_id=user_id,
                platform=platform,
                query=query,
                task_type=task_type,
                execution_mode=ExecutionMode.STREAM,
                user_config={
                    "use_planner": use_planner,
                    "enable_subagent": enable_subagent,
                }
            )

            return f"✅ 异步任务已创建！\n\n**任务ID**: `{task_id}`\n**任务类型**: {task_type}\n**查询**: {query}\n\n进度将实时推送给你..."

    @register("get_task_status")
    class GetTaskStatusTool(FunctionTool):
        name = "get_task_status"
        description = "查询任务状态"

        parameters = {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID"
                }
            },
            "required": ["task_id"]
        }

        async def execute(self, task_id: str, **kwargs):
            task = await self.task_manager.get_task(task_id)
            if not task:
                return f"❌ 任务 {task_id} 不存在"

            status_emoji = {
                "pending": "⏳",
                "running": "🔄",
                "waiting_subagent": "🤖",
                "checkpoint": "💾",
                "paused": "⏸️",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫",
            }

            emoji = status_emoji.get(task.status.value, "📋")

            lines = [
                f"{emoji} **任务状态**",
                f"**ID**: `{task.id}`",
                f"**状态**: {task.status.value}",
                f"**类型**: {task.task_type}",
                f"**创建时间**: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ]

            if task.completed_at:
                lines.append(f"**完成时间**: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")

            if task.error:
                lines.append(f"**错误**: {task.error}")

            return "\n".join(lines)

    @register("list_tasks")
    class ListTasksTool(FunctionTool):
        name = "list_tasks"
        description = "列出用户的所有任务"

        parameters = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "failed", "all"],
                    "default": "all",
                    "description": "按状态筛选"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "返回数量"
                }
            }
        }

        async def execute(self, status: str = "all", limit: int = 10, **kwargs):
            session = self.context.context
            user_id = session.user_id if hasattr(session, "user_id") else None

            if status == "all":
                status_filter = None
            else:
                status_filter = TaskStatus(status)

            tasks = await self.task_manager.list_tasks(
                user_id=user_id,
                status=status_filter
            )
            tasks = tasks[:limit]

            if not tasks:
                return "📋 暂无任务"

            lines = ["📋 **任务列表**\n"]
            for task in tasks:
                status_emoji = {
                    "pending": "⏳",
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                }
                emoji = status_emoji.get(task.status.value, "📋")
                lines.append(
                    f"{emoji} `{task.id[:8]}...` | {task.task_type} | {task.status.value} | "
                    f"{task.created_at.strftime('%m-%d %H:%M')}"
                )

            return "\n".join(lines)

    @register("cancel_task")
    class CancelTaskTool(FunctionTool):
        name = "cancel_task"
        description = "取消正在运行的任务"

        parameters = {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID"
                }
            },
            "required": ["task_id"]
        }

        async def execute(self, task_id: str, **kwargs):
            success = await self.task_manager.cancel_task(task_id)
            if success:
                return f"✅ 任务 {task_id} 已取消"
            return f"❌ 取消任务失败"

    @register("pause_task")
    class PauseTaskTool(FunctionTool):
        name = "pause_task"
        description = "暂停任务（可恢复）"

        parameters = {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID"
                }
            },
            "required": ["task_id"]
        }

        async def execute(self, task_id: str, **kwargs):
            success = await self.task_manager.pause_task(task_id)
            if success:
                return f"✅ 任务 {task_id} 已暂停，可以使用 /resume {task_id} 恢复"
            return f"❌ 暂停任务失败"

    @register("resume_task")
    class ResumeTaskTool(FunctionTool):
        name = "resume_task"
        description = "恢复已暂停的任务"

        parameters = {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID"
                }
            },
            "required": ["task_id"]
        }

        async def execute(self, task_id: str, **kwargs):
            success = await self.task_manager.resume_task(task_id)
            if success:
                return f"✅ 任务 {task_id} 已恢复"
            return f"❌ 恢复任务失败"

    @register("delete_task")
    class DeleteTaskTool(FunctionTool):
        name = "delete_task"
        description = "删除任务记录"

        parameters = {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID"
                }
            },
            "required": ["task_id"]
        }

        async def execute(self, task_id: str, **kwargs):
            success = await self.task_manager.delete_task(task_id)
            if success:
                return f"✅ 任务 {task_id} 已删除"
            return f"❌ 删除任务失败"

    async def terminate(self) -> None:
        await self.task_manager.close()
        self.context.logger.info("TaskManager Star terminated")