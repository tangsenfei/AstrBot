from __future__ import annotations

from astrbot.core import logger
from astrbot.core.langgraph.channel_adapter import ChannelAdapter
from astrbot.core.langgraph.interaction import InteractionCard, ResolvedCardUpdate


class ChatUIAdapter(ChannelAdapter):
    """ChatUI channel adapter — pushes interaction events via SSE writer callback."""

    def __init__(self):
        self._writer_callback = None

    def set_writer(self, writer_callback) -> None:
        self._writer_callback = writer_callback

    async def send_card(self, card: InteractionCard, extra: dict) -> str | None:
        writer = extra.get("writer") or self._writer_callback
        if writer:
            try:
                writer({
                    "type": "interaction_card",
                    "data": card.to_dict(),
                })
            except Exception as e:
                logger.warning(f"ChatUI: failed to send interaction card: {e}")
        return card.interaction_id

    async def update_card(self, update: ResolvedCardUpdate, channel_msg_id: str) -> None:
        writer = self._writer_callback
        if writer:
            try:
                writer({
                    "type": "interaction_card_update",
                    "data": {
                        "interaction_id": update.interaction_id,
                        "status": update.status,
                        "message": update.message,
                    },
                })
            except Exception as e:
                logger.warning(f"ChatUI: failed to update card: {e}")

    async def dismiss_card(self, channel_msg_id: str) -> None:
        writer = self._writer_callback
        if writer:
            try:
                writer({
                    "type": "interaction_card_dismiss",
                    "data": {"interaction_id": channel_msg_id},
                })
            except Exception as e:
                logger.warning(f"ChatUI: failed to dismiss card: {e}")
