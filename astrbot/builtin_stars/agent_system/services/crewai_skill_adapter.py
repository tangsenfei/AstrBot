"""
CrewAI Skill 适配器

将 CrewAI 原生技能转换为智能体系统的 Skill 模型

CrewAI 的技能通常通过 crewai 包定义，这里提供基础适配框架
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from astrbot.core import logger

from ..models import Skill, DisclosureLevel


class CrewAISkillAdapter:
    """CrewAI Skill 适配器
    
    负责发现和转换 CrewAI 原生技能
    
    CrewAI 技能来源:
    1. crewai-cli 安装的技能包
    2. 用户自定义的 CrewAI 技能
    """
    
    ID_PREFIX = "crewai_"
    
    @classmethod
    def discover_skills(cls) -> list[Skill]:
        """发现所有 CrewAI 技能
        
        Returns:
            Skill 列表
        """
        skills = []
        
        try:
            skills = cls._discover_from_crewai()
        except ImportError:
            logger.debug("crewai package not installed, skipping CrewAI skills")
        except Exception as e:
            logger.warning(f"Failed to discover CrewAI skills: {e}")
        
        return skills
    
    @classmethod
    def _discover_from_crewai(cls) -> list[Skill]:
        """从 crewai 包发现技能

        crewAI v1.x 中 Skill 类可能位于不同模块路径，
        依次尝试已知路径，均失败则返回空列表。

        Returns:
            Skill 列表
        """
        skills = []

        # 尝试多个可能的 Skill 导入路径
        skill_class = None
        for module_path in [
            "crewai.skills",
            "crewai.skill",
            "crewai",
        ]:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                if hasattr(mod, "Skill"):
                    skill_class = mod.Skill
                    break
            except (ImportError, ModuleNotFoundError):
                continue

        if skill_class is None:
            logger.debug("crewai Skill class not found in any known module path")
            return skills

        try:
            if hasattr(skill_class, '__subclasses__'):
                for subclass in skill_class.__subclasses__():
                    try:
                        skill = cls._convert_crewai_skill(subclass)
                        if skill:
                            skills.append(skill)
                    except Exception as e:
                        logger.warning(f"Failed to convert CrewAI skill: {e}")
        except Exception as e:
            logger.debug(f"Failed to enumerate CrewAI skill subclasses: {e}")

        return skills
    
    @classmethod
    def _convert_crewai_skill(cls, crewai_skill_class: type) -> Skill | None:
        """转换 CrewAI 技能类为 Skill 对象
        
        Args:
            crewai_skill_class: CrewAI 技能类
            
        Returns:
            Skill 对象，转换失败返回 None
        """
        name = getattr(crewai_skill_class, 'name', None) or crewai_skill_class.__name__
        description = getattr(crewai_skill_class, 'description', '') or ''
        
        skill_id = cls._generate_skill_id(name)
        now = datetime.now()
        
        return Skill(
            id=skill_id,
            name=name,
            description=description,
            source="crewai",
            category="",
            tools=getattr(crewai_skill_class, 'tools', []) or [],
            workflow={
                "type": "single",
                "description": description,
                "source": "crewai",
            },
            disclosure_level=DisclosureLevel.INSTRUCTIONS,
            version="1.0.0",
            enabled=True,
            metadata={
                "_crewai": {
                    "class_name": crewai_skill_class.__name__,
                    "module": getattr(crewai_skill_class, '__module__', ''),
                }
            },
            created_at=now,
            updated_at=now,
        )
    
    @classmethod
    def _generate_skill_id(cls, name: str) -> str:
        """生成技能 ID
        
        Args:
            name: 技能名称
            
        Returns:
            技能 ID
        """
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return f"{cls.ID_PREFIX}{normalized_name}"
    
    @classmethod
    def is_crewai_skill(cls, skill_id: str) -> bool:
        """判断是否为 CrewAI skill
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            是否为 CrewAI skill
        """
        return skill_id.startswith(cls.ID_PREFIX)
    
    @classmethod
    def get_skill(cls, skill_id: str) -> Skill | None:
        """获取指定 CrewAI 技能
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            Skill 对象，不存在则返回 None
        """
        skills = cls.discover_skills()
        for skill in skills:
            if skill.id == skill_id:
                return skill
        return None
