from __future__ import annotations

import asyncio
import json
from typing import Any

from astrbot.core import logger
from astrbot.core.langgraph.channel_adapter import ChannelAdapter
from astrbot.core.langgraph.interaction import InteractionCard, ResolvedCardUpdate


class FeishuAdapter(ChannelAdapter):
    """Feishu channel adapter — sends interactive cards via lark-oapi.

    Based on Hermes Agent reference architecture:
    - Sends Feishu interactive card JSON messages
    - Handles card.action.trigger callbacks via P2CardActionTriggerResponse
    - State mapping: interaction_id → thread_id for resolution
    """

    def __init__(self):
        self._client = None
        self._loop = None
        self._interaction_state: dict[str, dict] = {}
        self._resolve_callback = None

    def set_client(self, client: Any, loop: Any) -> None:
        """Set the lark_oapi client and event loop for sending."""
        self._client = client
        self._loop = loop

    def set_resolve_callback(self, callback):
        """Callback: callback(interaction_id, action_key, user_name) -> bool."""
        self._resolve_callback = callback

    def _make_button(self, label: str, action_key: str, interaction_id: str, btn_type: str = "default") -> dict:
        return {
            "tag": "button",
            "text": {"tag": "plain_text", "content": label},
            "type": btn_type,
            "value": {
                "action_key": action_key,
                "interaction_id": interaction_id,
            },
        }

    async def send_card(self, card: InteractionCard, extra: dict) -> str | None:
        if not self._client:
            logger.warning("[Feishu] No client configured, cannot send card")
            return None

        chat_id = extra.get("chat_id", "")
        if not chat_id:
            logger.warning("[Feishu] No chat_id in extra, cannot send card")
            return None

        try:
            buttons = []
            for action in card.actions:
                btn_type = "primary" if action.style == "primary" else "danger" if action.style == "danger" else "default"
                buttons.append(self._make_button(action.label, action.key, card.interaction_id, btn_type))

            header_template = "blue"
            if card.type == "error_recovery":
                header_template = "red"

            feishu_card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": card.title, "tag": "plain_text"},
                    "template": header_template,
                },
                "elements": [
                    {"tag": "markdown", "content": card.body},
                ],
            }

            if buttons:
                feishu_card["elements"].append({
                    "tag": "action",
                    "actions": buttons,
                })

            if card.fields:
                field_lines = []
                for f in card.fields:
                    field_lines.append(f"**{f.label}**: {f.default or '(输入)'}")
                feishu_card["elements"].insert(0, {
                    "tag": "markdown",
                    "content": "\n".join(field_lines),
                })

            payload = json.dumps(feishu_card, ensure_ascii=False)

            response = await self._client.im.v1.message.create({
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": payload,
            })

            if response and response.code == 0:
                message_id = response.data.get("message_id", "")
                self._interaction_state[card.interaction_id] = {
                    "message_id": message_id,
                    "chat_id": chat_id,
                }
                return message_id
            else:
                logger.warning(f"[Feishu] Failed to send card: {response}")
                return None

        except Exception as e:
            logger.error(f"[Feishu] Error sending card: {e}", exc_info=True)
            return None

    async def update_card(self, update: ResolvedCardUpdate, channel_msg_id: str) -> None:
        if not self._client:
            return
        try:
            resolved_card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": f"✅ 已{self._status_label(update.status)}", "tag": "plain_text"},
                    "template": "green" if update.status == "confirmed" else "grey",
                },
                "elements": [
                    {"tag": "markdown", "content": f"✅ **已{self._status_label(update.status)}** — {update.message}"},
                ],
            }
            payload = json.dumps(resolved_card, ensure_ascii=False)
            await self._client.im.v1.message.patch({
                "message_id": channel_msg_id,
                "content": payload,
            })
        except Exception as e:
            logger.warning(f"[Feishu] Failed to update card: {e}")

    async def dismiss_card(self, channel_msg_id: str) -> None:
        if not self._client:
            return
        try:
            await self._client.im.v1.message.delete({"message_id": channel_msg_id})
        except Exception as e:
            logger.warning(f"[Feishu] Failed to dismiss card: {e}")

    def on_card_action_trigger(self, event_data: Any) -> Any:
        """Handle card.action.trigger callback from Feishu WebSocket."""
        from lark_oapi.event.callback.model.p2_card_action_trigger import (
            P2CardActionTriggerResponse,
        )

        try:
            action_value = getattr(event_data, "action", None)
            if not action_value:
                return P2CardActionTriggerResponse()

            value_raw = getattr(action_value, "value", {}) or {}
            action_key = value_raw.get("action_key", "") if isinstance(value_raw, dict) else ""
            interaction_id = value_raw.get("interaction_id", "") if isinstance(value_raw, dict) else ""

            if not interaction_id:
                return P2CardActionTriggerResponse()

            operator = getattr(event_data, "operator", None)
            open_id = str(getattr(operator, "open_id", "") or "")
            user_name = open_id

            if self._resolve_callback:
                if self._loop and asyncio.iscoroutinefunction(self._resolve_callback):
                    asyncio.run_coroutine_threadsafe(
                        self._resolve_callback(interaction_id, action_key, user_name),
                        self._loop,
                    )

            response = P2CardActionTriggerResponse()
            try:
                from lark_oapi.event.callback.model.p2_card_action_trigger import (
                    CallBackCard,
                )
                card = CallBackCard()
                card.type = "raw"
                resolved_card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"content": "✅ 已处理", "tag": "plain_text"},
                        "template": "green",
                    },
                    "elements": [
                        {"tag": "markdown", "content": f"✅ **已处理** — {action_key}"},
                    ],
                }
                card.data = json.dumps(resolved_card, ensure_ascii=False)
                response.card = card
            except Exception:
                pass

            return response

        except Exception as e:
            logger.error(f"[Feishu] Error handling card action: {e}", exc_info=True)
            return P2CardActionTriggerResponse()

    @staticmethod
    def _status_label(status: str) -> str:
        return {"confirmed": "确认", "cancelled": "取消", "rejected": "拒绝", "modified": "修改"}.get(status, status)
