"""
记忆模块 Pipeline 钩子 -- 自动将消息流转为事件记录

提供全局函数供调用方在消息处理流程中调用：
- on_user_message(agent_id, content, user_id)
- on_agent_reply(agent_id, content)
- on_tool_call(agent_id, tool_name, params, result, success)
- on_scheduled_task(agent_id, task_name)
- on_system_event(agent_id, event_desc)
"""

import logging

from astrbot.core.memory.event_service import EventService

logger = logging.getLogger("astrbot.memory")


def on_user_message(agent_id: str, content: str, user_id: str = "") -> None:
    """记录用户消息事件"""
    try:
        EventService.append_event(
            agent_id=agent_id,
            event_type="user_message",
            role="user",
            content=content,
            created_by=user_id,
        )
    except Exception as e:
        logger.warning(f"Memory: failed to record user_message: {e}")


def on_agent_reply(agent_id: str, content: str) -> None:
    """记录 Agent 回复事件"""
    try:
        EventService.append_event(
            agent_id=agent_id,
            event_type="agent_reply",
            role="assistant",
            content=content,
            created_by=agent_id,
        )
    except Exception as e:
        logger.warning(f"Memory: failed to record agent_reply: {e}")


def on_tool_call(
    agent_id: str,
    tool_name: str,
    params: str = "",
    result: str = "",
    success: bool = True,
) -> None:
    """记录工具调用事件"""
    try:
        metadata = {
            "tool_name": tool_name,
            "params": params,
            "result": result,
            "success": success,
        }
        EventService.append_event(
            agent_id=agent_id,
            event_type="tool_call",
            role="tool",
            content=f"{tool_name}: {result[:500] if success else 'failed'}",
            metadata=metadata,
        )
    except Exception as e:
        logger.warning(f"Memory: failed to record tool_call: {e}")


def on_scheduled_task(agent_id: str, task_name: str, task_detail: str = "") -> None:
    """记录定时任务触发事件"""
    try:
        EventService.append_event(
            agent_id=agent_id,
            event_type="scheduled_task",
            role="system",
            content=f"{task_name}: {task_detail}" if task_detail else task_name,
            created_by="scheduler",
        )
    except Exception as e:
        logger.warning(f"Memory: failed to record scheduled_task: {e}")


def on_system_event(agent_id: str, event_desc: str) -> None:
    """记录系统事件"""
    try:
        EventService.append_event(
            agent_id=agent_id,
            event_type="system_event",
            role="system",
            content=event_desc,
            created_by="system",
        )
    except Exception as e:
        logger.warning(f"Memory: failed to record system_event: {e}")
