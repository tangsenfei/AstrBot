"""
DeerFlow Tools Bridge - Tools 双向转换桥接器

实现 AstrBot FunctionTool 和 LangChain BaseTool 之间的双向转换
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from astrbot.core import logger
from astrbot.core.agent.tool import FunctionTool, ToolSet

if TYPE_CHECKING:
    from langchain.tools import BaseTool

P = ParamSpec("P")
T = TypeVar("T")


class DeerFlowToolsBridge:
    """Tools 双向转换桥接器
    
    实现 AstrBot FunctionTool 和 LangChain BaseTool 之间的双向转换，
    支持 AstrBot Tools 在 DeerFlow 中使用，反之亦然。
    """
    
    _astrbot_tools_module_path = "astrbot.tools.deerflow_bridge"
    
    @staticmethod
    def astrbot_to_langchain(
        tool: FunctionTool,
        context_provider: Callable[[], Any] | None = None,
    ) -> "BaseTool":
        """将 AstrBot FunctionTool 转换为 LangChain BaseTool
        
        Args:
            tool: AstrBot FunctionTool 实例
            context_provider: 提供 AstrBot 上下文的回调函数
            
        Returns:
            LangChain BaseTool 实例
        """
        from langchain.tools import tool as langchain_tool
        
        @langchain_tool(tool.name)
        def converted_tool(**kwargs) -> str:
            f"""{tool.description}"""
            if tool.handler is None:
                return f"Error: Tool '{tool.name}' has no handler"
            
            try:
                if asyncio.iscoroutinefunction(tool.handler):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                asyncio.run,
                                tool.handler(**kwargs)
                            )
                            result = future.result(timeout=300)
                    else:
                        result = loop.run_until_complete(tool.handler(**kwargs))
                else:
                    result = tool.handler(**kwargs)
                
                if result is None:
                    return "Tool executed successfully (no output)"
                return str(result)
            except Exception as e:
                logger.error(f"Tool '{tool.name}' execution failed: {e}")
                return f"Error: {str(e)}"
        
        converted_tool.description = tool.description
        return converted_tool
    
    @staticmethod
    def toolset_to_langchain_tools(
        toolset: ToolSet,
        context_provider: Callable[[], Any] | None = None,
    ) -> list["BaseTool"]:
        """将 AstrBot ToolSet 转换为 LangChain Tools 列表
        
        Args:
            toolset: AstrBot ToolSet 实例
            context_provider: 提供 AstrBot 上下文的回调函数
            
        Returns:
            LangChain BaseTool 列表
        """
        return [
            DeerFlowToolsBridge.astrbot_to_langchain(tool, context_provider)
            for tool in toolset.tools
            if tool.active
        ]
    
    @staticmethod
    def generate_deerflow_tool_config(
        toolset: ToolSet,
        output_path: str | Path,
        group: str = "astrbot",
        excluded_tools: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """生成 DeerFlow 工具配置
        
        将 AstrBot Tools 写入 DeerFlow 配置格式
        
        Args:
            toolset: AstrBot ToolSet 实例
            output_path: 输出配置文件路径
            group: 工具分组名称
            excluded_tools: 要排除的工具名称列表
            
        Returns:
            工具配置列表
        """
        import yaml
        
        excluded = set(excluded_tools or [])
        tool_configs = []
        
        for tool in toolset.tools:
            if not tool.active or tool.name in excluded:
                continue
            
            tool_configs.append({
                "name": f"astrbot_{tool.name}",
                "group": group,
                "use": f"{DeerFlowToolsBridge._astrbot_tools_module_path}:{tool.name}_tool",
                "description": tool.description,
            })
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"tools": tool_configs},
                f,
                default_flow_style=False,
                allow_unicode=True,
            )
        
        return tool_configs
    
    @staticmethod
    def create_deerflow_tools_module(
        toolset: ToolSet,
        output_dir: str | Path,
        module_name: str = "deerflow_bridge",
    ) -> Path:
        """创建 DeerFlow 可导入的 Tools 模块
        
        动态生成 Python 模块，包含所有 AstrBot Tools 的 LangChain 版本
        
        Args:
            toolset: AstrBot ToolSet 实例
            output_dir: 输出目录
            module_name: 模块名称
            
        Returns:
            生成的模块文件路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        module_path = output_dir / f"{module_name}.py"
        
        lines = [
            '"""',
            f'AstrBot Tools for DeerFlow - Auto-generated',
            '"""',
            'from langchain.tools import tool',
            '',
        ]
        
        for func_tool in toolset.tools:
            if not func_tool.active:
                continue
            
            tool_name = func_tool.name
            tool_desc = func_tool.description.replace('"""', '\\"').replace("'", "\\'")
            
            lines.extend([
                f'@tool("{tool_name}")',
                f'def {tool_name}_tool(**kwargs) -> str:',
                f'    """{tool_desc}"""',
                f'    # This is a bridge tool. Actual execution is handled by AstrBot.',
                f'    # The tool should be registered via DeerFlowToolsBridge.',
                f'    return f"Bridge tool {tool_name} called with: {{kwargs}}"',
                '',
            ])
        
        lines.append('')
        lines.append('# Tool registry for runtime binding')
        lines.append('_TOOLS_REGISTRY = {}')
        lines.append('')
        lines.append('def register_tool(name: str, handler):')
        lines.append('    """Register a tool handler at runtime"""')
        lines.append('    _TOOLS_REGISTRY[name] = handler')
        lines.append('')
        
        with open(module_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        (output_dir / "__init__.py").write_text(
            f"from .{module_name} import *\n"
        )
        
        return module_path
    
    @staticmethod
    def register_astrbot_tools_to_deerflow_config(
        toolset: ToolSet,
        config_path: str | Path,
        group: str = "astrbot",
        excluded_tools: list[str] | None = None,
    ) -> int:
        """将 AstrBot Tools 注册到 DeerFlow 配置文件
        
        Args:
            toolset: AstrBot ToolSet 实例
            config_path: DeerFlow config.yaml 路径
            group: 工具分组名称
            excluded_tools: 要排除的工具名称列表
            
        Returns:
            注册的工具数量
        """
        import yaml
        
        config_path = Path(config_path)
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        existing_names = {t.get("name") for t in config.get("tools", [])}
        excluded = set(excluded_tools or [])
        registered = 0
        
        for tool in toolset.tools:
            if not tool.active or tool.name in excluded:
                continue
            
            tool_entry = {
                "name": f"astrbot_{tool.name}",
                "group": group,
                "use": f"{DeerFlowToolsBridge._astrbot_tools_module_path}:{tool.name}_tool",
            }
            
            if tool_entry["name"] not in existing_names:
                config.setdefault("tools", []).append(tool_entry)
                registered += 1
                logger.info(f"Registered AstrBot tool '{tool.name}' to DeerFlow config")
        
        if registered > 0:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        return registered


def create_bridge_tools_from_toolset(
    toolset: ToolSet,
    output_dir: str | Path,
) -> dict[str, Any]:
    """创建完整的桥接工具模块
    
    便利函数，一次性创建所有必要的文件
    
    Args:
        toolset: AstrBot ToolSet 实例
        output_dir: 输出目录
        
    Returns:
        包含生成文件信息的字典
    """
    output_dir = Path(output_dir)
    
    module_path = DeerFlowToolsBridge.create_deerflow_tools_module(
        toolset, output_dir
    )
    
    config_path = output_dir / "astrbot_tools.yaml"
    tool_configs = DeerFlowToolsBridge.generate_deerflow_tool_config(
        toolset, config_path
    )
    
    return {
        "module_path": str(module_path),
        "config_path": str(config_path),
        "tools_count": len(tool_configs),
        "tools": [t["name"] for t in tool_configs],
    }
