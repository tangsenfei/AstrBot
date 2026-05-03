from __future__ import annotations

from typing import Any

from .interaction import CardAction, InteractionCard
from .interaction_manager import get_interaction_manager

_task_center: Any = None


def set_task_center(tc: Any) -> None:
    global _task_center
    _task_center = tc


def get_task_center() -> Any:
    return _task_center


def _detect_channel(event: Any) -> str:
    try:
        platform_name = getattr(event, "platform", None)
        if platform_name:
            name = str(getattr(platform_name, "name", "") or "").lower()
            if "feishu" in name or "lark" in name:
                return "feishu"
        unified = getattr(event, "unified_msg_origin", "")
        if "feishu" in str(unified).lower() or "lark" in str(unified).lower():
            return "feishu"
    except Exception:
        pass
    return "chatui"


async def confirm_task(
    event: Any,
    task_type: str,
    summary: str,
    detail: str,
    estimated_steps: int = 3,
) -> dict:
    type_labels = {
        "plan_execute": "深度调研",
        "meeting": "圆桌会议",
        "workflow": "工作流",
        "crew": "Crew 编排",
    }
    label = type_labels.get(task_type, task_type)

    card = InteractionCard(
        interaction_id="",
        type="task_confirm",
        title="任务确认",
        body=(
            f"已理解你的需求，将创建以下任务：\n\n"
            f"**类型**：{label}\n"
            f"**摘要**：{summary}\n"
            f"**详情**：{detail}\n\n"
            f"预计时长：~{estimated_steps * 2} 分钟"
        ),
        actions=[
            CardAction(key="confirm", label="确认", style="primary"),
            CardAction(key="modify", label="修改需求", style="default"),
            CardAction(key="cancel", label="取消", style="danger"),
        ],
    )

    channel = _detect_channel(event)
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(
        card,
        thread_id="",
        channel=channel,
        channel_extra={"writer": getattr(event, "_stream_writer", None)},
    )

    if response.action_key == "confirm":
        return {"confirmed": True, "result": "confirmed"}
    elif response.action_key == "modify":
        return {
            "confirmed": False,
            "result": "modify",
            "modify_text": response.field_values.get("modify_text", ""),
        }
    else:
        return {"confirmed": False, "result": "cancelled"}


async def create_task(
    event: Any,
    task_type: str,
    config: dict,
    session_id: str,
) -> dict:
    tc = get_task_center()
    if tc is None:
        return {"error": "TaskCenter not initialized"}

    from .state import GraphRunContext

    run_ctx = GraphRunContext(
        provider=None,
        tool_executor=None,
        hooks=None,
        astr_event=event,
        config={},
    )

    task = await tc.create_task(
        task_type=task_type,
        config=config,
        session_id=session_id,
        run_ctx=run_ctx,
    )

    # dual-write to agent_system DB for dashboard visibility
    try:
        _db_create_task(
            task_type=task_type,
            config=config,
            task_id=task.task_id,
            thread_id=task.thread_id,
        )
    except Exception:
        pass

    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "thread_id": task.thread_id,
    }


def _db_create_task(task_type: str, config: dict, task_id: str, thread_id: str) -> None:
    from astrbot import logger

    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.task_service import TaskService

        db = get_database()
        task_service = TaskService(db)
        task_service.create_task(
            task_id=task_id,
            name=config.get("summary", task_type),
            description=config.get("detail", ""),
            task_type=task_type,
            category="daily",
            thread_id=thread_id,
        )
    except ImportError:
        logger.debug("agent_system not available, skipping DB task creation")
    except Exception as e:
        logger.warning(f"Failed to create DB task record: {e}")


async def get_task_status(
    event: Any,
    task_id: str,
) -> dict:
    tc = get_task_center()
    if tc is None:
        return {"error": "TaskCenter not initialized"}

    task = tc.get_task(task_id)
    if task is None:
        return {"error": f"Task {task_id} not found"}

    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status.value,
        "error": task.error,
        "result": task.result,
    }
