"""
智能体管理模块 - 技能管理路由

提供技能管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin


def register_skill_routes(plugin: "AgentSystemPlugin") -> None:
    """注册技能管理 API 路由

    Args:
        plugin: 插件实例
    """
    # 注册技能列表 API
    plugin.context.register_web_api(
        "/agent/skills",
        _list_skills,
        ["GET"],
        "获取技能列表"
    )

    # 注册技能详情 API
    plugin.context.register_web_api(
        "/agent/skills/<skill_id>",
        _get_skill,
        ["GET"],
        "获取技能详情"
    )

    # 注册创建技能 API
    plugin.context.register_web_api(
        "/agent/skills/add",
        _create_skill,
        ["POST"],
        "创建技能"
    )

    # 注册更新技能 API
    plugin.context.register_web_api(
        "/agent/skills/update",
        _update_skill,
        ["POST"],
        "更新技能"
    )

    # 注册删除技能 API
    plugin.context.register_web_api(
        "/agent/skills/delete",
        _delete_skill,
        ["POST"],
        "删除技能"
    )

    # 注册测试技能 API
    plugin.context.register_web_api(
        "/agent/skills/<skill_id>/test",
        _test_skill,
        ["POST"],
        "测试技能"
    )

    # 注册导入技能 API
    plugin.context.register_web_api(
        "/agent/skills/import",
        _import_skills,
        ["POST"],
        "导入技能"
    )

    # 注册导出技能 API
    plugin.context.register_web_api(
        "/agent/skills/export",
        _export_skills,
        ["GET"],
        "导出技能"
    )

    # 注册技能市场 API
    plugin.context.register_web_api(
        "/agent/skills/market",
        _get_skill_market,
        ["GET"],
        "获取社区技能市场"
    )

    # 注册技能分类 API
    plugin.context.register_web_api(
        "/agent/skills/categories",
        _get_categories,
        ["GET"],
        "获取技能分类列表"
    )

    # 注册 AstrBot 技能列表 API
    plugin.context.register_web_api(
        "/agent/skills/astrbot",
        _get_astrbot_skills,
        ["GET"],
        "获取 AstrBot 技能列表"
    )

    # 注册 AstrBot 技能导入 API
    plugin.context.register_web_api(
        "/agent/skills/astrbot/import",
        _import_astrbot_skills,
        ["POST"],
        "导入 AstrBot 技能"
    )

    # 注册 AstrBot 技能同步 API
    plugin.context.register_web_api(
        "/agent/skills/astrbot/sync",
        _sync_astrbot_skills,
        ["POST"],
        "同步 AstrBot 技能"
    )

    logger.info("Skill management API routes registered")


def _get_skill_service():
    """获取 SkillService 实例"""
    from ..services.skill_service import SkillService
    from ..database import get_database

    db = get_database()
    return SkillService(db)


async def _list_skills():
    """获取技能列表

    Query Parameters:
        category: 技能分类筛选
        include_astrbot: 是否包含 AstrBot 技能（默认 true）
    """
    try:
        service = _get_skill_service()

        category = request.args.get("category")
        include_astrbot = request.args.get("include_astrbot", "true").lower() == "true"
        
        if include_astrbot:
            skills = service.get_all_skills_with_astrbot(category)
        else:
            skills = service.get_skills(category)

        return Response().ok([s.to_dict() for s in skills]).__dict__

    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        return Response().error(str(e)).__dict__


async def _get_skill(skill_id: str):
    """获取技能详情

    Args:
        skill_id: 技能 ID
    """
    try:
        service = _get_skill_service()

        skill = service.get_skill(skill_id)
        
        if not skill:
            from ..services.astrbot_skill_adapter import AstrBotSkillAdapter
            if AstrBotSkillAdapter.is_astrbot_skill(skill_id):
                skill = service.get_astrbot_skill_by_id(skill_id)
        
        if not skill:
            return Response().error(f"技能 '{skill_id}' 不存在").__dict__

        return Response().ok(skill.to_dict()).__dict__

    except Exception as e:
        logger.error(f"Failed to get skill {skill_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_skill():
    """创建技能

    Request Body:
        {
            "name": "技能名称",
            "description": "技能描述",
            "category": "general",
            "tools": ["tool_id_1", "tool_id_2"],
            "workflow": {...},
            "disclosure_level": "metadata | instructions | resources",
            "version": "1.0.0",
            "enabled": true,
            "metadata": {...}
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        skill = service.create_skill(data)
        return Response().ok(skill.to_dict(), "技能创建成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create skill: {e}")
        return Response().error(str(e)).__dict__


async def _update_skill():
    """更新技能

    Request Body:
        {
            "id": "技能ID",
            "name": "技能名称",
            "description": "技能描述",
            "category": "general",
            "tools": ["tool_id_1", "tool_id_2"],
            "workflow": {...},
            "disclosure_level": "metadata | instructions | resources",
            "version": "1.0.0",
            "enabled": true,
            "metadata": {...}
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        skill_id = data.get("id") or data.get("skill_id")
        if not skill_id:
            return Response().error("缺少技能 ID").__dict__

        from ..services.astrbot_skill_adapter import AstrBotSkillAdapter
        
        if AstrBotSkillAdapter.is_astrbot_skill(skill_id):
            return Response().error("AstrBot 技能不能修改，请在 AstrBot 技能管理中操作").__dict__

        skill = service.update_skill(skill_id, data)
        if not skill:
            return Response().error(f"技能 '{skill_id}' 不存在").__dict__

        return Response().ok(skill.to_dict(), "技能更新成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update skill: {e}")
        return Response().error(str(e)).__dict__


async def _delete_skill():
    """删除技能

    Request Body:
        {
            "id": "技能ID"
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        skill_id = data.get("id") or data.get("skill_id")
        if not skill_id:
            return Response().error("缺少技能 ID").__dict__

        from ..services.astrbot_skill_adapter import AstrBotSkillAdapter
        
        if AstrBotSkillAdapter.is_astrbot_skill(skill_id):
            return Response().error("AstrBot 技能不能删除，请在 AstrBot 技能管理中操作").__dict__

        success = service.delete_skill(skill_id)
        if not success:
            return Response().error(f"技能 '{skill_id}' 不存在").__dict__

        return Response().ok(None, "技能删除成功").__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete skill: {e}")
        return Response().error(str(e)).__dict__


async def _test_skill(skill_id: str):
    """测试技能

    Args:
        skill_id: 技能 ID

    Request Body:
        {
            "params": {
                "param1": "value1",
                ...
            }
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json() or {}
        params = data.get("params", {})

        result = await service.test_skill(skill_id, params)
        return Response().ok(result).__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to test skill {skill_id}: {e}")
        return Response().error(str(e)).__dict__


async def _import_skills():
    """批量导入技能

    Request Body:
        {
            "skills": [
                {
                    "name": "技能名称",
                    "description": "技能描述",
                    "category": "general",
                    "tools": ["tool_id_1"],
                    "workflow": {...},
                    ...
                },
                ...
            ]
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        skills_data = data.get("skills", [])
        if not skills_data:
            return Response().error("技能列表不能为空").__dict__

        imported_skills = service.import_skills(skills_data)
        return Response().ok(
            [s.to_dict() for s in imported_skills],
            f"成功导入 {len(imported_skills)} 个技能"
        ).__dict__

    except Exception as e:
        logger.error(f"Failed to import skills: {e}")
        return Response().error(str(e)).__dict__


async def _export_skills():
    """导出技能

    Query Parameters:
        ids: 技能 ID 列表，逗号分隔（可选，不传则导出所有技能）
    """
    try:
        service = _get_skill_service()

        ids_param = request.args.get("ids")
        skill_ids = ids_param.split(",") if ids_param else None

        exported = service.export_skills(skill_ids)
        return Response().ok(exported).__dict__

    except Exception as e:
        logger.error(f"Failed to export skills: {e}")
        return Response().error(str(e)).__dict__


async def _get_skill_market():
    """获取社区技能市场"""
    try:
        service = _get_skill_service()
        market_skills = service.get_skill_market()
        return Response().ok(market_skills).__dict__

    except Exception as e:
        logger.error(f"Failed to get skill market: {e}")
        return Response().error(str(e)).__dict__


async def _get_categories():
    """获取技能分类列表"""
    try:
        service = _get_skill_service()
        categories = service.get_categories()
        return Response().ok(categories).__dict__

    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        return Response().error(str(e)).__dict__


async def _get_astrbot_skills():
    """获取 AstrBot 技能列表

    Query Parameters:
        active_only: 是否只返回激活的技能（默认 true）
    """
    try:
        service = _get_skill_service()

        active_only = request.args.get("active_only", "true").lower() == "true"
        skills = service.get_astrbot_skills(active_only=active_only)

        return Response().ok(skills).__dict__

    except Exception as e:
        logger.error(f"Failed to get AstrBot skills: {e}")
        return Response().error(str(e)).__dict__


async def _import_astrbot_skills():
    """导入 AstrBot 技能

    Request Body:
        {
            "skill_names": ["skill1", "skill2"]  // 可选，不传则导入所有激活的技能
        }
    """
    try:
        service = _get_skill_service()

        data = await request.get_json() or {}
        skill_names = data.get("skill_names")

        imported_skills = service.import_astrbot_skills(skill_names)

        return Response().ok(
            [s.to_dict() for s in imported_skills],
            f"成功导入 {len(imported_skills)} 个 AstrBot 技能"
        ).__dict__

    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to import AstrBot skills: {e}")
        return Response().error(str(e)).__dict__


async def _sync_astrbot_skills():
    """同步 AstrBot 技能

    将 AstrBot 的所有激活技能同步到智能体系统
    """
    try:
        service = _get_skill_service()

        result = service.sync_astrbot_skills()

        return Response().ok(
            result,
            f"同步完成：导入 {result['imported']} 个，更新 {result['updated']} 个，禁用 {result['disabled']} 个"
        ).__dict__

    except Exception as e:
        logger.error(f"Failed to sync AstrBot skills: {e}")
        return Response().error(str(e)).__dict__
