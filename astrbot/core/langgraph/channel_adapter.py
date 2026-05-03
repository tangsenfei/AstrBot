from abc import ABC, abstractmethod

from .interaction import InteractionCard, ResolvedCardUpdate


class ChannelAdapter(ABC):
    @abstractmethod
    async def send_card(self, card: InteractionCard, extra: dict) -> str | None:
        """Send an interaction card. Returns channel message ID on success."""

    @abstractmethod
    async def update_card(self, update: ResolvedCardUpdate, channel_msg_id: str) -> None:
        """Update a previously sent card (e.g. after user responds)."""

    @abstractmethod
    async def dismiss_card(self, channel_msg_id: str) -> None:
        """Dismiss/remove a previously sent card."""
