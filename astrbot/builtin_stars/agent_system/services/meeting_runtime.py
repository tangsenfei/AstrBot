"""Runtime coordinator for Meeting executions.

The route layer should not run long meetings or persist token-level events
directly in request/SSE paths. This runtime keeps live streaming in memory,
limits concurrent meeting graphs, and persists durable events in batches.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from astrbot.core import logger


LOW_VALUE_EVENTS = {"text_delta", "reasoning"}
PERSISTED_EVENTS = {
    "phase",
    "assistant_message",
    "tool_call",
    "tool_result",
    "interaction",
    "artifact",
    "error",
    "hitl_resolved",
    "user_message",
    "agent_call_start",
    "agent_call_end",
    "token",
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class MeetingRuntime:
    """Coordinates active Meeting graph runs and live event delivery."""

    def __init__(self, *, max_concurrent: int = 3, queue_size: int = 2000) -> None:
        self._max_concurrent = max(1, int(max_concurrent or 3))
        self._queue_size = max(100, int(queue_size or 2000))
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._tasks: dict[str, asyncio.Task] = {}
        self._persist_tasks: dict[str, asyncio.Task] = {}
        self._persist_queues: dict[str, asyncio.Queue] = {}
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lag_task: asyncio.Task | None = None

    async def start(
        self,
        meeting_id: str,
        service_factory: Callable[[], Any],
    ) -> dict[str, Any]:
        existing = self._tasks.get(meeting_id)
        if existing and not existing.done():
            return {
                "meeting_id": meeting_id,
                "started": False,
                "queued": True,
                "message": "会议已在运行队列中",
            }

        service = service_factory()
        meeting = service.get_meeting_summary(meeting_id)
        if meeting.get("status") == "running":
            return {
                "meeting_id": meeting_id,
                "started": False,
                "queued": False,
                "message": "会议已在进行中",
            }

        self._ensure_lag_monitor()
        self._ensure_persist_worker(meeting_id, service.db.db_path)
        task = asyncio.create_task(
            self._run_meeting(meeting_id, service_factory),
            name=f"meeting-runtime:{meeting_id}",
        )
        self._tasks[meeting_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(meeting_id, None))
        return {
            "meeting_id": meeting_id,
            "started": True,
            "queued": self.active_count >= self._max_concurrent,
            "max_concurrent": self._max_concurrent,
        }

    @property
    def active_count(self) -> int:
        return sum(1 for task in self._tasks.values() if not task.done())

    async def cancel(
        self,
        meeting_id: str,
        service_factory: Callable[[], Any],
    ) -> dict[str, Any]:
        task = self._tasks.pop(meeting_id, None)
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        service = service_factory()
        meeting = service.cancel_meeting(meeting_id)
        self._publish(
            meeting_id,
            {
                "id": f"runtime_cancelled_{uuid.uuid4().hex[:8]}",
                "event_type": "done",
                "role": "system",
                "speaker": "会议助理",
                "round": int(meeting.get("current_round") or 0),
                "content": "会议已取消",
                "payload": {"status": "cancelled"},
                "created_at": datetime.now().isoformat(),
            },
        )
        return meeting

    def subscribe(self, meeting_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers[meeting_id].add(queue)
        return queue

    def unsubscribe(self, meeting_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(meeting_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(meeting_id, None)

    def publish_stream_event(self, meeting_id: str, event: dict[str, Any]) -> None:
        payload = normalize_stream_event(meeting_id, event)
        self._publish(meeting_id, payload)
        self._enqueue_persist(meeting_id, event)

    def _publish(self, meeting_id: str, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(meeting_id, set())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                if payload.get("event_type") in LOW_VALUE_EVENTS:
                    continue
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    def _enqueue_persist(self, meeting_id: str, event: dict[str, Any]) -> None:
        queue = self._persist_queues.get(meeting_id)
        if queue is None:
            return
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            event_type = str(event.get("event") or "")
            if event_type in LOW_VALUE_EVENTS:
                return
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Meeting persist queue is full; dropping event for %s", meeting_id)

    async def _run_meeting(self, meeting_id: str, service_factory: Callable[[], Any]) -> None:
        async with self._semaphore:
            service = service_factory()
            db_path = service.db.db_path
            self._ensure_persist_worker(meeting_id, db_path)
            try:
                result = await service.start_meeting(
                    meeting_id,
                    event_sink=lambda event: self.publish_stream_event(meeting_id, event),
                )
                status = service.get_meeting_status(meeting_id)
                self._publish(
                    meeting_id,
                    {
                        "id": f"runtime_done_{uuid.uuid4().hex[:8]}",
                        "event_type": "done",
                        "role": "system",
                        "speaker": status.get("current_speaker") or "会议助理",
                        "round": int(status.get("current_round") or 0),
                        "content": "会议执行已结束",
                        "payload": {"status": status.get("status"), "result": result},
                        "created_at": datetime.now().isoformat(),
                    },
                )
            except Exception as exc:
                logger.error("Meeting runtime failed: %s: %s", meeting_id, exc, exc_info=True)
                self._publish(
                    meeting_id,
                    {
                        "id": f"runtime_error_{uuid.uuid4().hex[:8]}",
                        "event_type": "error",
                        "role": "system",
                        "speaker": "会议助理",
                        "round": 0,
                        "content": str(exc),
                        "payload": {"message": str(exc)},
                        "created_at": datetime.now().isoformat(),
                    },
                )
            finally:
                await self._drain_persist_queue(meeting_id)

    def _ensure_persist_worker(self, meeting_id: str, db_path: str | Path) -> None:
        task = self._persist_tasks.get(meeting_id)
        if task and not task.done():
            return
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        self._persist_queues[meeting_id] = queue
        self._persist_tasks[meeting_id] = asyncio.create_task(
            self._persist_loop(meeting_id, Path(db_path), queue),
            name=f"meeting-persist:{meeting_id}",
        )

    async def _persist_loop(self, meeting_id: str, db_path: Path, queue: asyncio.Queue) -> None:
        while True:
            batch: list[dict[str, Any]] = []
            try:
                first = await queue.get()
                if first is None:
                    break
                batch.append(first)
                deadline = time.monotonic() + 0.2
                while len(batch) < 50:
                    timeout = max(0, deadline - time.monotonic())
                    if timeout <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        break
                    if item is None:
                        break
                    batch.append(item)
                await asyncio.to_thread(persist_graph_event_batch, db_path, meeting_id, batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Failed to persist meeting event batch for %s: %s", meeting_id, exc, exc_info=True)
            finally:
                for _ in batch:
                    with suppress(ValueError):
                        queue.task_done()

    async def _drain_persist_queue(self, meeting_id: str) -> None:
        queue = self._persist_queues.get(meeting_id)
        if queue is None:
            return
        try:
            await queue.join()
            queue.put_nowait(None)
            task = self._persist_tasks.get(meeting_id)
            if task:
                await asyncio.wait_for(task, timeout=2)
        except Exception:
            pass
        finally:
            self._persist_queues.pop(meeting_id, None)
            self._persist_tasks.pop(meeting_id, None)

    def _ensure_lag_monitor(self) -> None:
        if self._lag_task and not self._lag_task.done():
            return
        self._lag_task = asyncio.create_task(self._lag_monitor(), name="meeting-loop-lag-monitor")

    async def _lag_monitor(self) -> None:
        loop = asyncio.get_running_loop()
        expected = loop.time() + 1
        while True:
            await asyncio.sleep(1)
            lag = loop.time() - expected
            if lag > 0.2 and self.active_count:
                logger.warning("Meeting runtime event loop lag %.3fs with %s active meetings", lag, self.active_count)
            expected = loop.time() + 1
            if not self.active_count:
                await asyncio.sleep(5)
                if not self.active_count:
                    self._lag_task = None
                    return


def normalize_stream_event(meeting_id: str, event: dict[str, Any]) -> dict[str, Any]:
    data = dict(event.get("data") or {})
    if event.get("node_id") and not data.get("node_id"):
        data["node_id"] = event.get("node_id")
    if event.get("timestamp") and not data.get("timestamp"):
        data["timestamp"] = event.get("timestamp")
    event_type = str(event.get("event") or data.get("event") or "log")
    speaker = (
        data.get("agent_name")
        or data.get("agent_label")
        or data.get("speaker")
        or ("用户" if event_type == "user_message" else "会议助理")
    )
    current_round = int(data.get("round") or 0)
    content = (
        data.get("text")
        or data.get("content")
        or data.get("delta")
        or data.get("reasoning")
        or data.get("reasoning_content")
        or data.get("thinking")
        or data.get("message")
        or data.get("label")
        or data.get("title")
        or ""
    )
    if event_type == "token" and not content:
        input_t = int(data.get("input") or data.get("input_tokens") or 0)
        output_t = int(data.get("output") or data.get("output_tokens") or 0)
        content = f"输入 {input_t} / 输出 {output_t}"
    return {
        "id": f"live_{event_type}_{uuid.uuid4().hex[:12]}",
        "meeting_id": meeting_id,
        "event_type": event_type,
        "role": "assistant" if event_type != "user_message" else "user",
        "speaker": speaker,
        "round": current_round,
        "content": str(content),
        "payload": data,
        "created_at": datetime.now().isoformat(),
    }


def persist_graph_event_batch(db_path: Path, meeting_id: str, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    rows: list[dict[str, Any]] = []
    updates: dict[str, Any] = {}
    interaction_ids: list[str] = []
    token_input = 0
    token_output = 0
    token_total = 0
    now = datetime.now().isoformat()

    for event in events:
        item = normalize_stream_event(meeting_id, event)
        event_type = item["event_type"]
        payload = item["payload"]
        if event_type == "token":
            input_t = int(payload.get("input") or payload.get("input_tokens") or 0)
            output_t = int(payload.get("output") or payload.get("output_tokens") or 0)
            total_t = int(payload.get("total") or payload.get("total_tokens") or input_t + output_t)
            token_input += input_t
            token_output += output_t
            token_total += total_t
        if event_type in LOW_VALUE_EVENTS:
            continue
        if event_type not in PERSISTED_EVENTS:
            event_type = "log"
            item["event_type"] = event_type
        rows.append({
            "id": f"mevt_{uuid.uuid4().hex[:12]}",
            "meeting_id": meeting_id,
            "event_type": event_type,
            "role": item["role"],
            "speaker": item["speaker"],
            "round": item["round"],
            "content": item["content"],
            "payload": json.dumps(payload, ensure_ascii=False),
            "created_at": item["created_at"],
        })
        if item["speaker"]:
            updates["current_speaker"] = item["speaker"]
        if item["round"]:
            updates["current_round"] = item["round"]
        if event_type == "phase":
            stage = payload.get("stage") or payload.get("phase")
            if stage:
                updates["stage"] = stage
            if payload.get("progress") is not None:
                updates["progress"] = int(payload.get("progress") or 0)
            if payload.get("status"):
                updates["status"] = payload.get("status")
        if event_type == "interaction":
            interaction_id = str(payload.get("interaction_id") or "")
            if interaction_id:
                interaction_ids.append(interaction_id)

    _persist_with_retry(db_path, meeting_id, rows, interaction_ids, updates, token_input, token_output, token_total, now)


def _persist_with_retry(
    db_path: Path,
    meeting_id: str,
    rows: list[dict[str, Any]],
    interaction_ids: list[str],
    updates: dict[str, Any],
    token_input: int,
    token_output: int,
    token_total: int,
    now: str,
) -> None:
    max_attempts = 5
    base_delay = 0.05
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        conn = sqlite3.connect(str(db_path), timeout=10)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            if rows:
                conn.executemany(
                    """
                    INSERT INTO meeting_events
                    (id, meeting_id, event_type, role, speaker, round, content, payload, created_at)
                    VALUES (:id, :meeting_id, :event_type, :role, :speaker, :round, :content, :payload, :created_at)
                    """,
                    rows,
                )
            if interaction_ids:
                placeholders = ",".join("?" for _ in interaction_ids)
                pending_count = conn.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM hitl_requests
                    WHERE id IN ({placeholders}) AND status = 'pending'
                    """,
                    tuple(interaction_ids),
                ).fetchone()["count"]
                if pending_count:
                    updates["status"] = "waiting_feedback"
            if token_input or token_output or token_total:
                conn.execute(
                    """
                    UPDATE meetings
                    SET input_tokens = COALESCE(input_tokens, 0) + ?,
                        output_tokens = COALESCE(output_tokens, 0) + ?,
                        total_tokens = COALESCE(total_tokens, 0) + ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (token_input, token_output, token_total, now, meeting_id),
                )
            if updates:
                current = conn.execute("SELECT status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
                if current and current["status"] in TERMINAL_STATUSES:
                    updates.pop("status", None)
                    updates.pop("stage", None)
                    updates.pop("progress", None)
                updates["updated_at"] = now
                set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
                if set_clause:
                    conn.execute(
                        f"UPDATE meetings SET {set_clause} WHERE id = ?",
                        tuple(updates.values()) + (meeting_id,),
                    )
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            last_exc = exc
            conn.rollback()
            if "locked" in str(exc).lower() and attempt < max_attempts:
                time.sleep(base_delay * (2 ** (attempt - 1)))
                continue
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    if last_exc:
        raise last_exc
