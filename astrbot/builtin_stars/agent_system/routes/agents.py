"""
智能体管理模块 - 智能体管理路由

提供智能体管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

# 全局插件实例引用，用于获取 Context
_plugin_instance: "AgentSystemPlugin | None" = None


def register_agent_routes(plugin: "AgentSystemPlugin") -> None:
    """注册智能体管理 API 路由

    Args:
        plugin: 插件实例
    """
    global _plugin_instance
    _plugin_instance = plugin

    # 注册智能体列表 API
    plugin.context.register_web_api(
        "/agent/agents",
        _list_agents,
        ["GET"],
        "获取智能体列表"
    )

    # 注册智能体详情 API
    plugin.context.register_web_api(
        "/agent/agents/<agent_id>",
        _get_agent,
        ["GET"],
        "获取智能体详情"
    )

    # 注册创建智能体 API
    plugin.context.register_web_api(
        "/agent/agents/add",
        _create_agent,
        ["POST"],
        "创建智能体"
    )

    # 注册更新智能体 API
    plugin.context.register_web_api(
        "/agent/agents/update",
        _update_agent,
        ["POST"],
        "更新智能体"
    )

    # 注册删除智能体 API
    plugin.context.register_web_api(
        "/agent/agents/delete",
        _delete_agent,
        ["POST"],
        "删除智能体"
    )

    # 注册切换智能体状态 API
    plugin.context.register_web_api(
        "/agent/agents/toggle",
        _toggle_agent,
        ["POST"],
        "切换智能体启用/禁用状态"
    )

    # 注册测试智能体 API
    plugin.context.register_web_api(
        "/agent/agents/test",
        _test_agent,
        ["POST"],
        "测试智能体"
    )

    # 注册复制智能体 API
    plugin.context.register_web_api(
        "/agent/agents/duplicate",
        _duplicate_agent,
        ["POST"],
        "复制智能体"
    )

    # 注册智能体模板 API
    plugin.context.register_web_api(
        "/agent/agents/templates",
        _get_templates,
        ["GET"],
        "获取智能体模板"
    )

    # 注册获取提供商列表 API
    plugin.context.register_web_api(
        "/agent/agents/providers",
        _get_providers,
        ["GET"],
        "获取可用的 LLM 提供商列表"
    )

    # 注册导入智能体 API
    plugin.context.register_web_api(
        "/agent/agents/import",
        _import_agents,
        ["POST"],
        "导入智能体"
    )

    logger.info("Agent management API routes registered")


def _get_agent_service():
    """获取 AgentService 实例"""
    from ..services.agent_service import AgentService
    from ..database import get_database

    db = get_database()

    # 获取 Context
    context = None
    if _plugin_instance and _plugin_instance.context:
        context = _plugin_instance.context

    return AgentService(db, context)


async def _list_agents():
    """获取智能体列表

    Query Parameters:
        category: 分类筛选（可选，按 metadata.category 筛选）
    """
    try:
        service = _get_agent_service()

        category = request.args.get("category")
        agents = service.get_agents(category)

        return Response().ok([a.to_dict() for a in agents]).__dict__

    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return Response().error(str(e)).__dict__


async def _get_agent(agent_id: str):
    """获取智能体详情

    Args:
        agent_id: 智能体 ID
    """
    try:
        service = _get_agent_service()

        agent = service.get_agent(agent_id)
        if not agent:
            return Response().error(f"智能体 '{agent_id}' 不存在").__dict__

        return Response().ok(agent.to_dict()).__dict__

    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_agent():
    """创建智能体

    Request Body:
        {
            "name": "智能体名称",
            "role": "角色定义",
            "goal": "目标",
            "backstory": "背景故事",
            "tools": ["tool_id_1", "tool_id_2"],
            "skills": ["skill_id_1"],
            "knowledge_id": "kb_xxx",
            "provider_id": "provider_xxx",
            "model_name": "gpt-4",
            "llm_config": {...},
            "memory_config": {...},
            "planning": false,
            "planning_effort": "medium",
            "max_iter": 20,
            "max_rpm": null,
            "verbose": false,
            "allow_delegation": false,
            "enabled": true,
            "metadata": {...}
        }
    """
    try:
        service = _get_agent_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        agent = service.create_agent(data)
        return Response().ok(agent.to_dict(), "智能体创建成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return Response().error(str(e)).__dict__


async def _update_agent():
    """更新智能体

    Request Body:
        {
            "id": "智能体ID",
            "name": "智能体名称",
            ...
        }
    """
    try:
        service = _get_agent_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            return Response().error("缺少智能体 ID").__dict__

        agent = service.update_agent(agent_id, data)
        if not agent:
            return Response().error(f"智能体 '{agent_id}' 不存在").__dict__

        return Response().ok(agent.to_dict(), "智能体更新成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update agent: {e}")
        return Response().error(str(e)).__dict__


async def _delete_agent():
    """删除智能体

    Request Body:
        {
            "id": "智能体ID"
        }
    """
    try:
        service = _get_agent_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            return Response().error("缺少智能体 ID").__dict__

        success = service.delete_agent(agent_id)
        if not success:
            return Response().error(f"智能体 '{agent_id}' 不存在").__dict__

        return Response().ok(None, "智能体删除成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        return Response().error(str(e)).__dict__


async def _toggle_agent():
    try:
        service = _get_agent_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            return Response().error("缺少智能体 ID").__dict__

        agent = service.get_agent(agent_id)
        if not agent:
            return Response().error(f"智能体 '{agent_id}' 不存在").__dict__

        enabled = not getattr(agent, 'enabled', True)
        updated = service.update_agent(agent_id, {"enabled": enabled})
        return Response().ok(updated.to_dict(), "状态切换成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to toggle agent: {e}")
        return Response().error(str(e)).__dict__


async def _test_agent():
    """测试智能体

    Request Body:
        {
            "id": "智能体ID",
            "message": "测试消息内容"
        }
    """
    try:
        service = _get_agent_service()

        data = await request.get_json() or {}
        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            return Response().error("缺少智能体 ID").__dict__

        message = data.get("message")
        if not message:
            return Response().error("测试消息不能为空").__dict__

        result = await service.test_agent(agent_id, message)
        return Response().ok(result).__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to test agent: {e}")
        return Response().error(str(e)).__dict__


async def _duplicate_agent():
    """复制智能体

    Request Body:
        {
            "id": "智能体ID"
        }
    """
    try:
        service = _get_agent_service()

        data = await request.get_json() or {}
        agent_id = data.get("id") or data.get("agent_id")
        if not agent_id:
            return Response().error("缺少智能体 ID").__dict__

        agent = service.duplicate_agent(agent_id)
        return Response().ok(agent.to_dict(), "智能体复制成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to duplicate agent: {e}")
        return Response().error(str(e)).__dict__


async def _get_templates():
    """获取智能体模板列表"""
    try:
        service = _get_agent_service()
        templates = service.get_templates()
        return Response().ok(templates).__dict__

    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        return Response().error(str(e)).__dict__


async def _get_providers():
    """获取可用的 LLM 提供商列表"""
    try:
        service = _get_agent_service()
        providers = service.get_providers()
        return Response().ok(providers).__dict__

    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        return Response().error(str(e)).__dict__


async def _import_agents():
    try:
        service = _get_agent_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        agents_data = data.get("agents", [])
        if not agents_data:
            return Response().error("智能体列表不能为空").__dict__

        imported = service.import_agents(agents_data)
        return Response().ok(
            [a.to_dict() for a in imported],
            f"成功导入 {len(imported)} 个智能体"
        ).__dict__
    except Exception as e:
        logger.error(f"Failed to import agents: {e}")
        return Response().error(str(e)).__dict__
