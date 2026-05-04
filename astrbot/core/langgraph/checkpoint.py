from __future__ import annotations

from pathlib import Path

_checkpointer = None
_checkpoint_db_path = None


def get_checkpoint_db_path():
    global _checkpoint_db_path
    if _checkpoint_db_path is None:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        _checkpoint_db_path = str(Path(get_astrbot_data_path()) / "langgraph_checkpoints.db")
    return _checkpoint_db_path


def create_checkpointer(db_path: str | Path | None = None):
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    if db_path:
        global _checkpoint_db_path
        _checkpoint_db_path = str(db_path)
    return None


def get_checkpointer():
    return _checkpointer


def set_checkpointer(checkpointer):
    global _checkpointer
    _checkpointer = checkpointer


def reset_checkpointer():
    global _checkpointer
    _checkpointer = None
