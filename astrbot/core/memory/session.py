import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

_engine = None


def get_memory_db_path() -> str:
    data_dir = get_astrbot_data_path()
    memory_dir = os.path.join(data_dir, "plugin_data", "memory")
    os.makedirs(memory_dir, exist_ok=True)
    return os.path.join(memory_dir, "memory.db")


def init_engine() -> None:
    global _engine
    if _engine is not None:
        return
    db_path = get_memory_db_path()
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    """Initialize database: create all tables + FTS5 index + identity unique constraint"""
    init_engine()
    import astrbot.core.memory.models  # noqa: F401

    SQLModel.metadata.create_all(_engine)

    with _engine.connect() as conn:
        try:
            conn.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_events_fts "
                "USING fts5(content, content=memory_events, content_rowid=rowid)"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS memory_events_fts_ai "
                "AFTER INSERT ON memory_events BEGIN "
                "INSERT INTO memory_events_fts(rowid, content) VALUES (new.rowid, new.content); END"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS memory_events_fts_ad "
                "AFTER DELETE ON memory_events BEGIN "
                "INSERT INTO memory_events_fts(memory_events_fts, rowid, content) VALUES('delete', old.rowid, old.content); END"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS memory_events_fts_au "
                "AFTER UPDATE ON memory_events BEGIN "
                "INSERT INTO memory_events_fts(memory_events_fts, rowid, content) VALUES('delete', old.rowid, old.content); "
                "INSERT INTO memory_events_fts(rowid, content) VALUES (new.rowid, new.content); END"
            )
        except Exception:
            pass

        try:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_unique "
                "ON memory_identity(owner_id, agent_id, key)"
            )
        except Exception:
            pass


def get_session() -> Session:
    if _engine is None:
        init_engine()
    return Session(_engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
