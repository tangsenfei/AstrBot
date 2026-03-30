"""
DeerFlow Client - DeerFlow 客户端封装

封装 DeerFlow 嵌入式运行时的调用
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from astrbot.core.agent.runners.deerflow.deerflow_embedded_runtime import (
        DeerFlowEmbeddedRuntime,
        EmbeddedRuntimeConfig,
    )


@dataclass
class DeerFlowConfig:
    """DeerFlow 配置"""
    config_path: str = ""
    backend_path: str = ""
    default_model: str = ""
    thinking_enabled: bool = True
    is_plan_mode: bool = True
    subagent_enabled: bool = False


class DeerFlowClient:
    """DeerFlow 客户端
    
    封装 DeerFlow 嵌入式运行时的调用
    """
    
    def __init__(self, config_path: str = "", config_manager = None) -> None:
        self.config_path = config_path
        self._config_manager = config_manager
        self._runtime: "DeerFlowEmbeddedRuntime | None" = None
        self._initialized = False
        self._embedded_mode = False
    
    def _resolve_model_name(self, model_name: str | None) -> str | None:
        """解析模型名称
        
        将 AstrBot 提供商 ID 映射到 DeerFlow 模型名称
        
        Args:
            model_name: AstrBot 提供商 ID 或 DeerFlow 模型名称
            
        Returns:
            DeerFlow 模型名称
        """
        if not model_name:
            return None
        
        if self._config_manager:
            return self._config_manager.get_deerflow_model_for_provider(model_name)
        
        return model_name
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._initialized:
            return
        
        try:
            from astrbot.core.agent.runners.deerflow.deerflow_embedded_runtime import (
                DeerFlowEmbeddedRuntime,
                EmbeddedRuntimeConfig,
            )
            
            config = EmbeddedRuntimeConfig(
                deerflow_config_path=self.config_path,
                auto_setup_path=True,
            )
            
            self._runtime = DeerFlowEmbeddedRuntime.initialize(config)
            await self._runtime.setup()
            
            self._embedded_mode = True
            self._initialized = True
            logger.info("DeerFlowClient initialized in embedded mode")
            
        except ImportError as e:
            logger.warning(f"DeerFlow embedded runtime not available (missing dependencies): {e}")
            logger.info("DeerFlowClient running in standalone mode (DeerFlow integration disabled)")
            self._initialized = True
            
        except FileNotFoundError as e:
            logger.warning(f"DeerFlow backend not found: {e}")
            logger.info("DeerFlowClient running in standalone mode (DeerFlow not installed)")
            self._initialized = True
            
        except Exception as e:
            logger.warning(f"DeerFlow embedded runtime initialization failed: {e}")
            logger.info("DeerFlowClient running in standalone mode")
            self._initialized = True
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self._runtime:
            try:
                await self._runtime.cleanup()
            except Exception:
                pass
        self._initialized = False
    
    async def invoke(
        self,
        thread_id: str,
        message: str,
        model_name: str | None = None,
        is_plan_mode: bool = True,
    ) -> dict[str, Any]:
        """同步调用 Agent
        
        Args:
            thread_id: 线程 ID
            message: 用户消息
            model_name: 模型名称
            is_plan_mode: 是否启用计划模式
            
        Returns:
            Agent 响应结果
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized")
        
        # 解析模型名称
        resolved_model = self._resolve_model_name(model_name)
        logger.info(f"Resolving model: {model_name} -> {resolved_model}")
        
        if self._runtime:
            return await self._runtime.invoke(
                thread_id=thread_id,
                message=message,
                model_name=resolved_model,
                is_plan_mode=is_plan_mode,
            )
        
        raise RuntimeError("DeerFlow runtime not available. Please install DeerFlow or check configuration.")
    
    async def stream(
        self,
        thread_id: str,
        message: str,
        model_name: str | None = None,
        is_plan_mode: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式调用 Agent
        
        Args:
            thread_id: 线程 ID
            message: 用户消息
            model_name: 模型名称
            is_plan_mode: 是否启用计划模式
            
        Yields:
            Agent 流式响应事件
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized")
        
        # 解析模型名称
        resolved_model = self._resolve_model_name(model_name)
        logger.info(f"Resolving model (stream): {model_name} -> {resolved_model}")
        
        if self._runtime:
            async for event in self._runtime.stream(
                thread_id=thread_id,
                message=message,
                model_name=resolved_model,
                is_plan_mode=is_plan_mode,
            ):
                yield event
            return
        
        raise RuntimeError("DeerFlow runtime not available. Please install DeerFlow or check configuration.")
    
    async def get_todos(self, thread_id: str) -> list[dict[str, Any]]:
        """获取任务列表
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            任务列表
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized")
        
        if self._runtime:
            return await self._runtime.get_todos(thread_id)
        
        return []
    
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
        if not self._initialized:
            raise RuntimeError("Client not initialized")
        
        if self._runtime:
            return await self._runtime.update_todos(thread_id, todos)
        
        return False
    
    def get_available_models(self) -> list[dict[str, Any]]:
        """获取可用模型列表"""
        if self._runtime:
            return self._runtime.get_available_models()
        return []
    
    def get_available_tools(self) -> list[str]:
        """获取可用工具列表"""
        if self._runtime:
            return self._runtime.get_available_tools()
        return []
    
    @property
    def is_embedded_mode(self) -> bool:
        """是否为嵌入式模式"""
        return self._embedded_mode
