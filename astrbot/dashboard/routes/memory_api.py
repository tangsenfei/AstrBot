from quart import request

from astrbot.core.memory.event_service import EventService
from astrbot.core.memory.session import init_db

from .route import Response, Route, RouteContext


class MemoryRoute(Route):
    def __init__(self, context: RouteContext, core_lifecycle) -> None:
        super().__init__(context)
        self.routes = {
            "/memory/events": ("GET", self.get_events),
            "/memory/events/export": ("GET", self.export_events),
            "/memory/events/<event_id>": ("GET", self.get_event_detail),
            "/memory/stats": ("GET", self.get_memory_stats),
        }
        self.register_routes()
        self.core_lifecycle = core_lifecycle
        init_db()

    async def get_events(self):
        agent_id = request.args.get("agent_id")
        event_type = request.args.get("type")
        search = request.args.get("search")
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))

        result = EventService.query_events(
            agent_id=agent_id,
            event_type=event_type,
            search=search,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return Response().ok(result).__dict__

    async def get_event_detail(self, event_id: str):
        event = EventService.get_event(event_id)
        if event is None:
            return Response().error("Event not found").__dict__
        return Response().ok(event).__dict__

    async def export_events(self):
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        event_type = request.args.get("type")

        events = EventService.export_events(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
        )
        return Response().ok({"items": events, "total": len(events)}).__dict__

    async def get_memory_stats(self):
        agent_id = request.args.get("agent_id")

        events_result = EventService.query_events(agent_id=agent_id, page_size=1)
        event_counts = EventService.get_event_count_by_agent()

        return (
            Response()
            .ok(
                {
                    "events_total": events_result["total"],
                    "event_counts_by_agent": event_counts,
                    "scenes_total": 0,
                    "claims_total": 0,
                    "rules_total": 0,
                    "identity_total": 0,
                    "active_prompts": 0,
                }
            )
            .__dict__
        )
