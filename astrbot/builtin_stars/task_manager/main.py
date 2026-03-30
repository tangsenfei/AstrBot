"""
NiceBot 任务管理插件 - 主入口

实现与 DeerFlow 的深度集成，提供异步复杂任务管理能力
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from quart import jsonify, request

from astrbot.core.star import Star, StarMetadata
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools
from astrbot.core import logger

if TYPE_CHECKING:
    from .deerflow_client import DeerFlowClient
    from .task_executor import TaskExecutor
    from .config_manager import ConfigManager


class TaskManagerPlugin(Star):
    """任务管理插件主类"""
    
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.config = context.get_config() or {}
        self.deerflow_client: "DeerFlowClient | None" = None
        self.task_executor: "TaskExecutor | None" = None
        self.config_manager: "ConfigManager | None" = None
        self._initialized = False
    
    @staticmethod
    def get_metadata() -> StarMetadata:
        return StarMetadata(
            name="task_manager",
            author="astrbot",
            desc="异步任务管理插件，支持 DeerFlow 2.0 集成",
            version="1.0.0",
        )
    
    async def initialize(self) -> None:
        """初始化插件"""
        if self._initialized:
            return
        
        from .deerflow_client import DeerFlowClient
        from .task_executor import TaskExecutor
        from .config_manager import ConfigManager
        
        # 先初始化配置管理器
        self.config_manager = ConfigManager(self.context)
        await self.config_manager.initialize()
        
        deerflow_config_path = self.config.get(
            "deerflow_config_path",
            str(Path(__file__).parent.parent.parent.parent.parent / "deer-flow" / "config.yaml")
        )
        
        # 创建 DeerFlowClient 时传入配置管理器
        self.deerflow_client = DeerFlowClient(
            config_path=deerflow_config_path,
            config_manager=self.config_manager
        )
        await self.deerflow_client.initialize()
        
        data_dir = Path(StarTools.get_data_dir("task_manager"))
        
        self.task_executor = TaskExecutor(
            deerflow_client=self.deerflow_client,
            config_manager=self.config_manager,
            data_dir=data_dir,
        )
        
        self._register_apis()
        
        self._initialized = True
        logger.info("TaskManagerPlugin initialized successfully")
    
    def _register_apis(self) -> None:
        """注册 Web API"""
        self.context.register_web_api(
            "/task_manager/config",
            self._api_get_config,
            ["GET"],
            "获取 DeerFlow 配置"
        )
        self.context.register_web_api(
            "/task_manager/config/provider",
            self._api_set_provider,
            ["POST"],
            "设置提供商"
        )
        self.context.register_web_api(
            "/task_manager/config/options",
            self._api_set_options,
            ["POST"],
            "设置选项"
        )
        self.context.register_web_api(
            "/task_manager/tasks",
            self._api_list_tasks,
            ["GET"],
            "获取任务列表"
        )
        self.context.register_web_api(
            "/task_manager/tasks",
            self._api_create_task,
            ["POST"],
            "创建任务"
        )
        # 使用通配符路由处理动态 task_id
        self.context.register_web_api(
            "/task_manager/tasks/*",
            self._api_task_router,
            ["GET", "POST", "DELETE"],
            "任务路由处理器"
        )
        logger.info("TaskManagerPlugin APIs registered")
    
    async def terminate(self) -> None:
        """终止插件"""
        if self.deerflow_client:
            await self.deerflow_client.cleanup()
        
        self._initialized = False
        logger.info("TaskManagerPlugin terminated")
    
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
    
    async def _api_get_config(self):
        """获取配置"""
        try:
            config_manager = self.get_config_manager()
            return self._json_response(config_manager.get_config_summary())
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_set_provider(self):
        """设置提供商"""
        try:
            data = await request.get_json()
            provider_id = data.get("provider_id", "")
            if not provider_id:
                return self._error_response("provider_id is required")
            
            config_manager = self.get_config_manager()
            success = config_manager.set_provider(provider_id)
            if success:
                # 返回对应的 DeerFlow 模型
                deerflow_model = config_manager.get_deerflow_model_for_provider(provider_id)
                return self._json_response({
                    "provider_id": provider_id,
                    "deerflow_model": deerflow_model
                }, message="Provider set")
            return self._error_response("Failed to set provider")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_set_options(self):
        """设置选项"""
        try:
            data = await request.get_json()
            config_manager = self.get_config_manager()
            success = config_manager.set_options(
                thinking_enabled=data.get("thinking_enabled"),
                is_plan_mode=data.get("is_plan_mode"),
                subagent_enabled=data.get("subagent_enabled"),
            )
            if success:
                return self._json_response({}, message="Options set")
            return self._error_response("Failed to set options")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_list_tasks(self):
        """获取任务列表"""
        try:
            executor = self.get_task_executor()
            tasks = executor.get_all_tasks()
            return self._json_response([t.to_dict() for t in tasks])
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_create_task(self):
        """创建任务"""
        try:
            data = await request.get_json()
            executor = self.get_task_executor()
            task = executor.create_task(
                title=data.get("title", ""),
                description=data.get("description", ""),
                model_name=data.get("model_name"),
                is_plan_mode=data.get("is_plan_mode", True),
            )
            return self._json_response(task.to_dict(), message="Task created")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_get_task(self, task_id: str):
        """获取任务详情"""
        try:
            executor = self.get_task_executor()
            task = executor.get_task(task_id)
            if not task:
                return self._error_response("Task not found")
            return self._json_response(task.to_dict())
        except Exception as e:
            return self._error_response(str(e))

    async def _api_task_router(self, *args, **kwargs):
        """任务路由处理器 - 处理所有 /task_manager/tasks/* 请求"""
        from quart import request

        # 获取请求路径
        path = request.path
        # 移除 /api/plug/task_manager/tasks/ 前缀
        prefix = "/api/plug/task_manager/tasks/"
        if path.startswith(prefix):
            subpath = path[len(prefix):]
        else:
            return self._error_response("Invalid path")

        # 解析路径
        parts = subpath.split("/")
        if not parts or not parts[0]:
            return self._error_response("Task ID required")

        task_id = parts[0]
        action = parts[1] if len(parts) > 1 else None

        method = request.method

        logger.info(f"Task router: task_id={task_id}, action={action}, method={method}")

        # 路由分发
        if method == "GET":
            # GET /task_manager/tasks/{task_id}
            return await self._api_get_task(task_id)
        elif method == "DELETE":
            # DELETE /task_manager/tasks/{task_id}
            return await self._api_delete_task(task_id)
        elif method == "POST":
            if action == "start":
                return await self._api_start_task(task_id)
            elif action == "pause":
                return await self._api_pause_task(task_id)
            elif action == "cancel":
                return await self._api_cancel_task(task_id)
            elif action == "approve":
                return await self._api_approve_plan(task_id)
            else:
                return self._error_response(f"Unknown action: {action}")
        else:
            return self._error_response(f"Unsupported method: {method}")

    async def _api_start_task(self, task_id: str):
        """启动任务"""
        logger.info(f"API: start_task called for task_id: {task_id}")
        try:
            executor = self.get_task_executor()
            logger.info(f"API: got executor, calling start_task")
            success, error_msg = await executor.start_task(task_id)
            logger.info(f"API: start_task returned success={success}, error={error_msg}")
            if success:
                return self._json_response({}, message="Task started")
            return self._error_response(error_msg or "Failed to start task")
        except Exception as e:
            logger.error(f"API: start_task exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._error_response(str(e))
    
    async def _api_pause_task(self, task_id: str):
        """暂停任务"""
        try:
            executor = self.get_task_executor()
            success = await executor.pause_task(task_id)
            if success:
                return self._json_response({}, message="Task paused")
            return self._error_response("Failed to pause task")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_cancel_task(self, task_id: str):
        """取消任务"""
        try:
            executor = self.get_task_executor()
            success = await executor.cancel_task(task_id)
            if success:
                return self._json_response({}, message="Task cancelled")
            return self._error_response("Failed to cancel task")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_approve_plan(self, task_id: str):
        """批准计划"""
        try:
            executor = self.get_task_executor()
            success = await executor.approve_plan(task_id)
            if success:
                return self._json_response({}, message="Plan approved")
            return self._error_response("Failed to approve plan")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _api_delete_task(self, task_id: str):
        """删除任务"""
        try:
            executor = self.get_task_executor()
            success = executor.delete_task(task_id)
            if success:
                return self._json_response({}, message="Task deleted")
            return self._error_response("Task not found")
        except Exception as e:
            return self._error_response(str(e))
    
    def get_deerflow_client(self) -> "DeerFlowClient":
        """获取 DeerFlow 客户端"""
        if not self.deerflow_client:
            raise RuntimeError("Plugin not initialized")
        return self.deerflow_client
    
    def get_task_executor(self) -> "TaskExecutor":
        """获取任务执行器"""
        if not self.task_executor:
            raise RuntimeError("Plugin not initialized")
        return self.task_executor
    
    def get_config_manager(self) -> "ConfigManager":
        """获取配置管理器"""
        if not self.config_manager:
            raise RuntimeError("Plugin not initialized")
        return self.config_manager


def main(context: Context):
    """插件入口函数"""
    return TaskManagerPlugin(context)
