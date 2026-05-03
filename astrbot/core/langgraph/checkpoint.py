from __future__ import annotations

from pathlib import Path

_checkpointer = None


def create_checkpointer(db_path: str | Path | None = None):
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    from langgraph.checkpoint.sqlite import SqliteSaver

    if db_path is None:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        db_path = Path(get_astrbot_data_path()) / "langgraph_checkpoints.db"
    _checkpointer = SqliteSaver.from_conn_string(str(db_path))
    return _checkpointer


def get_checkpointer():
    return _checkpointer


def reset_checkpointer():
    global _checkpointer
    _checkpointer = None
