"""GenericAgent runtime integration service."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.core import logger
from astrbot.core.star.star_tools import StarTools

from .skill_service import SkillService

DEFAULT_TOOL_POLICIES: list[dict[str, str]] = [
    {"tool_name": "code_run", "description": "执行 Python/PowerShell 代码"},
    {"tool_name": "file_read", "description": "读取文件"},
    {"tool_name": "file_write", "description": "写入文件"},
    {"tool_name": "file_patch", "description": "局部修改文件"},
    {"tool_name": "web_scan", "description": "扫描浏览器页面"},
    {"tool_name": "web_execute_js", "description": "执行浏览器 JavaScript"},
    {"tool_name": "ask_user", "description": "请求人工输入"},
    {"tool_name": "update_working_checkpoint", "description": "更新短期工作记忆"},
    {"tool_name": "start_long_term_update", "description": "沉淀长期记忆"},
]

TERMINAL_RUN_STATES = {"completed", "failed", "cancelled"}
GENERIC_AGENT_ERROR_RE = re.compile(r"!!!Error:\s*([^\n`]+)")

_service_singleton: GenericAgentRuntimeService | None = None


def get_generic_agent_service(db, context=None) -> GenericAgentRuntimeService:
    """Return the process-wide GenericAgent service singleton."""
    global _service_singleton
    if _service_singleton is None or _service_singleton.db is not db:
        _service_singleton = GenericAgentRuntimeService(db, context)
    elif context is not None:
        _service_singleton.context = context
    return _service_singleton


class GenericAgentRuntimeService:
    """Owns GenericAgent queueing, execution, event capture, and skill review."""

    def __init__(self, db, context=None) -> None:
        self.db = db
        self.context = context
        self._worker_task: asyncio.Task | None = None
        self._worker_lock = asyncio.Lock()
        self._current_process: asyncio.subprocess.Process | None = None
        self._current_run_id: str | None = None
        self._cancelled_runs: set[str] = set()
        self._history_repair_done = False

    # ------------------------------------------------------------------
    # Configuration

    def get_config(self) -> dict[str, Any]:
        self._ensure_error_only_history_repaired()
        settings = self._config_value("settings", {})
        default_runtime = self._data_root() / "runtime"
        config = {
            "source_path": settings.get("source_path")
            or str(self._default_source_path()),
            "runtime_path": settings.get("runtime_path") or str(default_runtime),
            "default_workspace_path": settings.get("default_workspace_path")
            or str(Path.cwd()),
            "llm_config": settings.get("llm_config") or {},
            "max_run_seconds": int(settings.get("max_run_seconds") or 1800),
            "soft_stop_seconds": int(settings.get("soft_stop_seconds") or 10),
            "updated_at": self._config_updated_at("settings"),
        }
        config["integration_status"] = self._integration_status(config)
        return config

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        current = self.get_config()
        llm_config = data.get("llm_config")
        if not isinstance(llm_config, dict):
            llm_config = current["llm_config"]
        update = {
            "source_path": str(data.get("source_path") or current["source_path"]),
            "runtime_path": str(data.get("runtime_path") or current["runtime_path"]),
            "default_workspace_path": str(
                data.get("default_workspace_path") or current["default_workspace_path"]
            ),
            "llm_config": self._clean_llm_config(llm_config),
            "max_run_seconds": int(
                data.get("max_run_seconds") or current["max_run_seconds"]
            ),
            "soft_stop_seconds": int(
                data.get("soft_stop_seconds") or current["soft_stop_seconds"]
            ),
        }
        self._set_config_value("settings", update)
        return self.get_config()

    # ------------------------------------------------------------------
    # Runs

    async def enqueue_run(self, data: dict[str, Any]) -> dict[str, Any]:
        goal = str(data.get("goal") or "").strip()
        if not goal:
            raise ValueError("goal 不能为空")

        config = self.get_config()
        run_id = data.get("id") or f"gar_{uuid.uuid4().hex[:12]}"
        now = self._now()
        expected_outputs = data.get("expected_outputs") or []
        if isinstance(expected_outputs, str):
            expected_outputs = [expected_outputs]
        row = {
            "id": run_id,
            "source": str(data.get("source") or "manual"),
            "goal": goal,
            "constraints": str(data.get("constraints") or ""),
            "expected_outputs": expected_outputs,
            "workspace_path": str(
                data.get("workspace_path") or config["default_workspace_path"]
            ),
            "parent_task_id": str(data.get("parent_task_id") or ""),
            "status": "pending",
            "queue_position": self._pending_count() + 1,
            "progress": 0,
            "summary": "",
            "artifacts": [],
            "error": "",
            "pid": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self.db.insert("generic_agent_runs", row)
        self._insert_event(run_id, "queued", "已加入 GenericAgent 队列", row)
        self._refresh_queue_positions()
        self._ensure_worker()
        return self.get_run(run_id)

    def list_runs(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        self._ensure_error_only_history_repaired()
        self._recover_interrupted_runs()
        self._ensure_worker()
        where = "1=1"
        params: tuple[Any, ...] = ()
        if status:
            where = "status = ?"
            params = (status,)
        rows = self.db.select_all(
            "generic_agent_runs",
            where=where,
            where_params=params,
            order_by="created_at DESC",
            limit=max(1, min(int(limit or 100), 500)),
        )
        return [self._run_dict(row) for row in rows]

    def list_runs_page(
        self,
        status: str | None = None,
        source: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 30,
    ) -> dict[str, Any]:
        self._ensure_error_only_history_repaired()
        self._recover_interrupted_runs()
        self._ensure_worker()
        conditions = ["1=1"]
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if source:
            conditions.append("source = ?")
            params.append(source)
        keyword = str(q or "").strip()
        if keyword:
            conditions.append("(goal LIKE ? OR summary LIKE ? OR error LIKE ? OR constraints LIKE ? OR workspace_path LIKE ?)")
            params.extend([f"%{keyword}%"] * 5)
        where = " AND ".join(conditions)
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 30), 100))
        total = self.db.execute(
            f"SELECT COUNT(*) AS count FROM generic_agent_runs WHERE {where}",
            tuple(params),
        ).fetchone()["count"]
        rows = self.db.execute(
            f"""
            SELECT *
            FROM generic_agent_runs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size, (page - 1) * page_size]),
        ).fetchall()
        return {
            "runs": [self._run_dict(row) for row in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def list_run_summaries(self, run_ids: list[str]) -> list[dict[str, Any]]:
        self._ensure_error_only_history_repaired()
        ids = [str(run_id).strip() for run_id in run_ids if str(run_id).strip()]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.execute(
            f"""
            SELECT *
            FROM generic_agent_runs
            WHERE id IN ({placeholders})
            """,
            tuple(ids),
        ).fetchall()
        by_id = {row["id"]: self._run_dict(row) for row in rows}
        return [by_id[run_id] for run_id in ids if run_id in by_id]

    def get_run(self, run_id: str) -> dict[str, Any]:
        self._ensure_error_only_history_repaired()
        self._recover_interrupted_runs()
        row = self.db.select_one(
            "generic_agent_runs",
            where="id = ?",
            where_params=(run_id,),
        )
        if not row:
            raise ValueError(f"GenericAgent run '{run_id}' 不存在")
        return self._run_dict(row)

    def list_events(
        self, run_id: str, after_seq: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        self.get_run(run_id)
        rows = self.db.execute(
            """
            SELECT rowid AS seq, *
            FROM generic_agent_events
            WHERE run_id = ? AND rowid > ?
            ORDER BY rowid ASC
            LIMIT ?
            """,
            (run_id, int(after_seq or 0), max(1, min(int(limit or 500), 2000))),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._parse_json(item.get("payload"), {})
            events.append(item)
        return events

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] == "pending":
            self._update_run(
                run_id,
                {"status": "cancelled", "completed_at": self._now(), "progress": 0},
            )
            self._insert_event(run_id, "cancelled", "未开始任务已取消", {})
            self._refresh_queue_positions()
            return self.get_run(run_id)

        if run["status"] != "running":
            return run

        self._cancelled_runs.add(run_id)
        self._insert_event(run_id, "stop_requested", "已请求软停止", {})
        stop_file = self._runtime_task_dir(run_id) / "_stop"
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stop", encoding="utf-8")

        soft_seconds = self.get_config()["soft_stop_seconds"]
        for _ in range(max(1, int(soft_seconds * 2))):
            await asyncio.sleep(0.5)
            latest = self.get_run(run_id)
            if latest["status"] in TERMINAL_RUN_STATES:
                return latest

        if self._current_run_id == run_id and self._current_process:
            self._insert_event(run_id, "force_kill", "软停止超时，强制终止进程", {})
            self._current_process.kill()
        return self.get_run(run_id)

    # ------------------------------------------------------------------
    # Tool policies

    def ensure_default_tool_policies(self) -> None:
        now = self._now()
        for item in DEFAULT_TOOL_POLICIES:
            existing = self.db.select_one(
                "generic_agent_tool_policies",
                where="tool_name = ?",
                where_params=(item["tool_name"],),
            )
            if not existing:
                self.db.insert(
                    "generic_agent_tool_policies",
                    {
                        "tool_name": item["tool_name"],
                        "enabled": 1,
                        "description": item["description"],
                        "updated_at": now,
                    },
                )

    def get_tool_policies(self) -> list[dict[str, Any]]:
        self.ensure_default_tool_policies()
        rows = self.db.select_all(
            "generic_agent_tool_policies",
            order_by="tool_name ASC",
        )
        result = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item.get("enabled"))
            result.append(item)
        return result

    def update_tool_policies(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        self.ensure_default_tool_policies()
        policies = data.get("tools") if isinstance(data.get("tools"), list) else []
        by_name = {item["tool_name"]: item for item in self.get_tool_policies()}
        now = self._now()
        for item in policies:
            tool_name = str(item.get("tool_name") or "").strip()
            if not tool_name or tool_name not in by_name:
                continue
            update = {"enabled": bool(item.get("enabled")), "updated_at": now}
            self.db.update(
                "generic_agent_tool_policies",
                update,
                where="tool_name = ?",
                where_params=(tool_name,),
            )
        return self.get_tool_policies()

    # ------------------------------------------------------------------
    # Skill reviews

    def list_skill_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        where = "1=1"
        params: tuple[Any, ...] = ()
        if status:
            where = "status = ?"
            params = (status,)
        rows = self.db.select_all(
            "generic_agent_skill_reviews",
            where=where,
            where_params=params,
            order_by="created_at DESC",
            limit=200,
        )
        return [dict(row) for row in rows]

    def approve_skill_review(self, review_id: str) -> dict[str, Any]:
        review = self.db.select_one(
            "generic_agent_skill_reviews",
            where="id = ?",
            where_params=(review_id,),
        )
        if not review:
            raise ValueError(f"技能审核 '{review_id}' 不存在")
        if review.get("status") == "approved" and review.get("synced_skill_id"):
            return dict(review)

        skill_service = SkillService(self.db)
        skill = skill_service.create_skill(
            {
                "name": review["title"],
                "description": review.get("description")
                or "GenericAgent 自进化沉淀技能",
                "source": "genericagent",
                "category": "genericagent",
                "disclosure_level": "instructions",
                "workflow": {
                    "type": "genericagent_skill",
                    "source_run_id": review["run_id"],
                    "source_path": review.get("source_path", ""),
                    "instructions": review.get("content", ""),
                },
                "metadata": {
                    "source": "genericagent",
                    "review_id": review_id,
                },
            }
        )
        reviewed_at = self._now()
        self.db.update(
            "generic_agent_skill_reviews",
            {
                "status": "approved",
                "synced_skill_id": skill.id,
                "reviewed_at": reviewed_at,
            },
            where="id = ?",
            where_params=(review_id,),
        )
        return dict(
            self.db.select_one(
                "generic_agent_skill_reviews",
                where="id = ?",
                where_params=(review_id,),
            )
        )

    def reject_skill_review(self, review_id: str) -> dict[str, Any]:
        review = self.db.select_one(
            "generic_agent_skill_reviews",
            where="id = ?",
            where_params=(review_id,),
        )
        if not review:
            raise ValueError(f"技能审核 '{review_id}' 不存在")
        self.db.update(
            "generic_agent_skill_reviews",
            {"status": "rejected", "reviewed_at": self._now()},
            where="id = ?",
            where_params=(review_id,),
        )
        return dict(
            self.db.select_one(
                "generic_agent_skill_reviews",
                where="id = ?",
                where_params=(review_id,),
            )
        )

    # ------------------------------------------------------------------
    # Worker

    def _ensure_worker(self) -> None:
        self._recover_interrupted_runs()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = loop.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        async with self._worker_lock:
            while True:
                run = self._next_pending_run()
                if not run:
                    self._refresh_queue_positions()
                    return
                await self._execute_run(run["id"])
                self._refresh_queue_positions()

    async def _execute_run(self, run_id: str) -> None:
        self._current_run_id = run_id
        run = self.get_run(run_id)
        config = self.get_config()
        started_at = self._now()
        self._update_run(
            run_id,
            {"status": "running", "started_at": started_at, "progress": 5, "error": ""},
        )
        self._insert_event(
            run_id, "lifecycle", "开始执行", {"config": self._public_config(config)}
        )

        try:
            runtime_dir = self._prepare_runtime_copy(config)
            mykey = self._write_mykey(runtime_dir, config)
            if not mykey:
                raise ValueError(
                    "GenericAgent LLM 配置为空，请先在工作台配置 llm_config"
                )
            self._write_filtered_tool_schema(runtime_dir)
            output_text = await self._run_generic_agent_process(
                run_id, runtime_dir, run, config
            )
            final_output = self._extract_final_output(output_text)
            error_message = self._classify_final_output_error(
                final_output or output_text
            )
            status = (
                "cancelled"
                if run_id in self._cancelled_runs
                else "failed"
                if error_message
                else "completed"
            )
            artifacts = self._collect_artifacts(
                run_id,
                runtime_dir,
                final_output,
                include_final_output=status == "completed",
            )
            summary = "" if error_message else self._extract_summary(final_output or output_text)
            self._update_run(
                run_id,
                {
                    "status": status,
                    "progress": 100 if status == "completed" else 0,
                    "summary": summary,
                    "artifacts": artifacts,
                    "completed_at": self._now(),
                    "error": error_message or "",
                },
            )
            self._insert_event(
                run_id,
                status,
                "执行失败" if status == "failed" else "执行结束",
                {
                    "summary": summary,
                    "artifacts": artifacts,
                    "final_output": final_output[:60000],
                    "error": error_message or "",
                },
            )
            if status == "completed":
                self._collect_skill_reviews(run_id, runtime_dir, started_at)
        except Exception as exc:
            logger.error(f"GenericAgent run failed: {run_id} - {exc}", exc_info=True)
            status = "cancelled" if run_id in self._cancelled_runs else "failed"
            self._update_run(
                run_id,
                {
                    "status": status,
                    "progress": 0,
                    "error": str(exc),
                    "completed_at": self._now(),
                },
            )
            self._insert_event(run_id, "error", "执行失败", {"message": str(exc)})
        finally:
            self._current_process = None
            self._current_run_id = None
            self._cancelled_runs.discard(run_id)

    def _recover_interrupted_runs(self) -> None:
        rows = self.db.select_all(
            "generic_agent_runs",
            where="status = ?",
            where_params=("running",),
        )
        if not rows:
            return

        config = self.get_config()
        runtime_dir = Path(config["runtime_path"]).expanduser().resolve()
        for row in rows:
            run = self._run_dict(row)
            run_id = run["id"]
            if run_id == self._current_run_id:
                continue

            pid = self._coerce_pid(run.get("pid"))
            if pid and self._pid_exists(pid):
                continue
            if not pid and self._is_recent_run_update(run):
                continue

            output_path = runtime_dir / "temp" / run_id / "output.txt"
            output_text = ""
            if output_path.exists():
                output_text = output_path.read_text(
                    encoding="utf-8", errors="replace"
                )

            if output_text and self._looks_like_completed_task_output(output_text):
                self._complete_interrupted_run_from_output(
                    run, runtime_dir, output_text
                )
                continue

            if not pid:
                continue

            message = "GenericAgent 进程已结束，但未检测到最终输出"
            self._update_run(
                run_id,
                {
                    "status": "failed",
                    "progress": 0,
                    "pid": None,
                    "error": message,
                    "completed_at": self._now(),
                },
            )
            self._insert_event(run_id, "error", "恢复中断运行失败", {"message": message})

        self._refresh_queue_positions()

    def _complete_interrupted_run_from_output(
        self, run: dict[str, Any], runtime_dir: Path, output_text: str
    ) -> None:
        run_id = run["id"]
        final_output = self._extract_final_output(output_text)
        error_message = self._classify_final_output_error(final_output or output_text)
        status = "failed" if error_message else "completed"
        artifacts = self._collect_artifacts(
            run_id,
            runtime_dir,
            final_output,
            include_final_output=status == "completed",
        )
        summary = "" if error_message else self._extract_summary(final_output or output_text)
        self._update_run(
            run_id,
            {
                "status": status,
                "progress": 100 if status == "completed" else 0,
                "summary": summary,
                "artifacts": artifacts,
                "pid": None,
                "completed_at": self._now(),
                "error": error_message or "",
            },
        )
        self._insert_event(
            run_id,
            status,
            "执行失败" if status == "failed" else "执行结束",
            {
                "summary": summary,
                "artifacts": artifacts,
                "final_output": final_output[:60000],
                "error": error_message or "",
                "recovered": True,
            },
        )
        if status == "completed":
            self._collect_skill_reviews(
                run_id,
                runtime_dir,
                run.get("started_at") or run.get("created_at") or self._now(),
            )

    @staticmethod
    def _coerce_pid(value: Any) -> int | None:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            return None
        return pid if pid > 0 else None

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    timeout=2,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.SubprocessError):
                return False
            output = result.stdout.decode(errors="ignore")
            return f'"{pid}"' in output

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except (OSError, SystemError):
            return False
        return True

    @staticmethod
    def _is_recent_run_update(run: dict[str, Any], seconds: int = 30) -> bool:
        timestamp = (
            run.get("updated_at") or run.get("started_at") or run.get("created_at")
        )
        if not timestamp:
            return False
        try:
            updated_at = datetime.fromisoformat(str(timestamp))
        except ValueError:
            return False
        return (datetime.now() - updated_at).total_seconds() < seconds

    async def _run_generic_agent_process(
        self,
        run_id: str,
        runtime_dir: Path,
        run: dict[str, Any],
        config: dict[str, Any],
    ) -> str:
        prompt = self._compose_prompt(run)
        task_dir = runtime_dir / "temp" / run_id
        task_dir.mkdir(parents=True, exist_ok=True)
        output_path = task_dir / "output.txt"
        last_output = ""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["GA_LANG"] = env.get("GA_LANG", "zh")
        env["PYTHONPATH"] = str(runtime_dir) + os.pathsep + env.get("PYTHONPATH", "")

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-X",
            "utf8",
            "-u",
            "agentmain.py",
            "--task",
            run_id,
            "--input",
            prompt,
            "--verbose",
            "--nobg",
            cwd=str(runtime_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._current_process = process
        self._current_run_id = run_id
        self._update_run(run_id, {"pid": process.pid, "progress": 10})
        self._insert_event(
            run_id, "process", "GenericAgent 进程已启动", {"pid": process.pid}
        )

        start = asyncio.get_running_loop().time()
        max_seconds = int(config.get("max_run_seconds") or 1800)
        stdout_done = False
        stdout_buffer: list[str] = []
        completed_output = ""
        completion_seen = False
        while True:
            if process.returncode is not None:
                break
            if asyncio.get_running_loop().time() - start > max_seconds:
                self._cancelled_runs.add(run_id)
                self._insert_event(
                    run_id,
                    "timeout",
                    "运行超时，强制终止",
                    {"max_run_seconds": max_seconds},
                )
                process.kill()
                break

            if process.stdout and not stdout_done:
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=0.5
                    )
                    if line:
                        text = line.decode("utf-8", errors="replace")
                        stdout_buffer.append(text)
                        self._record_terminal_output(run_id, text)
                    else:
                        stdout_done = True
                except asyncio.TimeoutError:
                    pass

            if output_path.exists():
                current = output_path.read_text(encoding="utf-8", errors="replace")
                if len(current) > len(last_output):
                    delta = current[len(last_output) :]
                    last_output = current
                    self._record_agent_delta(run_id, delta)
                if self._looks_like_completed_task_output(current):
                    completed_output = current
                    if not completion_seen:
                        completion_seen = True
                        self._insert_event(
                            run_id,
                            "process",
                            "GenericAgent 已输出最终结果",
                            {},
                        )
                        self._update_run(run_id, {"progress": 95})
                    if process.returncode is None:
                        process.terminate()
                    break
            await asyncio.sleep(0.5)

        if completed_output and process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        else:
            await process.wait()
        if process.stdout and not stdout_done:
            rest = await process.stdout.read()
            if rest:
                text = rest.decode("utf-8", errors="replace")
                stdout_buffer.append(text)
                self._record_terminal_output(run_id, text[-4000:])

        final_output = ""
        if output_path.exists():
            final_output = output_path.read_text(encoding="utf-8", errors="replace")
            if len(final_output) > len(last_output):
                self._record_agent_delta(run_id, final_output[len(last_output) :])
        if (
            process.returncode not in (0, None)
            and run_id not in self._cancelled_runs
            and not completed_output
        ):
            stderr_text = "".join(stdout_buffer)[-4000:]
            raise ValueError(
                stderr_text or f"GenericAgent 退出码: {process.returncode}"
            )
        return final_output or "".join(stdout_buffer)

    def _record_agent_delta(self, run_id: str, delta: str) -> None:
        text = delta.strip()
        if not text:
            return
        self._insert_event(run_id, "llm_chunk", "输出增量", {"text": text[-8000:]})
        for tool_name in re.findall(r"Tool:\s*`([^`]+)`", text):
            self._insert_event(
                run_id, "tool_call", f"调用工具 {tool_name}", {"tool_name": tool_name}
            )
        progress = min(95, 15 + len(text) // 200)
        self._update_run(run_id, {"progress": progress})

    def _record_terminal_output(self, run_id: str, text: str) -> None:
        useful_lines = [
            line.rstrip()
            for line in text.splitlines()
            if self._should_record_terminal_line(line)
        ]
        if not useful_lines:
            return
        self._insert_event(
            run_id,
            "terminal",
            "终端输出",
            {"text": "\n".join(useful_lines)[-4000:]},
        )

    @staticmethod
    def _looks_like_completed_task_output(text: str) -> bool:
        tail = (text or "")[-4000:]
        return "[ROUND END]" in tail or "[Info] Final response to user." in tail

    # ------------------------------------------------------------------
    # Runtime filesystem

    def _prepare_runtime_copy(self, config: dict[str, Any]) -> Path:
        source_path = Path(config["source_path"]).expanduser().resolve()
        if not source_path.exists():
            raise ValueError(f"GenericAgent 源码目录不存在: {source_path}")
        runtime_dir = Path(config["runtime_path"]).expanduser().resolve()
        runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        ignore = shutil.ignore_patterns(
            ".git", "__pycache__", ".venv", "memory", "temp", "*.pyc"
        )
        if not runtime_dir.exists():
            shutil.copytree(source_path, runtime_dir, ignore=ignore)
        else:
            for item in source_path.iterdir():
                if item.name in {".git", "__pycache__", ".venv", "temp", "memory"}:
                    continue
                target = runtime_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True, ignore=ignore)
                else:
                    shutil.copy2(item, target)
        (runtime_dir / "memory").mkdir(exist_ok=True)
        (runtime_dir / "temp" / "model_responses").mkdir(parents=True, exist_ok=True)
        return runtime_dir

    def _write_mykey(self, runtime_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        llm_config = self._normalize_llm_config(config.get("llm_config") or {})
        if not llm_config:
            return {}
        mykey_path = runtime_dir / "mykey.json"
        mykey_path.write_text(
            json.dumps(llm_config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return llm_config

    def _normalize_llm_config(self, llm_config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(llm_config, dict) or not llm_config:
            return {}

        if llm_config.get("provider_id") and self.context is not None:
            provider_cfg = self._provider_config_to_generic_agent(llm_config)
            if provider_cfg:
                return provider_cfg
            raise ValueError(
                f"无法从 NiceBot Provider '{llm_config.get('provider_id')}' 生成 GenericAgent LLM 配置，"
                "请检查该 Provider 是否启用，并且包含 key、api_base 和 model。"
            )

        if self._looks_like_generic_agent_config(llm_config):
            return llm_config

        session_type = str(llm_config.get("session_type") or "native_oai_config")
        allowed = {
            "name",
            "apikey",
            "api_key",
            "apibase",
            "api_base",
            "base_url",
            "model",
            "api_mode",
            "reasoning_effort",
            "temperature",
            "max_tokens",
            "max_retries",
            "connect_timeout",
            "read_timeout",
            "stream",
            "proxy",
            "fake_cc_system_prompt",
            "thinking_type",
            "thinking_budget_tokens",
            "user_agent",
        }
        session = {key: value for key, value in llm_config.items() if key in allowed}
        if "api_key" in session and "apikey" not in session:
            session["apikey"] = session.pop("api_key")
        if "api_base" in session and "apibase" not in session:
            session["apibase"] = session.pop("api_base")
        if "base_url" in session and "apibase" not in session:
            session["apibase"] = session.pop("base_url")
        if session.get("model"):
            session["model"] = self._scalar_text(session["model"])
        if session and not all(session.get(key) for key in ("apikey", "apibase", "model")):
            raise ValueError("GenericAgent LLM 配置缺少 apikey、apibase 或 model")
        return {session_type: session} if session else {}

    def _provider_config_to_generic_agent(
        self, llm_config: dict[str, Any]
    ) -> dict[str, Any]:
        provider_id = llm_config.get("provider_id")
        if not provider_id:
            return {}
        provider_config = self._merged_provider_config(provider_id)
        model = self._scalar_text(
            llm_config.get("model")
            or provider_config.get("model")
            or provider_config.get("model_name")
        )
        api_key = self._first_text(
            provider_config.get("api_key"),
            provider_config.get("apikey"),
            provider_config.get("key"),
            provider_config.get("openai_api_key"),
        )
        api_base = self._first_text(
            provider_config.get("api_base"),
            provider_config.get("base_url"),
            provider_config.get("api_base_url"),
            provider_config.get("openai_api_base"),
            "https://api.openai.com/v1",
        )
        if not model or not api_key:
            return {}
        model_text = str(model).lower()
        session_type = (
            "native_claude_config" if "claude" in model_text else "native_oai_config"
        )
        session = {
            "name": "nicebot-provider",
            "apikey": api_key,
            "apibase": api_base,
            "model": model,
            "api_mode": llm_config.get("api_mode", "chat_completions"),
        }
        for key in ("reasoning_effort", "temperature", "max_tokens"):
            if llm_config.get(key) not in (None, ""):
                session[key] = llm_config[key]
        if timeout := self._first_text(
            llm_config.get("timeout"), provider_config.get("timeout")
        ):
            session["timeout"] = timeout
            session["read_timeout"] = self._first_text(
                llm_config.get("read_timeout"),
                provider_config.get("read_timeout"),
                timeout,
            )
        if proxy := self._first_text(
            llm_config.get("proxy"),
            provider_config.get("proxy"),
            os.environ.get("HTTPS_PROXY"),
            os.environ.get("HTTP_PROXY"),
        ):
            session["proxy"] = proxy
        if max_retries := self._first_text(
            llm_config.get("max_retries"), provider_config.get("max_retries")
        ):
            session["max_retries"] = max_retries
        custom_headers = provider_config.get("custom_headers")
        if isinstance(custom_headers, dict) and custom_headers:
            session["custom_headers"] = custom_headers
        return {session_type: session}

    def _write_filtered_tool_schema(self, runtime_dir: Path) -> None:
        enabled = {
            item["tool_name"] for item in self.get_tool_policies() if item["enabled"]
        }
        for name in ("tools_schema.json", "tools_schema_cn.json"):
            path = runtime_dir / "assets" / name
            if not path.exists():
                continue
            tools = json.loads(path.read_text(encoding="utf-8"))
            filtered = [
                tool
                for tool in tools
                if tool.get("function", {}).get("name") in enabled
            ]
            path.write_text(
                json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    # ------------------------------------------------------------------
    # Helpers

    def _compose_prompt(self, run: dict[str, Any]) -> str:
        expected_outputs = run.get("expected_outputs") or []
        expected_text = (
            "\n".join(f"- {item}" for item in expected_outputs)
            or "- 按任务需要给出结果摘要"
        )
        constraints = run.get("constraints") or "无额外约束"
        return (
            "你是 NiceBot 内置的 GenericAgent OS 操作专家。请在当前工作目录中完成任务。\n\n"
            f"目标:\n{run['goal']}\n\n"
            f"约束:\n{constraints}\n\n"
            f"期望产物:\n{expected_text}\n\n"
            "完成后请给出简洁摘要、生成或修改的产物路径、以及需要用户注意的风险。"
        )

    def _collect_artifacts(
        self,
        run_id: str,
        runtime_dir: Path,
        final_output: str = "",
        include_final_output: bool = True,
    ) -> list[dict[str, Any]]:
        task_dir = runtime_dir / "temp" / run_id
        artifacts: list[dict[str, Any]] = []
        if not task_dir.exists():
            return artifacts
        for path in sorted(task_dir.glob("*")):
            if path.is_file() and path.name not in {"input.txt", "_stop"}:
                if path.name == "output.txt":
                    if not include_final_output:
                        continue
                    output_content = final_output or self._extract_final_output(
                        path.read_text(encoding="utf-8", errors="replace")
                    )
                    artifacts.append(
                        {
                            "name": "GenericAgent 最终输出",
                            "path": str(path),
                            "size": path.stat().st_size,
                            "summary": "GenericAgent 的最终回复",
                            "artifact_type": "final_output",
                            "content": output_content[:60000],
                        }
                    )
                    continue
                artifacts.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size": path.stat().st_size,
                        "artifact_type": "file",
                    }
                )
        return artifacts

    def _collect_skill_reviews(
        self, run_id: str, runtime_dir: Path, started_at: str
    ) -> None:
        memory_dir = runtime_dir / "memory"
        if not memory_dir.exists():
            return
        try:
            started_dt = datetime.fromisoformat(started_at)
        except ValueError:
            started_dt = datetime.now()
        for path in memory_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            if path.stat().st_mtime < started_dt.timestamp():
                continue
            lower_name = path.name.lower()
            if not any(token in lower_name for token in ("skill", "sop", "mem")):
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                continue
            review_id = f"gasr_{uuid.uuid4().hex[:12]}"
            title = f"GenericAgent 经验: {path.stem}"
            self.db.insert(
                "generic_agent_skill_reviews",
                {
                    "id": review_id,
                    "run_id": run_id,
                    "title": title[:120],
                    "description": "GenericAgent 在任务完成后更新的记忆/技能文件",
                    "content": content[:20000],
                    "source_path": str(path),
                    "status": "pending",
                    "synced_skill_id": "",
                    "created_at": self._now(),
                    "reviewed_at": None,
                },
            )
            self._insert_event(
                run_id,
                "skill_review",
                "生成待审核技能",
                {"review_id": review_id, "path": str(path)},
            )

    @staticmethod
    def _extract_summary(text: str) -> str:
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", text or "", flags=re.DOTALL)
        cleaned = re.sub(r"<summary>|</summary>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:600] or "GenericAgent 任务已结束"

    @classmethod
    def _classify_final_output_error(cls, text: str) -> str:
        if not cls._is_error_only_final_output(text):
            return ""
        lower = (text or "").lower()
        if "connectionerror" in lower or "apiconnectionerror" in lower:
            return "LLM 连接失败：无法连接到模型服务，请检查 GenericAgent Provider 的 endpoint、网络或代理配置。"
        if "timeout" in lower:
            return "LLM 请求超时：模型服务长时间未响应，请检查网络、代理或 Provider 超时配置。"
        if "http 401" in lower or "unauthorized" in lower:
            return "LLM 认证失败：Provider API Key 无效或权限不足。"
        if "http 403" in lower or "forbidden" in lower:
            return "LLM 访问被拒绝：Provider Key、模型权限或服务区域可能不匹配。"
        if "http 429" in lower or "rate limit" in lower:
            return "LLM 请求被限流：Provider 配额或调用频率已达到限制。"
        if "http 5" in lower:
            return "LLM 服务端错误：Provider 暂时不可用，请稍后重试或切换模型。"
        if "!!!error:" in lower:
            return "LLM 调用失败：GenericAgent 未得到有效模型输出，请检查 Provider 配置。"
        return ""

    @staticmethod
    def _is_error_only_final_output(text: str) -> bool:
        source = text or ""
        if "!!!Error:" not in source and "APIConnectionError" not in source:
            return False
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", source, flags=re.DOTALL)
        cleaned = re.sub(r"<summary>.*?</summary>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\*\*Turn\s+\d+\s+\.\.\.\*\*", "", cleaned)
        cleaned = GENERIC_AGENT_ERROR_RE.sub("", cleaned)
        cleaned = re.sub(r"APIConnectionError|ConnectionError|Timeout", "", cleaned)
        cleaned = cleaned.replace("[Info] Final response to user.", "")
        cleaned = cleaned.replace("[ROUND END]", "")
        cleaned = re.sub(r"`+", "", cleaned)
        cleaned = re.sub(r"\s+", "", cleaned)
        return len(cleaned) < 24

    @staticmethod
    def _extract_final_output(text: str) -> str:
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", text or "", flags=re.DOTALL)
        turns = list(re.finditer(r"\*\*Turn\s+\d+\s+\.\.\.\*\*", cleaned))
        if turns:
            cleaned = cleaned[turns[-1].end() :]
        cleaned = re.sub(r"<summary>.*?</summary>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or (text or "").strip()

    def _insert_event(
        self, run_id: str, event_type: str, title: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "id": f"gae_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "event_type": event_type,
            "title": title,
            "payload": payload,
            "created_at": self._now(),
        }
        self.db.insert("generic_agent_events", row)
        return row

    def _update_run(self, run_id: str, data: dict[str, Any]) -> None:
        update = dict(data)
        update["updated_at"] = self._now()
        self.db.update(
            "generic_agent_runs",
            update,
            where="id = ?",
            where_params=(run_id,),
        )

    def _next_pending_run(self) -> dict[str, Any] | None:
        row = self.db.select_one(
            "generic_agent_runs",
            where="status = ?",
            where_params=("pending",),
        )
        if not row:
            return None
        rows = self.db.select_all(
            "generic_agent_runs",
            where="status = ?",
            where_params=("pending",),
            order_by="created_at ASC",
            limit=1,
        )
        return self._run_dict(rows[0]) if rows else None

    def _pending_count(self) -> int:
        cursor = self.db.execute(
            "SELECT COUNT(*) AS count FROM generic_agent_runs WHERE status = ?",
            ("pending",),
        )
        return int(cursor.fetchone()["count"])

    def _refresh_queue_positions(self) -> None:
        rows = self.db.select_all(
            "generic_agent_runs",
            where="status = ?",
            where_params=("pending",),
            order_by="created_at ASC",
        )
        for idx, row in enumerate(rows, start=1):
            self.db.update(
                "generic_agent_runs",
                {"queue_position": idx, "updated_at": self._now()},
                where="id = ?",
                where_params=(row["id"],),
            )

    def _run_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["expected_outputs"] = self._parse_json(data.get("expected_outputs"), [])
        data["artifacts"] = self._parse_json(data.get("artifacts"), [])
        return data

    def _config_value(self, key: str, fallback: Any) -> Any:
        row = self.db.select_one(
            "generic_agent_config",
            where="key = ?",
            where_params=(key,),
        )
        if not row:
            return fallback
        return self._parse_json(row.get("value"), fallback)

    def _config_updated_at(self, key: str) -> str | None:
        row = self.db.select_one(
            "generic_agent_config",
            where="key = ?",
            where_params=(key,),
        )
        return row.get("updated_at") if row else None

    def _ensure_error_only_history_repaired(self) -> None:
        if self._history_repair_done:
            return
        self._history_repair_done = True
        try:
            self._repair_error_only_completed_runs()
        except Exception as exc:
            logger.warning(f"GenericAgent history repair skipped: {exc}")

    def _repair_error_only_completed_runs(self) -> None:
        rows = self.db.select_all(
            "generic_agent_runs",
            where="status = ?",
            where_params=("completed",),
            order_by="created_at DESC",
            limit=200,
        )
        for row in rows:
            run = self._run_dict(row)
            final_output = self._final_output_from_run_artifacts(run)
            if not final_output:
                final_output = str(run.get("summary") or "")
            error_message = self._classify_final_output_error(final_output)
            if not error_message:
                continue
            artifacts = [
                artifact
                for artifact in run.get("artifacts", [])
                if not self._artifact_is_error_only_final_output(artifact)
            ]
            self._update_run(
                run["id"],
                {
                    "status": "failed",
                    "progress": 0,
                    "summary": "",
                    "artifacts": artifacts,
                    "error": error_message,
                },
            )
            self._insert_event(
                run["id"],
                "failed",
                "历史运行纠偏为失败",
                {
                    "error": error_message,
                    "original_status": "completed",
                    "final_output": final_output[:60000],
                },
            )

    @classmethod
    def _artifact_is_error_only_final_output(cls, artifact: dict[str, Any]) -> bool:
        artifact_type = artifact.get("artifact_type") or artifact.get("type")
        path = str(artifact.get("path") or "")
        is_final = (
            artifact_type == "final_output"
            or artifact.get("name") == "GenericAgent 最终输出"
            or re.search(r"(^|[\\/])output\.txt$", path, re.IGNORECASE)
        )
        return bool(is_final and cls._is_error_only_final_output(str(artifact.get("content") or "")))

    @staticmethod
    def _final_output_from_run_artifacts(run: dict[str, Any]) -> str:
        for artifact in run.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            artifact_type = artifact.get("artifact_type") or artifact.get("type")
            if artifact_type == "final_output" or artifact.get("name") == "GenericAgent 最终输出":
                return str(artifact.get("content") or "")
        return ""

    def _merged_provider_config(self, provider_id: str) -> dict[str, Any]:
        if not provider_id or self.context is None:
            return {}
        provider_config: dict[str, Any] = {}
        if hasattr(self.context, "get_provider_by_id"):
            provider = self.context.get_provider_by_id(provider_id)
            provider_config = getattr(provider, "provider_config", {}) if provider else {}
        if hasattr(self.context, "provider_manager"):
            manager_config = (
                self.context.provider_manager.get_provider_config_by_id(
                    provider_id, merged=True
                )
                or {}
            )
            provider_config = {**manager_config, **provider_config}
        return provider_config

    def _set_config_value(self, key: str, value: Any) -> None:
        now = self._now()
        encoded = json.dumps(value, ensure_ascii=False)
        existing = self.db.select_one(
            "generic_agent_config",
            where="key = ?",
            where_params=(key,),
        )
        if existing:
            self.db.update(
                "generic_agent_config",
                {"value": encoded, "updated_at": now},
                where="key = ?",
                where_params=(key,),
            )
        else:
            self.db.insert(
                "generic_agent_config",
                {"key": key, "value": encoded, "updated_at": now},
            )

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if not value:
            return fallback
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    def _data_root(self) -> Path:
        root = StarTools.get_data_dir("agent_system") / "genericagent"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _default_source_path(self) -> Path:
        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "third_party" / "GenericAgent"
            if candidate.exists():
                return candidate
        return current.parents[5] / "third_party" / "GenericAgent"

    def _runtime_task_dir(self, run_id: str) -> Path:
        return (
            Path(self.get_config()["runtime_path"]).expanduser().resolve()
            / "temp"
            / run_id
        )

    @staticmethod
    def _clean_llm_config(llm_config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(llm_config, dict):
            return {}
        if llm_config.get("provider_id"):
            allowed = {
                "provider_id",
                "model",
                "api_mode",
                "reasoning_effort",
                "temperature",
                "max_tokens",
            }
            cleaned = {
                key: value
                for key, value in llm_config.items()
                if key in allowed and value not in (None, "")
            }
            if "model" in cleaned:
                cleaned["model"] = GenericAgentRuntimeService._scalar_text(
                    cleaned["model"]
                )
            return cleaned
        return llm_config

    def _integration_status(self, config: dict[str, Any]) -> dict[str, Any]:
        source_path = Path(config["source_path"]).expanduser()
        runtime_path = Path(config["runtime_path"]).expanduser()
        llm_config = config.get("llm_config") or {}
        last_llm_error = self._latest_llm_error()
        provider_proxy_configured = self._provider_proxy_configured(llm_config)
        return {
            "source_path": str(source_path),
            "runtime_path": str(runtime_path),
            "source_exists": source_path.exists(),
            "runtime_exists": runtime_path.exists(),
            "source_commit": self._git_commit(source_path),
            "runtime_ready": source_path.exists() and runtime_path.parent.exists(),
            "llm_configured": bool(llm_config),
            "llm_provider_id": llm_config.get("provider_id", ""),
            "llm_model": self._scalar_text(llm_config.get("model", "")),
            "llm_health": self._llm_health(llm_config, last_llm_error),
            "last_llm_error": last_llm_error,
            "provider_proxy_configured": provider_proxy_configured,
            "queue_mode": "single",
        }

    def _latest_llm_error(self) -> str:
        rows = self.db.select_all(
            "generic_agent_runs",
            where="status = ? AND error LIKE ?",
            where_params=("failed", "LLM%"),
            order_by="updated_at DESC",
            limit=1,
        )
        return str(rows[0].get("error") or "") if rows else ""

    def _provider_proxy_configured(self, llm_config: dict[str, Any]) -> bool:
        provider_id = str(llm_config.get("provider_id") or "")
        provider_config = self._merged_provider_config(provider_id)
        proxy = self._first_text(
            llm_config.get("proxy"),
            provider_config.get("proxy"),
            os.environ.get("HTTPS_PROXY"),
            os.environ.get("HTTP_PROXY"),
        )
        return bool(proxy)

    @staticmethod
    def _llm_health(llm_config: dict[str, Any], last_llm_error: str) -> str:
        if not llm_config:
            return "missing"
        if last_llm_error:
            return "unhealthy"
        return "configured"

    @staticmethod
    def _git_commit(path: Path) -> str:
        if not path.exists():
            return ""
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                capture_output=True,
                check=False,
                encoding="utf-8",
                timeout=3,
            )
        except Exception:
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    @staticmethod
    def _looks_like_generic_agent_config(llm_config: dict[str, Any]) -> bool:
        for key in llm_config:
            if key == "api_mode":
                continue
            if any(marker in key for marker in ("config", "cookie")):
                return True
            if key.endswith("_api") or key.startswith(("oai_", "claude_", "sider_")):
                return True
        return False

    @staticmethod
    def _should_record_terminal_line(line: str) -> bool:
        text = line.strip()
        if not text:
            return False
        if text in {"### [WORKING MEMORY]", "<history>", "</history>", "code run output:"}:
            return False
        if re.match(r"^Current turn:\s*\d+", text):
            return False
        noisy_prefixes = (
            "[Debug]",
            "[Cache]",
            "[Cut]",
            "[USER]",
            "[Agent]",
        )
        return not text.startswith(noisy_prefixes)

    @staticmethod
    def _first_text(*values: Any) -> str:
        for value in values:
            text = GenericAgentRuntimeService._scalar_text(value)
            if text:
                return text
        return ""

    @staticmethod
    def _scalar_text(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("value") or value.get("title") or "").strip()
        if isinstance(value, (list, tuple)):
            for item in value:
                text = GenericAgentRuntimeService._scalar_text(item)
                if text:
                    return text
            return ""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _public_config(config: dict[str, Any]) -> dict[str, Any]:
        public = dict(config)
        public["llm_config"] = bool(config.get("llm_config"))
        return public
