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
        (
            "/work/daily-dirs/<daily_dir_id>",
            _update_daily_dir,
            ["PATCH"],
            "更新 Work 日常目录",
        ),
        (
            "/work/daily-dirs/<daily_dir_id>",
            _delete_daily_dir,
            ["DELETE"],
            "归档 Work 日常目录",
        ),
        ("/work/tasks", _list_tasks, ["GET"], "Work 任务列表"),
        ("/work/tasks/summaries", _list_task_summaries, ["GET"], "Work 任务摘要列表"),
        (
            "/work/tasks/pending-hitl-count",
            _pending_hitl_count,
            ["GET"],
            "Work HITL 待处理数量",
        ),
        ("/work/config", _get_work_config, ["GET"], "获取 Work 配置"),
        ("/work/config", _update_work_config, ["PUT"], "更新 Work 配置"),
        ("/work/config/reset", _reset_work_config, ["POST"], "重置 Work 配置"),
        (
            "/work/tasks/history",
            _clear_work_history,
            ["DELETE"],
            "清理 Work 运行历史",
        ),
        ("/work/tasks", _create_task, ["POST"], "创建 Work 任务"),
        ("/work/tasks/<task_id>", _get_task, ["GET"], "获取 Work 任务详情"),
        ("/work/tasks/<task_id>/pause", _pause_task, ["POST"], "暂停 Work 任务"),
        ("/work/tasks/<task_id>/resume", _resume_task, ["POST"], "继续 Work 任务"),
        ("/work/tasks/<task_id>/terminate", _terminate_task, ["POST"], "终止 Work 任务"),
        ("/work/tasks/<task_id>/logs", _list_task_logs, ["GET"], "获取 Work 任务日志"),
        ("/work/tasks/<task_id>/events", _task_events, ["GET"], "Work 任务事件流"),
        ("/work/tasks/<task_id>/input", _submit_input, ["POST"], "Work 任务补充信息"),
        (
            "/work/tasks/<task_id>/nodes/<node_id>/retry",
            _retry_node,
            ["POST"],
            "重试 Work 节点",
        ),
        ("/work/tasks/<task_id>/hitl", _respond_hitl, ["POST"], "Work HITL 响应"),
        (
            "/work/tasks/<task_id>/artifacts",
            _list_artifacts,
            ["GET"],
            "Work 任务交付物",
        ),
        ("/hitl", _list_hitl, ["GET"], "HITL 请求列表"),
        (
            "/hitl/<interaction_id>/respond",
            _respond_hitl_by_id,
            ["POST"],
            "HITL 统一响应",
        ),
    ]
    for path, handler, methods, desc in routes:
        plugin.context.register_web_api(path, handler, methods, desc)
    logger.info("Work mode API routes registered")


def _get_work_service():
    from ..database import get_database
    from ..services.work_service import WorkService

    db = get_database()
    return WorkService(db, _plugin_ref.context if _plugin_ref else None)


def _get_work_config_service():
    from ..database import get_database
    from ..services.work_config_service import WorkConfigService

    return WorkConfigService(get_database())


async def _list_projects():
    try:
        include_inactive = request.args.get("include_inactive") == "1"
        return (
            Response().ok(_get_work_service().list_projects(include_inactive)).__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list work projects: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_project():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_work_service().create_project(data), "项目创建成功")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create work project: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_project(project_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_work_service().update_project(project_id, data), "项目已更新")
            .__dict__
        )
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
        return (
            Response()
            .ok(_get_work_service().list_daily_dirs(include_inactive))
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list daily dirs: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_daily_dir():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_work_service().create_daily_dir(data), "日常目录创建成功")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create daily dir: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_daily_dir(daily_dir_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(
                _get_work_service().update_daily_dir(daily_dir_id, data),
                "日常目录已更新",
            )
            .__dict__
        )
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
        return (
            Response().ok(_get_work_service().list_tasks(dict(request.args))).__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list work tasks: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_task_summaries():
    try:
        return (
            Response()
            .ok({"tasks": _get_work_service().list_task_summaries(_ids_from_request())})
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list work task summaries: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _pending_hitl_count():
    try:
        return Response().ok(_get_work_service().pending_hitl_count()).__dict__
    except Exception as e:
        logger.error(f"Failed to count pending work HITL requests: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_work_config():
    try:
        return Response().ok(_get_work_config_service().get_config()).__dict__
    except Exception as e:
        logger.error(f"Failed to get work config: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_work_config():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_work_config_service().update_config(data), "Work 配置已保存")
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to update work config: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _reset_work_config():
    try:
        return (
            Response()
            .ok(_get_work_config_service().reset_config(), "Work 配置已重置")
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to reset work config: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _clear_work_history():
    try:
        return (
            Response()
            .ok(_get_work_service().clear_work_history(), "Work 运行历史已清理")
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to clear work history: {e}", exc_info=True)
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
        return (
            Response()
            .ok(_get_work_service().get_task(task_id, logs_limit=logs_limit))
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to get work task {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _pause_task(task_id: str):
    try:
        return (
            Response()
            .ok(await _get_work_service().pause_task(task_id), "任务已请求暂停")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to pause work task {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _resume_task(task_id: str):
    try:
        return (
            Response()
            .ok(await _get_work_service().resume_task(task_id), "任务已继续")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to resume work task {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _terminate_task(task_id: str):
    try:
        return (
            Response()
            .ok(await _get_work_service().terminate_task(task_id), "任务已终止")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to terminate work task {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_task_logs(task_id: str):
    try:
        limit = request.args.get("limit", type=int)
        before_seq = request.args.get("before_seq", type=int)
        after_seq = request.args.get("after_seq", type=int)
        return (
            Response()
            .ok(
                _get_work_service().get_task_logs(
                    task_id,
                    logs_limit=limit,
                    before_seq=before_seq,
                    after_seq=after_seq,
                )
            )
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list work task logs {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _submit_input(task_id: str):
    try:
        data = await request.get_json() or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return Response().error("补充信息不能为空").__dict__
        return (
            Response()
            .ok(_get_work_service().submit_input(task_id, text), "补充信息已提交")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to submit work task input {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _retry_node(task_id: str, node_id: str):
    try:
        return (
            Response()
            .ok(await _get_work_service().retry_node(task_id, node_id), "节点已重新提交")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to retry work node {task_id}/{node_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _respond_hitl(task_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(await _get_work_service().respond_hitl(task_id, data), "已提交人工确认")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to respond work HITL {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_hitl():
    try:
        from ..database import get_database
        from ..services.hitl_service import HITLService

        task_id = request.args.get("task_id")
        return Response().ok(HITLService(get_database()).list_pending(task_id)).__dict__
    except Exception as e:
        logger.error(f"Failed to list HITL requests: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _respond_hitl_by_id(interaction_id: str):
    try:
        from ..database import get_database
        from ..services.hitl_service import HITLService

        data = await request.get_json() or {}
        result = await HITLService(get_database()).respond(
            interaction_id,
            data.get("action_key", "approve"),
            data.get("field_values", {}),
        )
        return Response().ok(result, "已提交人工确认").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to respond HITL {interaction_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_artifacts(task_id: str):
    try:
        return Response().ok(_get_work_service().list_artifacts(task_id)).__dict__
    except Exception as e:
        logger.error(f"Failed to list work artifacts {task_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _task_events(task_id: str):
    requested_after_seq = request.args.get("after_seq", type=int) or 0

    async def event_generator():
        service = _get_work_service()
        try:
            task = _task_event_snapshot(service, task_id)
            after_seq = requested_after_seq
            seen_artifacts: set[str] = set(_artifact_ids(service, task_id))
            last_status = task.get("status", "")
            yield _sse(
                "phase", {"status": last_status, "progress": task.get("progress", 0)}
            )
        except Exception:
            after_seq = 0
            seen_artifacts = set()
            last_status = ""
        for _ in range(3600):
            try:
                task = _task_event_snapshot(service, task_id)
                if task.get("status") != last_status:
                    last_status = task.get("status", "")
                    yield _sse(
                        "phase",
                        {"status": last_status, "progress": task.get("progress", 0)},
                    )

                for log in service.get_task_logs(
                    task_id, logs_limit=300, after_seq=after_seq
                ):
                    after_seq = max(after_seq, int(log.get("seq") or 0))
                    event_name = log.get("data", {}).get("event") or "log"
                    yield _sse(event_name, log)

                new_artifact_ids = [
                    artifact_id
                    for artifact_id in _artifact_ids(service, task_id)
                    if artifact_id not in seen_artifacts
                ]
                if new_artifact_ids:
                    artifacts = {
                        artifact.get("id"): artifact
                        for artifact in service.list_artifacts(task_id)
                    }
                    for artifact_id in new_artifact_ids:
                        seen_artifacts.add(artifact_id)
                        artifact = artifacts.get(artifact_id)
                        if artifact:
                            yield _sse("artifact", artifact)

                if last_status in ("completed", "failed", "retryable_failed", "cancelled"):
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


def _task_event_snapshot(service, task_id: str) -> dict:
    row = service.db.select_one(
        "agent_tasks",
        where="id = ?",
        where_params=(task_id,),
    )
    if not row:
        return {"status": "failed", "progress": 0}
    return {"status": row.get("status", ""), "progress": row.get("progress", 0)}


def _artifact_ids(service, task_id: str) -> list[str]:
    rows = service.db.execute(
        "SELECT id FROM work_artifacts WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ids_from_request() -> list[str]:
    values = request.args.getlist("ids")
    if not values:
        values = [request.args.get("ids", "")]
    ids: list[str] = []
    for value in values:
        ids.extend(item.strip() for item in str(value).split(",") if item.strip())
    return list(dict.fromkeys(ids))
