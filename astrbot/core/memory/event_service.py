import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import and_, func, select

from astrbot.core.memory.audit import write_audit_log
from astrbot.core.memory.models import MemoryEvent
from astrbot.core.memory.session import session_scope


class EventService:
    @staticmethod
    def append_event(
        agent_id: str = "main",
        event_type: str = "system_event",
        content: str = "",
        role: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> MemoryEvent:
        event_id = uuid.uuid4().hex
        event = MemoryEvent(
            id=event_id,
            agent_id=agent_id,
            type=event_type,
            role=role,
            content=content,
            event_meta=json.dumps(metadata or {}, ensure_ascii=False),
            created_by=created_by,
            created_at=datetime.now(),
        )
        with session_scope() as session:
            session.add(event)
            session.expire_on_commit = False

        write_audit_log(
            actor=created_by or "system",
            action="create",
            target_type="event",
            target_id=event_id,
            details=json.dumps(
                {"type": event_type, "agent_id": agent_id}, ensure_ascii=False
            ),
        )
        return event

    @staticmethod
    def query_events(
        agent_id: str | None = None,
        event_type: str | None = None,
        search: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        with session_scope() as session:
            conditions = []

            if agent_id:
                conditions.append(MemoryEvent.agent_id == agent_id)
            if event_type:
                types = [t.strip() for t in event_type.split(",") if t.strip()]
                if types:
                    conditions.append(MemoryEvent.type.in_(types))
            if start_time:
                conditions.append(MemoryEvent.created_at >= start_time)
            if end_time:
                conditions.append(MemoryEvent.created_at <= end_time)

            query = select(MemoryEvent)

            if search:
                search_condition = text(
                    "rowid IN (SELECT rowid FROM memory_events_fts WHERE memory_events_fts MATCH :q)"
                )
                query = query.where(search_condition).params(q=search)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(MemoryEvent.created_at.desc())

            count_query = select(func.count()).select_from(query.subquery())
            total = session.exec(count_query).one()

            offset = (page - 1) * page_size
            events = session.exec(query.offset(offset).limit(page_size)).all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_event_to_dict(e) for e in events],
            }

    @staticmethod
    def get_event(event_id: str) -> dict[str, Any] | None:
        with session_scope() as session:
            event = session.get(MemoryEvent, event_id)
            if event:
                return _event_to_dict(event)
        return None

    @staticmethod
    def get_event_count_by_agent() -> list[dict[str, Any]]:
        with session_scope() as session:
            stmt = select(
                MemoryEvent.agent_id,
                func.count().label("count"),
            ).group_by(MemoryEvent.agent_id)
            results = session.exec(stmt).all()
            return [{"agent_id": r[0], "count": r[1]} for r in results]

    @staticmethod
    def export_events(
        start_time: str | None = None,
        end_time: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as session:
            conditions = []
            if start_time:
                conditions.append(MemoryEvent.created_at >= start_time)
            if end_time:
                conditions.append(MemoryEvent.created_at <= end_time)
            if event_type:
                conditions.append(MemoryEvent.type == event_type)

            query = select(MemoryEvent).order_by(MemoryEvent.created_at.asc())
            if conditions:
                query = query.where(and_(*conditions))

            events = session.exec(query).all()
            return [_event_to_dict(e) for e in events]


def _event_to_dict(event: MemoryEvent) -> dict[str, Any]:
    meta_raw = event.event_meta if event.event_meta else "{}"
    try:
        meta = json.loads(meta_raw)
    except (json.JSONDecodeError, TypeError):
        meta = {}

    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "scene_id": event.scene_id,
        "type": event.type,
        "role": event.role,
        "content": event.content,
        "metadata": meta,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "created_by": event.created_by,
    }
