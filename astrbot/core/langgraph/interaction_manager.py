from __future__ import annotations

import asyncio
import time
import uuid

from astrbot.core import logger

from .channel_adapter import ChannelAdapter
from .interaction import (
    InteractionCard,
    InteractionResponse,
    InteractionState,
    ResolvedCardUpdate,
)


class InteractionManager:
    """Unified HITL interaction manager.

    Stores pending interactions and dispatches cards through
    registered channel adapters. Each pending interaction has
    an asyncio.Event that blocks the calling tool handler until
    the user submits a response.
    """

    def __init__(self):
        self._pending: dict[str, InteractionState] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._responses: dict[str, InteractionResponse] = {}
        self._adapters: dict[str, ChannelAdapter] = {}

    def register_adapter(self, channel: str, adapter: ChannelAdapter) -> None:
        self._adapters[channel] = adapter

    async def send_and_wait(
        self,
        card: InteractionCard,
        thread_id: str = "",
        channel: str = "chatui",
        channel_extra: dict | None = None,
    ) -> InteractionResponse:
        """Send card and block until user responds. Called from tool handler."""
        if not card.interaction_id:
            card.interaction_id = f"inter_{uuid.uuid4().hex[:12]}"

        _event = asyncio.Event()
        self._events[card.interaction_id] = _event

        state = InteractionState(
            interaction_id=card.interaction_id,
            thread_id=thread_id,
            channel=channel,
            card=card,
            created_at=time.time(),
        )
        self._pending[card.interaction_id] = state

        adapter = self._adapters.get(channel)
        if adapter:
            try:
                msg_id = await adapter.send_card(card, extra=channel_extra or {})
                if msg_id:
                    state.channel_message_id = msg_id
            except Exception as e:
                logger.error(f"Failed to send interaction card via {channel}: {e}")

        try:
            await asyncio.wait_for(
                _event.wait(),
                timeout=card.timeout_seconds if card.timeout_seconds > 0 else None,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Interaction {card.interaction_id} timed out")
            response = InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="cancel",
                field_values={},
                responded_at=time.time(),
            )
            self._responses[card.interaction_id] = response
            state.mark_resolved(response)
            return response

        response = self._responses.pop(card.interaction_id, None)
        if response is None:
            response = InteractionResponse(
                interaction_id=card.interaction_id,
                action_key="cancel",
                field_values={},
                responded_at=time.time(),
            )

        state.mark_resolved(response)

        if adapter and state.channel_message_id:
            try:
                update = ResolvedCardUpdate(
                    interaction_id=card.interaction_id,
                    status=(
                        "confirmed" if response.action_key == "confirm"
                        else "cancelled" if response.action_key == "cancel"
                        else "rejected" if response.action_key == "reject"
                        else "modified"
                    ),
                    message=f"已完成 — {response.action_key}",
                )
                await adapter.update_card(update, state.channel_message_id)
            except Exception as e:
                logger.warning(f"Failed to update card after resolution: {e}")

        return response

    def respond(self, interaction_id: str, response: InteractionResponse) -> bool:
        """Called when user submits a response (API/webhook callback)."""
        state = self._pending.get(interaction_id)
        if not state or state.resolved:
            return False

        self._responses[interaction_id] = response
        state.mark_resolved(response)

        _event = self._events.pop(interaction_id, None)
        if _event:
            _event.set()
        return True

    def get_pending_interaction(self, interaction_id: str) -> InteractionState | None:
        return self._pending.get(interaction_id)

    def get_pending_interactions(self) -> list[InteractionState]:
        return [s for s in self._pending.values() if not s.resolved]


_interaction_manager: InteractionManager | None = None


def set_interaction_manager(mgr: InteractionManager) -> None:
    global _interaction_manager
    _interaction_manager = mgr


def get_interaction_manager() -> InteractionManager:
    global _interaction_manager
    if _interaction_manager is None:
        _interaction_manager = InteractionManager()
    return _interaction_manager
