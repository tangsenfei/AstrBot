import json
import asyncio
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime

from astrbot.core.agent.tool import FunctionTool
from astrbot.core.provider.register import llm_tools

from .models import ToolSource, ToolStatus


@dataclass
class ToolMeta:
    name: str
    source: ToolSource
    description: str
    status: ToolStatus = ToolStatus.ENABLED
    config: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source.value,
            "description": self.description,
            "status": self.status.value,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ToolRegistry:
    MODULE_PATH = "astrbot.builtin_stars.tool_provider"

    def __init__(self):
        self._tools: Dict[str, FunctionTool] = {}
        self._metas: Dict[str, ToolMeta] = {}
        self._llm_tools = llm_tools
        self._lock = asyncio.Lock()
        # 配置文件路径：插件目录下的 config.json
        self._config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config.json"
        )

    def _convert_params_to_func_args(self, parameters: dict) -> list:
        func_args = []
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])
        
        for param_name, param_def in properties.items():
            param_type = param_def.get("type", "string")
            param_desc = param_def.get("description", "")
            
            func_args.append({
                "type": param_type,
                "name": param_name,
                "description": param_desc,
            })
        
        return func_args

    async def _register_tool_internal(
        self,
        name: str,
        handler: Callable,
        parameters: dict,
        description: str,
        source: ToolSource,
        config: dict = None,
        persist: bool = True,
    ) -> FunctionTool:
        """内部注册工具方法，不获取锁，供其他方法调用"""
        tool = FunctionTool(
            name=name,
            parameters=parameters,
            description=description,
            handler=handler,
        )
        tool.handler_module_path = self.MODULE_PATH
        tool.active = True

        now = datetime.now().isoformat()
        meta = ToolMeta(
            name=name,
            source=source,
            description=description,
            status=ToolStatus.ENABLED,
            config=config or {},
            created_at=now,
            updated_at=now,
        )

        if name in self._tools:
            await self._remove_tool_internal(name)

        self._tools[name] = tool
        self._metas[name] = meta
        
        func_args = self._convert_params_to_func_args(parameters)
        desc = description
        handler = handler

        self._llm_tools.add_func(name, func_args, desc, handler)

        if persist:
            await self._persist_config()
        return tool

    async def register_tool(
        self,
        name: str,
        handler: Callable,
        parameters: dict,
        description: str,
        source: ToolSource,
        config: dict = None,
    ) -> FunctionTool:
        async with self._lock:
            return await self._register_tool_internal(
                name, handler, parameters, description, source, config
            )

    async def unregister_tool(self, name: str) -> bool:
        async with self._lock:
            return await self._remove_tool_internal(name)

    async def _remove_tool_internal(self, name: str) -> bool:
        if name not in self._tools:
            return False

        try:
            self._llm_tools.remove_tool(name)
        except Exception:
            pass

        del self._tools[name]
        del self._metas[name]

        await self._persist_config()
        return True

    async def update_tool(self, name: str, config: dict, description: str = None) -> bool:
        """更新工具配置"""
        async with self._lock:
            if name not in self._tools:
                return False

            # 更新元数据
            self._metas[name].config = config
            if description:
                self._metas[name].description = description
            self._metas[name].updated_at = datetime.now().isoformat()

            # 重新注册工具以应用新配置
            await self._persist_config()
            return True

    async def enable_tool(self, name: str) -> bool:
        async with self._lock:
            if name not in self._tools:
                return False
            self._tools[name].active = True
            self._metas[name].status = ToolStatus.ENABLED
            self._metas[name].updated_at = datetime.now().isoformat()
            await self._persist_config()
            return True

    async def disable_tool(self, name: str) -> bool:
        async with self._lock:
            if name not in self._tools:
                return False
            self._tools[name].active = False
            self._metas[name].status = ToolStatus.DISABLED
            self._metas[name].updated_at = datetime.now().isoformat()
            await self._persist_config()
            return True

    def get_tool(self, name: str) -> Optional[FunctionTool]:
        return self._tools.get(name)

    def get_meta(self, name: str) -> Optional[ToolMeta]:
        return self._metas.get(name)

    def list_tools(
        self,
        source: Optional[ToolSource] = None,
        status: Optional[ToolStatus] = None,
    ) -> List[dict]:
        result = []
        for name, meta in self._metas.items():
            if source and meta.source != source:
                continue
            if status and meta.status != status:
                continue
            result.append(meta.to_dict())
        return result

    async def reload_all(self):
        async with self._lock:
            config = await self._load_config()
            await self._load_from_config(config)

    async def _persist_config(self):
        """将配置持久化到插件目录下的文件"""
        config = {
            "tools": {
                name: meta.to_dict()
                for name, meta in self._metas.items()
            }
        }
        try:
            # 使用异步方式写入文件
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: json.dump(
                    config,
                    open(self._config_file, 'w', encoding='utf-8'),
                    ensure_ascii=False,
                    indent=2
                )
            )
        except Exception as e:
            print(f"[ToolRegistry] Failed to persist config: {e}")

    async def _load_config(self) -> dict:
        """从插件目录下的文件加载配置"""
        try:
            if not os.path.exists(self._config_file):
                return {"tools": {}}

            loop = asyncio.get_event_loop()
            config = await loop.run_in_executor(
                None,
                lambda: json.load(open(self._config_file, 'r', encoding='utf-8'))
            )
            return config
        except Exception as e:
            print(f"[ToolRegistry] Failed to load config: {e}")
            return {"tools": {}}

    async def _load_from_config(self, config: dict):
        tools_config = config.get("tools", {})
        
        for name, tool_data in tools_config.items():
            source_str = tool_data.get("source")
            if not source_str:
                continue
            
            try:
                source = ToolSource(source_str)
            except ValueError:
                continue
            
            tool_config = tool_data.get("config", {})
            description = tool_data.get("description", "")
            enabled = tool_data.get("status", "enabled") == "enabled"
            
            if source == ToolSource.API_WRAPPER:
                from .api_wrapper_adapter import APIWrapperAdapter
                adapter = APIWrapperAdapter(self)
                # 使用内部方法注册工具，不持久化（配置已从文件加载）
                await adapter.add_tool(tool_config, persist=False)
                if not enabled:
                    await self.disable_tool(name)
            
            elif source == ToolSource.MCP:
                pass

    def clear_all(self):
        for name in list(self._tools.keys()):
            try:
                self._llm_tools.remove_tool(name)
            except Exception:
                pass
        self._tools.clear()
        self._metas.clear()
