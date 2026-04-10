"""
智能体管理模块 - 任务管理路由

提供任务管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin


def register_task_routes(plugin: "AgentSystemPlugin") -> None:
    plugin.context.register_web_api(
        "/agent/tasks",
        _list_tasks,
        ["GET"],
        "获取任务列表"
    )

    plugin.context.register_web_api(
        "/agent/tasks/stats",
        _get_task_stats,
        ["GET"],
        "获取任务统计"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>",
        _get_task,
        ["GET"],
        "获取任务详情"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>",
        _delete_task,
        ["DELETE"],
        "删除任务"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/pause",
        _pause_task,
        ["POST"],
        "暂停任务"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/resume",
        _resume_task,
        ["POST"],
        "恢复任务"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/cancel",
        _cancel_task,
        ["POST"],
        "取消任务"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/retry",
        _retry_task,
        ["POST"],
        "重试任务"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/feedback",
        _submit_feedback,
        ["POST"],
        "提交任务反馈"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/logs",
        _get_task_logs,
        ["GET"],
        "获取任务日志"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/subtasks",
        _get_subtasks,
        ["GET"],
        "获取子任务列表"
    )

    plugin.context.register_web_api(
        "/agent/tasks/<task_id>/tokens/timeseries",
        _get_token_timeseries,
        ["GET"],
        "获取任务 Token 时间序列"
    )

    logger.info("Task management API routes registered")


def _get_task_service():
    from ..services.task_service import TaskService
    from ..database import get_database

    db = get_database()
    return TaskService(db)


async def _list_tasks():
    try:
        service = _get_task_service()

        status = request.args.get("status")
        crew_id = request.args.get("crew_id")
        flow_id = request.args.get("flow_id")
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        page = request.args.get("page", "1")
        page_size = request.args.get("page_size", "20")

        try:
            page = max(1, int(page))
        except ValueError:
            page = 1

        try:
            page_size = max(1, min(100, int(page_size)))
        except ValueError:
            page_size = 20

        result = service.get_tasks(
            status=status,
            crew_id=crew_id,
            flow_id=flow_id,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )

        return Response().ok(result).__dict__
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return Response().error(str(e)).__dict__


async def _get_task(task_id: str):
    try:
        service = _get_task_service()
        task = service.get_task(task_id)
        if not task:
            return Response().error(f"任务 '{task_id}' 不存在").__dict__
        return Response().ok(task.to_dict()).__dict__
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _delete_task(task_id: str):
    try:
        service = _get_task_service()
        success = service.delete_task(task_id)
        if not success:
            return Response().error(f"任务 '{task_id}' 不存在").__dict__
        return Response().ok(None, "任务删除成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _pause_task(task_id: str):
    try:
        service = _get_task_service()
        success = service.pause_task(task_id)
        return Response().ok({"success": success}, "任务已暂停").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to pause task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _resume_task(task_id: str):
    try:
        service = _get_task_service()
        success = service.resume_task(task_id)
        return Response().ok({"success": success}, "任务已恢复").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to resume task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _cancel_task(task_id: str):
    try:
        service = _get_task_service()
        success = service.cancel_task(task_id)
        return Response().ok({"success": success}, "任务已取消").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _retry_task(task_id: str):
    try:
        service = _get_task_service()
        new_task = service.retry_task(task_id)
        return Response().ok(new_task.to_dict(), f"已创建新任务 '{new_task.id}'").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _submit_feedback(task_id: str):
    try:
        service = _get_task_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        feedback = data.get("feedback")
        if not feedback:
            return Response().error("反馈内容不能为空").__dict__

        result = service.submit_feedback(task_id, feedback)
        return Response().ok(result, "反馈提交成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to submit feedback for task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _get_task_logs(task_id: str):
    try:
        service = _get_task_service()
        task = service.get_task(task_id)
        if not task:
            return Response().error(f"任务 '{task_id}' 不存在").__dict__

        logs = service.get_task_logs(task_id)
        return Response().ok([log.to_dict() for log in logs]).__dict__
    except Exception as e:
        logger.error(f"Failed to get task logs {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _get_subtasks(task_id: str):
    try:
        service = _get_task_service()
        task = service.get_task(task_id)
        if not task:
            return Response().error(f"任务 '{task_id}' 不存在").__dict__

        subtasks = service.get_subtasks(task_id)
        return Response().ok([subtask.to_dict() for subtask in subtasks]).__dict__
    except Exception as e:
        logger.error(f"Failed to get subtasks for task {task_id}: {e}")
        return Response().error(str(e)).__dict__


async def _get_task_stats():
    try:
        service = _get_task_service()
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        stats = service.get_task_stats(start_time=start_time, end_time=end_time)
        return Response().ok(stats).__dict__
    except Exception as e:
        logger.error(f"Failed to get task stats: {e}")
        return Response().error(str(e)).__dict__


async def _get_token_timeseries(task_id: str):
    try:
        service = _get_task_service()
        result = service.get_token_timeseries(task_id)
        return Response().ok(result).__dict__
    except Exception as e:
        logger.error(f"Failed to get token timeseries for task {task_id}: {e}")
        return Response().error(str(e)).__dict__
