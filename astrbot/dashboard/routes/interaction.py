from quart import request

from astrbot.core import logger

from .route import Response, Route


class InteractionRoute(Route):
    def __init__(self, context) -> None:
        super().__init__(context)
        self.routes = {
            "/interaction/pending": ("GET", self.get_pending),
            "/interaction/respond": ("POST", self.respond),
        }
        self.register_routes()

    async def get_pending(self):
        try:
            from astrbot.core.langgraph.interaction_manager import (
                get_interaction_manager,
            )

            mgr = get_interaction_manager()
            pending = mgr.get_pending_interactions()
            cards = []
            try:
                from astrbot.builtin_stars.agent_system.database import get_database
                from astrbot.builtin_stars.agent_system.services.hitl_service import HITLService

                cards.extend(HITLService(get_database()).list_pending())
            except Exception:
                pass
            for state in pending:
                card = state.card.to_dict()
                card["thread_id"] = state.thread_id
                card["task_id"] = card.get("meta", {}).get("task_id") or state.thread_id
                card["channel"] = state.channel
                if not any(existing.get("interaction_id") == card.get("interaction_id") for existing in cards):
                    cards.append(card)
            return Response().ok({"cards": cards}).__dict__
        except Exception as e:
            logger.error(f"Get pending interactions error: {e}", exc_info=True)
            return Response().error(str(e)).__dict__

    async def respond(self):
        try:
            data = await request.get_json()
            if not data:
                return Response().error("Missing request body").__dict__

            interaction_id = data.get("interaction_id", "")
            action_key = data.get("action_key", "cancel")
            field_values = data.get("field_values", {})

            if not interaction_id:
                return Response().error("Missing interaction_id").__dict__

            from astrbot.builtin_stars.agent_system.database import get_database
            from astrbot.builtin_stars.agent_system.services.hitl_service import HITLService

            result = await HITLService(get_database()).respond(interaction_id, action_key, field_values)
            return Response().ok(result).__dict__
        except Exception as e:
            logger.error(f"Interaction respond error: {e}", exc_info=True)
            return Response().error(str(e)).__dict__
