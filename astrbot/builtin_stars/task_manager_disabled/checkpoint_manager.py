import json
import os
from pathlib import Path
from typing import Any
from astrbot import logger
from .models import Checkpoint, Task


class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "data/task_checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, task_id: str) -> Path:
        return self.checkpoint_dir / f"{task_id}.json"

    async def save(self, task_id: str, checkpoint: Checkpoint) -> bool:
        try:
            path = self._get_checkpoint_path(task_id)
            data = {
                "task_id": checkpoint.task_id,
                "step": checkpoint.step,
                "state": checkpoint.state,
                "subagent_results": checkpoint.subagent_results,
                "pending_tools": checkpoint.pending_tools,
                "stage_index": checkpoint.stage_index,
                "created_at": checkpoint.created_at.isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Checkpoint saved for task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    async def load(self, task_id: str) -> Checkpoint | None:
        try:
            path = self._get_checkpoint_path(task_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Checkpoint(
                task_id=data["task_id"],
                step=data["step"],
                state=data.get("state", {}),
                subagent_results=data.get("subagent_results", []),
                pending_tools=data.get("pending_tools", []),
                stage_index=data.get("stage_index", 0),
            )
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    async def delete(self, task_id: str) -> bool:
        try:
            path = self._get_checkpoint_path(task_id)
            if path.exists():
                path.unlink()
                logger.info(f"Checkpoint deleted for task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False

    async def exists(self, task_id: str) -> bool:
        return self._get_checkpoint_path(task_id).exists()

    async def list_checkpoints(self) -> list[str]:
        try:
            return [p.stem for p in self.checkpoint_dir.glob("*.json")]
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    async def create_from_task(self, task: Task, state: dict = None) -> Checkpoint:
        return Checkpoint(
            task_id=task.id,
            step=0,
            state=state or {},
            subagent_results=[],
            pending_tools=[],
            stage_index=0,
        )