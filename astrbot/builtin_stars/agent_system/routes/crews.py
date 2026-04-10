"""
智能体管理模块 - Crew 管理路由

提供 Crew 管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_instance: "AgentSystemPlugin | None" = None


def register_crew_routes(plugin: "AgentSystemPlugin") -> None:
    global _plugin_instance
    _plugin_instance = plugin

    plugin.context.register_web_api(
        "/agent/crews",
        _list_crews,
        ["GET"],
        "获取 Crew 列表"
    )

    plugin.context.register_web_api(
        "/agent/crews/<crew_id>",
        _get_crew,
        ["GET"],
        "获取 Crew 详情"
    )

    plugin.context.register_web_api(
        "/agent/crews/add",
        _create_crew,
        ["POST"],
        "创建 Crew"
    )

    plugin.context.register_web_api(
        "/agent/crews/update",
        _update_crew,
        ["POST"],
        "更新 Crew"
    )

    plugin.context.register_web_api(
        "/agent/crews/delete",
        _delete_crew,
        ["POST"],
        "删除 Crew"
    )

    plugin.context.register_web_api(
        "/agent/crews/execute",
        _execute_crew,
        ["POST"],
        "执行 Crew 任务"
    )

    plugin.context.register_web_api(
        "/agent/crews/test",
        _test_crew,
        ["POST"],
        "测试 Crew"
    )

    plugin.context.register_web_api(
        "/agent/crews/templates",
        _get_templates,
        ["GET"],
        "获取 Crew 模板"
    )

    plugin.context.register_web_api(
        "/agent/crews/import",
        _import_crews,
        ["POST"],
        "导入 Crew"
    )

    logger.info("Crew management API routes registered")


def _get_crew_service():
    from ..services.crew_service import CrewService
    from ..database import get_database

    db = get_database()
    context = None
    if _plugin_instance and _plugin_instance.context:
        context = _plugin_instance.context

    return CrewService(db, context)


async def _list_crews():
    try:
        service = _get_crew_service()
        enabled_only = request.args.get("enabled_only", "false").lower() == "true"
        crews = service.get_crews(enabled_only)
        return Response().ok([c.to_dict() for c in crews]).__dict__
    except Exception as e:
        logger.error(f"Failed to list crews: {e}")
        return Response().error(str(e)).__dict__


async def _get_crew(crew_id: str):
    try:
        service = _get_crew_service()
        crew = service.get_crew(crew_id)
        if not crew:
            return Response().error(f"Crew '{crew_id}' 不存在").__dict__

        from ..database import get_database
        db = get_database()
        tasks = []
        for task_id in crew.tasks:
            task_row = db.select_one("crew_tasks", where="id = ?", where_params=(task_id,))
            if task_row:
                tasks.append({
                    "id": task_row["id"],
                    "name": task_row["name"],
                    "description": task_row.get("description", ""),
                    "expected_output": task_row.get("expected_output", ""),
                    "agent_id": task_row.get("agent_id"),
                    "tools": _parse_json(task_row.get("tools", "[]")),
                    "context": _parse_json(task_row.get("context", "[]")),
                    "async_execution": bool(task_row.get("async_execution", 0)),
                    "config": _parse_json(task_row.get("config", "{}")),
                })

        crew_dict = crew.to_dict()
        crew_dict["task_details"] = tasks
        return Response().ok(crew_dict).__dict__
    except Exception as e:
        logger.error(f"Failed to get crew {crew_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_crew():
    try:
        service = _get_crew_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        crew = service.create_crew(data)
        return Response().ok(crew.to_dict(), "Crew 创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create crew: {e}")
        return Response().error(str(e)).__dict__


async def _update_crew():
    try:
        service = _get_crew_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        crew_id = data.get("id") or data.get("crew_id")
        if not crew_id:
            return Response().error("缺少 Crew ID").__dict__

        crew = service.update_crew(crew_id, data)
        if not crew:
            return Response().error(f"Crew '{crew_id}' 不存在").__dict__

        return Response().ok(crew.to_dict(), "Crew 更新成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update crew: {e}")
        return Response().error(str(e)).__dict__


async def _delete_crew():
    try:
        service = _get_crew_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        crew_id = data.get("id") or data.get("crew_id")
        if not crew_id:
            return Response().error("缺少 Crew ID").__dict__

        success = service.delete_crew(crew_id)
        if not success:
            return Response().error(f"Crew '{crew_id}' 不存在").__dict__

        return Response().ok(None, "Crew 删除成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete crew: {e}")
        return Response().error(str(e)).__dict__


async def _execute_crew():
    try:
        service = _get_crew_service()
        data = await request.get_json() or {}

        crew_id = data.get("id") or data.get("crew_id")
        if not crew_id:
            return Response().error("缺少 Crew ID").__dict__

        result = await service.execute_crew(crew_id, data)
        return Response().ok(result).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to execute crew: {e}")
        return Response().error(str(e)).__dict__


async def _test_crew():
    try:
        service = _get_crew_service()
        data = await request.get_json() or {}

        crew_id = data.get("id") or data.get("crew_id")
        if not crew_id:
            return Response().error("缺少 Crew ID").__dict__

        result = await service.test_crew(crew_id)
        return Response().ok(result).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to test crew: {e}")
        return Response().error(str(e)).__dict__


async def _get_templates():
    try:
        service = _get_crew_service()
        templates = service.get_templates()
        return Response().ok(templates).__dict__
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        return Response().error(str(e)).__dict__


async def _import_crews():
    try:
        service = _get_crew_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        crews_data = data.get("crews", [])
        if not crews_data:
            return Response().error("Crew 列表不能为空").__dict__

        imported = service.import_crews(crews_data)
        return Response().ok(
            [c.to_dict() for c in imported],
            f"成功导入 {len(imported)} 个 Crew"
        ).__dict__
    except Exception as e:
        logger.error(f"Failed to import crews: {e}")
        return Response().error(str(e)).__dict__


def _parse_json(value: str | dict | list | None) -> dict | list:
    import json
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
