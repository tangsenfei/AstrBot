"""
智能体管理模块 - Flow 管理路由

提供 Flow 编排相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_instance: "AgentSystemPlugin | None" = None


def register_flow_routes(plugin: "AgentSystemPlugin") -> None:
    global _plugin_instance
    _plugin_instance = plugin

    plugin.context.register_web_api(
        "/agent/flows",
        _list_flows,
        ["GET"],
        "获取 Flow 列表"
    )

    plugin.context.register_web_api(
        "/agent/flows/<flow_id>",
        _get_flow,
        ["GET"],
        "获取 Flow 详情"
    )

    plugin.context.register_web_api(
        "/agent/flows/<flow_id>",
        _patch_flow,
        ["PATCH"],
        "更新 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/add",
        _create_flow,
        ["POST"],
        "创建 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/update",
        _update_flow,
        ["POST"],
        "更新 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/delete",
        _delete_flow,
        ["POST"],
        "删除 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/toggle",
        _toggle_flow,
        ["POST"],
        "切换 Flow 启用/禁用状态"
    )

    plugin.context.register_web_api(
        "/agent/flows/validate",
        _validate_flow,
        ["POST"],
        "验证 Flow 配置"
    )

    plugin.context.register_web_api(
        "/agent/flows/simulate",
        _simulate_flow,
        ["POST"],
        "模拟 Flow 执行"
    )

    plugin.context.register_web_api(
        "/agent/flows/execute",
        _execute_flow,
        ["POST"],
        "执行 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/import",
        _import_flows,
        ["POST"],
        "导入 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/export",
        _export_flows,
        ["GET"],
        "导出 Flow"
    )

    plugin.context.register_web_api(
        "/agent/flows/templates",
        _get_flow_templates,
        ["GET"],
        "获取流程模板列表"
    )

    plugin.context.register_web_api(
        "/agent/flows/generate",
        _generate_flow,
        ["POST"],
        "根据描述生成流程"
    )

    plugin.context.register_web_api(
        "/agent/flows/<flow_id>/reset-builtin",
        _reset_builtin_flow,
        ["POST"],
        "初始化/还原内置流程"
    )

    plugin.context.register_web_api(
        "/agent/hitl-templates",
        _list_hitl_templates,
        ["GET", "POST"],
        "管理 HITL 模板"
    )

    plugin.context.register_web_api(
        "/agent/hitl-templates/<template_id>",
        _update_hitl_template,
        ["PATCH", "POST"],
        "更新 HITL 模板"
    )

    logger.info("Flow management API routes registered")


def _get_flow_service():
    from ..services.flow_service import FlowService
    from ..services.crew_service import CrewService
    from ..database import get_database

    db = get_database()
    context = None
    if _plugin_instance and _plugin_instance.context:
        context = _plugin_instance.context

    crew_service = CrewService(db, context)
    return FlowService(db, context, crew_service)


async def _list_flows():
    try:
        service = _get_flow_service()
        enabled_only = request.args.get("enabled_only", "false").lower() == "true"
        flows = service.get_flows(enabled_only)
        return Response().ok([f.to_dict() for f in flows]).__dict__
    except Exception as e:
        logger.error(f"Failed to list flows: {e}")
        return Response().error(str(e)).__dict__


async def _get_flow(flow_id: str):
    try:
        service = _get_flow_service()
        flow = service.get_flow(flow_id)
        if not flow:
            return Response().error(f"Flow '{flow_id}' 不存在").__dict__
        return Response().ok(flow.to_dict()).__dict__
    except Exception as e:
        logger.error(f"Failed to get flow {flow_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        flow = service.create_flow(data)
        return Response().ok(flow.to_dict(), "Flow 创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create flow: {e}")
        return Response().error(str(e)).__dict__


async def _update_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        flow = service.update_flow(flow_id, data)
        if not flow:
            return Response().error(f"Flow '{flow_id}' 不存在").__dict__

        return Response().ok(flow.to_dict(), "Flow 更新成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update flow: {e}")
        return Response().error(str(e)).__dict__


async def _delete_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        success = service.delete_flow(flow_id)
        if not success:
            return Response().error(f"Flow '{flow_id}' 不存在").__dict__

        return Response().ok(None, "Flow 删除成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete flow: {e}")
        return Response().error(str(e)).__dict__


async def _toggle_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        flow = service.get_flow(flow_id)
        if not flow:
            return Response().error(f"Flow '{flow_id}' 不存在").__dict__
        if flow.metadata.get("is_builtin") or flow.metadata.get("non_deletable"):
            return Response().error("内置 Flow 不允许禁用").__dict__

        enabled = not getattr(flow, 'enabled', True)
        updated = service.update_flow(flow_id, {"enabled": enabled})
        return Response().ok(updated.to_dict(), "状态切换成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to toggle flow: {e}")
        return Response().error(str(e)).__dict__


async def _patch_flow(flow_id: str):
    try:
        service = _get_flow_service()
        data = await request.get_json() or {}
        data["id"] = flow_id
        flow = service.update_flow(flow_id, data)
        if not flow:
            return Response().error(f"Flow '{flow_id}' 不存在").__dict__
        return Response().ok(flow.to_dict(), "Flow 更新成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to patch flow {flow_id}: {e}")
        return Response().error(str(e)).__dict__


async def _reset_builtin_flow(flow_id: str):
    try:
        service = _get_flow_service()
        from ..services.flow_service import BUILTIN_DAILY_WORK_FLOW_ID

        if flow_id != BUILTIN_DAILY_WORK_FLOW_ID:
            return Response().error("该 Flow 不是可初始化的内置流程").__dict__
        flow = service.reset_builtin_daily_work_flow()
        return Response().ok(flow.to_dict(), "内置流程已初始化").__dict__
    except Exception as e:
        logger.error(f"Failed to reset builtin flow {flow_id}: {e}")
        return Response().error(str(e)).__dict__


def _get_hitl_template_service():
    from ..database import get_database
    from ..services.hitl_template_service import HITLTemplateService

    return HITLTemplateService(get_database())


async def _list_hitl_templates():
    try:
        service = _get_hitl_template_service()
        if request.method == "POST":
            data = await request.get_json() or {}
            template = service.save_template(data)
            return Response().ok(template, "HITL 模板已保存").__dict__
        template_type = request.args.get("type") or request.args.get("template_type")
        return Response().ok(service.list_templates(template_type)).__dict__
    except Exception as e:
        logger.error(f"Failed to manage HITL templates: {e}")
        return Response().error(str(e)).__dict__


async def _update_hitl_template(template_id: str):
    try:
        service = _get_hitl_template_service()
        data = await request.get_json() or {}
        data["id"] = template_id
        if data.get("reset_builtin"):
            template = service.reset_builtin_template(template_id)
            if not template:
                return Response().error("该 HITL 模板不可初始化").__dict__
        else:
            template = service.save_template(data)
        return Response().ok(template, "HITL 模板已更新").__dict__
    except Exception as e:
        logger.error(f"Failed to update HITL template {template_id}: {e}")
        return Response().error(str(e)).__dict__


async def _validate_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json() or {}

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        result = service.validate_flow(flow_id)
        return Response().ok(result).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to validate flow: {e}")
        return Response().error(str(e)).__dict__


async def _simulate_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json() or {}

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        input_data = data.get("input", {})
        result = service.simulate_flow(flow_id, input_data)
        return Response().ok(result).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to simulate flow: {e}")
        return Response().error(str(e)).__dict__


async def _execute_flow():
    try:
        service = _get_flow_service()
        data = await request.get_json() or {}

        flow_id = data.get("id") or data.get("flow_id")
        if not flow_id:
            return Response().error("缺少 Flow ID").__dict__

        result = await service.execute_flow(flow_id, data)
        return Response().ok(result).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to execute flow: {e}")
        return Response().error(str(e)).__dict__


async def _import_flows():
    try:
        service = _get_flow_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        flows_data = data.get("flows", [])
        if not flows_data:
            return Response().error("Flow 列表不能为空").__dict__

        imported_flows = service.import_flows(flows_data)
        return Response().ok(
            [f.to_dict() for f in imported_flows],
            f"成功导入 {len(imported_flows)} 个 Flow"
        ).__dict__
    except Exception as e:
        logger.error(f"Failed to import flows: {e}")
        return Response().error(str(e)).__dict__


async def _export_flows():
    try:
        service = _get_flow_service()
        ids_param = request.args.get("ids")
        flow_ids = ids_param.split(",") if ids_param else None
        exported = service.export_flows(flow_ids)
        return Response().ok(exported).__dict__
    except Exception as e:
        logger.error(f"Failed to export flows: {e}")
        return Response().error(str(e)).__dict__


def _get_flow_generator():
    from ..services.flow_generator_skill import FlowGeneratorSkill
    return FlowGeneratorSkill()


async def _get_flow_templates():
    try:
        generator = _get_flow_generator()
        templates = generator.get_flow_templates()
        return Response().ok(templates).__dict__
    except Exception as e:
        logger.error(f"Failed to get flow templates: {e}")
        return Response().error(str(e)).__dict__


async def _generate_flow():
    try:
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        description = data.get("description", "")
        if not description:
            return Response().error("描述不能为空").__dict__

        generator = _get_flow_generator()
        flow_def = generator.generate_flow(description)
        return Response().ok(flow_def, "流程生成成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to generate flow: {e}")
        return Response().error(str(e)).__dict__
