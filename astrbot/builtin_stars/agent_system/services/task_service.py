"""
智能体管理模块 - 任务服务

提供任务的查询、控制、日志、统计等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from ..database import Database

from ..models import AgentTask, SubTask, ExecutionLog, TaskStatus


class TaskService:
    """任务管理服务"""

    def __init__(self, db: "Database"):
        self.db = db

    def get_tasks(
        self,
        status: str | None = None,
        crew_id: str | None = None,
        flow_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """获取任务列表（支持筛选、分页）

        Args:
            status: 任务状态筛选
            crew_id: Crew ID 筛选
            flow_id: Flow ID 筛选
            start_time: 开始时间筛选（ISO 格式）
            end_time: 结束时间筛选（ISO 格式）
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            包含任务列表和分页信息的字典
        """
        # 构建查询条件
        conditions = []
        params = []

        if status:
            try:
                TaskStatus(status)
                conditions.append("status = ?")
                params.append(status)
            except ValueError:
                pass

        if crew_id:
            conditions.append("crew_id = ?")
            params.append(crew_id)

        if flow_id:
            conditions.append("flow_id = ?")
            params.append(flow_id)

        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)

        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查询总数
        count_sql = f"SELECT COUNT(*) as count FROM agent_tasks WHERE {where_clause}"
        cursor = self.db.execute(count_sql, tuple(params))
        total = cursor.fetchone()["count"]

        # 分页查询
        offset = (page - 1) * page_size
        sql = f"""
            SELECT * FROM agent_tasks
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = self.db.execute(sql, tuple(params + [page_size, offset]))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            try:
                task = self._row_to_agent_task(dict(row))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to parse task {row.get('id')}: {e}")

        return {
            "tasks": [t.to_dict() for t in tasks],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def get_task(self, task_id: str) -> AgentTask | None:
        """获取任务详情

        Args:
            task_id: 任务 ID

        Returns:
            AgentTask 对象，不存在则返回 None
        """
        row = self.db.select_one("agent_tasks", where="id = ?", where_params=(task_id,))
        if row:
            return self._row_to_agent_task(row)
        return None

    def pause_task(self, task_id: str) -> bool:
        """暂停任务（仅 Flow）

        Args:
            task_id: 任务 ID

        Returns:
            是否暂停成功

        Raises:
            ValueError: 任务不存在、状态不允许暂停或非 Flow 任务
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")

        # 检查是否为 Flow 任务
        if not task.flow_id:
            raise ValueError("只有 Flow 任务支持暂停操作")

        # 检查状态
        if task.status != TaskStatus.RUNNING:
            raise ValueError(f"任务状态为 '{task.status.value}'，无法暂停")

        # 更新状态
        self.db.update(
            "agent_tasks",
            {
                "status": TaskStatus.PAUSED.value,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(task_id,),
        )

        logger.info(f"Task paused: {task_id}")
        return True

    def resume_task(self, task_id: str) -> bool:
        """恢复任务（仅 Flow）

        Args:
            task_id: 任务 ID

        Returns:
            是否恢复成功

        Raises:
            ValueError: 任务不存在、状态不允许恢复或非 Flow 任务
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")

        # 检查是否为 Flow 任务
        if not task.flow_id:
            raise ValueError("只有 Flow 任务支持恢复操作")

        # 检查状态
        if task.status != TaskStatus.PAUSED:
            raise ValueError(f"任务状态为 '{task.status.value}'，无法恢复")

        # 更新状态
        self.db.update(
            "agent_tasks",
            {
                "status": TaskStatus.RUNNING.value,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(task_id,),
        )

        logger.info(f"Task resumed: {task_id}")
        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否取消成功

        Raises:
            ValueError: 任务不存在或状态不允许取消
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")

        # 检查状态
        cancellable_statuses = [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.WAITING_FEEDBACK,
        ]
        if task.status not in cancellable_statuses:
            raise ValueError(f"任务状态为 '{task.status.value}'，无法取消")

        # 更新状态
        self.db.update(
            "agent_tasks",
            {
                "status": TaskStatus.CANCELLED.value,
                "completed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(task_id,),
        )

        # 同时取消所有子任务
        self.db.update(
            "sub_tasks",
            {
                "status": TaskStatus.CANCELLED.value,
                "completed_at": datetime.now().isoformat(),
            },
            where="parent_task_id = ? AND status NOT IN (?, ?, ?)",
            where_params=(
                task_id,
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            ),
        )

        logger.info(f"Task cancelled: {task_id}")
        return True

    def retry_task(self, task_id: str) -> AgentTask:
        """重试任务

        Args:
            task_id: 原任务 ID

        Returns:
            新创建的 AgentTask 对象

        Raises:
            ValueError: 任务不存在或状态不允许重试
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务 '{task_id}' 不存在")

        # 检查状态
        retryable_statuses = [TaskStatus.FAILED, TaskStatus.CANCELLED]
        if task.status not in retryable_statuses:
            raise ValueError(f"任务状态为 '{task.status.value}'，无法重试")

        # 创建新任务
        new_task_id = f"task_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        new_task_data = {
            "id": new_task_id,
            "crew_id": task.crew_id,
            "flow_id": task.flow_id,
            "name": task.name,
            "description": task.description,
            "status": TaskStatus.PENDING.value,
            "progress": 0,
            "input": task.input,
            "output": {},
            "result": None,
            "error": None,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "started_at": None,
            "completed_at": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        self.db.insert("agent_tasks", new_task_data)

        logger.info(f"Task retried: {task_id} -> {new_task_id}")
        return self._row_to_agent_task(new_task_data)

    def get_task_logs(self, task_id: str) -> list[ExecutionLog]:
        """获取任务日志

        Args:
            task_id: 任务 ID

        Returns:
            ExecutionLog 列表
        """
        rows = self.db.select_all(
            "execution_logs",
            where="task_id = ?",
            where_params=(task_id,),
            order_by="created_at ASC",
        )

        logs = []
        for row in rows:
            try:
                log = self._row_to_execution_log(row)
                logs.append(log)
            except Exception as e:
                logger.error(f"Failed to parse log {row.get('id')}: {e}")

        return logs

    def get_subtasks(self, task_id: str) -> list[SubTask]:
        """获取子任务列表

        Args:
            task_id: 父任务 ID

        Returns:
            SubTask 列表
        """
        rows = self.db.select_all(
            "sub_tasks",
            where="parent_task_id = ?",
            where_params=(task_id,),
            order_by="created_at ASC",
        )

        subtasks = []
        for row in rows:
            try:
                subtask = self._row_to_subtask(row)
                subtasks.append(subtask)
            except Exception as e:
                logger.error(f"Failed to parse subtask {row.get('id')}: {e}")

        return subtasks

    def get_task_stats(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """获取任务统计

        Args:
            start_time: 开始时间筛选（ISO 格式）
            end_time: 结束时间筛选（ISO 格式）

        Returns:
            统计数据字典
        """
        # 构建时间条件
        time_conditions = []
        time_params = []

        if start_time:
            time_conditions.append("created_at >= ?")
            time_params.append(start_time)

        if end_time:
            time_conditions.append("created_at <= ?")
            time_params.append(end_time)

        time_clause = " AND ".join(time_conditions) if time_conditions else "1=1"

        # 总任务数
        total_sql = f"SELECT COUNT(*) as count FROM agent_tasks WHERE {time_clause}"
        cursor = self.db.execute(total_sql, tuple(time_params))
        total_tasks = cursor.fetchone()["count"]

        # 各状态任务数
        status_sql = f"""
            SELECT status, COUNT(*) as count
            FROM agent_tasks
            WHERE {time_clause}
            GROUP BY status
        """
        cursor = self.db.execute(status_sql, tuple(time_params))
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # 今日任务数
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time()).isoformat()
        today_end = datetime.combine(today, datetime.max.time()).isoformat()

        today_sql = """
            SELECT COUNT(*) as count
            FROM agent_tasks
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor = self.db.execute(today_sql, (today_start, today_end))
        today_tasks = cursor.fetchone()["count"]

        # 今日 Token 消耗
        token_sql = """
            SELECT COALESCE(SUM(total_tokens), 0) as total,
                   COALESCE(SUM(input_tokens), 0) as input,
                   COALESCE(SUM(output_tokens), 0) as output
            FROM agent_tasks
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor = self.db.execute(token_sql, (today_start, today_end))
        token_row = cursor.fetchone()

        # 平均执行时间（仅计算已完成的任务）
        avg_time_sql = f"""
            SELECT AVG(
                (julianday(completed_at) - julianday(started_at)) * 24 * 60 * 60
            ) as avg_seconds
            FROM agent_tasks
            WHERE {time_clause}
            AND status = ?
            AND started_at IS NOT NULL
            AND completed_at IS NOT NULL
        """
        cursor = self.db.execute(
            avg_time_sql, tuple(time_params + [TaskStatus.COMPLETED.value])
        )
        avg_seconds = cursor.fetchone()["avg_seconds"] or 0

        return {
            "total_tasks": total_tasks,
            "status_counts": {
                "pending": status_counts.get(TaskStatus.PENDING.value, 0),
                "running": status_counts.get(TaskStatus.RUNNING.value, 0),
                "paused": status_counts.get(TaskStatus.PAUSED.value, 0),
                "waiting_feedback": status_counts.get(TaskStatus.WAITING_FEEDBACK.value, 0),
                "completed": status_counts.get(TaskStatus.COMPLETED.value, 0),
                "failed": status_counts.get(TaskStatus.FAILED.value, 0),
                "cancelled": status_counts.get(TaskStatus.CANCELLED.value, 0),
            },
            "today": {
                "tasks": today_tasks,
                "tokens": {
                    "total": token_row["total"],
                    "input": token_row["input"],
                    "output": token_row["output"],
                },
            },
            "average_execution_time_seconds": round(avg_seconds, 2),
        }

    # ==================== 私有方法 ====================

    def _row_to_agent_task(self, row: dict[str, Any]) -> AgentTask:
        """将数据库行转换为 AgentTask 对象"""
        return AgentTask(
            id=row["id"],
            crew_id=row.get("crew_id"),
            flow_id=row.get("flow_id"),
            name=row["name"],
            description=row.get("description", ""),
            status=TaskStatus(row.get("status", "pending")),
            progress=row.get("progress", 0),
            input=self._parse_json(row.get("input", "{}")),
            output=self._parse_json(row.get("output", "{}")),
            result=row.get("result"),
            error=row.get("error"),
            total_tokens=row.get("total_tokens", 0),
            input_tokens=row.get("input_tokens", 0),
            output_tokens=row.get("output_tokens", 0),
            started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )

    def _row_to_subtask(self, row: dict[str, Any]) -> SubTask:
        """将数据库行转换为 SubTask 对象"""
        return SubTask(
            id=row["id"],
            parent_task_id=row["parent_task_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            description=row.get("description", ""),
            status=TaskStatus(row.get("status", "pending")),
            progress=row.get("progress", 0),
            input=self._parse_json(row.get("input", "{}")),
            output=self._parse_json(row.get("output", "{}")),
            result=row.get("result"),
            error=row.get("error"),
            tokens=row.get("tokens", 0),
            started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
        )

    def _row_to_execution_log(self, row: dict[str, Any]) -> ExecutionLog:
        """将数据库行转换为 ExecutionLog 对象"""
        return ExecutionLog(
            id=row["id"],
            task_id=row["task_id"],
            sub_task_id=row.get("sub_task_id"),
            agent_id=row.get("agent_id"),
            level=row.get("level", "info"),
            message=row.get("message", ""),
            data=self._parse_json(row.get("data", "{}")),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
        )

    def _parse_json(self, value: str | dict | list | None) -> dict | list:
        """解析 JSON 字符串"""
        if value is None:
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
