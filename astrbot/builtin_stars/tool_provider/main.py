from astrbot.core.star import Star
from astrbot.core.star.context import Context
from quart import request
from astrbot.dashboard.routes.route import Response

from .registry import ToolRegistry
from .mcp_adapter import MCPAdapter
from .api_wrapper_adapter import APIWrapperAdapter


class ToolProviderStar(Star):
    def __init__(self, context: Context):
        self.context = context
        self.registry = ToolRegistry()
        self.mcp_adapter = MCPAdapter(self.registry)
        self.api_adapter = APIWrapperAdapter(self.registry)

        context.register_web_api(
            route="/tool-provider/tools",
            view_handler=self.list_tools,
            methods=["GET"],
            desc="列出所有工具",
        )
        context.register_web_api(
            route="/tool-provider/tools/add",
            view_handler=self.add_tool,
            methods=["POST"],
            desc="添加工具",
        )
        context.register_web_api(
            route="/tool-provider/tools/update",
            view_handler=self.update_tool,
            methods=["POST"],
            desc="更新工具",
        )
        context.register_web_api(
            route="/tool-provider/tools/delete",
            view_handler=self.delete_tool,
            methods=["POST"],
            desc="删除工具",
        )
        context.register_web_api(
            route="/tool-provider/tools/toggle",
            view_handler=self.toggle_tool,
            methods=["POST"],
            desc="启用/禁用工具",
        )
        context.register_web_api(
            route="/tool-provider/tools/test",
            view_handler=self.test_tool,
            methods=["POST"],
            desc="测试工具",
        )
        context.register_web_api(
            route="/tool-provider/mcp/servers",
            view_handler=self.list_mcp_servers,
            methods=["GET"],
            desc="列出 MCP 服务器",
        )
        context.register_web_api(
            route="/tool-provider/mcp/add",
            view_handler=self.add_mcp_server,
            methods=["POST"],
            desc="添加 MCP 服务器",
        )
        context.register_web_api(
            route="/tool-provider/mcp/remove",
            view_handler=self.remove_mcp_server,
            methods=["POST"],
            desc="移除 MCP 服务器",
        )
        context.register_web_api(
            route="/tool-provider/reload",
            view_handler=self.reload_tools,
            methods=["POST"],
            desc="重载所有工具",
        )

    async def initialize(self):
        await self.registry.reload_all()

    async def terminate(self):
        self.registry.clear_all()
        await self.mcp_adapter.close_all()
        await self.api_adapter.close()

    async def list_tools(self):
        source = request.args.get("source")
        status = request.args.get("status")

        from .models import ToolSource, ToolStatus
        source_enum = ToolSource(source) if source else None
        status_enum = ToolStatus(status) if status else None

        tools = self.registry.list_tools(source_enum, status_enum)
        return Response().ok(tools).__dict__

    async def add_tool(self):
        data = await request.get_json()
        tool_type = data.get("type")
        config = data.get("config", {})

        try:
            if tool_type == "api_wrapper":
                name = await self.api_adapter.add_tool(config)
            else:
                return Response().error("Unknown tool type").__dict__

            return Response().ok({"name": name}, "Tool added successfully").__dict__
        except Exception as e:
            return Response().error(str(e)).__dict__

    async def update_tool(self):
        """更新工具配置"""
        data = await request.get_json()
        name = data.get("name")
        config = data.get("config", {})
        description = data.get("description")

        if not name:
            return Response().error("Tool name is required").__dict__

        try:
            # 获取工具当前信息
            meta = self.registry.get_meta(name)
            if not meta:
                return Response().error("Tool not found").__dict__

            # 根据工具类型执行更新
            if meta.source.value == "api_wrapper":
                # 先更新注册表中的配置
                success = await self.registry.update_tool(name, config, description)
                if not success:
                    return Response().error("Failed to update tool").__dict__

                # 重新注册工具以应用新配置
                # 先删除旧工具
                await self.registry.unregister_tool(name)
                # 使用新配置重新添加
                await self.api_adapter.add_tool(config)

                return Response().ok(None, "Tool updated successfully").__dict__
            else:
                return Response().error("Updating MCP tools is not supported yet").__dict__
        except Exception as e:
            return Response().error(str(e)).__dict__

    async def delete_tool(self):
        data = await request.get_json()
        name = data.get("name")

        success = await self.registry.unregister_tool(name)
        if success:
            return Response().ok(None, "Tool deleted").__dict__
        return Response().error("Tool not found").__dict__

    async def toggle_tool(self):
        data = await request.get_json()
        name = data.get("name")
        enabled = data.get("enabled", True)

        if enabled:
            success = await self.registry.enable_tool(name)
        else:
            success = await self.registry.disable_tool(name)

        if success:
            return Response().ok(None, f"Tool {'enabled' if enabled else 'disabled'}").__dict__
        return Response().error("Tool not found").__dict__

    async def test_tool(self):
        """测试工具，支持 API Wrapper 和 MCP 工具"""
        data = await request.get_json()
        tool_name = data.get("name")
        test_params = data.get("params", {})

        if not tool_name:
            return Response().error("Tool name is required").__dict__

        # 获取工具元数据
        meta = self.registry.get_meta(tool_name)
        if not meta:
            return Response().error(f"Tool '{tool_name}' not found").__dict__

        try:
            if meta.source.value == "api_wrapper":
                # 使用保存的配置测试 API Wrapper
                config = meta.config
                result = await self.api_adapter.test_tool(config, test_params)
                if result["success"]:
                    return Response().ok(result).__dict__
                return Response().error(result["error"]).__dict__

            elif meta.source.value == "mcp":
                # 测试 MCP 工具
                server_name = meta.config.get("server")
                mcp_tool_name = meta.config.get("tool")
                if not server_name or not mcp_tool_name:
                    return Response().error("Invalid MCP tool configuration").__dict__

                result = await self.mcp_adapter.test_tool(server_name, mcp_tool_name, test_params)
                if result["success"]:
                    return Response().ok(result).__dict__
                return Response().error(result["error"]).__dict__

            else:
                return Response().error(f"Testing {meta.source.value} tools is not supported").__dict__

        except Exception as e:
            return Response().error(f"Test failed: {str(e)}").__dict__

    async def list_mcp_servers(self):
        servers = self.mcp_adapter.list_servers()
        return Response().ok(servers).__dict__

    async def add_mcp_server(self):
        data = await request.get_json()
        name = data.get("name")
        config = data.get("config", {})

        try:
            tools = await self.mcp_adapter.add_server(name, config)
            return Response().ok({"tools": tools}, f"Added {len(tools)} tools").__dict__
        except Exception as e:
            return Response().error(str(e)).__dict__

    async def remove_mcp_server(self):
        data = await request.get_json()
        name = data.get("name")

        success = await self.mcp_adapter.remove_server(name)
        if success:
            return Response().ok(None, "MCP server removed").__dict__
        return Response().error("Server not found").__dict__

    async def reload_tools(self):
        await self.registry.reload_all()
        return Response().ok(None, "Tools reloaded").__dict__
