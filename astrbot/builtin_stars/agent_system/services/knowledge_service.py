"""
智能体管理模块 - 知识库服务

提供知识库的 CRUD 操作、知识源管理、检索等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.star.star_tools import StarTools

if TYPE_CHECKING:
    from ..database import Database

from ..models import Knowledge, KnowledgeSource


class KnowledgeService:
    """知识库管理服务"""

    def __init__(self, db: "Database"):
        self.db = db
        # 知识库文件存储目录
        self.knowledge_dir = StarTools.get_data_dir("agent_system") / "knowledge"
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    def get_knowledge_list(self) -> list[Knowledge]:
        """获取知识库列表

        Returns:
            知识库列表
        """
        knowledge_list = []
        rows = self.db.select_all("knowledge", order_by="created_at DESC")

        for row in rows:
            try:
                knowledge = self._row_to_knowledge(row)
                knowledge_list.append(knowledge)
            except Exception as e:
                logger.error(f"Failed to parse knowledge {row.get('id')}: {e}")

        return knowledge_list

    def get_knowledge(self, knowledge_id: str) -> Knowledge | None:
        """获取单个知识库

        Args:
            knowledge_id: 知识库 ID

        Returns:
            知识库对象，不存在则返回 None
        """
        row = self.db.select_one("knowledge", where="id = ?", where_params=(knowledge_id,))
        if row:
            return self._row_to_knowledge(row)
        return None

    def create_knowledge(self, data: dict[str, Any]) -> Knowledge:
        """创建知识库

        Args:
            data: 知识库数据
                - name: 知识库名称（必填）
                - description: 描述
                - collection_name: 集合名称（可选，默认自动生成）
                - embedder_config: 嵌入模型配置
                - sources: 知识来源列表

        Returns:
            创建的知识库对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("知识库名称不能为空")

        # 生成 ID
        knowledge_id = data.get("id") or f"kb_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_knowledge(knowledge_id)
        if existing:
            raise ValueError(f"知识库 ID '{knowledge_id}' 已存在")

        # 检查名称是否已存在
        name = data["name"]
        existing_by_name = self.db.select_one("knowledge", where="name = ?", where_params=(name,))
        if existing_by_name:
            raise ValueError(f"知识库名称 '{name}' 已存在")

        # 生成集合名称
        collection_name = data.get("collection_name") or f"collection_{knowledge_id}"

        now = datetime.now()
        knowledge_data = {
            "id": knowledge_id,
            "name": name,
            "description": data.get("description", ""),
            "collection_name": collection_name,
            "sources": data.get("sources", []),
            "embedder_config": data.get("embedder_config", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("knowledge", knowledge_data)

        # 创建知识库存储目录
        kb_dir = self.knowledge_dir / knowledge_id
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "files").mkdir(exist_ok=True)

        logger.info(f"Created knowledge base: {knowledge_id}")
        return self._row_to_knowledge(knowledge_data)

    def update_knowledge(self, knowledge_id: str, data: dict[str, Any]) -> Knowledge | None:
        """更新知识库

        Args:
            knowledge_id: 知识库 ID
            data: 更新数据

        Returns:
            更新后的知识库对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找知识库
        row = self.db.select_one("knowledge", where="id = ?", where_params=(knowledge_id,))
        if not row:
            return None

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = ["name", "description", "embedder_config"]

        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        # 检查名称是否重复
        if "name" in data:
            existing = self.db.select_one(
                "knowledge",
                where="name = ? AND id != ?",
                where_params=(data["name"], knowledge_id)
            )
            if existing:
                raise ValueError(f"知识库名称 '{data['name']}' 已存在")

        # 更新数据库
        self.db.update(
            "knowledge",
            update_data,
            where="id = ?",
            where_params=(knowledge_id,)
        )

        logger.info(f"Updated knowledge base: {knowledge_id}")
        return self.get_knowledge(knowledge_id)

    def delete_knowledge(self, knowledge_id: str) -> bool:
        """删除知识库

        Args:
            knowledge_id: 知识库 ID

        Returns:
            是否删除成功
        """
        # 查找知识库
        row = self.db.select_one("knowledge", where="id = ?", where_params=(knowledge_id,))
        if not row:
            return False

        # 检查是否有关联的智能体
        agents = self.db.select_all("agents", where="knowledge_id = ?", where_params=(knowledge_id,))
        if agents:
            raise ValueError(f"知识库 '{knowledge_id}' 正在被 {len(agents)} 个智能体使用，无法删除")

        # 删除知识库
        self.db.delete("knowledge", where="id = ?", where_params=(knowledge_id,))

        # 删除知识库存储目录
        import shutil
        kb_dir = self.knowledge_dir / knowledge_id
        if kb_dir.exists():
            shutil.rmtree(kb_dir)

        logger.info(f"Deleted knowledge base: {knowledge_id}")
        return True

    def add_source(self, knowledge_id: str, source_data: dict[str, Any]) -> dict:
        """添加知识源

        Args:
            knowledge_id: 知识库 ID
            source_data: 知识源数据
                - type: 来源类型 (text, file, url, database)
                - name: 来源名称
                - content: 文本内容（type=text 时）
                - file_path: 文件路径（type=file 时）
                - url: URL 地址（type=url 时）
                - db_config: 数据库配置（type=database 时）

        Returns:
            添加的知识源数据

        Raises:
            ValueError: 数据验证失败
        """
        # 查找知识库
        knowledge = self.get_knowledge(knowledge_id)
        if not knowledge:
            raise ValueError(f"知识库 '{knowledge_id}' 不存在")

        # 验证来源类型
        source_type = source_data.get("type")
        if not source_type:
            raise ValueError("知识来源类型不能为空")

        try:
            source_type_enum = KnowledgeSource(source_type)
        except ValueError:
            raise ValueError(f"不支持的知识来源类型: {source_type}")

        # 生成来源 ID
        source_id = f"source_{uuid.uuid4().hex[:8]}"

        # 构建来源数据
        source = {
            "id": source_id,
            "type": source_type,
            "name": source_data.get("name", f"知识源_{source_id[:8]}"),
            "enabled": source_data.get("enabled", True),
            "created_at": datetime.now().isoformat(),
        }

        # 根据类型添加特定字段
        if source_type_enum == KnowledgeSource.TEXT:
            content = source_data.get("content")
            if not content:
                raise ValueError("文本知识源必须提供 content 字段")
            source["content"] = content
            source["char_count"] = len(content)

        elif source_type_enum == KnowledgeSource.FILE:
            file_path = source_data.get("file_path")
            if not file_path:
                raise ValueError("文件知识源必须提供 file_path 字段")
            source["file_path"] = file_path
            source["file_type"] = source_data.get("file_type", Path(file_path).suffix.lstrip("."))

        elif source_type_enum == KnowledgeSource.URL:
            url = source_data.get("url")
            if not url:
                raise ValueError("URL 知识源必须提供 url 字段")
            source["url"] = url

        elif source_type_enum == KnowledgeSource.DATABASE:
            db_config = source_data.get("db_config")
            if not db_config:
                raise ValueError("数据库知识源必须提供 db_config 字段")
            source["db_config"] = db_config

        # 更新知识库的 sources 字段
        sources = knowledge.sources.copy()
        sources.append(source)

        self.db.update(
            "knowledge",
            {
                "sources": sources,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(knowledge_id,)
        )

        logger.info(f"Added source {source_id} to knowledge base {knowledge_id}")
        return source

    def remove_source(self, knowledge_id: str, source_id: str) -> bool:
        """删除知识源

        Args:
            knowledge_id: 知识库 ID
            source_id: 知识源 ID

        Returns:
            是否删除成功
        """
        # 查找知识库
        knowledge = self.get_knowledge(knowledge_id)
        if not knowledge:
            return False

        # 查找并删除知识源
        sources = knowledge.sources.copy()
        original_count = len(sources)
        sources = [s for s in sources if s.get("id") != source_id]

        if len(sources) == original_count:
            return False

        # 更新数据库
        self.db.update(
            "knowledge",
            {
                "sources": sources,
                "updated_at": datetime.now().isoformat(),
            },
            where="id = ?",
            where_params=(knowledge_id,)
        )

        logger.info(f"Removed source {source_id} from knowledge base {knowledge_id}")
        return True

    def search(self, knowledge_id: str, query: str, top_k: int = 5) -> list[dict]:
        """检索知识

        Args:
            knowledge_id: 知识库 ID
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表

        Raises:
            ValueError: 知识库不存在或未配置嵌入模型
        """
        # 查找知识库
        knowledge = self.get_knowledge(knowledge_id)
        if not knowledge:
            raise ValueError(f"知识库 '{knowledge_id}' 不存在")

        # 获取 AstrBot 的知识库管理器
        try:
            from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager
            from astrbot.core.provider.manager import ProviderManager

            # 获取 ProviderManager 实例
            # 这里需要从全局上下文获取，暂时返回模拟数据
            logger.warning("Knowledge search requires integration with AstrBot's KnowledgeBaseManager")

            # 返回模拟数据（实际应调用 AstrBot 的知识库检索功能）
            return [{
                "chunk_id": f"chunk_{i}",
                "content": f"模拟检索结果 {i + 1}，查询: {query}",
                "score": 0.9 - i * 0.1,
                "source": "mock",
            } for i in range(min(top_k, 3))]

        except ImportError as e:
            logger.error(f"Failed to import KnowledgeBaseManager: {e}")
            raise ValueError("知识库检索功能不可用，请检查 AstrBot 版本")

    def reindex(self, knowledge_id: str) -> bool:
        """重建索引

        Args:
            knowledge_id: 知识库 ID

        Returns:
            是否重建成功

        Raises:
            ValueError: 知识库不存在
        """
        # 查找知识库
        knowledge = self.get_knowledge(knowledge_id)
        if not knowledge:
            raise ValueError(f"知识库 '{knowledge_id}' 不存在")

        # TODO: 实现索引重建逻辑
        # 这需要与 AstrBot 的知识库系统集成
        logger.info(f"Reindexing knowledge base: {knowledge_id}")

        # 更新更新时间
        self.db.update(
            "knowledge",
            {"updated_at": datetime.now().isoformat()},
            where="id = ?",
            where_params=(knowledge_id,)
        )

        return True

    def get_source_file_path(self, knowledge_id: str, filename: str) -> Path:
        """获取知识源文件存储路径

        Args:
            knowledge_id: 知识库 ID
            filename: 文件名

        Returns:
            文件存储路径
        """
        kb_dir = self.knowledge_dir / knowledge_id / "files"
        kb_dir.mkdir(parents=True, exist_ok=True)
        return kb_dir / filename

    # ==================== 私有方法 ====================

    def _row_to_knowledge(self, row: dict[str, Any]) -> Knowledge:
        """将数据库行转换为 Knowledge 对象"""
        return Knowledge(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            collection_name=row.get("collection_name", ""),
            sources=self._parse_json(row.get("sources", "[]")),
            embedder_config=self._parse_json(row.get("embedder_config", "{}")),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
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
