"""
智能体管理模块 - 工具服务

提供工具的 CRUD 操作、测试、导入导出等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from astrbot.core.provider.func_tool_manager import FunctionToolManager

    from ..database import Database

from ..models import Tool, ToolSource


class ToolService:
    """工具管理服务"""

    def __init__(self, db: Database, func_tool_manager: FunctionToolManager | None = None):
        self.db = db
        self._func_tool_manager = func_tool_manager

    @property
    def func_tool_manager(self) -> FunctionToolManager | None:
        """获取 FunctionToolManager 实例"""
        if self._func_tool_manager is None:
            # 尝试从全局上下文获取
            try:
                # 这里需要获取全局的 context，但这种方式不太优雅
                # 更好的方式是在初始化时传入
                logger.warning("FunctionToolManager not initialized, tool functionality may be limited")
            except Exception as e:
                logger.error(f"Failed to get FunctionToolManager: {e}")
        return self._func_tool_manager

    def get_tools(self, source: str | None = None) -> list[Tool]:
        """获取工具列表

        Args:
            source: 工具来源筛选，可选值: builtin, mcp, custom, api_wrapper

        Returns:
            工具列表
        """
        tools = []

        # 1. 获取数据库中的自定义工具和 API 封装工具
        if source is None or source in ("custom", "api_wrapper"):
            where_clause = "1=1"
            params: tuple = ()

            if source:
                where_clause = "source = ?"
                params = (source,)

            db_tools = self.db.select_all(
                "tools",
                where=where_clause,
                where_params=params,
                order_by="created_at DESC"
            )

            for row in db_tools:
                try:
                    tool = self._row_to_tool(row)
                    tools.append(tool)
                except Exception as e:
                    logger.error(f"Failed to parse tool {row.get('id')}: {e}")

        # 2. 获取内置工具（从 func_tool_manager）
        if source is None or source == "builtin":
            builtin_tools = self._get_builtin_tools()
            tools.extend(builtin_tools)

        # 3. 获取 MCP 工具
        if source is None or source == "mcp":
            mcp_tools = self._get_mcp_tools()
            tools.extend(mcp_tools)

        return tools

    def get_tool(self, tool_id: str) -> Tool | None:
        """获取单个工具

        Args:
            tool_id: 工具 ID

        Returns:
            工具对象，不存在则返回 None
        """
        # 先从数据库查找
        row = self.db.select_one("tools", where="id = ?", where_params=(tool_id,))
        if row:
            return self._row_to_tool(row)

        # 从内置工具查找
        builtin_tools = self._get_builtin_tools()
        for tool in builtin_tools:
            if tool.id == tool_id:
                return tool

        # 从 MCP 工具查找
        mcp_tools = self._get_mcp_tools()
        for tool in mcp_tools:
            if tool.id == tool_id:
                return tool

        return None

    def create_tool(self, data: dict[str, Any]) -> Tool:
        """创建工具

        Args:
            data: 工具数据

        Returns:
            创建的工具对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("工具名称不能为空")

        # 生成 ID
        tool_id = data.get("id") or f"tool_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_tool(tool_id)
        if existing:
            raise ValueError(f"工具 ID '{tool_id}' 已存在")

        # 设置默认值
        source = ToolSource(data.get("source", "custom"))
        if source in (ToolSource.BUILTIN, ToolSource.MCP):
            raise ValueError(f"不能创建 {source.value} 类型的工具")

        now = datetime.now()
        tool_data = {
            "id": tool_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "source": source.value,
            "parameters": data.get("parameters", {}),
            "return_type": data.get("return_type"),
            "version": data.get("version", "1.0.0"),
            "enabled": data.get("enabled", True),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("tools", tool_data)

        logger.info(f"Created tool: {tool_id}")
        return self._row_to_tool(tool_data)

    def update_tool(self, tool_id: str, data: dict[str, Any]) -> Tool | None:
        """更新工具

        Args:
            tool_id: 工具 ID
            data: 更新数据

        Returns:
            更新后的工具对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找工具
        row = self.db.select_one("tools", where="id = ?", where_params=(tool_id,))
        if not row:
            return None

        # 检查工具来源
        source = ToolSource(row["source"])
        if source in (ToolSource.BUILTIN, ToolSource.MCP):
            raise ValueError(f"不能修改 {source.value} 类型的工具")

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = [
            "name", "description", "parameters", "return_type",
            "version", "enabled", "metadata"
        ]

        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        # 更新数据库
        self.db.update(
            "tools",
            update_data,
            where="id = ?",
            where_params=(tool_id,)
        )

        logger.info(f"Updated tool: {tool_id}")
        return self.get_tool(tool_id)

    def delete_tool(self, tool_id: str) -> bool:
        """删除工具

        Args:
            tool_id: 工具 ID

        Returns:
            是否删除成功

        Raises:
            ValueError: 不能删除内置或 MCP 工具
        """
        # 查找工具
        row = self.db.select_one("tools", where="id = ?", where_params=(tool_id,))
        if not row:
            return False

        # 检查工具来源
        source = ToolSource(row["source"])
        if source in (ToolSource.BUILTIN, ToolSource.MCP):
            raise ValueError(f"不能删除 {source.value} 类型的工具")

        # 删除工具
        self.db.delete("tools", where="id = ?", where_params=(tool_id,))
        logger.info(f"Deleted tool: {tool_id}")
        return True

    async def test_tool(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """测试工具

        Args:
            tool_id: 工具 ID
            params: 测试参数

        Returns:
            测试结果

        Raises:
            ValueError: 工具不存在或参数错误
        """
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"工具 '{tool_id}' 不存在")

        result = {
            "tool_id": tool_id,
            "tool_name": tool.name,
            "params": params,
            "success": False,
            "output": None,
            "error": None,
            "execution_time_ms": 0,
        }

        start_time = datetime.now()

        try:
            # 根据工具来源执行测试
            if tool.source == ToolSource.BUILTIN:
                output = await self._test_builtin_tool(tool, params)
            elif tool.source == ToolSource.MCP:
                output = await self._test_mcp_tool(tool, params)
            elif tool.source == ToolSource.CUSTOM:
                output = await self._test_custom_tool(tool, params)
            elif tool.source == ToolSource.API_WRAPPER:
                output = await self._test_api_wrapper_tool(tool, params)
            else:
                raise ValueError(f"不支持的工具来源: {tool.source.value}")

            result["success"] = True
            result["output"] = output

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Tool test failed: {tool_id} - {e}")

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)

        return result

    def import_tools(self, tools_data: list[dict[str, Any]]) -> list[Tool]:
        """批量导入工具

        Args:
            tools_data: 工具数据列表

        Returns:
            导入的工具列表
        """
        imported_tools = []

        for data in tools_data:
            try:
                # 生成新的 ID 避免冲突
                if "id" in data:
                    original_id = data["id"]
                    existing = self.get_tool(data["id"])
                    if existing:
                        data["id"] = f"{original_id}_{uuid.uuid4().hex[:4]}"

                tool = self.create_tool(data)
                imported_tools.append(tool)
            except Exception as e:
                logger.error(f"Failed to import tool: {e}")

        logger.info(f"Imported {len(imported_tools)} tools")
        return imported_tools

    def export_tools(self, tool_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """导出工具

        Args:
            tool_ids: 要导出的工具 ID 列表，为 None 则导出所有可导出的工具

        Returns:
            工具数据列表
        """
        exported = []

        if tool_ids:
            tools = [self.get_tool(tid) for tid in tool_ids]
            tools = [t for t in tools if t is not None]
        else:
            # 导出所有自定义和 API 封装工具
            tools = self.get_tools(source="custom") + self.get_tools(source="api_wrapper")

        for tool in tools:
            # 只导出自定义和 API 封装工具
            if tool.source in (ToolSource.CUSTOM, ToolSource.API_WRAPPER):
                exported.append(tool.to_dict())

        logger.info(f"Exported {len(exported)} tools")
        return exported

    # ==================== 私有方法 ====================

    def _row_to_tool(self, row: dict[str, Any]) -> Tool:
        """将数据库行转换为 Tool 对象"""
        return Tool(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            source=ToolSource(row.get("source", "custom")),
            parameters=self._parse_json(row.get("parameters", "{}")),
            return_type=row.get("return_type"),
            version=row.get("version", "1.0.0"),
            enabled=bool(row.get("enabled", 1)),
            metadata=self._parse_json(row.get("metadata", "{}")),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )

    def _parse_json(self, value: str | dict | list | None) -> dict | list:
        """解析 JSON 字符串"""
        if value is None:
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_builtin_tools(self) -> list[Tool]:
        """获取内置工具列表"""
        tools = []

        if self._func_tool_manager:
            try:
                for func_tool in self._func_tool_manager.iter_builtin_tools():
                    tool = Tool(
                        id=f"builtin_{func_tool.name}",
                        name=func_tool.name,
                        description=func_tool.description or "",
                        source=ToolSource.BUILTIN,
                        parameters=func_tool.parameters or {},
                        return_type=None,
                        version="1.0.0",
                        enabled=getattr(func_tool, "active", True),
                        metadata={
                            "handler_module_path": getattr(func_tool, "handler_module_path", None),
                            "is_background_task": getattr(func_tool, "is_background_task", False),
                            "is_astrbot_builtin": True,
                        },
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    tools.append(tool)

                for func_tool in self._func_tool_manager.func_list:
                    if isinstance(func_tool, type) and hasattr(func_tool, "mcp_server_name"):
                        continue
                    if hasattr(func_tool, "mcp_server_name"):
                        continue

                    tool = Tool(
                        id=f"builtin_{func_tool.name}",
                        name=func_tool.name,
                        description=func_tool.description or "",
                        source=ToolSource.BUILTIN,
                        parameters=func_tool.parameters or {},
                        return_type=None,
                        version="1.0.0",
                        enabled=getattr(func_tool, "active", True),
                        metadata={
                            "handler_module_path": getattr(func_tool, "handler_module_path", None),
                            "is_background_task": getattr(func_tool, "is_background_task", False),
                            "is_astrbot_builtin": False,
                        },
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    tools.append(tool)

            except Exception as e:
                logger.error(f"Failed to get builtin tools from FunctionToolManager: {e}")

        return tools

    def _get_mcp_tools(self) -> list[Tool]:
        """获取 MCP 工具列表"""
        tools = []

        if not self._func_tool_manager:
            return tools

        try:
            for func_tool in self._func_tool_manager.func_list:
                # 只处理 MCP 工具
                if not hasattr(func_tool, "mcp_server_name"):
                    continue

                tool = Tool(
                    id=f"mcp_{func_tool.mcp_server_name}_{func_tool.name}",
                    name=func_tool.name,
                    description=func_tool.description or "",
                    source=ToolSource.MCP,
                    parameters=func_tool.parameters or {},
                    return_type=None,
                    version="1.0.0",
                    enabled=getattr(func_tool, "active", True),
                    metadata={
                        "mcp_server_name": func_tool.mcp_server_name,
                    },
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                tools.append(tool)

        except Exception as e:
            logger.error(f"Failed to get MCP tools: {e}")

        return tools

    async def _test_builtin_tool(self, tool: Tool, params: dict[str, Any]) -> Any:
        """测试内置工具"""
        if not self._func_tool_manager:
            raise ValueError("FunctionToolManager 未初始化")

        try:
            # 获取原始工具名称（去掉 builtin_ 前缀）
            original_name = tool.name
            func_tool = self._func_tool_manager.get_func(original_name)

            if not func_tool:
                raise ValueError(f"内置工具 '{original_name}' 不存在")

            if not func_tool.handler:
                raise ValueError(f"工具 '{original_name}' 没有可执行的处理器")

            # 执行工具
            result = await func_tool.handler(**params)

            if hasattr(result, "__aiter__"):
                # 异步生成器
                outputs = []
                async for item in result:
                    outputs.append(str(item))
                return "\n".join(outputs)

            return result

        except Exception as e:
            raise ValueError(f"执行内置工具失败: {e}") from e

    async def _test_mcp_tool(self, tool: Tool, params: dict[str, Any]) -> Any:
        """测试 MCP 工具"""
        if not self._func_tool_manager:
            raise ValueError("FunctionToolManager 未初始化")

        try:
            mcp_server_name = tool.metadata.get("mcp_server_name")
            if not mcp_server_name:
                raise ValueError("MCP 工具缺少服务器名称")

            # 获取 MCP 客户端
            mcp_client = self._func_tool_manager.mcp_client_dict.get(mcp_server_name)
            if not mcp_client:
                raise ValueError(f"MCP 服务器 '{mcp_server_name}' 未连接")

            # 调用 MCP 工具
            result = await mcp_client.call_tool(tool.name, params)

            return result

        except Exception as e:
            raise ValueError(f"执行 MCP 工具失败: {e}") from e

    async def _test_custom_tool(self, tool: Tool, params: dict[str, Any]) -> Any:
        """测试自定义工具"""
        # TODO: 实现自定义工具的执行逻辑
        raise ValueError("自定义工具测试功能尚未实现")

    async def _test_api_wrapper_tool(self, tool: Tool, params: dict[str, Any]) -> Any:
        """测试 API 封装工具"""
        try:
            from astrbot.builtin_stars.tool_provider.api_wrapper_adapter import (
                APIWrapperAdapter,
            )

            # 从 metadata 获取 API 配置
            api_config = tool.metadata.get("api_config", {})
            if not api_config:
                raise ValueError("API 封装工具缺少 API 配置")

            adapter = APIWrapperAdapter(None)
            result = await adapter.test_tool(api_config, params)

            if result.get("success"):
                return result.get("output")
            else:
                raise ValueError(result.get("error", "API 调用失败"))

        except Exception as e:
            raise ValueError(f"执行 API 封装工具失败: {e}") from e
