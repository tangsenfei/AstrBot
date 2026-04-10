"""
智能体管理模块 - 工具管理路由

提供工具管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_instance: "AgentSystemPlugin | None" = None


def register_tool_routes(plugin: "AgentSystemPlugin") -> None:
    """注册工具管理 API 路由

    Args:
        plugin: 插件实例
    """
    global _plugin_instance
    _plugin_instance = plugin

    plugin.context.register_web_api(
        "/agent/tools",
        _list_tools,
        ["GET"],
        "获取工具列表"
    )

    plugin.context.register_web_api(
        "/agent/tools/<tool_id>",
        _get_tool,
        ["GET"],
        "获取工具详情"
    )

    plugin.context.register_web_api(
        "/agent/tools/add",
        _create_tool,
        ["POST"],
        "创建工具"
    )

    plugin.context.register_web_api(
        "/agent/tools/update",
        _update_tool,
        ["POST"],
        "更新工具"
    )

    plugin.context.register_web_api(
        "/agent/tools/delete",
        _delete_tool,
        ["POST"],
        "删除工具"
    )

    plugin.context.register_web_api(
        "/agent/tools/toggle",
        _toggle_tool,
        ["POST"],
        "切换工具启用/禁用状态"
    )

    plugin.context.register_web_api(
        "/agent/tools/test",
        _test_tool,
        ["POST"],
        "测试工具"
    )

    plugin.context.register_web_api(
        "/agent/tools/import",
        _import_tools,
        ["POST"],
        "导入工具"
    )

    plugin.context.register_web_api(
        "/agent/tools/export",
        _export_tools,
        ["GET"],
        "导出工具"
    )

    logger.info("Tool management API routes registered")


def _get_tool_service():
    """获取 ToolService 实例"""
    from ..services.tool_service import ToolService
    from ..database import get_database

    db = get_database()

    func_tool_manager = None
    if _plugin_instance and _plugin_instance.context:
        func_tool_manager = _plugin_instance.context.get_llm_tool_manager()

    return ToolService(db, func_tool_manager)


async def _list_tools():
    """获取工具列表

    Query Parameters:
        source: 工具来源筛选 (builtin, mcp, custom, api_wrapper)
    """
    try:
        service = _get_tool_service()

        source = request.args.get("source")
        tools = service.get_tools(source)

        return Response().ok([t.to_dict() for t in tools]).__dict__

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        return Response().error(str(e)).__dict__


async def _get_tool(tool_id: str):
    """获取工具详情

    Args:
        tool_id: 工具 ID
    """
    try:
        service = _get_tool_service()

        tool = service.get_tool(tool_id)
        if not tool:
            return Response().error(f"工具 '{tool_id}' 不存在").__dict__

        return Response().ok(tool.to_dict()).__dict__

    except Exception as e:
        logger.error(f"Failed to get tool {tool_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_tool():
    """创建工具

    Request Body:
        {
            "name": "工具名称",
            "description": "工具描述",
            "source": "custom | api_wrapper",
            "parameters": {...},
            "return_type": "string",
            "version": "1.0.0",
            "enabled": true,
            "metadata": {...}
        }
    """
    try:
        service = _get_tool_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        tool = service.create_tool(data)
        return Response().ok(tool.to_dict(), "工具创建成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create tool: {e}")
        return Response().error(str(e)).__dict__


async def _update_tool():
    """更新工具

    Request Body:
        {
            "id": "工具ID",
            "name": "工具名称",
            ...
        }
    """
    try:
        service = _get_tool_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        tool_id = data.get("id") or data.get("tool_id")
        if not tool_id:
            return Response().error("缺少工具 ID").__dict__

        tool = service.update_tool(tool_id, data)
        if not tool:
            return Response().error(f"工具 '{tool_id}' 不存在").__dict__

        return Response().ok(tool.to_dict(), "工具更新成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update tool: {e}")
        return Response().error(str(e)).__dict__


async def _delete_tool():
    """删除工具

    Request Body:
        {
            "id": "工具ID"
        }
    """
    try:
        service = _get_tool_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        tool_id = data.get("id") or data.get("tool_id")
        if not tool_id:
            return Response().error("缺少工具 ID").__dict__

        success = service.delete_tool(tool_id)
        if not success:
            return Response().error(f"工具 '{tool_id}' 不存在").__dict__

        return Response().ok(None, "工具删除成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete tool: {e}")
        return Response().error(str(e)).__dict__


async def _toggle_tool():
    try:
        service = _get_tool_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        tool_id = data.get("id") or data.get("tool_id")
        if not tool_id:
            return Response().error("缺少工具 ID").__dict__

        tool = service.get_tool(tool_id)
        if not tool:
            return Response().error(f"工具 '{tool_id}' 不存在").__dict__

        enabled = not getattr(tool, 'enabled', True)
        updated = service.update_tool(tool_id, {"enabled": enabled})
        return Response().ok(updated.to_dict(), "状态切换成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to toggle tool: {e}")
        return Response().error(str(e)).__dict__


async def _test_tool():
    """测试工具

    Request Body:
        {
            "id": "工具ID",
            "params": {...}
        }
    """
    try:
        service = _get_tool_service()

        data = await request.get_json() or {}
        tool_id = data.get("id") or data.get("tool_id")
        if not tool_id:
            return Response().error("缺少工具 ID").__dict__

        params = data.get("params", {})

        result = await service.test_tool(tool_id, params)
        return Response().ok(result).__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to test tool: {e}")
        return Response().error(str(e)).__dict__


async def _import_tools():
    """批量导入工具

    Request Body:
        {
            "tools": [
                {
                    "name": "工具名称",
                    "description": "工具描述",
                    "source": "custom",
                    "parameters": {...},
                    ...
                },
                ...
            ]
        }
    """
    try:
        service = _get_tool_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        tools_data = data.get("tools", [])
        if not tools_data:
            return Response().error("工具列表不能为空").__dict__

        imported_tools = service.import_tools(tools_data)
        return Response().ok(
            [t.to_dict() for t in imported_tools],
            f"成功导入 {len(imported_tools)} 个工具"
        ).__dict__

    except Exception as e:
        logger.error(f"Failed to import tools: {e}")
        return Response().error(str(e)).__dict__


async def _export_tools():
    """导出工具

    Query Parameters:
        ids: 工具 ID 列表，逗号分隔（可选，不传则导出所有可导出的工具）
    """
    try:
        service = _get_tool_service()

        ids_param = request.args.get("ids")
        tool_ids = ids_param.split(",") if ids_param else None

        exported = service.export_tools(tool_ids)
        return Response().ok(exported).__dict__

    except Exception as e:
        logger.error(f"Failed to export tools: {e}")
        return Response().error(str(e)).__dict__
