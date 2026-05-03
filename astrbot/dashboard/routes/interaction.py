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
                card = state.card.to_dict()
                card["thread_id"] = state.thread_id
                card["task_id"] = card.get("meta", {}).get("task_id") or state.thread_id
                card["channel"] = state.channel
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
                try:
                    state = mgr.get_pending_interaction(interaction_id)
                    task_id = ""
                    if state:
                        task_id = state.card.meta.get("task_id") or state.thread_id
                    if task_id:
                        from datetime import datetime

                        from astrbot.builtin_stars.agent_system.database import get_database

                        get_database().update(
                            "agent_tasks",
                            {
                                "status": "running",
                                "interaction_id": "",
                                "updated_at": datetime.now().isoformat(),
                            },
                            where="id = ?",
                            where_params=(task_id,),
                        )
                except Exception:
                    pass
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
