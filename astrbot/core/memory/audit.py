import uuid
from datetime import datetime

from astrbot.core.memory.models import MemoryAuditLog
from astrbot.core.memory.session import session_scope


def write_audit_log(
    actor: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: str | None = None,
) -> MemoryAuditLog:
    log_entry = MemoryAuditLog(
        id=uuid.uuid4().hex,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or "{}",
        created_at=datetime.now(),
    )
    with session_scope() as session:
        session.add(log_entry)
        session.expire_on_commit = False
    return log_entry
