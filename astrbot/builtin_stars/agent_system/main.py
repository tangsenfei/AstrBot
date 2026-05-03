"""
NiceBot 智能体管理模块 - 主入口

基于 LangGraph 实现多智能体协作、任务分解、执行追踪、Token 消耗监控
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from quart import jsonify

from astrbot.api import llm_tool
from astrbot.api.event import AstrMessageEvent
from astrbot.core import logger
from astrbot.core.star import Star, StarMetadata
from astrbot.core.star.context import Context

if TYPE_CHECKING:
    from .database import Database


class AgentSystemPlugin(Star):
    """智能体管理插件主类"""

    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.config = context.get_config() or {}
        self.db: Database | None = None
        self._initialized = False

    @staticmethod
    def get_metadata() -> StarMetadata:
        return StarMetadata(
            name="agent_system",
            author="astrbot",
            desc="智能体管理模块，基于 LangGraph 实现多智能体协作、任务分解、执行追踪、Token 消耗监控",
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

        # 自动初始化会议助手 Agent
        self._ensure_meeting_assistant()

        # 自动初始化专家库 Agent
        self._ensure_expert_agents()

        self._initialized = True
        logger.info("AgentSystemPlugin initialized successfully")

    def _ensure_meeting_assistant(self) -> None:
        """确保会议助手 Agent 存在"""
        from .services.agent_service import AgentService
        service = AgentService(self.db, self.context)
        assistant = service.ensure_meeting_assistant()
        if assistant:
            logger.info(f"Meeting assistant agent ready: {assistant.id} ({assistant.name})")
        else:
            logger.warning("Failed to ensure meeting assistant agent")

    def _ensure_expert_agents(self) -> None:
        """确保所有专家模板都已创建为智能体"""
        from .services.agent_service import AgentService
        service = AgentService(self.db, self.context)
        created = service.ensure_expert_agents()
        if created > 0:
            logger.info(f"Auto-created {created} expert agents")
        else:
            logger.info("All expert agents already exist")

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
            register_agent_routes,
            register_crew_routes,
            register_flow_routes,
            register_knowledge_routes,
            register_roundtable_routes,
            register_skill_routes,
            register_task_routes,
            register_tool_routes,
            register_work_routes,
        )
        register_tool_routes(self)
        register_knowledge_routes(self)
        register_skill_routes(self)
        register_agent_routes(self)
        register_crew_routes(self)
        register_flow_routes(self)
        register_roundtable_routes(self)
        register_task_routes(self)
        register_work_routes(self)

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

    def get_database(self) -> Database:
        """获取数据库实例"""
        if not self.db:
            raise RuntimeError("Plugin not initialized")
        return self.db

    @llm_tool(name="meeting_save_document")
    async def meeting_save_document(
        self,
        event: AstrMessageEvent,
        title: str,
        content: str,
        doc_type: str = "minutes",
        format: str = "markdown",
    ) -> str:
        """保存会议文档（会议纪要、行动项、交付物等）到文件系统。在会议结束时调用此工具保存产出物。

        Args:
            title(string): 文档标题，例如"项目启动会会议纪要"
            content(string): 文档内容，Markdown 格式
            doc_type(string): 文档类型，可选值：minutes(会议纪要)、action_items(行动项)、deliverable(交付物)、report(报告)。默认为 minutes
            format(string): 文件格式，可选值：markdown、text。默认为 markdown
        """
        try:
            data_dir = os.path.join(os.getcwd(), "data", "meeting_documents")
            os.makedirs(data_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-", "，", "。"))[:50]
            filename = f"{timestamp}_{safe_title}.{format}"
            filepath = os.path.join(data_dir, filename)

            type_labels = {
                "minutes": "会议纪要",
                "action_items": "行动项",
                "deliverable": "交付物",
                "report": "报告",
            }
            type_label = type_labels.get(doc_type, "文档")

            header = f"# {title}\n\n"
            header += f"> 类型：{type_label} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + content)

            logger.info(f"Meeting document saved: {filepath}")
            return f"文档已保存：{filename}\n路径：{filepath}"
        except Exception as e:
            logger.error(f"Failed to save meeting document: {e}")
            return f"保存文档失败：{str(e)}"

    @llm_tool(name="meeting_generate_action_items")
    async def meeting_generate_action_items(
        self,
        event: AstrMessageEvent,
        discussion_summary: str,
        participants: str = "",
    ) -> str:
        """根据会议讨论内容生成结构化的行动项清单。在会议结束或每轮讨论后调用此工具提炼行动项。

        Args:
            discussion_summary(string): 会议讨论内容摘要或完整讨论记录
            participants(string): 参会者名单，用逗号分隔。例如"张三,李四,王五"
        """
        try:
            participant_list = [p.strip() for p in participants.split(",") if p.strip()] if participants else []

            action_items_prompt = "根据以下讨论内容，提炼出具体的行动项：\n\n"
            action_items_prompt += discussion_summary
            action_items_prompt += "\n\n请按以下格式输出行动项：\n"
            action_items_prompt += "1. 【行动项描述】| 责任人：xxx | 截止时间：xxx | 优先级：高/中/低\n"

            if participant_list:
                action_items_prompt += f"\n参会者名单：{', '.join(participant_list)}\n请从参会者中分配责任人。"

            return action_items_prompt
        except Exception as e:
            logger.error(f"Failed to generate action items: {e}")
            return f"生成行动项失败：{str(e)}"


def main(context: Context):
    """插件入口函数"""
    return AgentSystemPlugin(context)
