# AstrBot/astrbot/core/memory/__init__.py
"""
NiceBot 记忆系统核心模块

提供多类型记忆能力：
- 事件记录（Event）— 基础数据层
- 场景管理（Scene）— 事件分组
- 语义记忆（Semantic Claim）— 结构化事实/偏好
- 程序性记忆（Procedural Rule）— 规则/策略  
- 身份记忆（Identity）— Agent 画像
- 提示词管理（Prompt）— 版本化提示词
- 审计日志（Audit Log）— 操作追踪
"""

from astrbot.core.memory.models import (
    MemoryEvent,
    MemoryScene,
    MemorySemanticClaim,
    MemoryProceduralRule,
    MemoryIdentity,
    MemoryPrompt,
    MemoryAuditLog,
)

__all__ = [
    "MemoryEvent",
    "MemoryScene",
    "MemorySemanticClaim",
    "MemoryProceduralRule",
    "MemoryIdentity",
    "MemoryPrompt",
    "MemoryAuditLog",
]
