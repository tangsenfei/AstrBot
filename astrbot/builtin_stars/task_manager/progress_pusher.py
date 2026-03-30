import asyncio
from abc import ABC, abstractmethod
from typing import Any
from astrbot import logger
from .models import TaskProgress, TaskStatus


class ProgressPusher(ABC):
    @abstractmethod
    async def push(self, task_id: str, progress: TaskProgress) -> bool:
        pass


class PlatformProgressPusher(ProgressPusher):
    def __init__(self, platform_manager: Any):
        self.platform_manager = platform_manager

    async def push(self, task_id: str, progress: TaskProgress) -> bool:
        try:
            message = self._build_message(progress)
            return await self._send_to_platform(progress.platform, progress.user_id, message)
        except Exception as e:
            logger.error(f"Failed to push progress: {e}")
            return False

    def _build_message(self, progress: TaskProgress) -> str:
        emoji_map = {
            "pending": "⏳",
            "running": "🔄",
            "waiting_subagent": "🤖",
            "checkpoint": "💾",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫",
        }
        emoji = emoji_map.get(progress.status.value, "📋")

        lines = [
            f"{emoji} **任务进行中**",
            f"**ID**: `{progress.task_id[:8]}...`",
            f"**阶段**: {progress.stage}",
            f"**进度**: {progress.total_progress}%",
        ]

        if progress.completed_items:
            lines.append("**已完成**:")
            for item in progress.completed_items[:3]:
                lines.append(f"  - {item}")
            if len(progress.completed_items) > 3:
                lines.append(f"  ... 还有 {len(progress.completed_items) - 3} 项")

        if progress.message:
            lines.append(f"**状态**: {progress.message}")

        return "\n".join(lines)

    async def _send_to_platform(self, platform: str, user_id: str, message: str) -> bool:
        try:
            if platform == "feishu":
                return await self._send_feishu(user_id, message)
            elif platform == "qq":
                return await self._send_qq(user_id, message)
            elif platform == "telegram":
                return await self._send_telegram(user_id, message)
            else:
                logger.warning(f"Unsupported platform: {platform}")
                return False
        except Exception as e:
            logger.error(f"Failed to send to platform: {e}")
            return False

    async def _send_feishu(self, chat_id: str, message: str) -> bool:
        logger.info(f"[Feishu] Sending to {chat_id}: {message[:50]}...")
        return True

    async def _send_qq(self, user_id: str, message: str) -> bool:
        logger.info(f"[QQ] Sending to {user_id}: {message[:50]}...")
        return True

    async def _send_telegram(self, chat_id: str, message: str) -> bool:
        logger.info(f"[Telegram] Sending to {chat_id}: {message[:50]}...")
        return True


class WebSocketProgressPusher(ProgressPusher):
    def __init__(self, ws_manager: Any = None):
        self.ws_manager = ws_manager

    async def push(self, task_id: str, progress: TaskProgress) -> bool:
        try:
            if self.ws_manager:
                await self.ws_manager.broadcast({
                    "type": "task_progress",
                    "task_id": task_id,
                    "progress": {
                        "status": progress.status.value,
                        "stage": progress.stage,
                        "stage_progress": progress.stage_progress,
                        "total_progress": progress.total_progress,
                        "message": progress.message,
                        "completed_items": progress.completed_items,
                        "timestamp": progress.timestamp.isoformat(),
                    }
                })
                return True
            return False
        except Exception as e:
            logger.error(f"WebSocket push failed: {e}")
            return False


class ProgressDispatcher:
    def __init__(self):
        self._pushers: list[ProgressPusher] = []

    def add_pusher(self, pusher: ProgressPusher):
        self._pushers.append(pusher)

    async def dispatch(self, task_id: str, progress: TaskProgress) -> int:
        success_count = 0
        for pusher in self._pushers:
            try:
                if await pusher.push(task_id, progress):
                    success_count += 1
            except Exception as e:
                logger.error(f"Pusher {type(pusher).__name__} failed: {e}")
        return success_count