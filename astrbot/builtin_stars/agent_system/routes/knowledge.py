"""
智能体管理模块 - 知识库管理路由

提供知识库管理相关的 REST API
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin


def register_knowledge_routes(plugin: "AgentSystemPlugin") -> None:
    plugin.context.register_web_api(
        "/agent/knowledge",
        _list_knowledge,
        ["GET"],
        "获取知识库列表"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/<knowledge_id>",
        _get_knowledge,
        ["GET"],
        "获取知识库详情"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/create",
        _create_knowledge,
        ["POST"],
        "创建知识库"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/update",
        _update_knowledge,
        ["POST"],
        "更新知识库"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/delete",
        _delete_knowledge,
        ["POST"],
        "删除知识库"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/sources/add",
        _add_source,
        ["POST"],
        "添加知识源"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/sources/delete",
        _remove_source,
        ["POST"],
        "删除知识源"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/retrieve",
        _search_knowledge,
        ["POST"],
        "检索知识"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/search",
        _search_knowledge,
        ["POST"],
        "搜索知识"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/upload",
        _upload_source,
        ["POST"],
        "上传知识源文件"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/fetch-url",
        _fetch_url,
        ["POST"],
        "抓取URL内容"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/import-db",
        _import_db,
        ["POST"],
        "导入数据库"
    )

    plugin.context.register_web_api(
        "/agent/knowledge/reindex",
        _reindex_knowledge,
        ["POST"],
        "重建索引"
    )

    logger.info("Knowledge management API routes registered")


def _get_knowledge_service():
    from ..services.knowledge_service import KnowledgeService
    from ..database import get_database

    db = get_database()
    return KnowledgeService(db)


async def _list_knowledge():
    try:
        service = _get_knowledge_service()
        knowledge_list = service.get_knowledge_list()
        return Response().ok([k.to_dict() for k in knowledge_list]).__dict__
    except Exception as e:
        logger.error(f"Failed to list knowledge bases: {e}")
        return Response().error(str(e)).__dict__


async def _get_knowledge(knowledge_id: str):
    try:
        service = _get_knowledge_service()
        knowledge = service.get_knowledge(knowledge_id)
        if not knowledge:
            return Response().error(f"知识库 '{knowledge_id}' 不存在").__dict__
        return Response().ok(knowledge.to_dict()).__dict__
    except Exception as e:
        logger.error(f"Failed to get knowledge {knowledge_id}: {e}")
        return Response().error(str(e)).__dict__


async def _create_knowledge():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge = service.create_knowledge(data)
        return Response().ok(knowledge.to_dict(), "知识库创建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create knowledge: {e}")
        return Response().error(str(e)).__dict__


async def _update_knowledge():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("id") or data.get("knowledge_id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        knowledge = service.update_knowledge(knowledge_id, data)
        if not knowledge:
            return Response().error(f"知识库 '{knowledge_id}' 不存在").__dict__

        return Response().ok(knowledge.to_dict(), "知识库更新成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update knowledge: {e}")
        return Response().error(str(e)).__dict__


async def _delete_knowledge():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("id") or data.get("knowledge_id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        success = service.delete_knowledge(knowledge_id)
        if not success:
            return Response().error(f"知识库 '{knowledge_id}' 不存在").__dict__

        return Response().ok(None, "知识库删除成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to delete knowledge: {e}")
        return Response().error(str(e)).__dict__


async def _add_source():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("knowledge_id") or data.get("id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        source = service.add_source(knowledge_id, data)
        return Response().ok(source, "知识源添加成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to add source: {e}")
        return Response().error(str(e)).__dict__


async def _remove_source():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("knowledge_id")
        source_id = data.get("source_id") or data.get("id")
        if not knowledge_id or not source_id:
            return Response().error("缺少知识库 ID 或知识源 ID").__dict__

        success = service.remove_source(knowledge_id, source_id)
        if not success:
            return Response().error(f"知识源 '{source_id}' 不存在").__dict__

        return Response().ok(None, "知识源删除成功").__dict__
    except Exception as e:
        logger.error(f"Failed to remove source: {e}")
        return Response().error(str(e)).__dict__


async def _search_knowledge():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("knowledge_id") or data.get("id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        query = data.get("query")
        if not query:
            return Response().error("查询文本不能为空").__dict__

        top_k = data.get("top_k", 5)
        results = service.search(knowledge_id, query, top_k)
        return Response().ok(results).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to search knowledge: {e}")
        return Response().error(str(e)).__dict__


async def _upload_source():
    try:
        service = _get_knowledge_service()
        files = await request.files
        form_data = await request.form

        knowledge_id = form_data.get("knowledge_id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        result = service.upload_source(knowledge_id, files, form_data)
        return Response().ok(result, "上传成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to upload source: {e}")
        return Response().error(str(e)).__dict__


async def _fetch_url():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("knowledge_id")
        url = data.get("url")
        if not knowledge_id or not url:
            return Response().error("缺少知识库 ID 或 URL").__dict__

        result = service.fetch_url(knowledge_id, url)
        return Response().ok(result, "URL 抓取成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to fetch URL: {e}")
        return Response().error(str(e)).__dict__


async def _import_db():
    try:
        service = _get_knowledge_service()
        data = await request.get_json()
        if not data:
            return Response().error("请求体不能为空").__dict__

        knowledge_id = data.get("knowledge_id")
        db_config = data.get("db_config")
        if not knowledge_id or not db_config:
            return Response().error("缺少知识库 ID 或数据库配置").__dict__

        result = service.import_db(knowledge_id, db_config)
        return Response().ok(result, "数据库导入成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to import DB: {e}")
        return Response().error(str(e)).__dict__


async def _reindex_knowledge():
    try:
        service = _get_knowledge_service()
        data = await request.get_json() or {}

        knowledge_id = data.get("knowledge_id") or data.get("id")
        if not knowledge_id:
            return Response().error("缺少知识库 ID").__dict__

        success = service.reindex(knowledge_id)
        if not success:
            return Response().error(f"知识库 '{knowledge_id}' 不存在").__dict__

        return Response().ok(None, "索引重建成功").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to reindex knowledge: {e}")
        return Response().error(str(e)).__dict__
