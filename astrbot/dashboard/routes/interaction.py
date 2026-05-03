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
            for state in pending:
                cards.append({
                    "interaction_id": state.interaction_id,
                    "type": state.card.type,
                    "title": state.card.title,
                    "body": state.card.body,
                    "fields": [
                        {
                            "key": f.key,
                            "label": f.label,
                            "field_type": f.field_type,
                            "required": f.required,
                            "default": f.default,
                            "options": f.options,
                        }
                        for f in state.card.fields
                    ],
                    "actions": [
                        {"key": a.key, "label": a.label, "style": a.style}
                        for a in state.card.actions
                    ],
                    "timeout_seconds": state.card.timeout_seconds,
                    "channel": state.channel,
                })
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

            import time

            from astrbot.core.langgraph.interaction import InteractionResponse

            response = InteractionResponse(
                interaction_id=interaction_id,
                action_key=action_key,
                field_values=field_values,
                responded_at=time.time(),
            )

            from astrbot.core.langgraph.interaction_manager import (
                get_interaction_manager,
            )

            mgr = get_interaction_manager()
            ok = mgr.respond(interaction_id, response)

            if ok:
                return Response().ok(
                    {"interaction_id": interaction_id, "action": action_key}
                ).__dict__
            else:
                return (
                    Response()
                    .error(f"Interaction {interaction_id} not found or already resolved")
                    .__dict__
                )
        except Exception as e:
            logger.error(f"Interaction respond error: {e}", exc_info=True)
            return Response().error(str(e)).__dict__
