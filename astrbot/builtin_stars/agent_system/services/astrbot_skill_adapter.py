"""
AstrBot Skill 适配器

将 AstrBot 的 SkillInfo（标准 Anthropic 格式）转换为智能体系统的 Skill 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger
from astrbot.core.skills.skill_manager import SkillInfo

from ..models import Skill, DisclosureLevel

if TYPE_CHECKING:
    pass


class AstrBotSkillAdapter:
    """AstrBot Skill 适配器
    
    负责将 AstrBot 的 SkillInfo 转换为智能体系统的 Skill 模型
    
    关键差异处理：
    1. ID 生成：使用 skill name 作为 ID（添加前缀避免冲突）
    2. 字段映射：allowed_tools -> tools
    3. 默认值：设置 workflow 和 disclosure_level 默认值
    4. Metadata：保留已扁平化的 metadata（AstrBot 已处理）
    """
    
    ID_PREFIX = "astrbot_"
    
    @classmethod
    def skill_info_to_skill(cls, skill_info: SkillInfo) -> Skill:
        """将 AstrBot SkillInfo 转换为智能体系统 Skill
        
        Args:
            skill_info: AstrBot 的 SkillInfo 对象
            
        Returns:
            智能体系统的 Skill 对象
        """
        skill_id = cls._generate_skill_id(skill_info.name)
        
        now = datetime.now()
        
        return Skill(
            id=skill_id,
            name=skill_info.name,
            description=skill_info.description or "",
            category=cls._determine_category(skill_info),
            tools=skill_info.allowed_tools or [],
            workflow=cls._create_default_workflow(skill_info),
            disclosure_level=DisclosureLevel.INSTRUCTIONS,
            version=cls._extract_version(skill_info.metadata),
            enabled=skill_info.active,
            metadata=cls._process_metadata(skill_info),
            created_at=now,
            updated_at=now,
        )
    
    @classmethod
    def _generate_skill_id(cls, name: str) -> str:
        """生成技能 ID
        
        使用前缀避免与用户创建的技能 ID 冲突
        
        Args:
            name: 技能名称
            
        Returns:
            技能 ID
        """
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return f"{cls.ID_PREFIX}{normalized_name}"
    
    @classmethod
    def _determine_category(cls, skill_info: SkillInfo) -> str:
        """确定技能分类
        
        根据 metadata 或其他信息推断分类
        
        Args:
            skill_info: SkillInfo 对象
            
        Returns:
            分类字符串
        """
        metadata = skill_info.metadata or {}
        
        if "category" in metadata:
            return str(metadata["category"])
        
        if "requires" in metadata:
            requires = metadata["requires"]
            if "bins" in requires or "cli" in str(requires).lower():
                return "automation"
        
        if any(keyword in skill_info.description.lower() for keyword in ["搜索", "search", "查询"]):
            return "search"
        
        if any(keyword in skill_info.description.lower() for keyword in ["分析", "analysis", "数据"]):
            return "analysis"
        
        if any(keyword in skill_info.description.lower() for keyword in ["开发", "development", "代码"]):
            return "development"
        
        return "general"
    
    @classmethod
    def _create_default_workflow(cls, skill_info: SkillInfo) -> dict[str, Any]:
        """创建默认工作流定义
        
        为 AstrBot skill 创建一个简单的工作流定义
        
        Args:
            skill_info: SkillInfo 对象
            
        Returns:
            工作流定义字典
        """
        return {
            "type": "single",
            "description": skill_info.description,
            "source": "astrbot",
            "skill_file": skill_info.path,
        }
    
    @classmethod
    def _extract_version(cls, metadata: dict[str, str] | None) -> str:
        """从 metadata 中提取版本号
        
        Args:
            metadata: metadata 字典
            
        Returns:
            版本号字符串
        """
        if not metadata:
            return "1.0.0"
        
        if "version" in metadata:
            return str(metadata["version"])
        
        return "1.0.0"
    
    @classmethod
    def _process_metadata(cls, skill_info: SkillInfo) -> dict[str, Any]:
        """处理 metadata
        
        保留 AstrBot 的 metadata，并添加额外信息
        
        Args:
            skill_info: SkillInfo 对象
            
        Returns:
            处理后的 metadata 字典
        """
        metadata = dict(skill_info.metadata or {})
        
        metadata["_astrbot"] = {
            "path": skill_info.path,
            "source_type": skill_info.source_type,
            "source_label": skill_info.source_label,
            "local_exists": skill_info.local_exists,
            "sandbox_exists": skill_info.sandbox_exists,
            "license": skill_info.license,
            "compatibility": skill_info.compatibility,
        }
        
        return metadata
    
    @classmethod
    def is_astrbot_skill(cls, skill_id: str) -> bool:
        """判断是否为 AstrBot skill
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            是否为 AstrBot skill
        """
        return skill_id.startswith(cls.ID_PREFIX)
    
    @classmethod
    def batch_convert(cls, skill_infos: list[SkillInfo]) -> list[Skill]:
        """批量转换 SkillInfo 列表
        
        Args:
            skill_infos: SkillInfo 列表
            
        Returns:
            Skill 列表
        """
        skills = []
        for skill_info in skill_infos:
            try:
                skill = cls.skill_info_to_skill(skill_info)
                skills.append(skill)
            except Exception as e:
                logger.error(f"Failed to convert skill {skill_info.name}: {e}")
        
        return skills
