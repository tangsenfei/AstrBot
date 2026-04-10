"""
智能体管理模块 - 技能服务

提供技能的 CRUD 操作、测试、导入导出等功能
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

from ..models import Skill, DisclosureLevel


class SkillService:
    """技能管理服务"""

    def __init__(self, db: "Database"):
        self.db = db
        self._skills_dir: Path | None = None

    @property
    def skills_dir(self) -> Path:
        """获取技能文件存储目录"""
        if self._skills_dir is None:
            self._skills_dir = StarTools.get_data_dir("agent_system") / "skills"
            self._skills_dir.mkdir(parents=True, exist_ok=True)
        return self._skills_dir

    def get_skills(self, category: str | None = None) -> list[Skill]:
        """获取技能列表

        Args:
            category: 技能分类筛选

        Returns:
            技能列表
        """
        where_clause = "1=1"
        params: tuple = ()

        if category:
            where_clause = "category = ?"
            params = (category,)

        rows = self.db.select_all(
            "skills",
            where=where_clause,
            where_params=params,
            order_by="created_at DESC"
        )

        skills = []
        for row in rows:
            try:
                skill = self._row_to_skill(row)
                skills.append(skill)
            except Exception as e:
                logger.error(f"Failed to parse skill {row.get('id')}: {e}")

        return skills

    def get_skill(self, skill_id: str) -> Skill | None:
        """获取单个技能

        Args:
            skill_id: 技能 ID

        Returns:
            技能对象，不存在则返回 None
        """
        row = self.db.select_one("skills", where="id = ?", where_params=(skill_id,))
        if row:
            return self._row_to_skill(row)
        return None

    def create_skill(self, data: dict[str, Any]) -> Skill:
        """创建技能

        Args:
            data: 技能数据

        Returns:
            创建的技能对象

        Raises:
            ValueError: 数据验证失败
        """
        # 验证必填字段
        if not data.get("name"):
            raise ValueError("技能名称不能为空")

        # 生成 ID
        skill_id = data.get("id") or f"skill_{uuid.uuid4().hex[:8]}"

        # 检查 ID 是否已存在
        existing = self.get_skill(skill_id)
        if existing:
            raise ValueError(f"技能 ID '{skill_id}' 已存在")

        # 验证披露级别
        disclosure_level = DisclosureLevel(data.get("disclosure_level", "metadata"))

        # 验证工具 ID 列表
        tools = data.get("tools", [])
        if not isinstance(tools, list):
            raise ValueError("tools 必须是列表")

        # 验证工作流定义
        workflow = data.get("workflow", {})
        if not isinstance(workflow, dict):
            raise ValueError("workflow 必须是字典")

        now = datetime.now()
        skill_data = {
            "id": skill_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "category": data.get("category", "general"),
            "tools": tools,
            "workflow": workflow,
            "disclosure_level": disclosure_level.value,
            "version": data.get("version", "1.0.0"),
            "enabled": data.get("enabled", True),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 插入数据库
        self.db.insert("skills", skill_data)

        # 保存技能文件
        self._save_skill_file(skill_id, skill_data)

        logger.info(f"Created skill: {skill_id}")
        return self._row_to_skill(skill_data)

    def update_skill(self, skill_id: str, data: dict[str, Any]) -> Skill | None:
        """更新技能

        Args:
            skill_id: 技能 ID
            data: 更新数据

        Returns:
            更新后的技能对象，不存在则返回 None

        Raises:
            ValueError: 数据验证失败
        """
        # 查找技能
        row = self.db.select_one("skills", where="id = ?", where_params=(skill_id,))
        if not row:
            return None

        # 准备更新数据
        update_data = {
            "updated_at": datetime.now().isoformat(),
        }

        # 可更新字段
        updatable_fields = [
            "name", "description", "category", "tools", "workflow",
            "disclosure_level", "version", "enabled", "metadata"
        ]

        for field in updatable_fields:
            if field in data:
                # 特殊处理
                if field == "disclosure_level":
                    update_data[field] = DisclosureLevel(data[field]).value
                elif field == "tools":
                    if not isinstance(data[field], list):
                        raise ValueError("tools 必须是列表")
                    update_data[field] = data[field]
                elif field == "workflow":
                    if not isinstance(data[field], dict):
                        raise ValueError("workflow 必须是字典")
                    update_data[field] = data[field]
                else:
                    update_data[field] = data[field]

        # 更新数据库
        self.db.update(
            "skills",
            update_data,
            where="id = ?",
            where_params=(skill_id,)
        )

        # 更新技能文件
        updated_skill = self.get_skill(skill_id)
        if updated_skill:
            self._save_skill_file(skill_id, updated_skill.to_dict())

        logger.info(f"Updated skill: {skill_id}")
        return updated_skill

    def delete_skill(self, skill_id: str) -> bool:
        """删除技能

        Args:
            skill_id: 技能 ID

        Returns:
            是否删除成功
        """
        # 查找技能
        row = self.db.select_one("skills", where="id = ?", where_params=(skill_id,))
        if not row:
            return False

        # 检查是否被 Agent 使用
        agents = self.db.select_all("agents", where="enabled = 1")
        for agent in agents:
            skills_json = agent.get("skills", "[]")
            try:
                skills_list = json.loads(skills_json) if isinstance(skills_json, str) else skills_json
                if skill_id in skills_list:
                    raise ValueError(f"技能 '{skill_id}' 正被智能体 '{agent['name']}' 使用，无法删除")
            except json.JSONDecodeError:
                pass

        # 删除技能
        self.db.delete("skills", where="id = ?", where_params=(skill_id,))

        # 删除技能文件
        skill_file = self.skills_dir / f"{skill_id}.json"
        if skill_file.exists():
            skill_file.unlink()

        logger.info(f"Deleted skill: {skill_id}")
        return True

    async def test_skill(self, skill_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """测试技能

        Args:
            skill_id: 技能 ID
            params: 测试参数

        Returns:
            测试结果

        Raises:
            ValueError: 技能不存在或参数错误
        """
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"技能 '{skill_id}' 不存在")

        result = {
            "skill_id": skill_id,
            "skill_name": skill.name,
            "params": params,
            "success": False,
            "output": None,
            "error": None,
            "execution_time_ms": 0,
            "disclosure_level": skill.disclosure_level.value,
            "tools_used": [],
        }

        start_time = datetime.now()

        try:
            # 根据披露级别返回不同的信息
            if skill.disclosure_level == DisclosureLevel.METADATA:
                # 只返回元数据
                result["output"] = {
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                }
            elif skill.disclosure_level == DisclosureLevel.INSTRUCTIONS:
                # 返回指令
                result["output"] = {
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "workflow": skill.workflow,
                }
            elif skill.disclosure_level == DisclosureLevel.RESOURCES:
                # 返回完整资源
                result["output"] = {
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "workflow": skill.workflow,
                    "tools": skill.tools,
                }
                result["tools_used"] = skill.tools

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Skill test failed: {skill_id} - {e}")

        end_time = datetime.now()
        result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)

        return result

    def import_skills(self, skills_data: list[dict[str, Any]]) -> list[Skill]:
        """批量导入技能

        Args:
            skills_data: 技能数据列表

        Returns:
            导入的技能列表
        """
        imported_skills = []

        for data in skills_data:
            try:
                # 生成新的 ID 避免冲突
                if "id" in data:
                    original_id = data["id"]
                    existing = self.get_skill(data["id"])
                    if existing:
                        data["id"] = f"{original_id}_{uuid.uuid4().hex[:4]}"

                skill = self.create_skill(data)
                imported_skills.append(skill)
            except Exception as e:
                logger.error(f"Failed to import skill: {e}")

        logger.info(f"Imported {len(imported_skills)} skills")
        return imported_skills

    def export_skills(self, skill_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """导出技能

        Args:
            skill_ids: 要导出的技能 ID 列表，为 None 则导出所有技能

        Returns:
            技能数据列表
        """
        exported = []

        if skill_ids:
            skills = [self.get_skill(sid) for sid in skill_ids]
            skills = [s for s in skills if s is not None]
        else:
            skills = self.get_skills()

        for skill in skills:
            exported.append(skill.to_dict())

        logger.info(f"Exported {len(exported)} skills")
        return exported

    def get_skill_market(self) -> list[dict[str, Any]]:
        """获取社区技能市场

        Returns:
            技能市场列表
        """
        # TODO: 实现从远程获取社区技能
        # 目前返回示例数据
        return [
            {
                "id": "market_web_search",
                "name": "网络搜索",
                "description": "使用搜索引擎搜索互联网信息",
                "category": "search",
                "tools": ["builtin_web_search"],
                "workflow": {
                    "type": "single",
                    "description": "执行网络搜索并返回结果"
                },
                "disclosure_level": "instructions",
                "version": "1.0.0",
                "author": "community",
                "downloads": 1500,
                "rating": 4.5,
            },
            {
                "id": "market_code_review",
                "name": "代码审查",
                "description": "对代码进行审查，提供改进建议",
                "category": "development",
                "tools": ["builtin_code_analyzer"],
                "workflow": {
                    "type": "multi_step",
                    "steps": [
                        {"action": "analyze", "description": "分析代码结构"},
                        {"action": "review", "description": "审查代码质量"},
                        {"action": "suggest", "description": "提供改进建议"}
                    ]
                },
                "disclosure_level": "instructions",
                "version": "1.0.0",
                "author": "community",
                "downloads": 800,
                "rating": 4.2,
            },
            {
                "id": "market_data_analysis",
                "name": "数据分析",
                "description": "对数据进行统计分析并生成报告",
                "category": "analysis",
                "tools": ["builtin_data_processor", "builtin_chart_generator"],
                "workflow": {
                    "type": "pipeline",
                    "steps": [
                        {"action": "load", "description": "加载数据"},
                        {"action": "clean", "description": "清洗数据"},
                        {"action": "analyze", "description": "分析数据"},
                        {"action": "visualize", "description": "可视化结果"}
                    ]
                },
                "disclosure_level": "resources",
                "version": "1.0.0",
                "author": "community",
                "downloads": 1200,
                "rating": 4.8,
            }
        ]

    def get_categories(self) -> list[dict[str, Any]]:
        """获取技能分类列表

        Returns:
            分类列表
        """
        # 预定义分类
        categories = [
            {"id": "general", "name": "通用", "description": "通用技能"},
            {"id": "search", "name": "搜索", "description": "搜索相关技能"},
            {"id": "development", "name": "开发", "description": "开发相关技能"},
            {"id": "analysis", "name": "分析", "description": "数据分析技能"},
            {"id": "communication", "name": "沟通", "description": "沟通协作技能"},
            {"id": "automation", "name": "自动化", "description": "自动化任务技能"},
        ]

        # 统计每个分类的技能数量
        for category in categories:
            skills = self.get_skills(category["id"])
            category["count"] = len(skills)

        return categories

    # ==================== 私有方法 ====================

    def _row_to_skill(self, row: dict[str, Any]) -> Skill:
        """将数据库行转换为 Skill 对象"""
        return Skill(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            category=row.get("category", "general"),
            tools=self._parse_json(row.get("tools", "[]")),
            workflow=self._parse_json(row.get("workflow", "{}")),
            disclosure_level=DisclosureLevel(row.get("disclosure_level", "metadata")),
            version=row.get("version", "1.0.0"),
            enabled=bool(row.get("enabled", 1)),
            metadata=self._parse_json(row.get("metadata", "{}")),
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

    def _save_skill_file(self, skill_id: str, data: dict[str, Any]) -> None:
        """保存技能到文件

        Args:
            skill_id: 技能 ID
            data: 技能数据
        """
        try:
            skill_file = self.skills_dir / f"{skill_id}.json"
            with open(skill_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved skill file: {skill_file}")
        except Exception as e:
            logger.error(f"Failed to save skill file: {skill_id} - {e}")

    def _load_skill_file(self, skill_id: str) -> dict[str, Any] | None:
        """从文件加载技能

        Args:
            skill_id: 技能 ID

        Returns:
            技能数据，不存在则返回 None
        """
        try:
            skill_file = self.skills_dir / f"{skill_id}.json"
            if skill_file.exists():
                with open(skill_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load skill file: {skill_id} - {e}")
        return None

    # ==================== AstrBot Skill 集成 ====================

    def get_all_skills_with_astrbot(self, category: str | None = None) -> list[Skill]:
        """获取所有技能（包含 AstrBot 技能，运行时合并）

        Args:
            category: 技能分类筛选

        Returns:
            合并后的技能列表
        """
        from astrbot.core.skills.skill_manager import SkillManager
        from .astrbot_skill_adapter import AstrBotSkillAdapter

        db_skills = self.get_skills(category)

        try:
            skill_manager = SkillManager()
            astrbot_skill_infos = skill_manager.list_skills(active_only=True)

            astrbot_skills = AstrBotSkillAdapter.batch_convert(astrbot_skill_infos)

            if category:
                astrbot_skills = [s for s in astrbot_skills if s.category == category]

            db_skill_ids = {skill.id for skill in db_skills}
            merged_skills = list(db_skills)

            for astrbot_skill in astrbot_skills:
                if astrbot_skill.id not in db_skill_ids:
                    merged_skills.append(astrbot_skill)

            logger.debug(
                f"Merged skills: {len(db_skills)} from DB + "
                f"{len(astrbot_skills)} from AstrBot = {len(merged_skills)} total"
            )

            return merged_skills

        except Exception as e:
            logger.error(f"Failed to merge AstrBot skills: {e}")
            return db_skills

    def get_astrbot_skills(self, active_only: bool = True) -> list[dict[str, Any]]:
        """获取 AstrBot 的技能列表

        Args:
            active_only: 是否只返回激活的技能

        Returns:
            AstrBot 技能列表（已转换为智能体系统格式）
        """
        from astrbot.core.skills.skill_manager import SkillManager
        from .astrbot_skill_adapter import AstrBotSkillAdapter

        try:
            skill_manager = SkillManager()
            skill_infos = skill_manager.list_skills(active_only=active_only)

            skills = AstrBotSkillAdapter.batch_convert(skill_infos)

            return [skill.to_dict() for skill in skills]

        except Exception as e:
            logger.error(f"Failed to get AstrBot skills: {e}")
            return []

    def get_astrbot_skill_by_id(self, skill_id: str) -> Skill | None:
        """根据 ID 获取 AstrBot 技能

        Args:
            skill_id: 技能 ID（必须以 astrbot_ 开头）

        Returns:
            Skill 对象，不存在则返回 None
        """
        from astrbot.core.skills.skill_manager import SkillManager
        from .astrbot_skill_adapter import AstrBotSkillAdapter

        if not AstrBotSkillAdapter.is_astrbot_skill(skill_id):
            return None

        try:
            skill_manager = SkillManager()
            skill_infos = skill_manager.list_skills(active_only=False)

            for skill_info in skill_infos:
                converted_id = AstrBotSkillAdapter._generate_skill_id(skill_info.name)
                if converted_id == skill_id:
                    return AstrBotSkillAdapter.skill_info_to_skill(skill_info)

            return None

        except Exception as e:
            logger.error(f"Failed to get AstrBot skill {skill_id}: {e}")
            return None

    def import_astrbot_skills(self, skill_names: list[str] | None = None) -> list[Skill]:
        """导入 AstrBot 技能到智能体系统

        Args:
            skill_names: 要导入的技能名称列表，为 None 则导入所有激活的技能

        Returns:
            导入的技能列表

        Raises:
            ValueError: 导入失败
        """
        from astrbot.core.skills.skill_manager import SkillManager
        from .astrbot_skill_adapter import AstrBotSkillAdapter

        try:
            skill_manager = SkillManager()
            all_skill_infos = skill_manager.list_skills(active_only=True)

            if skill_names:
                skill_infos = [
                    si for si in all_skill_infos if si.name in skill_names
                ]
            else:
                skill_infos = all_skill_infos

            if not skill_infos:
                logger.warning("No AstrBot skills found to import")
                return []

            skills = AstrBotSkillAdapter.batch_convert(skill_infos)

            imported_skills = []
            for skill in skills:
                try:
                    existing = self.get_skill(skill.id)
                    if existing:
                        self.update_skill(skill.id, skill.to_dict())
                        imported_skills.append(self.get_skill(skill.id))
                    else:
                        skill_dict = skill.to_dict()
                        del skill_dict["created_at"]
                        del skill_dict["updated_at"]
                        imported_skills.append(self.create_skill(skill_dict))
                except Exception as e:
                    logger.error(f"Failed to import skill {skill.name}: {e}")

            logger.info(f"Imported {len(imported_skills)} AstrBot skills")
            return imported_skills

        except Exception as e:
            logger.error(f"Failed to import AstrBot skills: {e}")
            raise ValueError(f"导入 AstrBot 技能失败: {e}")

    def sync_astrbot_skills(self) -> dict[str, Any]:
        """同步 AstrBot 技能

        将 AstrBot 的所有激活技能同步到智能体系统：
        - 新增的技能会被导入
        - 已存在的技能会被更新
        - 不再存在的 AstrBot 技能会被标记为禁用（不删除）

        Returns:
            同步结果统计
        """
        from astrbot.core.skills.skill_manager import SkillManager
        from .astrbot_skill_adapter import AstrBotSkillAdapter

        result = {
            "imported": 0,
            "updated": 0,
            "disabled": 0,
            "errors": [],
        }

        try:
            skill_manager = SkillManager()
            astrbot_skill_infos = skill_manager.list_skills(active_only=True)

            astrbot_skill_names = {si.name for si in astrbot_skill_infos}

            skills = AstrBotSkillAdapter.batch_convert(astrbot_skill_infos)

            for skill in skills:
                try:
                    existing = self.get_skill(skill.id)
                    if existing:
                        self.update_skill(skill.id, skill.to_dict())
                        result["updated"] += 1
                    else:
                        skill_dict = skill.to_dict()
                        del skill_dict["created_at"]
                        del skill_dict["updated_at"]
                        self.create_skill(skill_dict)
                        result["imported"] += 1
                except Exception as e:
                    error_msg = f"Failed to sync skill {skill.name}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

            all_skills = self.get_skills()
            for skill in all_skills:
                if AstrBotSkillAdapter.is_astrbot_skill(skill.id):
                    original_name = skill.id.replace(AstrBotSkillAdapter.ID_PREFIX, "")
                    normalized_name = original_name.replace("_", "-")

                    if normalized_name not in astrbot_skill_names and original_name not in astrbot_skill_names:
                        try:
                            self.update_skill(skill.id, {"enabled": False})
                            result["disabled"] += 1
                        except Exception as e:
                            error_msg = f"Failed to disable skill {skill.id}: {e}"
                            logger.error(error_msg)
                            result["errors"].append(error_msg)

            logger.info(f"AstrBot skills sync completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to sync AstrBot skills: {e}")
            result["errors"].append(str(e))
            return result
