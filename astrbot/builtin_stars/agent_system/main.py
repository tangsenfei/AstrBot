"""
NiceBot 智能体管理模块 - 主入口

支持 CrewAI 集成，实现多智能体协作、任务分解、执行追踪、Token 消耗监控
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quart import jsonify, request

from astrbot.core.star import Star, StarMetadata
from astrbot.core.star.context import Context
from astrbot.core import logger

if TYPE_CHECKING:
    from .database import Database


class AgentSystemPlugin(Star):
    """智能体管理插件主类"""

    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.config = context.get_config() or {}
        self.db: "Database | None" = None
        self._initialized = False

    @staticmethod
    def get_metadata() -> StarMetadata:
        return StarMetadata(
            name="agent_system",
            author="astrbot",
            desc="智能体管理模块，支持 CrewAI 集成，实现多智能体协作、任务分解、执行追踪、Token 消耗监控",
            version="1.0.0",
        )

    async def initialize(self) -> None:
        """初始化插件"""
        if self._initialized:
            return

        from .database import init_database

        # 初始化数据库
        self.db = init_database()

        # 注册 Web API
        self._register_apis()

        self._initialized = True
        logger.info("AgentSystemPlugin initialized successfully")

    def _register_apis(self) -> None:
        """注册 Web API"""
        # 健康检查 API
        self.context.register_web_api(
            "/agent_system/health",
            self._api_health_check,
            ["GET"],
            "健康检查"
        )

        # 注册工具管理 API
        from .routes import (
            register_tool_routes,
            register_knowledge_routes,
            register_skill_routes,
            register_agent_routes,
            register_crew_routes,
            register_flow_routes,
        )
        register_tool_routes(self)
        register_knowledge_routes(self)
        register_skill_routes(self)
        register_agent_routes(self)
        register_crew_routes(self)
        register_flow_routes(self)

        logger.info("AgentSystemPlugin APIs registered")

    async def terminate(self) -> None:
        """终止插件"""
        from .database import close_database

        close_database()
        self._initialized = False
        logger.info("AgentSystemPlugin terminated")

    def _json_response(self, data: Any, status: str = "ok", message: str | None = None) -> Any:
        """生成 JSON 响应"""
        return jsonify({
            "status": status,
            "message": message,
            "data": data
        })

    def _error_response(self, message: str) -> Any:
        """生成错误响应"""
        return jsonify({
            "status": "error",
            "message": message,
            "data": None
        })

    async def _api_health_check(self):
        """健康检查 API"""
        try:
            # 检查数据库连接
            if self.db:
                self.db.execute("SELECT 1")
                db_status = "connected"
            else:
                db_status = "not_initialized"

            return self._json_response({
                "plugin": "agent_system",
                "version": "1.0.0",
                "database": db_status,
                "status": "healthy"
            }, message="AgentSystem is running")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return self._error_response(f"Health check failed: {e}")

    def get_database(self) -> "Database":
        """获取数据库实例"""
        if not self.db:
            raise RuntimeError("Plugin not initialized")
        return self.db


def main(context: Context):
    """插件入口函数"""
    return AgentSystemPlugin(context)
