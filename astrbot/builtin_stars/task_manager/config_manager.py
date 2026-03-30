"""
Config Manager - 配置管理器

管理 DeerFlow LLM 配置，支持直接选择 AstrBot 已配置的 LLM
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from astrbot.core.star.context import Context

CONFIG_FILE_NAME = "deerflow_config.json"


@dataclass
class LLMProviderConfig:
    """LLM 提供者配置"""
    name: str
    provider_type: str = "unknown"
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] = field(default_factory=list)
    default_model: str | None = None
    is_enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "api_key": "***" if self.api_key else None,
            "base_url": self.base_url,
            "models": self.models,
            "default_model": self.default_model,
            "is_enabled": self.is_enabled,
        }


@dataclass
class DeerFlowLLMConfig:
    """DeerFlow LLM 配置"""
    provider_id: str = ""  # AstrBot 提供商 ID
    thinking_enabled: bool = True
    is_plan_mode: bool = True
    subagent_enabled: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "thinking_enabled": self.thinking_enabled,
            "is_plan_mode": self.is_plan_mode,
            "subagent_enabled": self.subagent_enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeerFlowLLMConfig":
        return cls(
            provider_id=data.get("provider_id", ""),
            thinking_enabled=data.get("thinking_enabled", True),
            is_plan_mode=data.get("is_plan_mode", True),
            subagent_enabled=data.get("subagent_enabled", False),
        )


class ConfigManager:
    """配置管理器
    
    管理 DeerFlow LLM 配置，支持直接选择 AstrBot 已配置的 LLM
    """
    
    def __init__(self, context: "Context") -> None:
        self.context = context
        self._astrbot_providers: dict[str, LLMProviderConfig] = {}
        self._deerflow_config: DeerFlowLLMConfig = DeerFlowLLMConfig()
        self._config_path: Path | None = None
        self._providers_loaded = False
    
    async def initialize(self) -> None:
        """初始化配置管理器"""
        self._config_path = self._get_config_path()
        self._load_deerflow_config()
        logger.info("ConfigManager initialized")
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        from astrbot.core.star.star_tools import StarTools
        data_dir = StarTools.get_data_dir("task_manager")
        return data_dir / CONFIG_FILE_NAME
    
    def _get_astrbot_config_path(self) -> Path:
        """获取 AstrBot 配置文件路径"""
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        return Path(get_astrbot_data_path()) / "cmd_config.json"
    
    def _load_providers_from_config(self) -> None:
        """从配置文件加载提供商信息"""
        if self._providers_loaded:
            return
        
        try:
            config_path = self._get_astrbot_config_path()
            if not config_path.exists():
                logger.warning(f"AstrBot config not found: {config_path}")
                return
            
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            
            providers = config.get("provider", [])
            logger.info(f"Found {len(providers)} providers from config file")
            
            for provider in providers:
                provider_id = provider.get("id", "")
                if not provider_id:
                    continue
                
                provider_type = provider.get("type", "unknown")
                provider_model = provider.get("model", [])
                
                if isinstance(provider_model, str):
                    models = [provider_model]
                else:
                    models = provider_model if provider_model else []
                
                config_obj = LLMProviderConfig(
                    name=provider_id,
                    provider_type=provider_type,
                    api_key=provider.get("api_key"),
                    base_url=provider.get("api_base"),
                    models=models,
                    default_model=models[0] if models else None,
                    is_enabled=True,
                )
                self._astrbot_providers[provider_id] = config_obj
            
            self._providers_loaded = True
            logger.info(f"Loaded {len(self._astrbot_providers)} AstrBot providers from config")
            
        except Exception as e:
            logger.error(f"Failed to load AstrBot providers from config: {e}")
    
    def _load_deerflow_config(self) -> None:
        """加载 DeerFlow 配置"""
        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._deerflow_config = DeerFlowLLMConfig.from_dict(data)
                logger.info(f"Loaded DeerFlow config from: {self._config_path}")
            except Exception as e:
                logger.warning(f"Failed to load DeerFlow config: {e}")
    
    def _save_deerflow_config(self) -> bool:
        """保存 DeerFlow 配置"""
        if not self._config_path:
            return False
        
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._deerflow_config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved DeerFlow config to: {self._config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save DeerFlow config: {e}")
            return False
    
    def get_astrbot_providers(self) -> list[LLMProviderConfig]:
        """获取 AstrBot 已配置的 LLM 提供者列表"""
        self._load_providers_from_config()
        return list(self._astrbot_providers.values())
    
    def get_astrbot_provider(self, name: str) -> LLMProviderConfig | None:
        """获取指定的 AstrBot LLM 提供者"""
        self._load_providers_from_config()
        return self._astrbot_providers.get(name)
    
    def get_deerflow_config(self) -> DeerFlowLLMConfig:
        """获取 DeerFlow LLM 配置"""
        return self._deerflow_config
    
    def set_provider(self, provider_id: str) -> bool:
        """设置 LLM 提供者
        
        Args:
            provider_id: AstrBot 提供商 ID
        """
        self._deerflow_config.provider_id = provider_id
        return self._save_deerflow_config()
    
    def get_deerflow_model_for_provider(self, provider_id: str) -> str:
        """获取 DeerFlow 模型名称
        
        直接使用传入的模型名称（provider_id 实际存储的是 DeerFlow 模型名）
        
        Args:
            provider_id: DeerFlow 模型名称
            
        Returns:
            DeerFlow 模型名称
        """
        if not provider_id:
            return self.get_default_model()
        
        # 验证模型是否有效
        available_models = {m['name'] for m in self.get_deerflow_available_models()}
        if provider_id in available_models:
            return provider_id
        
        # 无效则返回默认模型
        logger.warning(f"Model '{provider_id}' not found in DeerFlow config, using default")
        return self.get_default_model()
    
    def set_options(
        self,
        thinking_enabled: bool | None = None,
        is_plan_mode: bool | None = None,
        subagent_enabled: bool | None = None,
    ) -> bool:
        """设置 DeerFlow 选项"""
        if thinking_enabled is not None:
            self._deerflow_config.thinking_enabled = thinking_enabled
        if is_plan_mode is not None:
            self._deerflow_config.is_plan_mode = is_plan_mode
        if subagent_enabled is not None:
            self._deerflow_config.subagent_enabled = subagent_enabled
        return self._save_deerflow_config()
    
    def get_deerflow_available_models(self) -> list[dict[str, Any]]:
        """获取 DeerFlow 可用模型列表
        
        Returns:
            模型列表，每个模型包含 name, display_name, supports_thinking 等
        """
        try:
            # 从 DeerFlow 配置中读取模型列表
            deerflow_config_path = Path(__file__).parent.parent.parent.parent.parent / "deer-flow" / "config.yaml"
            if not deerflow_config_path.exists():
                logger.warning(f"DeerFlow config not found: {deerflow_config_path}")
                return []
            
            import yaml
            with open(deerflow_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            models = config.get('models', [])
            return [
                {
                    "name": model.get('name', ''),
                    "display_name": model.get('display_name', model.get('name', '')),
                    "supports_thinking": model.get('supports_thinking', False),
                    "supports_vision": model.get('supports_vision', False),
                }
                for model in models
            ]
        except Exception as e:
            logger.error(f"Failed to get DeerFlow models: {e}")
            return []
    
    def get_selected_model(self) -> str:
        """获取当前选择的 DeerFlow 模型名称"""
        return self._deerflow_config.model_name
    
    def get_default_model(self) -> str:
        """获取默认模型（从 DeerFlow 配置中读取）"""
        models = self.get_deerflow_available_models()
        if not models:
            return ""
        
        # 如果已选择模型且有效，返回已选择的
        selected = self._deerflow_config.model_name
        if selected and any(m['name'] == selected for m in models):
            return selected
        
        # 返回第一个模型作为默认
        return models[0]['name']
    
    def get_available_models(self) -> list[dict[str, str]]:
        """获取 DeerFlow 可用模型列表（用于 API 兼容）"""
        return [
            {
                "provider": model['name'],
                "model": model['name'],
                "display_name": model['display_name'],
            }
            for model in self.get_deerflow_available_models()
        ]
    
    def get_config_summary(self) -> dict[str, Any]:
        """获取配置摘要"""
        provider_id = self._deerflow_config.provider_id
        deerflow_model = self.get_deerflow_model_for_provider(provider_id) if provider_id else self.get_default_model()
        
        return {
            "deerflow": self._deerflow_config.to_dict(),
            "deerflow_models": self.get_deerflow_available_models(),
            "available_models": self.get_available_models(),
            "default_model": self.get_default_model(),
            "selected_provider": provider_id,
            "deerflow_model": deerflow_model,
        }
