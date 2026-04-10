"""
智能体管理模块 - 数据库初始化

使用 SQLite 存储所有数据
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from astrbot.core import logger
from astrbot.core.star.star_tools import StarTools


class Database:
    """数据库管理类"""

    def __init__(self, db_path: str | Path | None = None):
        """初始化数据库

        Args:
            db_path: 数据库文件路径，如果为 None 则使用默认路径
        """
        if db_path is None:
            data_dir = StarTools.get_data_dir("agent_system")
            db_path = data_dir / "agent.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # 启用外键约束
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL 语句"""
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """批量执行 SQL 语句"""
        return self.conn.executemany(sql, params_list)

    def commit(self) -> None:
        """提交事务"""
        self.conn.commit()

    def create_tables(self) -> None:
        """创建所有表"""
        # 工具表
        self.execute("""
            CREATE TABLE IF NOT EXISTS tools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source TEXT NOT NULL DEFAULT 'builtin',
                parameters TEXT DEFAULT '{}',
                return_type TEXT,
                version TEXT DEFAULT '1.0.0',
                enabled INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 技能表
        self.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                tools TEXT DEFAULT '[]',
                workflow TEXT DEFAULT '{}',
                disclosure_level TEXT DEFAULT 'metadata',
                version TEXT DEFAULT '1.0.0',
                enabled INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 知识库表
        self.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                collection_name TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                embedder_config TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 智能体表
        self.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                goal TEXT,
                backstory TEXT,
                tools TEXT DEFAULT '[]',
                skills TEXT DEFAULT '[]',
                knowledge_id TEXT,
                provider_id TEXT,
                model_name TEXT,
                llm_config TEXT DEFAULT '{}',
                memory_config TEXT DEFAULT '{}',
                planning INTEGER DEFAULT 0,
                planning_effort TEXT DEFAULT 'medium',
                max_iter INTEGER DEFAULT 20,
                max_rpm INTEGER,
                verbose INTEGER DEFAULT 0,
                allow_delegation INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (knowledge_id) REFERENCES knowledge(id)
            )
        """)

        # Crew 任务表
        self.execute("""
            CREATE TABLE IF NOT EXISTS crew_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                expected_output TEXT,
                agent_id TEXT,
                tools TEXT DEFAULT '[]',
                context TEXT DEFAULT '[]',
                async_execution INTEGER DEFAULT 0,
                config TEXT DEFAULT '{}',
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Crew 表
        self.execute("""
            CREATE TABLE IF NOT EXISTS crews (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                agents TEXT DEFAULT '[]',
                tasks TEXT DEFAULT '[]',
                process TEXT DEFAULT 'sequential',
                manager_llm TEXT,
                memory INTEGER DEFAULT 0,
                cache INTEGER DEFAULT 1,
                max_rpm INTEGER,
                share_agent_output INTEGER DEFAULT 1,
                verbose INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 流程节点表
        self.execute("""
            CREATE TABLE IF NOT EXISTS flow_nodes (
                id TEXT PRIMARY KEY,
                flow_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'start',
                config TEXT DEFAULT '{}',
                position TEXT DEFAULT '{"x": 0, "y": 0}',
                FOREIGN KEY (flow_id) REFERENCES flows(id) ON DELETE CASCADE
            )
        """)

        # 流程边表
        self.execute("""
            CREATE TABLE IF NOT EXISTS flow_edges (
                id TEXT PRIMARY KEY,
                flow_id TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                condition TEXT DEFAULT '{}',
                FOREIGN KEY (flow_id) REFERENCES flows(id) ON DELETE CASCADE,
                FOREIGN KEY (source) REFERENCES flow_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target) REFERENCES flow_nodes(id) ON DELETE CASCADE
            )
        """)

        # 流程表
        self.execute("""
            CREATE TABLE IF NOT EXISTS flows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 智能体任务执行表
        self.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id TEXT PRIMARY KEY,
                crew_id TEXT,
                flow_id TEXT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                input TEXT DEFAULT '{}',
                output TEXT DEFAULT '{}',
                result TEXT,
                error TEXT,
                total_tokens INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (crew_id) REFERENCES crews(id),
                FOREIGN KEY (flow_id) REFERENCES flows(id)
            )
        """)

        # 子任务表
        self.execute("""
            CREATE TABLE IF NOT EXISTS sub_tasks (
                id TEXT PRIMARY KEY,
                parent_task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                input TEXT DEFAULT '{}',
                output TEXT DEFAULT '{}',
                result TEXT,
                error TEXT,
                tokens INTEGER DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (parent_task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # 执行日志表
        self.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                sub_task_id TEXT,
                agent_id TEXT,
                level TEXT DEFAULT 'info',
                message TEXT,
                data TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (sub_task_id) REFERENCES sub_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Token 统计表
        self.execute("""
            CREATE TABLE IF NOT EXISTS token_stats (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_id TEXT,
                model_name TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # 数据库迁移
        self._migrate_tables()

        # 创建索引
        self._create_indexes()

        self.commit()
        logger.info(f"Database tables created at {self.db_path}")

    def _migrate_tables(self) -> None:
        """数据库迁移：检查并添加缺失的列"""
        migrations = [
            ("agents", "knowledge_id", "TEXT"),
            ("agents", "planning", "INTEGER DEFAULT 0"),
            ("agents", "planning_effort", "TEXT DEFAULT 'medium'"),
            ("agents", "max_iter", "INTEGER DEFAULT 20"),
            ("agents", "max_rpm", "INTEGER"),
            ("agents", "verbose", "INTEGER DEFAULT 0"),
            ("agents", "allow_delegation", "INTEGER DEFAULT 0"),
            ("agents", "memory_config", "TEXT DEFAULT '{}'"),
            ("agent_tasks", "flow_id", "TEXT"),
            ("agent_tasks", "total_tokens", "INTEGER DEFAULT 0"),
            ("agent_tasks", "input_tokens", "INTEGER DEFAULT 0"),
            ("agent_tasks", "output_tokens", "INTEGER DEFAULT 0"),
        ]

        for table, column, col_type in migrations:
            try:
                cursor = self.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if column not in columns:
                    logger.info(f"Adding column {column} to table {table}")
                    self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except Exception as e:
                logger.warning(f"Migration warning for {table}.{column}: {e}")

    def _create_indexes(self) -> None:
        """创建索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tools_source ON tools(source)",
            "CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)",
            "CREATE INDEX IF NOT EXISTS idx_skills_enabled ON skills(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_agents_enabled ON agents(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_agents_provider ON agents(provider_id)",
            "CREATE INDEX IF NOT EXISTS idx_crews_enabled ON crews(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_flows_enabled ON flows(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_agent_tasks_crew ON agent_tasks(crew_id)",
            "CREATE INDEX IF NOT EXISTS idx_agent_tasks_flow ON agent_tasks(flow_id)",
            "CREATE INDEX IF NOT EXISTS idx_sub_tasks_parent ON sub_tasks(parent_task_id)",
            "CREATE INDEX IF NOT EXISTS idx_sub_tasks_agent ON sub_tasks(agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_execution_logs_task ON execution_logs(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_token_stats_task ON token_stats(task_id)",
        ]

        for index_sql in indexes:
            self.execute(index_sql)

    def insert(self, table: str, data: dict[str, Any]) -> None:
        """插入数据"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = self._prepare_values(data)

        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute(sql, values)
        self.commit()

    def update(self, table: str, data: dict[str, Any], where: str, where_params: tuple = ()) -> None:
        """更新数据"""
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = self._prepare_values(data)

        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        self.execute(sql, values + where_params)
        self.commit()

    def delete(self, table: str, where: str, where_params: tuple = ()) -> None:
        """删除数据"""
        sql = f"DELETE FROM {table} WHERE {where}"
        self.execute(sql, where_params)
        self.commit()

    def select_one(self, table: str, where: str = "1=1", where_params: tuple = ()) -> dict[str, Any] | None:
        """查询单条数据"""
        sql = f"SELECT * FROM {table} WHERE {where} LIMIT 1"
        cursor = self.execute(sql, where_params)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def select_all(self, table: str, where: str = "1=1", where_params: tuple = (), order_by: str | None = None) -> list[dict[str, Any]]:
        """查询多条数据"""
        sql = f"SELECT * FROM {table} WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        cursor = self.execute(sql, where_params)
        return [dict(row) for row in cursor.fetchall()]

    def _prepare_values(self, data: dict[str, Any]) -> tuple:
        """准备值，将字典和列表转换为 JSON 字符串"""
        values = []
        for v in data.values():
            if isinstance(v, (dict, list)):
                values.append(json.dumps(v, ensure_ascii=False))
            elif isinstance(v, bool):
                values.append(1 if v else 0)
            else:
                values.append(v)
        return tuple(values)


# 全局数据库实例
_db: Database | None = None


def get_database() -> Database:
    """获取数据库实例"""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


def init_database(db_path: str | Path | None = None) -> Database:
    """初始化数据库

    Args:
        db_path: 数据库文件路径，如果为 None 则使用默认路径

    Returns:
        Database: 数据库实例
    """
    global _db
    _db = Database(db_path)
    _db.create_tables()
    logger.info("AgentSystem database initialized")
    return _db


def close_database() -> None:
    """关闭数据库"""
    global _db
    if _db:
        _db.close()
        _db = None
        logger.info("AgentSystem database closed")
