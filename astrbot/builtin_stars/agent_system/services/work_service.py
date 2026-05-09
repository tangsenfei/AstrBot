"""Work mode facade service.

This layer keeps the Work UI independent from the lower-level Agent System
screens while still reusing agent_tasks, LangGraph TaskCenter, flows, crews and
the shared HITL interaction manager.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.core import logger

from ..models import TaskStatus, WorkArtifact, WorkDailyDir, WorkProject
from .task_service import TaskService


class WorkService:
    def __init__(self, db, context=None) -> None:
        self.db = db
        self.context = context
        self.task_service = TaskService(db)

    # ------------------------------------------------------------------
    # Projects

    def list_projects(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        where = "1=1" if include_inactive else "status = 'active'"
        rows = self.db.select_all("work_projects", where=where, order_by="updated_at DESC")
        return [self._row_to_project(row).to_dict() for row in rows]

    def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("项目名称不能为空")
        directory = self._normalize_dir(data.get("directory"), ["projects", name])
        goal = str(data.get("goal") or "")
        rules = str(data.get("rules") or "")
        now = datetime.now()
        project_id = data.get("id") or f"wp_{uuid.uuid4().hex[:10]}"

        self._write_project_files(directory, goal, rules)
        row = {
            "id": project_id,
            "name": name,
            "directory": str(directory),
            "goal": goal,
            "rules": rules,
            "status": data.get("status", "active"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self.db.insert("work_projects", row)
        return self._row_to_project(row).to_dict()

    def update_project(self, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self.db.select_one("work_projects", where="id = ?", where_params=(project_id,))
        if not row:
            raise ValueError(f"项目 '{project_id}' 不存在")

        update: dict[str, Any] = {"updated_at": datetime.now().isoformat()}
        for key in ("name", "goal", "rules", "status"):
            if key in data:
                update[key] = data[key]
        if "directory" in data:
            update["directory"] = str(self._normalize_dir(data.get("directory"), ["projects", row["name"]]))

        directory = Path(update.get("directory") or row["directory"])
        goal = str(update.get("goal", row.get("goal", "")) or "")
        rules = str(update.get("rules", row.get("rules", "")) or "")
        self._write_project_files(directory, goal, rules)

        self.db.update("work_projects", update, where="id = ?", where_params=(project_id,))
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        row = self.db.select_one("work_projects", where="id = ?", where_params=(project_id,))
        if not row:
            return False
        self.db.update(
            "work_projects",
            {"status": "archived", "updated_at": datetime.now().isoformat()},
            where="id = ?",
            where_params=(project_id,),
        )
        return True

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.db.select_one("work_projects", where="id = ?", where_params=(project_id,))
        if not row:
            raise ValueError(f"项目 '{project_id}' 不存在")
        return self._row_to_project(row).to_dict()

    # ------------------------------------------------------------------
    # Daily dirs

    def ensure_default_daily_dir(self) -> None:
        rows = self.db.select_all("work_daily_dirs", where="status = 'active'", limit=1)
        if rows:
            return
        self.create_daily_dir({
            "name": "默认日常任务",
            "directory": str(self._default_work_root() / "daily"),
            "default_rules": "用于临时、日常和非项目归属任务。",
        })

    def list_daily_dirs(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        self.ensure_default_daily_dir()
        where = "1=1" if include_inactive else "status = 'active'"
        rows = self.db.select_all("work_daily_dirs", where=where, order_by="updated_at DESC")
        return [self._row_to_daily_dir(row).to_dict() for row in rows]

    def create_daily_dir(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("日常目录名称不能为空")
        directory = self._normalize_dir(data.get("directory"), ["daily", name])
        directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        row = {
            "id": data.get("id") or f"wd_{uuid.uuid4().hex[:10]}",
            "name": name,
            "directory": str(directory),
            "default_rules": str(data.get("default_rules") or ""),
            "status": data.get("status", "active"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self.db.insert("work_daily_dirs", row)
        return self._row_to_daily_dir(row).to_dict()

    def update_daily_dir(self, daily_dir_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self.db.select_one("work_daily_dirs", where="id = ?", where_params=(daily_dir_id,))
        if not row:
            raise ValueError(f"日常目录 '{daily_dir_id}' 不存在")
        update: dict[str, Any] = {"updated_at": datetime.now().isoformat()}
        for key in ("name", "default_rules", "status"):
            if key in data:
                update[key] = data[key]
        if "directory" in data:
            directory = self._normalize_dir(data.get("directory"), ["daily", row["name"]])
            directory.mkdir(parents=True, exist_ok=True)
            update["directory"] = str(directory)
        self.db.update("work_daily_dirs", update, where="id = ?", where_params=(daily_dir_id,))
        updated = self.db.select_one("work_daily_dirs", where="id = ?", where_params=(daily_dir_id,))
        return self._row_to_daily_dir(updated).to_dict()

    def delete_daily_dir(self, daily_dir_id: str) -> bool:
        row = self.db.select_one("work_daily_dirs", where="id = ?", where_params=(daily_dir_id,))
        if not row:
            return False
        self.db.update(
            "work_daily_dirs",
            {"status": "archived", "updated_at": datetime.now().isoformat()},
            where="id = ?",
            where_params=(daily_dir_id,),
        )
        return True

    # ------------------------------------------------------------------
    # Tasks

    def list_tasks(self, filters: dict[str, Any]) -> dict[str, Any]:
        conditions = ["work_scope != ''"]
        params: list[Any] = []
        for key, column in (
            ("status", "status"),
            ("work_scope", "work_scope"),
            ("project_id", "work_project_id"),
            ("daily_dir_id", "work_daily_dir_id"),
            ("work_task_kind", "work_task_kind"),
        ):
            value = filters.get(key)
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)
        q = str(filters.get("q") or "").strip()
        if q:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        page = max(1, int(filters.get("page") or 1))
        page_size = max(1, min(100, int(filters.get("page_size") or 50)))
        include_hitl_cards = str(filters.get("include_hitl_cards") or "").lower() in {"1", "true", "yes"}
        where = " AND ".join(conditions)
        total = self.db.execute(
            f"SELECT COUNT(*) AS count FROM agent_tasks WHERE {where}",
            tuple(params),
        ).fetchone()["count"]
        rows = self.db.execute(
            f"""
            SELECT
                id, name, description, task_type, status, progress, category,
                work_scope, work_project_id, work_daily_dir_id, work_task_kind,
                interaction_id, total_tokens, input_tokens, output_tokens,
                created_at, updated_at, started_at, completed_at
            FROM agent_tasks
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size, (page - 1) * page_size]),
        ).fetchall()
        task_rows = [dict(row) for row in rows]
        hitl_cards_by_task = self._pending_hitl_cards_by_task()
        return {
            "tasks": [
                self._enrich_task_dict(
                    self._row_to_task_summary(row),
                    cards_by_task=hitl_cards_by_task,
                    include_hitl_cards=include_hitl_cards,
                )
                for row in task_rows
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def list_task_summaries(self, task_ids: list[str]) -> list[dict[str, Any]]:
        ids = [str(task_id).strip() for task_id in task_ids if str(task_id).strip()]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.execute(
            f"""
            SELECT
                id, name, description, task_type, status, progress, category,
                work_scope, work_project_id, work_daily_dir_id, work_task_kind,
                interaction_id, total_tokens, input_tokens, output_tokens,
                created_at, updated_at, started_at, completed_at
            FROM agent_tasks
            WHERE id IN ({placeholders})
            """,
            tuple(ids),
        ).fetchall()
        hitl_cards_by_task = self._pending_hitl_cards_by_task()
        by_id = {
            row["id"]: self._enrich_task_dict(
                self._row_to_task_summary(dict(row)),
                cards_by_task=hitl_cards_by_task,
                include_hitl_cards=False,
            )
            for row in rows
        }
        return [by_id[task_id] for task_id in ids if task_id in by_id]

    async def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("任务名称不能为空")
        kind = data.get("work_task_kind") or data.get("task_kind") or "workflow"
        if kind not in ("single_agent", "multi_agent", "workflow"):
            kind = "workflow"

        scope = data.get("work_scope") or ("project" if data.get("work_project_id") else "daily")
        project = self._get_project_row(data.get("work_project_id")) if scope == "project" else None
        daily_dir = self._get_daily_dir_row(data.get("work_daily_dir_id")) if scope == "daily" else None
        if scope == "daily" and not daily_dir:
            self.ensure_default_daily_dir()
            daily_dir = self.db.select_all("work_daily_dirs", where="status = 'active'", limit=1)[0]
        context_pack = self._build_context_pack(project, daily_dir)

        executor_config = dict(data.get("executor_config") or {})
        builtin_flow_id = ""
        flow_id = executor_config.get("flow_id") or data.get("flow_id")
        default_agents: dict[str, str] = {}
        if scope == "daily":
            try:
                from .agent_service import AgentService
                from .flow_service import BUILTIN_DAILY_WORK_FLOW_ID, FlowService
                from .hitl_template_service import HITLTemplateService

                agent_service = AgentService(self.db, self.context)
                agent_service.ensure_work_builtin_agents()
                default_agents = agent_service.get_work_builtin_agent_ids()
                HITLTemplateService(self.db).ensure_builtin_templates()
                FlowService(self.db, self.context).ensure_builtin_daily_work_flow()
                builtin_flow_id = BUILTIN_DAILY_WORK_FLOW_ID
                flow_id = flow_id or BUILTIN_DAILY_WORK_FLOW_ID
            except Exception:
                pass
        flow_definition = self._get_flow_definition(flow_id) if flow_id else {}
        flow_runtime_config = self._extract_work_flow_runtime_config(flow_definition) if flow_definition else {}

        executor_config = {
            **dict(flow_runtime_config.get("executor_config") or {}),
            **executor_config,
        }
        plan_config = {
            "enabled": scope == "daily",
            "effort": "medium",
            "task_mode": "normal",
            **dict(flow_runtime_config.get("plan_config") or {}),
            **dict(data.get("plan_config") or {}),
        }
        valid_task_modes = ("quick", "normal", "deep")
        if plan_config.get("task_mode") not in valid_task_modes:
            plan_config["task_mode"] = "normal"
        review_config = {
            "enabled": False,
            "max_rework": 3,
            **dict(flow_runtime_config.get("review_config") or {}),
            **dict(data.get("review_config") or {}),
        }
        input_data = dict(data.get("input") or {})
        input_data.setdefault("goal", data.get("goal") or data.get("description") or name)
        input_data["work_context"] = context_pack
        executor_config["flow_id"] = flow_id or executor_config.get("flow_id") or ""
        executor_config.setdefault("default_agents", default_agents)
        clarification_config = {
            "enabled": scope == "daily",
            **dict(flow_runtime_config.get("clarification_config") or {}),
            **dict(data.get("clarification_config") or {}),
        }

        graph_type = "work_task"
        task_id = data.get("id") or f"task_{uuid.uuid4().hex[:12]}"
        session_id = data.get("session_id", "work")
        thread_id = data.get("thread_id") or f"{session_id}:{task_id}"

        if not clarification_config.get("content_provider_type") and flow_definition:
            clarification_config.update(self._extract_hitl_node_config(flow_definition, "clarification"))

        if not clarification_config.get("template_id"):
            clarification_config["template_id"] = "builtin_work_requirement_clarification"
        graph_config = {
            "task_id": task_id,
            "thread_id": thread_id,
            "task_name": name,
            "task_desc": data.get("description", ""),
            "planning_enabled": plan_config.get("enabled", False),
            "work_task_kind": kind,
            "executor_config": executor_config,
            "builtin_flow_id": builtin_flow_id,
            "flow_id": flow_id,
            "flow_definition": flow_definition,
            "plan_config": plan_config,
            "task_mode": plan_config.get("task_mode", "normal"),
            "review_config": review_config,
            "clarification_config": clarification_config,
            "input": input_data,
            "provider_id": data.get("provider_id") or executor_config.get("provider_id"),
            "session_id": session_id,
        }

        self.task_service.create_task(
            task_id=task_id,
            name=name,
            description=data.get("description", ""),
            task_type=graph_type,
            crew_id=self._clean_fk(executor_config.get("crew_id")) if kind == "multi_agent" else None,
            flow_id=self._clean_fk(flow_id),
            input_data=input_data,
            category="work",
            thread_id=thread_id,
            work_scope=scope,
            work_project_id=project["id"] if project else None,
            work_daily_dir_id=daily_dir["id"] if daily_dir else None,
            work_task_kind=kind,
            executor_config=executor_config,
            plan_config=plan_config,
            review_config=review_config,
        )
        start_result = await self._start_task_center_task(graph_type, graph_config)
        now = datetime.now().isoformat()
        if start_result.get("started"):
            current = self.db.select_one("agent_tasks", where="id = ?", where_params=(task_id,))
            if not current or current.get("status") != TaskStatus.WAITING_FEEDBACK.value:
                self.db.update(
                    "agent_tasks",
                    {"status": TaskStatus.RUNNING.value, "started_at": now, "updated_at": now},
                    where="id = ?",
                    where_params=(task_id,),
                )
            self._append_log(task_id, "info", "Work 任务已进入执行队列", start_result)
        else:
            error = start_result.get("error") or "TaskCenter 启动失败"
            self.db.update(
                "agent_tasks",
                {"status": TaskStatus.FAILED.value, "error": error, "updated_at": now},
                where="id = ?",
                where_params=(task_id,),
            )
            self._append_log(task_id, "error", "Work 任务启动失败", {"error": error})
        return self.get_task(task_id)

    def get_task(self, task_id: str, logs_limit: int | None = None) -> dict[str, Any]:
        task = self.task_service.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")
        data = task.to_dict()
        data["logs"] = self.get_task_logs(task_id, logs_limit=logs_limit)
        data["subtasks"] = [s.to_dict() for s in self.task_service.get_subtasks(task_id)]
        data["artifacts"] = self.list_artifacts(task_id)
        persisted_steps = self._get_persisted_steps(task_id)
        data["steps"] = self._merge_step_sources(data.get("steps", []), persisted_steps, task_id)
        data["steps_tree"] = self._build_steps_tree(data["steps"])
        data["dependency_edges"] = self._dependency_edges(data["steps"])
        data["timeline"] = self._build_timeline(
            task_id,
            logs=data["logs"],
            steps=data["steps"],
            steps_tree=data["steps_tree"],
            artifacts=data["artifacts"],
        )
        self._repair_completed_status(data)
        return self._enrich_task_dict(data)

    def submit_input(self, task_id: str, text: str) -> dict[str, Any]:
        task = self.task_service.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")
        payload = {
            "text": text,
            "decision": "inject_next_llm_call",
            "created_at": datetime.now().isoformat(),
        }
        pending_input = json.dumps(payload, ensure_ascii=False)
        self.db.update(
            "agent_tasks",
            {
                "pending_input": pending_input,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(task_id,),
        )
        self._append_log(task_id, "info", "人工补充信息已提交", payload)
        return payload

    async def respond_hitl(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        interaction_id = data.get("interaction_id")
        if not interaction_id:
            task = self.task_service.get_task(task_id)
            interaction_id = task.interaction_id if task else ""
        if not interaction_id:
            raise ValueError("缺少 interaction_id")

        from .hitl_service import HITLService

        result = await HITLService(self.db).respond(
            interaction_id,
            data.get("action_key", "approve"),
            data.get("field_values", {}),
        )
        self._append_log(task_id, "info", "HITL 响应已提交", result)
        return result

    def get_task_logs(
        self,
        task_id: str,
        logs_limit: int | None = None,
        *,
        before_seq: int | None = None,
        after_seq: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["task_id = ?"]
        params: list[Any] = [task_id]
        if before_seq:
            conditions.append("rowid < ?")
            params.append(int(before_seq))
        if after_seq:
            conditions.append("rowid > ?")
            params.append(int(after_seq))

        limit_sql = ""
        if logs_limit:
            limit = max(1, min(5000, int(logs_limit)))
            limit_sql = " LIMIT ?"
            params.append(limit)
        rows = self.db.execute(
            f"""
            SELECT rowid AS seq, *
            FROM execution_logs
            WHERE {" AND ".join(conditions)}
            ORDER BY rowid ASC
            {limit_sql}
            """,
            tuple(params),
        ).fetchall()
        logs = []
        for row in rows:
            try:
                row_dict = dict(row)
                log = self.task_service._row_to_execution_log(row_dict).to_dict()
                log["seq"] = row_dict.get("seq")
                logs.append(log)
            except Exception:
                continue
        return logs

    def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.select_all(
            "work_artifacts",
            where="task_id = ?",
            where_params=(task_id,),
            order_by="created_at ASC",
        )
        return [self._row_to_artifact(row).to_dict() for row in rows]

    def _enrich_task_dict(
        self,
        task: dict[str, Any],
        *,
        cards_by_task: dict[str, list[dict[str, Any]]] | None = None,
        include_hitl_cards: bool = True,
    ) -> dict[str, Any]:
        task_id = task.get("id", "")
        hitl_cards = (
            (cards_by_task or {}).get(task_id, [])
            if cards_by_task is not None
            else self._pending_hitl_cards_for_task(task_id)
        )
        task["has_hitl"] = bool(hitl_cards)
        task["hitl_cards"] = hitl_cards if include_hitl_cards else []
        if hitl_cards:
            active = hitl_cards[0]
            task["active_hitl"] = active
            task["hitl_summary"] = {
                "interaction_id": active.get("interaction_id", task.get("interaction_id", "")),
                "title": active.get("title", ""),
                "type": active.get("type", ""),
                "created_at": active.get("created_at"),
            }
            task["interaction_id"] = active.get("interaction_id", task.get("interaction_id", ""))
            task["interaction_title"] = active.get("title", "")
            task["interaction_type"] = active.get("type", "")
            task["status"] = "waiting_feedback"
        else:
            task["active_hitl"] = None
            task["hitl_summary"] = None
        return task

    def _row_to_task_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "name": row.get("name", ""),
            "description": row.get("description", ""),
            "task_type": row.get("task_type", ""),
            "status": self._display_status(row),
            "progress": row.get("progress", 0),
            "category": row.get("category", ""),
            "work_scope": row.get("work_scope", ""),
            "work_project_id": row.get("work_project_id"),
            "work_daily_dir_id": row.get("work_daily_dir_id"),
            "work_task_kind": row.get("work_task_kind", ""),
            "interaction_id": row.get("interaction_id", ""),
            "total_tokens": row.get("total_tokens", 0),
            "input_tokens": row.get("input_tokens", 0),
            "output_tokens": row.get("output_tokens", 0),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
        }

    def _display_status(self, task: dict[str, Any]) -> str:
        status = task.get("status", "pending")
        if status == TaskStatus.RUNNING.value and int(task.get("progress") or 0) >= 100:
            return TaskStatus.COMPLETED.value
        return status

    def _repair_completed_status(self, task: dict[str, Any]) -> None:
        if task.get("status") != TaskStatus.RUNNING.value or int(task.get("progress") or 0) < 100:
            return
        task["status"] = TaskStatus.COMPLETED.value
        now = datetime.now().isoformat()
        task["completed_at"] = task.get("completed_at") or now
        try:
            self.db.update(
                "agent_tasks",
                {"status": TaskStatus.COMPLETED.value, "completed_at": task["completed_at"], "updated_at": now},
                where="id = ?",
                where_params=(task.get("id"),),
            )
        except Exception:
            pass

    def _pending_hitl_cards_by_task(self) -> dict[str, list[dict[str, Any]]]:
        from .hitl_service import HITLService

        cards_by_task: dict[str, list[dict[str, Any]]] = {}
        for card in HITLService(self.db).list_pending():
            task_id = card.get("task_id")
            if task_id:
                cards_by_task.setdefault(task_id, []).append(card)
        try:
            from astrbot.core.langgraph.interaction_manager import (
                get_interaction_manager,
            )

            for state in get_interaction_manager().get_pending_interactions():
                card = state.card.to_dict()
                task_id = card.get("meta", {}).get("task_id") or state.thread_id
                if not task_id:
                    continue
                if any(existing.get("interaction_id") == card.get("interaction_id") for existing in cards_by_task.get(task_id, [])):
                    continue
                card["thread_id"] = state.thread_id
                card["task_id"] = task_id
                card["channel"] = state.channel
                cards_by_task.setdefault(task_id, []).append(card)
        except Exception:
            pass
        return cards_by_task

    def _pending_hitl_cards_for_task(self, task_id: str) -> list[dict[str, Any]]:
        if not task_id:
            return []
        from .hitl_service import HITLService

        cards = HITLService(self.db).list_pending(task_id)
        try:
            from astrbot.core.langgraph.interaction_manager import (
                get_interaction_manager,
            )

            for state in get_interaction_manager().get_pending_interactions():
                card = state.card.to_dict()
                card_task_id = card.get("meta", {}).get("task_id") or state.thread_id
                if card_task_id != task_id:
                    continue
                if any(existing.get("interaction_id") == card.get("interaction_id") for existing in cards):
                    continue
                card["thread_id"] = state.thread_id
                card["task_id"] = task_id
                card["channel"] = state.channel
                cards.append(card)
        except Exception:
            pass
        return cards

    def _build_steps_tree(self, raw_steps: Any) -> list[dict[str, Any]]:
        steps = raw_steps
        if isinstance(raw_steps, str):
            try:
                steps = json.loads(raw_steps)
            except json.JSONDecodeError:
                steps = []
        if not isinstance(steps, list):
            steps = []
        normalized: list[dict[str, Any]] = []

        def collect(items: list[Any], parent_id: str | None = None) -> None:
            for item in items:
                index = len(normalized)
                source = dict(item) if isinstance(item, dict) else {"description": str(item)}
                children = source.pop("children", [])
                source_parent = source.get("parent_id") or source.get("parent")
                if parent_id and (
                    not source_parent
                    or str(source_parent).split(":")[-1] == str(parent_id).split(":")[-1]
                ):
                    source["parent_id"] = parent_id
                if parent_id:
                    source["depth"] = 2
                step = self._normalize_step(source, index)
                normalized.append(step)
                if isinstance(children, list):
                    collect(children, step["id"])

        collect(steps)
        by_id: dict[str, dict[str, Any]] = {}
        for step in normalized:
            existing = by_id.get(step["id"])
            if existing:
                existing.update({k: v for k, v in step.items() if v not in (None, "", [])})
            else:
                by_id[step["id"]] = step
        normalized = list(by_id.values())
        by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for step in normalized:
            parent = step.get("parent_id") or None
            by_parent.setdefault(parent, []).append(step)
        for step in normalized:
            children = by_parent.get(step["id"], [])
            step["children"] = sorted(children, key=lambda item: item.get("sort_order", 0))[:20]
        return sorted(by_parent.get(None, []), key=lambda item: item.get("sort_order", 0))

    def _get_persisted_steps(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.select_all(
            "work_task_steps",
            where="task_id = ?",
            where_params=(task_id,),
            order_by="depth ASC, sort_order ASC",
        )
        steps = []
        for index, row in enumerate(rows):
            step = {
                "id": row.get("id"),
                "parent_id": row.get("parent_id"),
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "status": row.get("status", "pending"),
                "dependencies": self._parse_json(row.get("dependencies", "[]"), []),
                "executor": row.get("executor", ""),
                "executor_type": row.get("executor_type", ""),
                "executor_id": row.get("executor_id", ""),
                "reviewer_id": row.get("reviewer_id", ""),
                "result": row.get("result", ""),
                "result_ref": row.get("result_ref", ""),
                "depth": row.get("depth", 1),
                "sort_order": row.get("sort_order", index),
                "started_at": row.get("started_at"),
                "completed_at": row.get("completed_at"),
                "updated_at": row.get("updated_at"),
            }
            steps.append(self._normalize_step(step, index))
        return steps

    def _dependency_edges(self, raw_steps: Any) -> list[dict[str, str]]:
        steps = raw_steps if isinstance(raw_steps, list) else []
        edges = []
        def visit(step: Any) -> None:
            if not isinstance(step, dict):
                return
            target = str(step.get("id") or "")
            for source in step.get("dependencies") or step.get("depends_on") or []:
                if source and target:
                    edges.append({"source": str(source), "target": target})
            for child in step.get("children") or []:
                visit(child)
        for step in steps:
            visit(step)
        return edges

    def _merge_step_sources(
        self,
        raw_steps: Any,
        persisted_steps: list[dict[str, Any]],
        task_id: str,
    ) -> list[dict[str, Any]]:
        raw = self._parse_json(raw_steps, []) if isinstance(raw_steps, str) else raw_steps
        raw = raw if isinstance(raw, list) else []
        if not persisted_steps:
            return raw
        if not raw:
            return persisted_steps

        persisted_by_key: dict[str, dict[str, Any]] = {}
        for step in persisted_steps:
            step_id = str(step.get("id") or "")
            if not step_id:
                continue
            persisted_by_key[step_id] = step
            if step_id.startswith(f"{task_id}:"):
                persisted_by_key[step_id[len(task_id) + 1:]] = step

        seen: set[str] = set()

        def overlay(item: Any) -> dict[str, Any]:
            source = dict(item) if isinstance(item, dict) else {"description": str(item)}
            children = source.get("children", [])
            step_id = str(source.get("id") or "")
            persisted = persisted_by_key.get(step_id) or persisted_by_key.get(f"{task_id}:{step_id}")
            if persisted:
                seen.add(str(persisted.get("id") or ""))
                seen.add(str(persisted.get("id") or "").removeprefix(f"{task_id}:"))
                merged = {**source, **{k: v for k, v in persisted.items() if v not in (None, "", [])}}
                if children:
                    merged["children"] = [overlay(child) for child in children]
                return merged
            if children:
                source["children"] = [overlay(child) for child in children]
            return source

        merged = [overlay(step) for step in raw]
        raw_has_children = self._nested_step_count(raw) > len(raw)
        for step in persisted_steps:
            step_id = str(step.get("id") or "")
            short_id = step_id.removeprefix(f"{task_id}:")
            if step_id in seen or short_id in seen:
                continue
            if raw_has_children and short_id.startswith("step_"):
                continue
            merged.append(step)
        return merged

    def _nested_step_count(self, steps: Any) -> int:
        if isinstance(steps, str):
            steps = self._parse_json(steps, [])
        if not isinstance(steps, list):
            return 0
        total = 0
        for item in steps:
            total += 1
            if isinstance(item, dict):
                total += self._nested_step_count(item.get("children", []))
        return total

    @staticmethod
    def _normalize_step(step: Any, index: int) -> dict[str, Any]:
        source = step if isinstance(step, dict) else {"description": str(step)}
        step_id = str(source.get("id") or f"step_{index + 1}")
        dependencies = source.get("dependencies")
        if dependencies is None:
            dependencies = source.get("depends_on") or ([] if index == 0 or source.get("parent_id") else [f"step_{index}"])
        if not isinstance(dependencies, list):
            dependencies = [dependencies] if dependencies else []
        title = source.get("title") or source.get("name") or source.get("description") or f"步骤 {index + 1}"
        return {
            "id": step_id,
            "parent_id": source.get("parent_id") or source.get("parent"),
            "title": title,
            "description": source.get("description") or title,
            "status": source.get("status", "pending"),
            "dependencies": [str(dep) for dep in dependencies if dep],
            "executor": source.get("executor") or source.get("agent") or "",
            "executor_type": source.get("executor_type", ""),
            "executor_id": source.get("executor_id", ""),
            "reviewer_id": source.get("reviewer_id", ""),
            "result": source.get("result", ""),
            "result_ref": source.get("result_ref", ""),
            "depth": min(2, int(source.get("depth") or (2 if source.get("parent_id") else 1))),
            "sort_order": int(source.get("sort_order") or index),
            "stats": source.get("stats", {}),
            "error": source.get("error", ""),
            "started_at": source.get("started_at"),
            "completed_at": source.get("completed_at"),
            "updated_at": source.get("updated_at"),
        }

    def _build_timeline(
        self,
        task_id: str,
        *,
        logs: list[dict[str, Any]],
        steps: list[dict[str, Any]],
        steps_tree: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        flat_steps = self._flatten_steps_for_timeline(steps_tree or steps)
        stage_steps = [step for step in flat_steps if self._is_stage_id(step.get("id"))]
        execution_roots = [step for step in (steps_tree or []) if not self._is_stage_id(step.get("id"))]

        stage_defaults = [
            ("stage_clarify", "需求明确", "确认任务目标、交付形式和完成标准"),
            ("stage_plan", "规划", "生成最多二级任务树和依赖关系"),
            ("stage_assign", "分配", "分配执行智能体"),
            ("stage_execute", "执行", "按前置依赖顺序执行任务"),
            ("stage_review", "审查", "审查任务结果是否达标"),
            ("stage_deliver", "交付", "生成最终交付物"),
        ]
        stage_by_short = {self._short_timeline_id(step.get("id"), task_id): step for step in stage_steps}
        stages: list[dict[str, Any]] = []
        for order, (stage_id, title, description) in enumerate(stage_defaults):
            source = stage_by_short.get(stage_id, {})
            if stage_id == "stage_review" and not source and not any(self._event_stage_id(log, task_id) == stage_id for log in logs):
                continue
            stages.append({
                "id": stage_id,
                "title": source.get("title") or title,
                "description": source.get("description") or description,
                "status": source.get("status", "pending"),
                "sort_order": source.get("sort_order", order),
                "agent": self._timeline_agent(source),
                "entered_at": source.get("started_at"),
                "completed_at": source.get("completed_at"),
                "_completed_from_step": bool(source.get("completed_at")),
                "_last_event_at": None,
                "duration_ms": self._duration_ms(source.get("started_at"), source.get("completed_at")),
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "events": [],
            })

        stage_map = {stage["id"]: stage for stage in stages}
        current_stage = stages[0]["id"] if stages else "unclassified"
        unclassified = {
            "id": "unclassified",
            "title": "未归类日志",
            "description": "旧任务或缺少 trace 元数据的事件",
            "status": "done" if logs else "pending",
            "sort_order": 999,
            "agent": {},
            "entered_at": None,
            "completed_at": None,
            "_completed_from_step": False,
            "_last_event_at": None,
            "duration_ms": None,
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "events": [],
        }
        step_events: dict[str, list[dict[str, Any]]] = {}

        for index, log in enumerate(logs):
            event = self._timeline_event(log, index, task_id)
            stage_id = event.get("stage_id") or current_stage
            if stage_id not in stage_map:
                stage_id = self._phase_to_stage((log.get("data") or {}).get("phase")) or stage_id
            if stage_id in stage_map:
                current_stage = stage_id
                stage = stage_map[stage_id]
            else:
                stage = unclassified
            event["stage_id"] = stage["id"]
            stage["events"].append(event)
            self._merge_event_bounds(stage, event)
            self._merge_event_agent(stage, event)
            self._merge_event_tokens(stage, event)

            step_id = self._short_timeline_id(event.get("step_id"), task_id)
            if step_id:
                step_events.setdefault(step_id, []).append(event)

        for artifact in artifacts:
            event = {
                "id": artifact.get("id", ""),
                "kind": "artifact",
                "title": artifact.get("title") or "任务交付物",
                "content": artifact.get("content", ""),
                "created_at": artifact.get("created_at"),
                "stage_id": "stage_deliver",
                "step_id": "",
                "agent": {},
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "raw": artifact,
            }
            stage = stage_map.get("stage_deliver")
            if stage and not any(item.get("id") == event["id"] for item in stage["events"]):
                stage["events"].append(event)
                self._merge_event_bounds(stage, event)

        for stage in stages:
            if not stage.get("completed_at") and stage.get("_last_event_at"):
                stage["completed_at"] = stage["_last_event_at"]
            if not stage.get("duration_ms"):
                stage["duration_ms"] = self._duration_ms(stage.get("entered_at"), stage.get("completed_at"))
            if stage["events"] and not stage.get("completed_at") and stage.get("status") in {"done", "completed", "failed", "cancelled"}:
                stage["completed_at"] = stage["events"][-1].get("created_at")
                stage["duration_ms"] = self._duration_ms(stage.get("entered_at"), stage.get("completed_at"))
            stage.pop("_completed_from_step", None)
            stage.pop("_last_event_at", None)
        if unclassified["events"]:
            unclassified.pop("_completed_from_step", None)
            unclassified.pop("_last_event_at", None)
            stages.append(unclassified)

        return {
            "stages": stages,
            "execution_graph": [
                self._timeline_execution_node(node, task_id, step_events)
                for node in execution_roots
            ],
            "unclassified_events": unclassified["events"],
        }

    def _timeline_event(self, log: dict[str, Any], index: int, task_id: str) -> dict[str, Any]:
        data = log.get("data") or {}
        event_type = data.get("event") or "log"
        kind = "hitl_call" if event_type == "interaction" else "hitl_result" if event_type == "hitl_resolved" else event_type
        title = self._timeline_event_title(kind, log, data)
        content = data.get("text") or data.get("result") or data.get("output") or data.get("message") or log.get("message") or ""
        token_usage = self._timeline_token_usage(data) if event_type == "token" else {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        return {
            "id": log.get("id") or f"log-{index}",
            "seq": log.get("seq"),
            "kind": kind,
            "event": event_type,
            "title": title,
            "content": content,
            "created_at": log.get("created_at"),
            "stage_id": self._event_stage_id(log, task_id),
            "step_id": self._short_timeline_id(data.get("step_id"), task_id),
            "agent": {"id": data.get("agent_id") or log.get("agent_id") or "", "label": data.get("agent_label") or ""},
            "tool_call_id": data.get("tool_call_id") or data.get("id") or "",
            "token_usage": token_usage,
            "raw": log,
        }

    def _event_stage_id(self, log: dict[str, Any], task_id: str) -> str:
        data = log.get("data") or {}
        explicit = self._short_timeline_id(data.get("stage_id"), task_id)
        if explicit:
            return explicit
        return self._phase_to_stage(data.get("phase")) or self._phase_to_stage(data.get("node_id")) or ""

    @staticmethod
    def _phase_to_stage(value: Any) -> str:
        phase = str(value or "")
        mapping = {
            "prepare": "stage_clarify",
            "clarification": "stage_clarify",
            "clarification_done": "stage_clarify",
            "clarification_more": "stage_clarify",
            "plan": "stage_plan",
            "plan_done": "stage_plan",
            "plan_approved": "stage_plan",
            "plan_revision_requested": "stage_plan",
            "assign": "stage_assign",
            "assign_done": "stage_assign",
            "execute": "stage_execute",
            "step_done": "stage_execute",
            "review": "stage_review",
            "review_done": "stage_review",
            "rework_planned": "stage_review",
            "finalize": "stage_deliver",
            "completed": "stage_deliver",
        }
        return mapping.get(phase, "")

    @staticmethod
    def _timeline_event_title(kind: str, log: dict[str, Any], data: dict[str, Any]) -> str:
        if kind == "tool_call":
            return f"调用工具：{data.get('name') or data.get('tool') or 'tool'}"
        if kind == "tool_result":
            return f"工具结果：{data.get('name') or data.get('tool') or 'tool'}"
        if kind == "hitl_call":
            return data.get("title") or "发起人工确认"
        if kind == "hitl_result":
            return f"人工已处理：{data.get('action_key') or ''}".strip()
        if kind == "token":
            return "Token 消耗"
        if kind == "text_delta":
            return data.get("agent_label") or "Agent 输出"
        if kind == "reasoning":
            return data.get("agent_label") or "Agent 思考"
        if kind == "artifact":
            return data.get("title") or "交付物"
        if kind == "phase":
            return data.get("label") or data.get("phase") or "阶段更新"
        return data.get("label") or log.get("message") or kind

    @staticmethod
    def _timeline_token_usage(data: dict[str, Any]) -> dict[str, int]:
        stats = data.get("stats", {}) if isinstance(data, dict) else {}
        usage = stats.get("token_usage", {}) if isinstance(stats, dict) else {}
        input_tokens = int(data.get("input_tokens") or data.get("input") or usage.get("input_other") or usage.get("input") or 0)
        output_tokens = int(data.get("output_tokens") or data.get("output") or usage.get("output") or 0)
        total_tokens = int(data.get("total_tokens") or data.get("total") or usage.get("total") or input_tokens + output_tokens)
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}

    def _timeline_execution_node(
        self,
        step: dict[str, Any],
        task_id: str,
        step_events: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        short_id = self._short_timeline_id(step.get("id"), task_id)
        events = step_events.get(short_id, [])
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for event in events:
            self._add_tokens(token_usage, event.get("token_usage") or {})
        agent = self._timeline_agent(step)
        for event in events:
            agent = self._merged_agent(agent, event.get("agent") or {})
        node = {
            "id": short_id or step.get("id", ""),
            "title": step.get("title") or step.get("description") or step.get("name") or short_id,
            "description": step.get("description") or step.get("title") or "",
            "status": step.get("status", "pending"),
            "dependencies": [self._short_timeline_id(dep, task_id) for dep in (step.get("dependencies") or [])],
            "agent": agent,
            "entered_at": step.get("started_at") or (events[0].get("created_at") if events else None),
            "completed_at": step.get("completed_at") or (events[-1].get("created_at") if events and step.get("status") in {"done", "completed", "failed", "cancelled"} else None),
            "duration_ms": self._duration_ms(step.get("started_at"), step.get("completed_at")),
            "result": step.get("result", ""),
            "result_ref": step.get("result_ref", ""),
            "token_usage": token_usage or step.get("stats", {}),
            "events": events,
            "children": [],
        }
        node["duration_ms"] = node["duration_ms"] or self._duration_ms(node.get("entered_at"), node.get("completed_at"))
        node["children"] = [
            self._timeline_execution_node(child, task_id, step_events)
            for child in (step.get("children") or [])
            if not self._is_stage_id(child.get("id"))
        ]
        return node

    @staticmethod
    def _timeline_agent(source: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(source.get("executor_id") or source.get("agent_id") or source.get("agent") or ""),
            "label": str(source.get("agent_label") or source.get("executor") or source.get("agent") or ""),
            "type": str(source.get("executor_type") or "agent"),
        }

    @staticmethod
    def _flatten_steps_for_timeline(steps: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        def visit(items: Any) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                result.append(item)
                visit(item.get("children"))
        visit(steps)
        return result

    @staticmethod
    def _short_timeline_id(value: Any, task_id: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        prefix = f"{task_id}:"
        return raw[len(prefix):] if raw.startswith(prefix) else raw

    def _is_stage_id(self, value: Any) -> bool:
        return self._short_timeline_id(value, "").startswith("stage_") or ":stage_" in str(value or "")

    @staticmethod
    def _duration_ms(start: Any, end: Any) -> int | None:
        if not start or not end:
            return None
        try:
            start_dt = datetime.fromisoformat(str(start))
            end_dt = datetime.fromisoformat(str(end))
        except (TypeError, ValueError):
            return None
        return max(0, int((end_dt - start_dt).total_seconds() * 1000))

    @staticmethod
    def _merge_event_bounds(stage: dict[str, Any], event: dict[str, Any]) -> None:
        created_at = event.get("created_at")
        if not created_at:
            return
        if not stage.get("entered_at") or str(created_at) < str(stage.get("entered_at")):
            stage["entered_at"] = created_at
        if not stage.get("_last_event_at") or str(created_at) > str(stage.get("_last_event_at")):
            stage["_last_event_at"] = created_at
        if not stage.get("_completed_from_step") and (
            not stage.get("completed_at") or str(created_at) > str(stage.get("completed_at"))
        ):
            stage["completed_at"] = created_at

    @staticmethod
    def _merge_event_agent(stage: dict[str, Any], event: dict[str, Any]) -> None:
        stage["agent"] = WorkService._merged_agent(stage.get("agent") or {}, event.get("agent") or {})

    @staticmethod
    def _merged_agent(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, str]:
        current_id = str(current.get("id") or "")
        current_label = str(current.get("label") or "")
        incoming_id = str(incoming.get("id") or "")
        incoming_label = str(incoming.get("label") or "")
        return {
            "id": current_id or incoming_id,
            "label": incoming_label or current_label,
            "type": str(current.get("type") or incoming.get("type") or "agent"),
        }

    def _merge_event_tokens(self, stage: dict[str, Any], event: dict[str, Any]) -> None:
        self._add_tokens(stage["token_usage"], event.get("token_usage") or {})

    @staticmethod
    def _add_tokens(target: dict[str, int], source: dict[str, Any]) -> None:
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            target[key] = int(target.get(key) or 0) + int(source.get(key) or 0)

    # ------------------------------------------------------------------
    # Helpers

    async def _start_task_center_task(self, graph_type: str, graph_config: dict[str, Any]) -> dict[str, Any]:
        try:
            from astrbot.core.langgraph.state import GraphRunContext
            from astrbot.core.langgraph.task_tools import get_task_center

            tc = get_task_center()
            if tc is None:
                raise RuntimeError("TaskCenter not initialized")
            provider = self._resolve_provider(graph_config.get("provider_id"))
            run_ctx = GraphRunContext(
                provider=provider,
                tool_executor=None,
                hooks=None,
                astr_event=None,
                config={"streaming_response": True},
            )
            record = await tc.create_task(
                task_type=graph_type,
                config=graph_config,
                session_id=graph_config.get("thread_id", "work"),
                run_ctx=run_ctx,
            )
            return {"started": True, "task_id": record.task_id, "thread_id": record.thread_id}
        except Exception as e:
            logger.warning(f"Work task failed to start TaskCenter execution: {e}", exc_info=True)
            return {"started": False, "error": str(e)}

    def _resolve_provider(self, provider_id: str | None):
        if self.context is None:
            return None
        if provider_id and hasattr(self.context, "get_provider_by_id"):
            provider = self.context.get_provider_by_id(provider_id)
            if provider is not None:
                return provider
        if hasattr(self.context, "get_using_provider"):
            return self.context.get_using_provider(None)
        return None

    @staticmethod
    def _clean_fk(value: Any) -> str | None:
        value = str(value or "").strip()
        return value or None

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    def _get_project_row(self, project_id: str | None) -> dict[str, Any] | None:
        if not project_id:
            return None
        return self.db.select_one("work_projects", where="id = ? AND status = 'active'", where_params=(project_id,))

    def _get_daily_dir_row(self, daily_dir_id: str | None) -> dict[str, Any] | None:
        if not daily_dir_id:
            return None
        return self.db.select_one("work_daily_dirs", where="id = ? AND status = 'active'", where_params=(daily_dir_id,))

    def _build_context_pack(
        self,
        project: dict[str, Any] | None,
        daily_dir: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if project:
            directory = Path(project["directory"])
            file_rules = self._read_text(directory / ".nicebot" / "rules.md")
            file_goal = self._read_text(directory / ".nicebot" / "goal.md")
            return {
                "scope": "project",
                "project_id": project["id"],
                "directory": str(directory),
                "goal": project.get("goal") or file_goal,
                "rules": "\n\n".join(x for x in [project.get("rules", ""), file_rules] if x),
            }
        if daily_dir:
            return {
                "scope": "daily",
                "daily_dir_id": daily_dir["id"],
                "directory": daily_dir["directory"],
                "rules": daily_dir.get("default_rules", ""),
            }
        return {"scope": "daily", "directory": str(self._default_work_root() / "daily")}

    def _get_flow_definition(self, flow_id: str) -> dict[str, Any]:
        from .flow_service import FlowService

        service = FlowService(self.db, self.context)
        flow = service.get_flow(flow_id)
        if not flow:
            raise ValueError(f"流程 '{flow_id}' 不存在")
        return service._flow_to_definition(flow)

    def _extract_hitl_node_config(self, flow_definition: dict[str, Any], builtin_stage: str) -> dict[str, Any]:
        nodes = flow_definition.get("nodes", [])
        for node in nodes:
            config = node.get("config", {}) or {}
            if config.get("builtin_stage") == builtin_stage and node.get("type") == "hitl":
                result = {}
                for key in ("content_provider_type", "content_provider_agent_id", "template_id", "repeat_until_clear", "content_payload"):
                    if key in config:
                        result[key] = config[key]
                return result
        return {}

    def _extract_work_flow_runtime_config(self, flow_definition: dict[str, Any]) -> dict[str, dict[str, Any]]:
        nodes = flow_definition.get("nodes", []) if isinstance(flow_definition, dict) else []

        def config_for(stage: str) -> dict[str, Any]:
            for node in nodes:
                config = node.get("config", {}) or {}
                if isinstance(config, dict) and config.get("builtin_stage") == stage:
                    return config
            return {}

        result: dict[str, dict[str, Any]] = {
            "clarification_config": {},
            "plan_config": {},
            "executor_config": {},
            "review_config": {},
        }

        clarify = config_for("clarification")
        for key in (
            "content_provider_type",
            "content_provider_agent_id",
            "template_id",
            "repeat_until_clear",
            "content_payload",
            "content_system_prompt",
            "content_prompt",
        ):
            if key in clarify:
                result["clarification_config"][key] = clarify[key]

        mode_strategy = config_for("task_mode_strategy")
        modes = mode_strategy.get("modes") if isinstance(mode_strategy, dict) else None
        if isinstance(modes, dict):
            result["plan_config"]["modes"] = modes
        if mode_strategy.get("default_mode"):
            result["plan_config"]["task_mode"] = mode_strategy["default_mode"]

        plan = config_for("plan")
        if plan.get("agent_id"):
            result["plan_config"]["agent_id"] = plan["agent_id"]
            result["executor_config"]["assistant_agent_id"] = plan["agent_id"]
        for source, target in (
            ("system_prompt", "system_prompt"),
            ("prompt", "prompt_template"),
            ("max_depth", "max_depth"),
            ("output", "output"),
        ):
            if source in plan:
                result["plan_config"][target] = plan[source]

        approval = config_for("plan_hitl")
        if approval.get("template_id"):
            result["plan_config"]["approval_template_id"] = approval["template_id"]
        if "body_template" in approval:
            result["plan_config"]["approval_body_template"] = approval["body_template"]
        if "default_enabled" in approval:
            result["plan_config"]["enabled"] = bool(approval.get("default_enabled"))

        execute = config_for("execute_dag")
        if execute.get("default_agent_id"):
            result["executor_config"]["executor_agent_id"] = execute["default_agent_id"]
        if execute.get("assigner_agent_id"):
            result["executor_config"]["assistant_agent_id"] = execute["assigner_agent_id"]
        if execute.get("research_agent_id"):
            result["executor_config"]["researcher_agent_id"] = execute["research_agent_id"]
        for source, target in (
            ("system_prompt", "execute_system_prompt"),
            ("prompt", "execute_prompt_template"),
            ("assignment_system_prompt", "assignment_system_prompt"),
            ("assignment_prompt", "assignment_prompt_template"),
        ):
            if source in execute:
                result["executor_config"][target] = execute[source]

        review = config_for("review")
        if review.get("reviewer_id"):
            result["executor_config"]["reviewer_agent_id"] = review["reviewer_id"]
            result["review_config"]["reviewer_id"] = review["reviewer_id"]
        if "default_enabled" in review:
            result["review_config"]["enabled"] = bool(review.get("default_enabled"))
        if review.get("default_max_rework") is not None:
            result["review_config"]["max_rework"] = review.get("default_max_rework")
        for source, target in (
            ("system_prompt", "system_prompt"),
            ("prompt", "prompt_template"),
        ):
            if source in review:
                result["review_config"][target] = review[source]

        rework = config_for("rework_hitl")
        for source, target in (
            ("template_id", "rework_template_id"),
            ("title", "rework_title"),
            ("body", "rework_body"),
        ):
            if source in rework:
                result["review_config"][target] = rework[source]

        deliver = config_for("deliverable")
        if deliver.get("assistant_id"):
            result["executor_config"].setdefault("assistant_agent_id", deliver["assistant_id"])
        if deliver.get("reporter_id"):
            result["executor_config"]["reporter_agent_id"] = deliver["reporter_id"]
        if deliver.get("artifact_type"):
            result["executor_config"]["artifact_type"] = deliver["artifact_type"]
        for source, target in (
            ("system_prompt", "finalize_system_prompt"),
            ("prompt", "finalize_prompt_template"),
        ):
            if source in deliver:
                result["executor_config"][target] = deliver[source]

        return result

    def _append_log(
        self,
        task_id: str,
        level: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.db.insert(
            "execution_logs",
            {
                "id": f"log_{uuid.uuid4().hex[:12]}",
                "task_id": task_id,
                "sub_task_id": None,
                "agent_id": None,
                "level": level,
                "message": message,
                "data": data or {},
                "created_at": datetime.now().isoformat(),
            },
        )

    def _default_work_root(self) -> Path:
        return Path(self.db.db_path).parent / "workspaces"

    def _normalize_dir(self, value: Any, fallback_parts: list[str]) -> Path:
        path = Path(str(value or "")).expanduser() if value else self._default_work_root().joinpath(*fallback_parts)
        if not path.is_absolute():
            path = self._default_work_root() / path
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def _write_project_files(self, directory: Path, goal: str, rules: str) -> None:
        nicebot_dir = directory / ".nicebot"
        nicebot_dir.mkdir(parents=True, exist_ok=True)
        (nicebot_dir / "goal.md").write_text(goal or "# 项目目标\n\n", encoding="utf-8")
        (nicebot_dir / "rules.md").write_text(rules or "# 项目规则\n\n", encoding="utf-8")

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _row_to_project(self, row: dict[str, Any]) -> WorkProject:
        return WorkProject(
            id=row["id"],
            name=row["name"],
            directory=row["directory"],
            goal=row.get("goal", ""),
            rules=row.get("rules", ""),
            status=row.get("status", "active"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_daily_dir(self, row: dict[str, Any]) -> WorkDailyDir:
        return WorkDailyDir(
            id=row["id"],
            name=row["name"],
            directory=row["directory"],
            default_rules=row.get("default_rules", ""),
            status=row.get("status", "active"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_artifact(self, row: dict[str, Any]) -> WorkArtifact:
        metadata = row.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        return WorkArtifact(
            id=row["id"],
            task_id=row["task_id"],
            title=row["title"],
            artifact_type=row.get("artifact_type", "markdown"),
            content=row.get("content", ""),
            file_path=row.get("file_path", ""),
            metadata=metadata,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
