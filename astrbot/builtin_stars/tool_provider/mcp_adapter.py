import asyncio
from typing import Optional, List, Any

from .registry import ToolRegistry, ToolSource
from .models import ToolSource as TS


class MCPAdapter:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._sessions: dict = {}
        self._server_configs: dict = {}
        self._read_streams: dict = {}
        self._write_streams: dict = {}
        self._exit_stacks: dict = {}
        self._tasks: dict = {}

    async def add_server(self, name: str, config: dict) -> List[str]:
        try:
            from mcp.client.session import ClientSession
            from mcp.client.sse import sse_client
            from mcp.client.stdio import stdio_client, StdioServerParameters
        except ImportError:
            raise ImportError("请安装 mcp 包: pip install mcp")

        if name in self._sessions:
            await self.remove_server(name)

        self._server_configs[name] = config

        transport_type = config.get("transport", "stdio")

        try:
            if transport_type == "sse":
                read, write, exit_stack = await self._connect_sse(config)
            else:
                read, write, exit_stack = await self._connect_stdio(config)

            self._read_streams[name] = read
            self._write_streams[name] = write
            self._exit_stacks[name] = exit_stack

            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()  # 关键：初始化 session
            self._sessions[name] = session

            tools = await session.list_tools()
            registered = []

            for mcp_tool in tools:
                tool_name = f"mcp_{name}_{mcp_tool.name}"
                handler = self._create_handler(name, mcp_tool.name)

                parameters = mcp_tool.inputSchema
                if isinstance(parameters, str):
                    import json
                    parameters = json.loads(parameters)

                await self.registry.register_tool(
                    name=tool_name,
                    handler=handler,
                    parameters=parameters,
                    description=f"[MCP:{name}] {mcp_tool.description}",
                    source=ToolSource.MCP,
                    config={"server": name, "tool": mcp_tool.name},
                )
                registered.append(tool_name)

            return registered

        except Exception as e:
            if name in self._sessions:
                del self._sessions[name]
            if name in self._read_streams:
                del self._read_streams[name]
            if name in self._write_streams:
                del self._write_streams[name]
            raise e

    async def _connect_stdio(self, config: dict):
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from contextlib import AsyncExitStack

        command = config.get("command", "npx")
        args = config.get("args", [])
        env = config.get("env", {})

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env if env else None,
        )

        # 使用 AsyncExitStack 来管理上下文
        exit_stack = AsyncExitStack()
        stdio_cm = stdio_client(server_params)
        read, write = await exit_stack.enter_async_context(stdio_cm)
        return read, write, exit_stack

    async def _connect_sse(self, config: dict):
        from mcp.client.sse import sse_client
        from contextlib import AsyncExitStack

        url = config.get("url")
        if not url:
            raise ValueError("SSE transport requires 'url' in config")

        # 使用 AsyncExitStack 来管理上下文
        exit_stack = AsyncExitStack()
        sse_cm = sse_client(url)
        read, write = await exit_stack.enter_async_context(sse_cm)
        return read, write, exit_stack

    async def remove_server(self, name: str) -> bool:
        if name not in self._sessions and name not in self._exit_stacks:
            return False

        tools_to_remove = [
            tool_name
            for tool_name, meta in self.registry._metas.items()
            if meta.source == ToolSource.MCP and meta.config.get("server") == name
        ]

        for tool_name in tools_to_remove:
            try:
                await self.registry.unregister_tool(tool_name)
            except Exception:
                pass

        # 关闭 session，使用 try-except 捕获任何异常
        try:
            session = self._sessions.get(name)
            if session:
                await session.__aexit__(None, None, None)
        except Exception as e:
            print(f"[MCPAdapter] Warning: Error closing session for {name}: {e}")

        # 关闭 exit_stack（transport 连接）
        try:
            exit_stack = self._exit_stacks.get(name)
            if exit_stack:
                await exit_stack.aclose()
        except Exception as e:
            print(f"[MCPAdapter] Warning: Error closing transport for {name}: {e}")

        # 清理资源，忽略任何异常
        self._sessions.pop(name, None)
        self._server_configs.pop(name, None)
        self._read_streams.pop(name, None)
        self._write_streams.pop(name, None)
        self._exit_stacks.pop(name, None)

        return True

    def _create_handler(self, server_name: str, tool_name: str):
        async def handler(context, **kwargs) -> str:
            session = self._sessions.get(server_name)
            if not session:
                return f"Error: MCP server {server_name} not connected"

            try:
                result = await session.call_tool(tool_name, arguments=kwargs)
                if hasattr(result, "content"):
                    content = result.content
                    if isinstance(content, list):
                        texts = []
                        for item in content:
                            if hasattr(item, "text"):
                                texts.append(item.text)
                            else:
                                texts.append(str(item))
                        return "\n".join(texts)
                    return str(content)
                return str(result)
            except Exception as e:
                return f"MCP tool call failed: {str(e)}"

        return handler

    async def list_available_tools(self, server_name: str) -> List[dict]:
        session = self._sessions.get(server_name)
        if not session:
            return []
        tools = await session.list_tools()
        return [{"name": t.name, "description": t.description} for t in tools]

    def list_servers(self) -> List[dict]:
        return [
            {"name": name, "config": config, "connected": name in self._sessions}
            for name, config in self._server_configs.items()
        ]

    async def test_tool(self, server_name: str, tool_name: str, params: dict = None) -> dict:
        """测试 MCP 工具"""
        session = self._sessions.get(server_name)
        if not session:
            return {"success": False, "error": f"MCP server '{server_name}' not connected"}

        try:
            result = await session.call_tool(tool_name, arguments=params or {})

            # 解析结果
            content_parts = []
            if hasattr(result, "content"):
                for item in result.content:
                    if hasattr(item, "text"):
                        content_parts.append(item.text)
                    else:
                        content_parts.append(str(item))

            return {
                "success": True,
                "result": "\n".join(content_parts),
                "isError": getattr(result, "isError", False)
            }
        except Exception as e:
            return {"success": False, "error": f"MCP tool call failed: {str(e)}"}

    async def close_all(self):
        """关闭所有 MCP 服务器连接"""
        all_names = set(self._sessions.keys()) | set(self._exit_stacks.keys())
        for name in all_names:
            try:
                await self.remove_server(name)
            except Exception as e:
                print(f"[MCPAdapter] Warning: Error removing server {name}: {e}")
                # 强制清理
                self._sessions.pop(name, None)
                self._server_configs.pop(name, None)
                self._read_streams.pop(name, None)
                self._write_streams.pop(name, None)
                self._exit_stacks.pop(name, None)
