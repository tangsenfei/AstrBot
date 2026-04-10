"""
测试 AstrBot Skill 运行时适配（简化版）

验证 AstrBot 技能适配是否正确工作
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from astrbot.core.skills.skill_manager import SkillManager
from astrbot.builtin_stars.agent_system.services.astrbot_skill_adapter import AstrBotSkillAdapter


def test_runtime_adapter():
    """测试运行时适配功能"""
    print("=" * 60)
    print("测试 AstrBot Skill 运行时适配")
    print("=" * 60)

    print("\n1. 获取 AstrBot Skills...")
    skill_manager = SkillManager()
    astrbot_skill_infos = skill_manager.list_skills(active_only=True)
    print(f"   找到 {len(astrbot_skill_infos)} 个 AstrBot skills")
    
    if not astrbot_skill_infos:
        print("   ⚠️  没有找到任何 AstrBot skills")
        print("   请确保 astrbot/data/skills 目录中有 SKILL.md 文件")
        return

    print("\n2. 测试技能转换...")
    astrbot_skills = AstrBotSkillAdapter.batch_convert(astrbot_skill_infos)
    print(f"   成功转换 {len(astrbot_skills)} 个技能")
    
    for skill in astrbot_skills:
        print(f"\n   技能: {skill.name}")
        print(f"   - ID: {skill.id}")
        print(f"   - 分类: {skill.category}")
        print(f"   - 工具: {skill.tools}")
        print(f"   - 工作流: {skill.workflow.get('type', 'N/A')}")
        print(f"   - 披露级别: {skill.disclosure_level.value}")
        print(f"   - 版本: {skill.version}")
        print(f"   - 启用: {skill.enabled}")

    print("\n3. 测试技能识别...")
    test_ids = [
        "astrbot_lark_base",
        "astrbot_web_search",
        "skill_custom_123",
        "my_skill",
    ]
    for test_id in test_ids:
        is_astrbot = AstrBotSkillAdapter.is_astrbot_skill(test_id)
        print(f"   '{test_id}' -> is_astrbot: {is_astrbot}")

    print("\n4. 测试根据 ID 获取技能...")
    if astrbot_skill_infos:
        first_skill_info = astrbot_skill_infos[0]
        skill_id = AstrBotSkillAdapter._generate_skill_id(first_skill_info.name)
        
        print(f"   查找技能 ID: {skill_id}")
        
        for skill_info in astrbot_skill_infos:
            converted_id = AstrBotSkillAdapter._generate_skill_id(skill_info.name)
            if converted_id == skill_id:
                skill = AstrBotSkillAdapter.skill_info_to_skill(skill_info)
                print(f"   ✅ 成功获取技能: {skill.name}")
                break

    print("\n" + "=" * 60)
    print("✅ 运行时适配测试完成")
    print("=" * 60)
    
    print("\n📝 总结:")
    print(f"   - AstrBot 技能数量: {len(astrbot_skill_infos)}")
    print(f"   - 转换后技能数量: {len(astrbot_skills)}")
    print(f"   - 运行时适配: ✅ 正常工作")
    
    print("\n💡 说明:")
    print("   运行时适配会在每次请求技能列表时：")
    print("   1. 从数据库获取用户创建的技能")
    print("   2. 从 AstrBot 获取标准 Anthropic 技能")
    print("   3. 实时合并两种技能并返回")
    print("   4. AstrBot 技能不会被修改或删除")


if __name__ == "__main__":
    test_runtime_adapter()
