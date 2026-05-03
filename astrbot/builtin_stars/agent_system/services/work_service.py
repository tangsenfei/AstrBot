"""Work mode facade service.

This layer keeps the Work UI independent from the lower-level Agent System
screens while still reusing agent_tasks, LangGraph TaskCenter, flows, crews and
the shared HITL interaction manager.
"""
from __future__ import annotations

import asyncio
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
        where = " AND ".join(conditions)
        total = self.db.execute(
            f"SELECT COUNT(*) AS count FROM agent_tasks WHERE {where}",
            tuple(params),
        ).fetchone()["count"]
        rows = self.db.execute(
            f"""
            SELECT * FROM agent_tasks
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size, (page - 1) * page_size]),
        ).fetchall()
        return {
            "tasks": [self.task_service._row_to_agent_task(dict(row)).to_dict() for row in rows],
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
        kind = data.get("work_task_kind") or data.get("task_kind") or "single_agent"
        if kind not in ("single_agent", "multi_agent", "workflow"):
            raise ValueError("work_task_kind 必须是 single_agent/multi_agent/workflow")

        scope = data.get("work_scope") or ("project" if data.get("work_project_id") else "daily")
        project = self._get_project_row(data.get("work_project_id")) if scope == "project" else None
        daily_dir = self._get_daily_dir_row(data.get("work_daily_dir_id")) if scope == "daily" else None
        if scope == "daily" and not daily_dir:
            self.ensure_default_daily_dir()
            daily_dir = self.db.select_all("work_daily_dirs", where="status = 'active'", limit=1)[0]
        context_pack = self._build_context_pack(project, daily_dir)

        executor_config = dict(data.get("executor_config") or {})
        plan_config = {"enabled": False, **dict(data.get("plan_config") or {})}
        review_config = {"enabled": False, "max_rework": 1, **dict(data.get("review_config") or {})}
        input_data = dict(data.get("input") or {})
        input_data.setdefault("goal", data.get("goal") or data.get("description") or name)
        input_data["work_context"] = context_pack

        graph_type = "workflow" if kind == "workflow" else "work_task"
        task_id = data.get("id") or f"task_{uuid.uuid4().hex[:12]}"
        session_id = data.get("session_id", "work")
        thread_id = data.get("thread_id") or f"{session_id}:{task_id}"
        graph_config = {
            "task_id": task_id,
            "thread_id": thread_id,
            "task_name": name,
            "task_desc": data.get("description", ""),
            "work_task_kind": kind,
            "executor_config": executor_config,
            "plan_config": plan_config,
            "review_config": review_config,
            "input": input_data,
            "provider_id": data.get("provider_id") or executor_config.get("provider_id"),
            "session_id": session_id,
        }
        if kind == "workflow":
            flow_id = executor_config.get("flow_id") or data.get("flow_id")
            if not flow_id:
                raise ValueError("workflow 任务需要 flow_id")
            flow_definition = self._get_flow_definition(flow_id)
            graph_config["flow_definition"] = flow_definition
            graph_config["current_node_id"] = ""
            graph_config["node_results"] = {}

        task = self.task_service.create_task(
            task_id=task_id,
            name=name,
            description=data.get("description", ""),
            task_type=graph_type,
            crew_id=self._clean_fk(executor_config.get("crew_id")) if kind == "multi_agent" else None,
            flow_id=self._clean_fk(executor_config.get("flow_id") or data.get("flow_id")) if kind == "workflow" else None,
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
        await self._start_task_center_task(graph_type, graph_config)
        return task.to_dict()

    def get_task(self, task_id: str) -> dict[str, Any]:
        task = self.task_service.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")
        data = task.to_dict()
        data["logs"] = self.get_task_logs(task_id)
        data["subtasks"] = [s.to_dict() for s in self.task_service.get_subtasks(task_id)]
        data["artifacts"] = self.list_artifacts(task_id)
        return data

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

        from astrbot.core.langgraph.interaction import InteractionResponse
        from astrbot.core.langgraph.interaction_manager import get_interaction_manager

        response = InteractionResponse(
            interaction_id=interaction_id,
            action_key=data.get("action_key", "approve"),
            field_values=data.get("field_values", {}),
            responded_at=datetime.now().timestamp(),
        )
        ok = get_interaction_manager().respond(interaction_id, response)
        if not ok:
            raise ValueError(f"交互 '{interaction_id}' 不存在或已处理")
        self._append_log(task_id, "info", "HITL 响应已提交", response.field_values)
        return {"interaction_id": interaction_id, "action_key": response.action_key}

    def get_task_logs(self, task_id: str) -> list[dict[str, Any]]:
        return [log.to_dict() for log in self.task_service.get_task_logs(task_id)]

    def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.select_all(
            "work_artifacts",
            where="task_id = ?",
            where_params=(task_id,),
            order_by="created_at ASC",
        )
        return [self._row_to_artifact(row).to_dict() for row in rows]

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
                session_id=graph_config.get("session_id", "work"),
                run_ctx=run_ctx,
            )
            return {"task_id": record.task_id, "thread_id": record.thread_id}
        except Exception as e:
            logger.warning(f"Work task will be recorded without live TaskCenter execution: {e}")
            return {}

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
