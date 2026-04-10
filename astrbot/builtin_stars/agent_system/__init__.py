"""
NiceBot 智能体管理模块

支持 CrewAI 集成，实现多智能体协作、任务分解、执行追踪、Token 消耗监控
"""
from .main import main, AgentSystemPlugin
from .models import (
    ToolSource,
    Tool,
    DisclosureLevel,
    Skill,
    KnowledgeSource,
    Knowledge,
    PlanningEffort,
    Agent,
    ProcessType,
    CrewTask,
    Crew,
    FlowNodeType,
    FlowNode,
    FlowEdge,
    Flow,
    TaskStatus,
    AgentTask,
    SubTask,
    ExecutionLog,
    TokenStats,
)

__all__ = [
    "main",
    "AgentSystemPlugin",
    "ToolSource",
    "Tool",
    "DisclosureLevel",
    "Skill",
    "KnowledgeSource",
    "Knowledge",
    "PlanningEffort",
    "Agent",
    "ProcessType",
    "CrewTask",
    "Crew",
    "FlowNodeType",
    "FlowNode",
    "FlowEdge",
    "Flow",
    "TaskStatus",
    "AgentTask",
    "SubTask",
    "ExecutionLog",
    "TokenStats",
]
