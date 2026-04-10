"""
智能体管理模块 - 路由层
"""
from .tools import register_tool_routes
from .skills import register_skill_routes
from .agents import register_agent_routes
from .knowledge import register_knowledge_routes
from .crews import register_crew_routes
from .flows import register_flow_routes

__all__ = [
    "register_tool_routes",
    "register_skill_routes",
    "register_agent_routes",
    "register_knowledge_routes",
    "register_crew_routes",
    "register_flow_routes",
]
