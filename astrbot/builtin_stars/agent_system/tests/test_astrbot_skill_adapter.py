"""
测试 AstrBot Skill 适配器

验证适配层是否正确工作
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from astrbot.core.skills.skill_manager import SkillManager, SkillInfo
from astrbot.builtin_stars.agent_system.services.astrbot_skill_adapter import AstrBotSkillAdapter


def test_adapter():
    """测试适配器基本功能"""
    print("=" * 60)
    print("测试 AstrBot Skill 适配器")
    print("=" * 60)

    print("\n1. 获取 AstrBot Skills...")
    skill_manager = SkillManager()
    skill_infos = skill_manager.list_skills(active_only=True)

    print(f"   找到 {len(skill_infos)} 个 AstrBot skills")

    if not skill_infos:
        print("   ⚠️  没有找到任何 AstrBot skills，请确保 data/skills 目录中有 SKILL.md 文件")
        return

    print("\n2. 测试单个 Skill 转换...")
    first_skill = skill_infos[0]
    print(f"   原始 Skill: {first_skill.name}")
    print(f"   - description: {first_skill.description[:50]}...")
    print(f"   - metadata: {first_skill.metadata}")
    print(f"   - allowed_tools: {first_skill.allowed_tools}")

    converted = AstrBotSkillAdapter.skill_info_to_skill(first_skill)
    print(f"\n   转换后 Skill: {converted.id}")
    print(f"   - name: {converted.name}")
    print(f"   - category: {converted.category}")
    print(f"   - tools: {converted.tools}")
    print(f"   - workflow: {converted.workflow}")
    print(f"   - disclosure_level: {converted.disclosure_level.value}")
    print(f"   - version: {converted.version}")
    print(f"   - enabled: {converted.enabled}")
    print(f"   - metadata keys: {list(converted.metadata.keys())}")

    print("\n3. 测试批量转换...")
    all_converted = AstrBotSkillAdapter.batch_convert(skill_infos)
    print(f"   成功转换 {len(all_converted)}/{len(skill_infos)} 个 skills")

    print("\n4. 测试 ID 生成...")
    test_names = ["lark-base", "my skill", "test_skill"]
    for name in test_names:
        skill_id = AstrBotSkillAdapter._generate_skill_id(name)
        is_astrbot = AstrBotSkillAdapter.is_astrbot_skill(skill_id)
        print(f"   '{name}' -> '{skill_id}' (is_astrbot: {is_astrbot})")

    print("\n5. 测试分类推断...")
    test_cases = [
        ("web-search", "搜索互联网信息", {}),
        ("data-analysis", "分析数据并生成报告", {}),
        ("code-review", "代码开发工具", {}),
        ("automation-cli", "自动化工具", {"requires": "bins: lark-cli"}),
    ]
    for name, desc, metadata in test_cases:
        skill_info = SkillInfo(
            name=name,
            description=desc,
            path="/test/path",
            active=True,
            metadata=metadata,
        )
        category = AstrBotSkillAdapter._determine_category(skill_info)
        print(f"   '{name}' -> category: {category}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_adapter()
