"""Work mode facade service.

This layer keeps the Work UI independent from the lower-level Agent System
screens while still reusing agent_tasks, LangGraph TaskCenter, flows, crews and
the shared HITL interaction manager.
"""
from __future__ import annotations

import json
import time
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
                from .flow_service import BUILTIN_DAILY_WORK_FLOW_ID, FlowService
                from .agent_service import AgentService
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
        plan_config = {"enabled": scope == "daily", "effort": "medium", "task_mode": "normal", **dict(data.get("plan_config") or {})}
        valid_task_modes = ("quick", "normal", "deep")
        if plan_config.get("task_mode") not in valid_task_modes:
            plan_config["task_mode"] = "normal"
        review_config = {"enabled": False, "max_rework": 3, **dict(data.get("review_config") or {})}
        input_data = dict(data.get("input") or {})
        input_data.setdefault("goal", data.get("goal") or data.get("description") or name)
        input_data["work_context"] = context_pack
        executor_config["flow_id"] = flow_id or executor_config.get("flow_id") or ""
        executor_config.setdefault("default_agents", default_agents)
        clarification_config = {"enabled": scope == "daily", **dict(data.get("clarification_config") or {})}

        graph_type = "work_task"
        task_id = data.get("id") or f"task_{uuid.uuid4().hex[:12]}"
        session_id = data.get("session_id", "work")
        thread_id = data.get("thread_id") or f"{session_id}:{task_id}"
        flow_definition = self._get_flow_definition(flow_id) if flow_id else {}

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

        task = self.task_service.create_task(
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
        data["steps"] = persisted_steps or data.get("steps", [])
        data["steps_tree"] = self._build_steps_tree(data["steps"])
        data["dependency_edges"] = self._dependency_edges(data["steps"])
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

    async def resume_hitl_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """唤醒因 HITL 超时而挂起的任务（用户重新提交响应）。"""
        task = self.task_service.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")

        from astrbot.core.langgraph.task_tools import get_task_center
        from astrbot.core.langgraph.interaction import InteractionResponse

        tc = get_task_center()
        record = tc.get_task(task_id)
        if not record:
            raise ValueError("任务执行器未找到")

        # 构造 InteractionResponse 作为 resume_value
        response = InteractionResponse(
            interaction_id=data.get("interaction_id", task.interaction_id or ""),
            action_key=data.get("action_key", "confirm"),
            field_values=data.get("field_values", {}),
            responded_at=time.time(),
        )

        await tc.resume_task(task_id, response)
        self._append_log(task_id, "info", "HITL 超时任务已唤醒并恢复执行", {"action_key": response.action_key})
        return {"resumed": True, "task_id": task_id}

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

        # 如果数据库状态已经是终态，不再用 HITL  pending 状态覆盖
        db_status = task.get("status", "")
        if db_status in ("cancelled", "completed", "failed"):
            task["active_hitl"] = None
            task["hitl_summary"] = None
            return task

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
        normalized = [self._normalize_step(step, index) for index, step in enumerate(steps)]
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
        for step in steps:
            if not isinstance(step, dict):
                continue
            target = str(step.get("id") or "")
            for source in step.get("dependencies") or step.get("depends_on") or []:
                if source and target:
                    edges.append({"source": str(source), "target": target})
        return edges

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
        }

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
