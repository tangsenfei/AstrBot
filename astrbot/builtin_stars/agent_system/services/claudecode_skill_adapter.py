 """
ClaudeCode Skill 适配器

读取用户的 Claude Code skill 配置，转换为智能体系统的 Skill 模型

Claude Code 的 skill 配置通常位于:
- ~/.claude/skills/ 目录下的 .md 文件
- 项目根目录的 .claude/skills/ 目录
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.core import logger

from ..models import Skill, DisclosureLevel


class ClaudeCodeSkillAdapter:
    """ClaudeCode Skill 适配器
    
    负责读取 Claude Code 的 skill 配置并转换为智能体系统的 Skill 模型
    
    Claude Code skill 格式:
    ---
    name: skill-name
    description: What this skill does
    ---
    Skill instructions in markdown
    """
    
    ID_PREFIX = "claudcode_"
    
    SKILL_DIRS = [
        Path.home() / ".claude" / "skills",
        Path.cwd() / ".claude" / "skills",
    ]
    
    @classmethod
    def discover_skills(cls) -> list[Skill]:
        """发现所有 ClaudeCode 技能
        
        Returns:
            Skill 列表
        """
        skills = []
        seen_names = set()
        
        for skill_dir in cls.SKILL_DIRS:
            if not skill_dir.exists():
                continue
            
            for skill_file in skill_dir.rglob("*.md"):
                try:
                    skill = cls._parse_skill_file(skill_file)
                    if skill and skill.name not in seen_names:
                        skills.append(skill)
                        seen_names.add(skill.name)
                except Exception as e:
                    logger.warning(f"Failed to parse ClaudeCode skill {skill_file}: {e}")
        
        return skills
    
    @classmethod
    def _parse_skill_file(cls, file_path: Path) -> Skill | None:
        """解析 ClaudeCode skill 文件
        
        Args:
            file_path: skill 文件路径
            
        Returns:
            Skill 对象，解析失败返回 None
        """
        content = file_path.read_text(encoding="utf-8", errors="replace")
        
        name = ""
        description = ""
        instructions = ""
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                instructions = parts[2].strip()
                
                for line in frontmatter.split("\n"):
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line[5:].strip().strip('"').strip("'")
                    elif line.startswith("description:"):
                        description = line[12:].strip().strip('"').strip("'")
            else:
                instructions = content
        else:
            instructions = content
        
        if not name:
            name = file_path.stem
        
        if not description:
            first_line = instructions.split("\n")[0] if instructions else ""
            description = first_line.strip("# ").strip()[:200] if first_line else ""
        
        skill_id = cls._generate_skill_id(name)
        now = datetime.now()
        
        return Skill(
            id=skill_id,
            name=name,
            description=description,
            source="claudcode",
            category="",
            tools=[],
            workflow={
                "type": "single",
                "description": description,
                "source": "claudcode",
                "skill_file": str(file_path),
            },
            disclosure_level=DisclosureLevel.INSTRUCTIONS,
            version="1.0.0",
            enabled=True,
            metadata={
                "_claudcode": {
                    "path": str(file_path),
                    "instructions_preview": instructions[:500],
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
    def is_claudcode_skill(cls, skill_id: str) -> bool:
        """判断是否为 ClaudeCode skill
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            是否为 ClaudeCode skill
        """
        return skill_id.startswith(cls.ID_PREFIX)
    
    @classmethod
    def get_skill(cls, skill_id: str) -> Skill | None:
        """获取指定 ClaudeCode 技能
        
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
