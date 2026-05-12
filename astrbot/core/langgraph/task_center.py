from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .state import StreamEvent, TaskRecord, TaskStatus

_DEBUG_LOG_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "task_center_debug.log"
)
NOISY_STREAM_EVENTS = {"text_delta", "reasoning"}


def _merge_steps(task: TaskRecord, new_steps: list[dict]) -> None:
    """Merge new steps into existing, preserving completed results."""
    existing = {}
    for index, step in enumerate(task.steps or []):
        key = str(
            step.get("id") or step.get("description") or step.get("content") or index
        )
        existing[key] = step
    for s in new_steps:
        key = str(
            s.get("id") or s.get("description") or s.get("content") or len(existing) + 1
        )
        if key in existing:
            existing[key].update(s)
        else:
            existing[key] = s
    task.steps = list(existing.values())


def _debug_log(msg: str) -> None:
    try:
        with open(str(_DEBUG_LOG_PATH), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
            f.flush()
    except Exception:
        pass


class TaskCenter:
    EXECUTOR_REGISTRY: dict[str, Callable] = {}

    def __init__(self, checkpointer) -> None:
        self._checkpointer = checkpointer
        self._tasks: dict[str, TaskRecord] = {}
        self._running_graphs: dict[str, asyncio.Task] = {}
        self._db_callback: Callable[[str, dict], Awaitable[None]] | None = None

    def set_db_callback(self, callback: Callable[[str, dict], Awaitable[None]]) -> None:
        self._db_callback = callback

    async def _sync_to_db(self, task: TaskRecord) -> None:
        if self._db_callback is None:
            return
        try:
            status_map = {
                TaskStatus.CREATED: "pending",
                TaskStatus.DISPATCHED: "pending",
                TaskStatus.RUNNING: "running",
                TaskStatus.PAUSE_REQUESTED: "pause_requested",
                TaskStatus.PAUSED: "paused",
                TaskStatus.WAITING_FEEDBACK: "waiting_feedback",
                TaskStatus.RESUMING: "running",
                TaskStatus.DONE: "completed",
                TaskStatus.FAILED: "failed",
                TaskStatus.RETRYABLE_FAILED: "retryable_failed",
                TaskStatus.CANCELLED: "cancelled",
            }
            updates = {
                "status": status_map.get(task.status, task.status.value),
                "progress": 100 if task.status == TaskStatus.DONE else task.progress,
                "result": task.result_text,
                "steps": json.dumps(task.steps, ensure_ascii=False),
                "pending_input": task.interaction_text,
                "interaction_id": task.interaction_id,
                "input_tokens": task.input_tokens,
                "output_tokens": task.output_tokens,
                "total_tokens": task.total_tokens,
                "updated_at": datetime.now().isoformat(),
            }
            if task.status in (
                TaskStatus.DONE,
                TaskStatus.FAILED,
                TaskStatus.RETRYABLE_FAILED,
                TaskStatus.CANCELLED,
            ):
                updates["completed_at"] = datetime.now().isoformat()
            if task.status == TaskStatus.RUNNING and not task._started_at_db_set:
                updates["started_at"] = datetime.now().isoformat()
                task._started_at_db_set = True
            if task.error:
                updates["error"] = task.error
            await self._db_callback(
                task.thread_id,
                updates,
            )
        except Exception as e2:
            _debug_log(
                f"_persist_stream_event EXCEPTION: {e2}\n{traceback.format_exc()}"
            )

    def _install_run_writer(self, task: TaskRecord) -> None:
        run_ctx = task.run_ctx
        if run_ctx is None:
            return
        previous_writer = getattr(run_ctx, "writer", None)

        def writer(event: StreamEvent) -> None:
            if previous_writer:
                try:
                    previous_writer(event)
                except Exception:
                    pass
            self._handle_stream_event(task, event)
            if task.stream_callback:
                asyncio.create_task(task.stream_callback(event))

        run_ctx.writer = writer

    def _handle_stream_event(self, task: TaskRecord, event: StreamEvent) -> None:
        event_type = event.get("event", "event")
        data = event.get("data", {}) or {}
        if event_type == "text_delta":
            text = str(data.get("text") or "")
            if text:
                task.result_text = (task.result_text + text)[-120000:]
        elif event_type == "phase":
            status = data.get("status")
            if status == "cancelled":
                task.status = TaskStatus.CANCELLED
            elif status == "pause_requested":
                task.status = TaskStatus.PAUSE_REQUESTED
            elif status == "paused":
                task.status = TaskStatus.PAUSED
            elif status == "running" and task.status == TaskStatus.WAITING_FEEDBACK:
                task.status = TaskStatus.RUNNING
            progress = data.get("progress")
            if isinstance(progress, int | float):
                task.progress = max(0, min(100, int(progress)))
            steps = data.get("steps")
            if isinstance(steps, list):
                _merge_steps(task, steps)
        elif event_type == "artifact":
            content = str(data.get("content") or "")
            if content:
                task.result_text = content
        elif event_type == "token":
            input_t = data.get("input") or data.get("input_tokens") or 0
            output_t = data.get("output") or data.get("output_tokens") or 0
            task.input_tokens += int(input_t)
            task.output_tokens += int(output_t)
            task.total_tokens += int(
                data.get("total") or data.get("total_tokens") or input_t + output_t
            )
        elif event_type == "error":
            task.error = str(data.get("message") or data)
        elif event_type == "tool_call":
            pass
        elif event_type == "tool_result":
            pass
        elif event_type in ("interaction_card", "interaction"):
            task.status = TaskStatus.WAITING_FEEDBACK
            task.interaction_text = str(data.get("body") or data.get("title") or "")[
                :500
            ]
            task.interaction_id = str(data.get("interaction_id") or "")

        if event_type not in {*NOISY_STREAM_EVENTS, "token"}:
            asyncio.create_task(self._sync_to_db(task))
        asyncio.create_task(self._persist_stream_event(task, event))

    async def _persist_stream_event(self, task: TaskRecord, event: StreamEvent) -> None:
        try:
            _debug_log(
                f"_persist_stream_event ENTER: task_id={task.task_id} thread_id={task.thread_id}"
            )
            from astrbot.builtin_stars.agent_system.database import get_database

            db = get_database()
            _debug_log(f"  db={db}")
            row = db.select_one(
                "agent_tasks", where="thread_id = ?", where_params=(task.thread_id,)
            )
            _debug_log(f"  row by thread_id: {row is not None}")
            if not row:
                row = db.select_one(
                    "agent_tasks", where="id = ?", where_params=(task.task_id,)
                )
                _debug_log(f"  row by task_id: {row is not None}")
            if not row:
                _debug_log(
                    f"_persist_stream_event: task not found! task_id={task.task_id} thread_id={task.thread_id}"
                )
                return
            task_id = row["id"]
            event_type = event.get("event", "event")
            data = event.get("data", {}) or {}
            now = datetime.now().isoformat()

            if event_type == "token":
                data_dict = data if isinstance(data, dict) else {}
                input_tokens, output_tokens, total_tokens = self._extract_token_counts(
                    data_dict
                )
                if not total_tokens:
                    total_tokens = input_tokens + output_tokens
                db.insert(
                    "token_stats",
                    {
                        "id": f"tok_{uuid.uuid4().hex[:12]}",
                        "task_id": task_id,
                        "agent_id": data_dict.get("agent_id"),
                        "model_name": (data_dict.get("stats") or {}).get("model")
                        if isinstance(data_dict.get("stats"), dict)
                        else data_dict.get("model"),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "created_at": now,
                    },
                )
                db.update(
                    "agent_tasks",
                    {
                        "input_tokens": int(row.get("input_tokens") or 0)
                        + input_tokens,
                        "output_tokens": int(row.get("output_tokens") or 0)
                        + output_tokens,
                        "total_tokens": int(row.get("total_tokens") or 0)
                        + total_tokens,
                        "updated_at": now,
                    },
                    where="id = ?",
                    where_params=(task_id,),
                )
                return

            data_dict = data if isinstance(data, dict) else {"value": data}
            if event_type in NOISY_STREAM_EVENTS and self._coalesce_stream_log(
                db, task_id, event_type, data_dict, now
            ):
                return

            db.insert(
                "execution_logs",
                {
                    "id": f"log_{uuid.uuid4().hex[:12]}",
                    "task_id": task_id,
                    "sub_task_id": None,
                    "agent_id": self._safe_log_agent_id(db, data_dict),
                    "level": "error" if event_type == "error" else "info",
                    "message": self._event_message(event_type, data_dict),
                    "data": {
                        "event": event_type,
                        **data_dict,
                    },
                    "created_at": now,
                },
            )

            if event_type == "interaction" and isinstance(data, dict):
                try:
                    from astrbot.builtin_stars.agent_system.services.hitl_service import (
                        HITLService,
                    )

                    HITLService(db).upsert_from_card(
                        data,
                        task_id=task_id,
                        session_id=task.session_id,
                        channel="chatui",
                        metadata={
                            "thread_id": task.thread_id,
                            "node_id": event.get("node_id", ""),
                            "stage_id": data.get("stage_id", ""),
                            "step_id": data.get("step_id", ""),
                            "agent_id": data.get("agent_id", ""),
                            "agent_label": data.get("agent_label", ""),
                        },
                    )
                except Exception as e_hitl:
                    _debug_log(f"hitl upsert failed: {e_hitl}")
                current_status = row.get("status", "")
                if current_status not in ("cancelled", "completed", "failed"):
                    db.update(
                        "agent_tasks",
                        {
                            "interaction_id": data.get("interaction_id", ""),
                            "status": "waiting_feedback",
                            "updated_at": now,
                        },
                        where="id = ?",
                        where_params=(task_id,),
                    )

            if (
                event_type == "phase"
                and isinstance(data, dict)
                and isinstance(data.get("steps"), list)
            ):
                self._persist_work_steps(db, task_id, data["steps"], now)

            if event_type == "artifact" and isinstance(data, dict):
                artifact_id = f"art_{uuid.uuid4().hex[:12]}"
                db.insert(
                    "work_artifacts",
                    {
                        "id": artifact_id,
                        "task_id": task_id,
                        "title": data.get("title") or "任务交付物",
                        "artifact_type": data.get("artifact_type", "markdown"),
                        "content": data.get("content", ""),
                        "file_path": data.get("file_path", ""),
                        "metadata": data.get("metadata", {}),
                        "created_at": now,
                    },
                )
                deliverables = json.loads(row.get("deliverables") or "[]")
                deliverables.append(
                    {"id": artifact_id, "title": data.get("title") or "任务交付物"}
                )
                db.update(
                    "agent_tasks",
                    {"deliverables": deliverables, "updated_at": now},
                    where="id = ?",
                    where_params=(task_id,),
                )
        except Exception as e3:
            _debug_log(
                f"_persist_stream_event outer EXCEPTION: {e3}\n{traceback.format_exc()}"
            )

    @staticmethod
    def _persist_work_steps(
        db, task_id: str, steps: list[dict[str, Any]], now: str
    ) -> None:
        def scoped_id(value: Any) -> str:
            raw = str(value or "").strip()
            if not raw:
                return ""
            return raw if raw.startswith(f"{task_id}:") else f"{task_id}:{raw}"

        def persist_step(
            step: dict[str, Any],
            index: int,
            parent_id: str | None = None,
            depth: int | None = None,
        ) -> None:
            if not isinstance(step, dict):
                return
            raw_step_id = str(step.get("id") or f"step_{index + 1}")
            step_id = scoped_id(raw_step_id)
            raw_parent_id = step.get("parent_id") or step.get("parent") or parent_id
            scoped_parent_id = scoped_id(raw_parent_id) if raw_parent_id else None
            dependencies = step.get("dependencies")
            if dependencies is None:
                dependencies = step.get("depends_on") or []
            if not isinstance(dependencies, list):
                dependencies = [dependencies] if dependencies else []
            effective_depth = min(
                2, int(depth or step.get("depth") or (2 if scoped_parent_id else 1))
            )
            row = {
                "id": step_id,
                "task_id": task_id,
                "parent_id": scoped_parent_id,
                "title": step.get("title")
                or step.get("name")
                or step.get("description")
                or f"步骤 {index + 1}",
                "description": step.get("description") or step.get("title") or "",
                "status": step.get("status", "pending"),
                "dependencies": [scoped_id(dep) for dep in dependencies if dep],
                "executor": step.get("executor") or step.get("agent") or "",
                "executor_type": step.get("executor_type") or "",
                "executor_id": step.get("executor_id") or "",
                "reviewer_id": step.get("reviewer_id") or "",
                "result": step.get("result", ""),
                "result_ref": step.get("result_ref", ""),
                "depth": effective_depth,
                "sort_order": int(
                    step.get("sort_order")
                    if step.get("sort_order") is not None
                    else index
                ),
                "updated_at": now,
            }
            existing = db.select_one(
                "work_task_steps",
                where="id = ? AND task_id = ?",
                where_params=(step_id, task_id),
            )
            if existing:
                updates = {k: v for k, v in row.items() if k not in {"id", "task_id"}}
                if row["status"] in {"running"} and not existing.get("started_at"):
                    updates["started_at"] = now
                if row["status"] in {
                    "done",
                    "completed",
                    "failed",
                    "cancelled",
                } and not existing.get("completed_at"):
                    updates["completed_at"] = now
                db.update(
                    "work_task_steps",
                    updates,
                    where="id = ? AND task_id = ?",
                    where_params=(step_id, task_id),
                )
            else:
                row["started_at"] = now if row["status"] == "running" else None
                row["completed_at"] = (
                    now
                    if row["status"] in {"done", "completed", "failed", "cancelled"}
                    else None
                )
                db.insert("work_task_steps", row)
            for child_index, child in enumerate(step.get("children") or []):
                if isinstance(child, dict):
                    persist_step(child, child_index, raw_step_id, 2)

        for index, step in enumerate(steps):
            persist_step(step, index)

    @staticmethod
    def _coalesce_stream_log(
        db, task_id: str, event_type: str, data: dict[str, Any], now: str
    ) -> bool:
        rows = db.execute(
            """
            SELECT rowid, *
            FROM execution_logs
            WHERE task_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchall()
        if not rows:
            return False

        latest = dict(rows[0])
        try:
            latest_data = json.loads(latest.get("data") or "{}")
        except (TypeError, json.JSONDecodeError):
            return False

        if latest_data.get("event") != event_type:
            return False
        if TaskCenter._stream_trace_key(latest_data) != TaskCenter._stream_trace_key(
            data
        ):
            return False

        merged_text = f"{latest_data.get('text') or ''}{data.get('text') or ''}"
        latest_data.update(data)
        latest_data["event"] = event_type
        latest_data["text"] = merged_text
        db.update(
            "execution_logs",
            {
                "message": TaskCenter._event_message(event_type, latest_data),
                "data": latest_data,
                "created_at": now,
            },
            where="rowid = ?",
            where_params=(latest["rowid"],),
        )
        return True

    @staticmethod
    def _stream_trace_key(data: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(data.get("stage_id") or ""),
            str(data.get("step_id") or ""),
            str(data.get("agent_id") or ""),
            str(data.get("agent_label") or data.get("agent") or ""),
            str(data.get("step_label") or ""),
        )

    @staticmethod
    def _safe_log_agent_id(db, data: dict[str, Any]) -> str | None:
        agent_id = str(data.get("agent_id") or "").strip()
        if not agent_id:
            return None
        try:
            if db.select_one("agents", where="id = ?", where_params=(agent_id,)):
                return agent_id
        except Exception:
            return None
        return None

    @staticmethod
    def _event_message(event_type: str, data: dict[str, Any]) -> str:
        if event_type == "text_delta":
            return str(data.get("text", ""))[:500]
        if event_type == "reasoning":
            return str(data.get("text", ""))[:500]
        if event_type == "tool_call":
            return f"调用工具：{data.get('name') or data.get('function', {}).get('name') or 'tool'}"
        if event_type == "tool_result":
            return "工具调用完成"
        if event_type == "phase":
            return str(data.get("label") or data.get("phase") or "阶段更新")
        if event_type == "artifact":
            return f"生成交付物：{data.get('title') or '任务交付物'}"
        if event_type == "interaction":
            return f"等待人工确认：{data.get('title') or data.get('type') or ''}"
        if event_type == "token":
            return "Token 统计更新"
        if event_type == "error":
            return str(data.get("message") or "任务错误")
        return event_type

    @staticmethod
    def _extract_token_counts(data: dict[str, Any]) -> tuple[int, int, int]:
        stats = data.get("stats") if isinstance(data, dict) else {}
        usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}

        def read_number(*keys: str) -> int:
            for key in keys:
                source = usage if key.startswith("usage.") else data
                name = key.replace("usage.", "", 1)
                value = source.get(name) if isinstance(source, dict) else None
                try:
                    number = int(value or 0)
                except (TypeError, ValueError):
                    number = 0
                if number:
                    return number
            return 0

        input_tokens = read_number(
            "input_tokens", "input", "usage.input_other", "usage.input"
        )
        output_tokens = read_number("output_tokens", "output", "usage.output")
        total_tokens = read_number("total_tokens", "total", "usage.total")
        return input_tokens, output_tokens, total_tokens

    @classmethod
    def register_executor(cls, task_type: str, builder: Callable):
        cls.EXECUTOR_REGISTRY[task_type] = builder

    async def create_task(
        self,
        task_type: str,
        config: dict,
        session_id: str,
        stream_callback: Callable[[StreamEvent], Awaitable[None]] | None = None,
        run_ctx: Any = None,
    ) -> TaskRecord:
        config = dict(config or {})
        task_id = str(config.get("task_id") or f"task_{uuid.uuid4().hex[:12]}")
        thread_id = str(config.get("thread_id") or f"{session_id}:{task_id}")
        config["task_id"] = task_id
        config["thread_id"] = thread_id
        config.setdefault("session_id", session_id)

        task = TaskRecord(
            task_id=task_id,
            task_type=task_type,
            session_id=session_id,
            thread_id=thread_id,
            status=TaskStatus.CREATED,
            config=config,
            hitl_context=None,
            result=None,
            error=None,
            created_at=time.time(),
            updated_at=time.time(),
            stream_callback=stream_callback,
            run_ctx=run_ctx,
        )
        self._tasks[task_id] = task

        runner = asyncio.create_task(self._run_task(task))
        self._running_graphs[task_id] = runner
        return task

    async def _get_or_create_checkpointer(self):
        if self._checkpointer is not None:
            return self._checkpointer

        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        from astrbot.core.langgraph.checkpoint import (
            get_checkpoint_db_path,
            set_checkpointer,
        )

        db_path = get_checkpoint_db_path()
        conn = await aiosqlite.connect(db_path)
        checkpointer = AsyncSqliteSaver(conn)
        set_checkpointer(checkpointer)
        self._checkpointer = checkpointer
        return checkpointer

    async def _run_task(self, task: TaskRecord):
        _debug_log(
            f"_run_task ENTER: task_id={task.task_id} thread_id={task.thread_id} task_type={task.task_type}"
        )
        builder = self.EXECUTOR_REGISTRY.get(task.task_type)
        _debug_log(f"  builder found: {builder is not None}")
        if not builder:
            task.status = TaskStatus.FAILED
            task.error = f"Unknown task_type: {task.task_type}"
            task.updated_at = time.time()
            await self._sync_to_db(task)
            return

        checkpointer = await self._get_or_create_checkpointer()
        _debug_log(f"  checkpointer: {checkpointer}")

        _debug_log("  building graph...")
        try:
            graph = builder(config=task.config, checkpointer=checkpointer)
            _debug_log(f"  graph built: {graph}")
        except Exception as e_g:
            _debug_log(f"  graph build FAILED: {e_g}\n{traceback.format_exc()}")
            raise
        task.status = TaskStatus.RUNNING
        task.updated_at = time.time()
        self._install_run_writer(task)
        _debug_log("  run_writer installed, emitting started event...")
        self._handle_stream_event(
            task,
            StreamEvent(
                event="phase",
                data={
                    "phase": "started",
                    "label": "任务执行器已启动",
                    "progress": task.progress,
                },
                timestamp=time.time(),
                node_id="task_center",
            ),
        )
        await self._sync_to_db(task)
        _debug_log("  synced to db, starting astream_events...")

        try:
            async for event in graph.astream_events(
                task.config,
                config={
                    "configurable": {
                        "thread_id": task.thread_id,
                        "run_ctx": task.run_ctx,
                    }
                },
                version="v2",
            ):
                _debug_log(
                    f"  astream event: {event.get('event')} name={event.get('name')}"
                )
                if event["event"] == "on_custom_event":
                    stream_event = event["data"]
                    if task.stream_callback:
                        await task.stream_callback(stream_event)

                elif event["event"] == "on_interrupt":
                    _debug_log("  on_interrupt received!")
                    task.status = TaskStatus.PAUSED
                    task.hitl_context = event["data"]
                    task.updated_at = time.time()
                    await self._sync_to_db(task)
                    return

            _debug_log("  astream_events loop ended normally")
            if task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.DONE
            task.result = {"output": "Task completed"}
            task.updated_at = time.time()
            if task.status == TaskStatus.DONE:
                self._handle_stream_event(
                    task,
                    StreamEvent(
                        event="phase",
                        data={
                            "phase": "done",
                            "label": "任务执行器已结束",
                            "progress": 100,
                        },
                        timestamp=time.time(),
                        node_id="task_center",
                    ),
                )
            await self._sync_to_db(task)
        except asyncio.CancelledError:
            _debug_log(f"  _run_task CANCELLED: {task.task_id}")
            task.status = TaskStatus.CANCELLED
            task.updated_at = time.time()
            await self._sync_to_db(task)
            raise
        except Exception as e:
            _debug_log(
                f"  _run_task EXCEPTION: {task.task_id} error={e}\n{traceback.format_exc()}"
            )
            retryable = bool(getattr(e, "retryable", False)) or e.__class__.__name__ in {
                "WorkLLMCallError",
                "WorkLLMIdleTimeout",
            }
            task.status = TaskStatus.RETRYABLE_FAILED if retryable else TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = time.time()
            self._handle_stream_event(
                task,
                StreamEvent(
                    event="error",
                    data={"message": str(e)},
                    timestamp=time.time(),
                    node_id="task_center",
                ),
            )
            await self._sync_to_db(task)
        finally:
            self._running_graphs.pop(task.task_id, None)

    async def resume_task(self, task_id: str, resume_value: Any):
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PAUSE_REQUESTED:
            task.status = TaskStatus.RUNNING
            task.updated_at = time.time()
            await self._sync_to_db(task)
            return
        if not task or task.status != TaskStatus.PAUSED:
            raise ValueError(f"Task {task_id} is not paused")

        task.status = TaskStatus.RESUMING
        task.updated_at = time.time()
        builder = self.EXECUTOR_REGISTRY[task.task_type]
        graph = builder(config=task.config, checkpointer=self._checkpointer)
        self._install_run_writer(task)

        runner = asyncio.create_task(self._resume_task_body(task, graph, resume_value))
        self._running_graphs[task_id] = runner

    async def _resume_task_body(self, task: TaskRecord, graph, resume_value: Any):
        from langgraph.types import Command

        try:
            async for event in graph.astream_events(
                Command(resume=resume_value),
                config={
                    "configurable": {
                        "thread_id": task.thread_id,
                        "run_ctx": task.run_ctx,
                    }
                },
                version="v2",
            ):
                if event["event"] == "on_custom_event":
                    stream_event = event["data"]
                    if task.stream_callback:
                        await task.stream_callback(stream_event)
                elif event["event"] == "on_interrupt":
                    task.status = TaskStatus.PAUSED
                    task.hitl_context = event["data"]
                    task.updated_at = time.time()
                    await self._sync_to_db(task)
                    return

            if task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.DONE
            task.result = {"output": "Task completed"}
            task.updated_at = time.time()
            if task.status == TaskStatus.DONE:
                self._handle_stream_event(
                    task,
                    StreamEvent(
                        event="phase",
                        data={
                            "phase": "done",
                            "label": "任务执行器已结束",
                            "progress": 100,
                        },
                        timestamp=time.time(),
                        node_id="task_center",
                    ),
                )
            await self._sync_to_db(task)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.updated_at = time.time()
            await self._sync_to_db(task)
            raise
        except Exception as e:
            retryable = bool(getattr(e, "retryable", False)) or e.__class__.__name__ in {
                "WorkLLMCallError",
                "WorkLLMIdleTimeout",
            }
            task.status = TaskStatus.RETRYABLE_FAILED if retryable else TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = time.time()
            self._handle_stream_event(
                task,
                StreamEvent(
                    event="error",
                    data={"message": str(e)},
                    timestamp=time.time(),
                    node_id="task_center",
                ),
            )
            await self._sync_to_db(task)
        finally:
            self._running_graphs.pop(task.task_id, None)

    async def cancel_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        running = self._running_graphs.pop(task_id, None)
        if running and not running.done():
            running.cancel()
        task.status = TaskStatus.CANCELLED
        task.updated_at = time.time()
        await self._sync_to_db(task)

    async def request_pause_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status not in {TaskStatus.RUNNING, TaskStatus.RESUMING}:
            raise ValueError(f"Task {task_id} is not running")
        task.status = TaskStatus.PAUSE_REQUESTED
        task.updated_at = time.time()
        await self._sync_to_db(task)

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def list_tasks(self, session_id: str | None = None) -> list[TaskRecord]:
        if session_id:
            return [t for t in self._tasks.values() if t.session_id == session_id]
        return list(self._tasks.values())
