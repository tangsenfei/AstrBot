"""
DeerFlow Integration Manager - 统一集成管理器

管理 AstrBot 与 DeerFlow 之间的深度融合，包括：
- Skills 双向同步
- Tools 双向注册
- 配置统一管理
- 生命周期管理
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.agent.tool import ToolSet
from astrbot.core.agent.runners.deerflow.deerflow_skills_bridge import DeerFlowSkillsBridge
from astrbot.core.agent.runners.deerflow.deerflow_tools_bridge import DeerFlowToolsBridge

if TYPE_CHECKING:
    from astrbot.core.agent.runners.deerflow.deerflow_agent_runner import DeerFlowAgentRunner


@dataclass
class DeerFlowIntegrationConfig:
    """DeerFlow 集成配置"""
    
    api_base: str = "http://127.0.0.1:2024"
    
    skills_sync_mode: str = "bidirectional"
    astrbot_skills_path: str = "data/skills"
    deerflow_skills_path: str = "deer-flow/skills"
    
    share_astrbot_tools: bool = True
    share_deerflow_tools: bool = True
    excluded_tools: list[str] = field(default_factory=list)
    
    auto_sync_on_startup: bool = True
    sync_interval_seconds: int = 300
    
    deerflow_config_path: str = "deer-flow/config.yaml"


class DeerFlowIntegrationManager:
    """DeerFlow 统一集成管理器
    
    管理 AstrBot 与 DeerFlow 之间的深度融合
    """
    
    _instance: "DeerFlowIntegrationManager | None" = None
    
    def __init__(self, config: DeerFlowIntegrationConfig) -> None:
        self.config = config
        self.skills_bridge = DeerFlowSkillsBridge(
            astrbot_skills_path=config.astrbot_skills_path,
            deerflow_skills_path=config.deerflow_skills_path,
        )
        self._sync_task: asyncio.Task | None = None
        self._running = False
    
    @classmethod
    def get_instance(cls) -> "DeerFlowIntegrationManager":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("DeerFlowIntegrationManager not initialized")
        return cls._instance
    
    @classmethod
    def initialize(cls, config: DeerFlowIntegrationConfig) -> "DeerFlowIntegrationManager":
        """初始化单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance
    
    async def start(self) -> None:
        """启动集成管理器"""
        if self._running:
            return
        
        self._running = True
        
        if self.config.auto_sync_on_startup:
            await self.sync_all()
        
        if self.config.sync_interval_seconds > 0:
            self._sync_task = asyncio.create_task(self._periodic_sync())
        
        logger.info("DeerFlow Integration Manager started")
    
    async def stop(self) -> None:
        """停止集成管理器"""
        self._running = False
        
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        
        logger.info("DeerFlow Integration Manager stopped")
    
    async def sync_all(self) -> dict[str, Any]:
        """执行完整同步
        
        Returns:
            同步结果摘要
        """
        result = {
            "skills": {},
            "tools": {},
            "errors": [],
        }
        
        try:
            if self.config.skills_sync_mode == "bidirectional":
                result["skills"] = self.skills_bridge.bidirectional_sync()
            elif self.config.skills_sync_mode == "to_deerflow":
                result["skills"] = {"to_deerflow": self.skills_bridge.sync_to_deerflow()}
            elif self.config.skills_sync_mode == "from_deerflow":
                result["skills"] = {"from_deerflow": self.skills_bridge.sync_from_deerflow()}
        except Exception as e:
            result["errors"].append(f"Skills sync failed: {e}")
            logger.error(f"Skills sync failed: {e}")
        
        logger.info(f"DeerFlow sync completed: {result}")
        return result
    
    async def _periodic_sync(self) -> None:
        """定期同步任务"""
        while self._running:
            try:
                await asyncio.sleep(self.config.sync_interval_seconds)
                await self.sync_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync failed: {e}")
    
    def register_astrbot_tools(
        self,
        toolset: ToolSet,
        deerflow_config_path: str | None = None,
    ) -> int:
        """注册 AstrBot Tools 到 DeerFlow
        
        Args:
            toolset: AstrBot ToolSet 实例
            deerflow_config_path: DeerFlow 配置路径（可选，默认使用配置中的路径）
            
        Returns:
            注册的工具数量
        """
        config_path = deerflow_config_path or self.config.deerflow_config_path
        
        return DeerFlowToolsBridge.register_astrbot_tools_to_deerflow_config(
            toolset=toolset,
            config_path=config_path,
            excluded_tools=self.config.excluded_tools,
        )
    
    def get_unified_skills_prompt(self) -> str:
        """获取统一的 Skills 系统提示"""
        return self.skills_bridge.build_unified_skills_prompt()
    
    def get_unified_skills(self) -> list:
        """获取统一的 Skills 列表"""
        return self.skills_bridge.get_unified_skills()
    
    def create_bridge_tools_module(
        self,
        toolset: ToolSet,
        output_dir: str | Path,
    ) -> dict[str, Any]:
        """创建桥接工具模块
        
        Args:
            toolset: AstrBot ToolSet 实例
            output_dir: 输出目录
            
        Returns:
            生成结果信息
        """
        return create_bridge_tools_from_toolset(toolset, output_dir)


def create_integration_manager_from_config(
    config_dict: dict[str, Any],
) -> DeerFlowIntegrationManager:
    """从配置字典创建集成管理器
    
    Args:
        config_dict: 配置字典
        
    Returns:
        DeerFlowIntegrationManager 实例
    """
    config = DeerFlowIntegrationConfig(
        api_base=config_dict.get("api_base", "http://127.0.0.1:2024"),
        skills_sync_mode=config_dict.get("skills", {}).get("sync_mode", "bidirectional"),
        astrbot_skills_path=config_dict.get("skills", {}).get("astrbot_path", "data/skills"),
        deerflow_skills_path=config_dict.get("skills", {}).get("deerflow_path", "deer-flow/skills"),
        share_astrbot_tools=config_dict.get("tools", {}).get("share_astrbot_tools", True),
        share_deerflow_tools=config_dict.get("tools", {}).get("share_deerflow_tools", True),
        excluded_tools=config_dict.get("tools", {}).get("excluded_tools", []),
        auto_sync_on_startup=config_dict.get("auto_sync_on_startup", True),
        sync_interval_seconds=config_dict.get("sync_interval_seconds", 300),
        deerflow_config_path=config_dict.get("deerflow_config_path", "deer-flow/config.yaml"),
    )
    
    return DeerFlowIntegrationManager.initialize(config)
