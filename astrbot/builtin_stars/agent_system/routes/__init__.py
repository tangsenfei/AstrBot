"""
智能体管理模块 - 路由层
"""
from .tools import register_tool_routes
from .skills import register_skill_routes
from .agents import register_agent_routes
from .knowledge import register_knowledge_routes
from .crews import register_crew_routes
from .flows import register_flow_routes
from .work import register_work_routes
from .meeting import register_meeting_routes
from .cli_agents import register_cli_agent_routes
from .generic_agent import register_generic_agent_routes

__all__ = [
    "register_cli_agent_routes",
    "register_generic_agent_routes",
    "register_tool_routes",
    "register_skill_routes",
    "register_agent_routes",
    "register_knowledge_routes",
    "register_crew_routes",
    "register_flow_routes",
    "register_work_routes",
    "register_meeting_routes",
]
