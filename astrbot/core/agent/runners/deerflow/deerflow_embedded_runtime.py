"""
DeerFlow Embedded Runtime - 嵌入式运行时

将 DeerFlow 的 LangGraph 能力直接嵌入 AstrBot 进程，
无需启动独立的 LangGraph Server，实现零网络开销的深度融合。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typing

if not hasattr(typing, 'override'):
    from typing_extensions import override
    typing.override = override

from langchain_core.runnables import RunnableConfig

from astrbot.core import logger

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.pregel import Pregel


@dataclass
class EmbeddedRuntimeConfig:
    """嵌入式运行时配置"""
    
    deerflow_config_path: str = ""
    deerflow_backend_path: str = ""
    
    checkpointer_type: str = "memory"
    checkpointer_connection: str = ""
    
    default_model: str = ""
    thinking_enabled: bool = True
    is_plan_mode: bool = True
    subagent_enabled: bool = False
    max_concurrent_subagents: int = 3
    
    skills_path: str = ""
    custom_skills_path: str = ""
    
    auto_setup_path: bool = True
    

class DeerFlowEmbeddedRuntime:
    """DeerFlow 嵌入式运行时
    
    将 DeerFlow 的核心能力直接嵌入 AstrBot 进程，
    实现零网络开销的深度融合。
    
    特点：
    - 单进程运行，无需独立 LangGraph Server
    - 共享 AstrBot 的配置和资源
    - 直接调用 Agent API，无 HTTP 开销
    - 支持 Skills/Tools 双向集成
    """
    
    _instance: "DeerFlowEmbeddedRuntime | None" = None
    
    def __init__(self, config: EmbeddedRuntimeConfig) -> None:
        self.config = config
        self._initialized = False
        self._checkpointer: "BaseCheckpointSaver | None" = None
        self._agents: dict[str, "Pregel"] = {}
        self._deerflow_modules_loaded = False
        
    @classmethod
    def get_instance(cls) -> "DeerFlowEmbeddedRuntime":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("DeerFlowEmbeddedRuntime not initialized")
        return cls._instance
    
    @classmethod
    def initialize(cls, config: EmbeddedRuntimeConfig) -> "DeerFlowEmbeddedRuntime":
        """初始化单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance
    
    async def setup(self) -> None:
        """初始化嵌入式运行时"""
        if self._initialized:
            return
        
        self._setup_python_path()
        self._setup_deerflow_config()
        
        await self._load_deerflow_modules()
        
        await self._init_checkpointer()
        
        self._initialized = True
        logger.info("DeerFlow Embedded Runtime initialized successfully")
    
    def _setup_python_path(self) -> None:
        """设置 Python 路径以导入 DeerFlow 模块"""
        if self.config.deerflow_backend_path:
            backend_path = Path(self.config.deerflow_backend_path)
        else:
            backend_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "deer-flow" / "backend"
        
        if backend_path.exists():
            backend_str = str(backend_path)
            packages_path = str(backend_path / "packages" / "harness")
            
            if backend_str not in sys.path:
                sys.path.insert(0, backend_str)
            if packages_path not in sys.path:
                sys.path.insert(0, packages_path)
            
            logger.info(f"Added DeerFlow to Python path: {backend_str}")
        else:
            raise FileNotFoundError(f"DeerFlow backend not found at: {backend_path}")
    
    def _setup_deerflow_config(self) -> None:
        """设置 DeerFlow 配置路径"""
        if self.config.deerflow_config_path:
            config_path = self.config.deerflow_config_path
        else:
            config_path = str(Path(__file__).parent.parent.parent.parent.parent.parent.parent / "deer-flow" / "config.yaml")
        
        if Path(config_path).exists():
            os.environ["DEER_FLOW_CONFIG_PATH"] = config_path
            logger.info(f"Set DeerFlow config path: {config_path}")
        else:
            raise FileNotFoundError(f"DeerFlow config not found at: {config_path}")
    
    async def _load_deerflow_modules(self) -> None:
        """加载 DeerFlow 核心模块"""
        if self._deerflow_modules_loaded:
            return
        
        try:
            from deerflow.config.app_config import get_app_config
            from deerflow.agents.lead_agent.agent import make_lead_agent
            
            app_config = get_app_config()
            logger.info(f"Loaded DeerFlow config with {len(app_config.models)} models")
            
            self._deerflow_modules_loaded = True
            
        except ImportError as e:
            logger.error(f"Failed to import DeerFlow modules: {e}")
            raise
    
    async def _init_checkpointer(self) -> None:
        """初始化检查点存储"""
        from deerflow.agents.checkpointer.async_provider import make_checkpointer
        
        async with make_checkpointer() as checkpointer:
            self._checkpointer = checkpointer
        
        logger.info(f"Initialized checkpointer: {type(self._checkpointer).__name__}")
    
    def _resolve_model_name(self, model_name: str | None) -> str:
        """解析模型名称，如果无效则返回默认模型
        
        Args:
            model_name: 传入的模型名称
            
        Returns:
            有效的模型名称
        """
        if not model_name:
            return self.config.default_model
        
        if not self._deerflow_modules_loaded:
            return model_name
        
        try:
            from deerflow.config.app_config import get_app_config
            
            app_config = get_app_config()
            available_models = {m.name for m in app_config.models}
            
            if model_name in available_models:
                return model_name
            
            # 模型名称无效，使用默认模型
            logger.warning(f"Model '{model_name}' not found in DeerFlow config, using default: {self.config.default_model}")
            return self.config.default_model
            
        except Exception as e:
            logger.error(f"Failed to resolve model name: {e}")
            return model_name
    
    def create_agent(
        self,
        thread_id: str,
        model_name: str | None = None,
        thinking_enabled: bool | None = None,
        is_plan_mode: bool | None = None,
        subagent_enabled: bool | None = None,
        agent_name: str | None = None,
    ) -> "Pregel":
        """创建 Agent 实例
        
        Args:
            thread_id: 线程 ID
            model_name: 模型名称
            thinking_enabled: 是否启用思考模式
            is_plan_mode: 是否启用计划模式
            subagent_enabled: 是否启用子代理
            agent_name: 自定义代理名称
            
        Returns:
            LangGraph Pregel Agent 实例
        """
        if not self._initialized:
            raise RuntimeError("Runtime not initialized. Call setup() first.")
        
        from deerflow.agents.lead_agent.agent import make_lead_agent
        
        # 解析模型名称
        resolved_model = self._resolve_model_name(model_name)
        
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "model_name": resolved_model,
                "thinking_enabled": thinking_enabled if thinking_enabled is not None else self.config.thinking_enabled,
                "is_plan_mode": is_plan_mode if is_plan_mode is not None else self.config.is_plan_mode,
                "subagent_enabled": subagent_enabled if subagent_enabled is not None else self.config.subagent_enabled,
                "max_concurrent_subagents": self.config.max_concurrent_subagents,
                "agent_name": agent_name,
            }
        )
        
        agent = make_lead_agent(config)
        
        cache_key = f"{thread_id}:{model_name or 'default'}"
        self._agents[cache_key] = agent
        
        return agent
    
    async def invoke(
        self,
        thread_id: str,
        message: str,
        model_name: str | None = None,
        is_plan_mode: bool | None = None,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        """同步调用 Agent
        
        Args:
            thread_id: 线程 ID
            message: 用户消息
            model_name: 模型名称
            is_plan_mode: 是否启用计划模式
            agent_name: 自定义代理名称
            
        Returns:
            Agent 响应结果
        """
        from langchain_core.messages import HumanMessage
        
        agent = self.create_agent(
            thread_id=thread_id,
            model_name=model_name,
            is_plan_mode=is_plan_mode,
            agent_name=agent_name,
        )
        
        config = RunnableConfig(
            configurable={"thread_id": thread_id},
            checkpointer=self._checkpointer,
        )
        
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )
        
        return result
    
    async def stream(
        self,
        thread_id: str,
        message: str,
        model_name: str | None = None,
        is_plan_mode: bool | None = None,
        agent_name: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式调用 Agent
        
        Args:
            thread_id: 线程 ID
            用户消息
            model_name: 模型名称
            is_plan_mode: 是否启用计划模式
            agent_name: 自定义代理名称
            
        Yields:
            Agent 流式响应事件，格式与 DeerFlow client 兼容
        """
        from deerflow.client import DeerFlowClient
        
        # 解析模型名称
        resolved_model = self._resolve_model_name(model_name)
        
        # 创建 DeerFlow 客户端
        client = DeerFlowClient(
            checkpointer=self._checkpointer,
            model_name=resolved_model,
            plan_mode=is_plan_mode if is_plan_mode is not None else True,
        )
        
        # 在线程池中运行同步的 stream 方法
        loop = asyncio.get_event_loop()
        
        def run_stream():
            return list(client.stream(message=message, thread_id=thread_id))
        
        events = await loop.run_in_executor(None, run_stream)
        
        # 转换事件格式
        for event in events:
            yield {
                "type": event.type,
                "data": event.data,
            }
    
    async def get_thread_state(self, thread_id: str) -> dict[str, Any]:
        """获取线程状态
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            线程状态
        """
        if not self._checkpointer:
            return {}
        
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await self._checkpointer.aget(config)
        return state
    
    async def get_todos(self, thread_id: str) -> list[dict[str, Any]]:
        """获取任务列表
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            任务列表
        """
        state = await self.get_thread_state(thread_id)
        return state.get("todos", [])
    
    async def update_todos(
        self,
        thread_id: str,
        todos: list[dict[str, Any]],
    ) -> bool:
        """更新任务列表
        
        Args:
            thread_id: 线程 ID
            todos: 新的任务列表
            
        Returns:
            是否更新成功
        """
        if not self._checkpointer:
            return False
        
        config = RunnableConfig(configurable={"thread_id": thread_id})
        current_state = await self._checkpointer.aget(config)
        
        if current_state is None:
            current_state = {}
        
        current_state["todos"] = todos
        
        await self._checkpointer.aput(config, current_state)
        return True
    
    def get_available_tools(self) -> list[str]:
        """获取可用工具列表"""
        if not self._deerflow_modules_loaded:
            return []
        
        try:
            from deerflow.tools import get_available_tools
            
            tools = get_available_tools()
            return [tool.name for tool in tools]
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []
    
    def get_available_models(self) -> list[dict[str, Any]]:
        """获取可用模型列表"""
        if not self._deerflow_modules_loaded:
            return []
        
        try:
            from deerflow.config.app_config import get_app_config
            
            app_config = get_app_config()
            return [
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "supports_vision": model.supports_vision,
                    "supports_thinking": model.supports_thinking,
                }
                for model in app_config.models
            ]
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._agents.clear()
        self._checkpointer = None
        self._initialized = False
        logger.info("DeerFlow Embedded Runtime cleaned up")


@asynccontextmanager
async def create_embedded_runtime(
    config: EmbeddedRuntimeConfig | None = None,
) -> AsyncIterator[DeerFlowEmbeddedRuntime]:
    """创建嵌入式运行时的上下文管理器
    
    Args:
        config: 运行时配置
        
    Yields:
        DeerFlowEmbeddedRuntime 实例
    """
    if config is None:
        config = EmbeddedRuntimeConfig()
    
    runtime = DeerFlowEmbeddedRuntime.initialize(config)
    
    try:
        await runtime.setup()
        yield runtime
    finally:
        await runtime.cleanup()


def _get_default_model_from_deerflow_config(config_path: str) -> str:
    """从 DeerFlow 配置文件中读取默认模型
    
    Args:
        config_path: DeerFlow 配置文件路径
        
    Returns:
        默认模型名称，如果找不到则返回第一个模型
    """
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        models = config.get('models', [])
        if not models:
            return ""
        
        # 查找标记为默认的模型
        for model in models:
            if model.get('default', False):
                return model.get('name', '')
        
        # 如果没有标记默认，返回第一个模型
        return models[0].get('name', '')
        
    except Exception as e:
        logger.warning(f"Failed to read default model from DeerFlow config: {e}")
        return ""


def init_embedded_runtime_from_astrbot_config(
    astrbot_config: dict[str, Any],
) -> DeerFlowEmbeddedRuntime:
    """从 AstrBot 配置初始化嵌入式运行时
    
    Args:
        astrbot_config: AstrBot 配置字典
        
    Returns:
        DeerFlowEmbeddedRuntime 实例
    """
    deerflow_config = astrbot_config.get("deerflow", {})
    
    # 获取 DeerFlow 配置文件路径
    deerflow_config_path = deerflow_config.get("config_path", "")
    if not deerflow_config_path:
        deerflow_config_path = str(Path(__file__).parent.parent.parent.parent.parent.parent.parent / "deer-flow" / "config.yaml")
    
    # 从 DeerFlow 配置中读取默认模型
    default_model = deerflow_config.get("default_model", "")
    if not default_model and Path(deerflow_config_path).exists():
        default_model = _get_default_model_from_deerflow_config(deerflow_config_path)
        logger.info(f"Loaded default model from DeerFlow config: {default_model}")
    
    config = EmbeddedRuntimeConfig(
        deerflow_config_path=deerflow_config_path,
        deerflow_backend_path=deerflow_config.get("backend_path", ""),
        checkpointer_type=deerflow_config.get("checkpointer", {}).get("type", "memory"),
        checkpointer_connection=deerflow_config.get("checkpointer", {}).get("connection", ""),
        default_model=default_model,
        thinking_enabled=deerflow_config.get("thinking_enabled", True),
        is_plan_mode=deerflow_config.get("is_plan_mode", True),
        subagent_enabled=deerflow_config.get("subagent_enabled", False),
        max_concurrent_subagents=deerflow_config.get("max_concurrent_subagents", 3),
        skills_path=deerflow_config.get("skills", {}).get("path", ""),
        custom_skills_path=deerflow_config.get("skills", {}).get("custom_path", ""),
    )
    
    return DeerFlowEmbeddedRuntime.initialize(config)
