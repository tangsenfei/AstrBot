"""
DeerFlow Skills Bridge - Skills 双向同步桥接器

实现 AstrBot 和 DeerFlow 之间的 Skills 双向同步
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from astrbot.core import logger
from astrbot.core.skills.skill_manager import SkillInfo, SkillManager, build_skills_prompt

if TYPE_CHECKING:
    from deerflow.skills.loader import Skill


class DeerFlowSkillsBridge:
    """Skills 双向同步桥接器
    
    实现 AstrBot 和 DeerFlow 之间的 Skills 双向同步，
    确保两边的 Skills 保持一致。
    """
    
    def __init__(
        self,
        astrbot_skills_path: str,
        deerflow_skills_path: str,
    ) -> None:
        self.astrbot_manager = SkillManager(astrbot_skills_path)
        self.deerflow_skills_path = Path(deerflow_skills_path)
    
    def sync_to_deerflow(self, overwrite: bool = False) -> list[str]:
        """将 AstrBot Skills 同步到 DeerFlow
        
        Args:
            overwrite: 是否覆盖已存在的 Skills
            
        Returns:
            同步成功的 Skill 名称列表
        """
        synced = []
        custom_dir = self.deerflow_skills_path / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)
        
        for skill in self.astrbot_manager.list_skills(active_only=True):
            src = Path(skill.path).parent
            dst = custom_dir / skill.name
            
            if dst.exists() and not overwrite:
                continue
            
            try:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                synced.append(skill.name)
                logger.info(f"Synced skill '{skill.name}' to DeerFlow")
            except Exception as e:
                logger.error(f"Failed to sync skill '{skill.name}': {e}")
        
        return synced
    
    def sync_from_deerflow(self, overwrite: bool = False) -> list[str]:
        """从 DeerFlow 同步 Skills 到 AstrBot
        
        Args:
            overwrite: 是否覆盖已存在的 Skills
            
        Returns:
            同步成功的 Skill 名称列表
        """
        synced = []
        
        try:
            from deerflow.skills.loader import load_skills
            deerflow_skills = load_skills(self.deerflow_skills_path, enabled_only=True)
        except ImportError:
            logger.warning("DeerFlow skills module not available")
            return synced
        
        for skill in deerflow_skills:
            src = Path(skill.path).parent
            dst = Path(self.astrbot_manager.skills_root) / skill.name
            
            if dst.exists() and not overwrite:
                continue
            
            try:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                synced.append(skill.name)
                logger.info(f"Synced skill '{skill.name}' from DeerFlow")
            except Exception as e:
                logger.error(f"Failed to sync skill '{skill.name}': {e}")
        
        return synced
    
    def bidirectional_sync(self) -> dict[str, list[str]]:
        """双向同步 Skills
        
        Returns:
            包含 'to_deerflow' 和 'from_deerflow' 两个列表的字典
        """
        return {
            "to_deerflow": self.sync_to_deerflow(),
            "from_deerflow": self.sync_from_deerflow(),
        }
    
    def get_unified_skills(self, active_only: bool = True) -> list[SkillInfo]:
        """获取统一的 Skills 列表
        
        合并 AstrBot 和 DeerFlow 的 Skills，去重后返回
        
        Args:
            active_only: 是否只返回激活的 Skills
            
        Returns:
            合并后的 Skills 列表
        """
        all_skills: dict[str, SkillInfo] = {}
        
        # 加载 AstrBot Skills
        for skill in self.astrbot_manager.list_skills(active_only=active_only):
            all_skills[skill.name] = skill
        
        # 加载 DeerFlow Skills
        try:
            from deerflow.skills.loader import load_skills
            for skill in load_skills(self.deerflow_skills_path, enabled_only=active_only):
                if skill.name not in all_skills:
                    all_skills[skill.name] = SkillInfo(
                        name=skill.name,
                        description=skill.description or "",
                        path=str(Path(skill.path).parent),
                        active=True,
                        source_type="deerflow",
                        source_label="deerflow",
                        license=skill.license or "",
                        allowed_tools=skill.allowed_tools or [],
                    )
        except ImportError:
            pass
        
        return list(all_skills.values())
    
    def build_unified_skills_prompt(self, active_only: bool = True) -> str:
        """构建统一的 Skills 系统提示
        
        Args:
            active_only: 是否只包含激活的 Skills
            
        Returns:
            用于注入系统提示的 Skills 描述
        """
        skills = self.get_unified_skills(active_only=active_only)
        return build_skills_prompt(skills)
