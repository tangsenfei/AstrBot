"""Work mode facade routes."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from quart import Response as QuartResponse
from quart import request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_ref: AgentSystemPlugin | None = None


def register_work_routes(plugin: AgentSystemPlugin) -> None:
    global _plugin_ref
    _plugin_ref = plugin
    routes = [
        ("/work/projects", _list_projects, ["GET"], "Work 项目列表"),
        ("/work/projects", _create_project, ["POST"], "创建 Work 项目"),
        ("/work/projects/<project_id>", _update_project, ["PATCH"], "更新 Work 项目"),
        ("/work/projects/<project_id>", _delete_project, ["DELETE"], "归档 Work 项目"),
        ("/work/daily-dirs", _list_daily_dirs, ["GET"], "Work 日常目录列表"),
        ("/work/daily-dirs", _create_daily_dir, ["POST"], "创建 Work 日常目录"),
        ("/work/daily-dirs/<daily_dir_id>", _update_daily_dir, ["PATCH"], "更新 Work 日常目录"),
        ("/work/daily-dirs/<daily_dir_id>", _delete_daily_dir, ["DELETE"], "归档 Work 日常目录"),
        ("/work/tasks", _list_tasks, ["GET"], "Work 任务列表"),
        ("/work/tasks", _create_task, ["POST"], "创建 Work 任务"),
        ("/work/tasks/<task_id>", _get_task, ["GET"], "获取 Work 任务详情"),
        ("/work/tasks/<task_id>/events", _task_events, ["GET"], "Work 任务事件流"),
        ("/work/tasks/<task_id>/input", _submit_input, ["POST"], "Work 任务补充信息"),
        ("/work/tasks/<task_id>/hitl", _respond_hitl, ["POST"], "Work HITL 响应"),
        ("/work/tasks/<task_id>/artifacts", _list_artifacts, ["GET"], "Work 任务交付物"),
    ]
    for path, handler, methods, desc in routes:
        plugin.context.register_web_api(path, handler, methods, desc)
    logger.info("Work mode API routes registered")


def _get_work_service():
    from ..database import get_database
    from ..services.work_service import WorkService

    db = get_database()
    return WorkService(db, _plugin_ref.context if _plugin_ref else None)


async def _list_projects():
    try:
        include_inactive = request.args.get("include_inactive") == "1"
        return Response().ok(_get_work_service().list_projects(include_inactive)).__dict__
    except Exception as e:
        logger.error(f"Failed to list work projects: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_project():
    try:
        data = await request.get_json() or {}
        return Response().ok(_get_work_service().create_project(data), "项目创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create work project: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_project(project_id: str):
    try:
        data = await request.get_json() or {}
        return Response().ok(_get_work_service().update_project(project_id, data), "项目已更新").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update work project {project_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _delete_project(project_id: str):
    try:
        ok = _get_work_service().delete_project(project_id)
        if not ok:
            return Response().error(f"项目 '{project_id}' 不存在").__dict__
        return Response().ok({"success": True}, "项目已归档").__dict__
    except Exception as e:
        logger.error(f"Failed to delete work project {project_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_daily_dirs():
    try:
        include_inactive = request.args.get("include_inactive") == "1"
        return Response().ok(_get_work_service().list_daily_dirs(include_inactive)).__dict__
    except Exception as e:
        logger.error(f"Failed to list daily dirs: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_daily_dir():
    try:
        data = await request.get_json() or {}
        return Response().ok(_get_work_service().create_daily_dir(data), "日常目录创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create daily dir: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_daily_dir(daily_dir_id: str):
    try:
        data = await request.get_json() or {}
        return Response().ok(_get_work_service().update_daily_dir(daily_dir_id, data), "日常目录已更新").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update daily dir {daily_dir_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _delete_daily_dir(daily_dir_id: str):
    try:
        ok = _get_work_service().delete_daily_dir(daily_dir_id)
        if not ok:
            return Response().error(f"日常目录 '{daily_dir_id}' 不存在").__dict__
        return Response().ok({"success": True}, "日常目录已归档").__dict__
    except Exception as e:
        logger.error(f"Failed to delete daily dir {daily_dir_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_tasks():
    try:
        return Response().ok(_get_work_service().list_tasks(dict(request.args))).__dict__
    except Exception as e:
        logger.error(f"Failed to list work tasks: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_task():
    try:
        data = await request.get_json() or {}
        task = await _get_work_service().create_task(data)
        return Response().ok(task, "任务创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create work task: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_task(task_id: str):
    try:
        logs_limit = request.args.get("logs_limit", type=int)
        return Response().ok(_get_work_service().get_task(task_id, logs_limit=logs_limit)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to get work task {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _submit_input(task_id: str):
    try:
        data = await request.get_json() or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return Response().error("补充信息不能为空").__dict__
        return Response().ok(_get_work_service().submit_input(task_id, text), "补充信息已提交").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to submit work task input {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _respond_hitl(task_id: str):
    try:
        data = await request.get_json() or {}
        return Response().ok(await _get_work_service().respond_hitl(task_id, data), "已提交人工确认").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to respond work HITL {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_artifacts(task_id: str):
    try:
        return Response().ok(_get_work_service().list_artifacts(task_id)).__dict__
    except Exception as e:
        logger.error(f"Failed to list work artifacts {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _task_events(task_id: str):
    async def event_generator():
        service = _get_work_service()
        try:
            task = service.get_task(task_id, logs_limit=200)
            existing_logs = task.get("logs", [])
            seen_logs: set[str] = {log.get("id") for log in existing_logs if log.get("id")}
            seen_artifacts: set[str] = {a.get("id") for a in task.get("artifacts", []) if a.get("id")}
            last_status = task.get("status", "")
            yield _sse("phase", {"status": last_status, "progress": task.get("progress", 0)})
        except Exception:
            seen_logs = set()
            seen_artifacts = set()
            last_status = ""
        for _ in range(3600):
            try:
                task = service.get_task(task_id, logs_limit=200)
                if task.get("status") != last_status:
                    last_status = task.get("status", "")
                    yield _sse("phase", {"status": last_status, "progress": task.get("progress", 0)})

                for log in task.get("logs", []):
                    log_id = log.get("id")
                    if log_id and log_id not in seen_logs:
                        seen_logs.add(log_id)
                        event_name = log.get("data", {}).get("event") or "log"
                        yield _sse(event_name, log)

                for artifact in task.get("artifacts", []):
                    artifact_id = artifact.get("id")
                    if artifact_id and artifact_id not in seen_artifacts:
                        seen_artifacts.add(artifact_id)
                        yield _sse("artifact", artifact)

                if last_status in ("completed", "failed", "cancelled"):
                    yield _sse("done", {"status": last_status})
                    break
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                break
            await asyncio.sleep(1)
        yield _sse("heartbeat", {})

    response = QuartResponse(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    response.timeout = None
    return response


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
