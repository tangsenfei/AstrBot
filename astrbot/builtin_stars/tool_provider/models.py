from enum import Enum


class ToolSource(Enum):
    MCP = "mcp"
    API_WRAPPER = "api_wrapper"
    NATIVE = "native"


class ToolStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
