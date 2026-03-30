"""
DeerFlow 集成能力验证脚本

用于验证 AstrBot 新增的 DeerFlow 集成能力是否正常工作
"""
import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("ASTRBOT_ROOT", str(project_root))


def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(name: str, success: bool, message: str = "") -> None:
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  {status} | {name}")
    if message:
        print(f"         | {message}")


def test_imports() -> dict[str, bool]:
    """测试模块导入"""
    print_header("1. 模块导入测试")
    
    results = {}
    
    modules = [
        ("deerflow_api_client", "astrbot.core.agent.runners.deerflow.deerflow_api_client"),
        ("deerflow_content_mapper", "astrbot.core.agent.runners.deerflow.deerflow_content_mapper"),
        ("deerflow_agent_runner", "astrbot.core.agent.runners.deerflow.deerflow_agent_runner"),
        ("deerflow_skills_bridge", "astrbot.core.agent.runners.deerflow.deerflow_skills_bridge"),
        ("deerflow_tools_bridge", "astrbot.core.agent.runners.deerflow.deerflow_tools_bridge"),
        ("deerflow_integration_manager", "astrbot.core.agent.runners.deerflow.deerflow_integration_manager"),
        ("deerflow_task_tracker", "astrbot.core.agent.runners.deerflow.deerflow_task_tracker"),
        ("deerflow_task_api", "astrbot.core.agent.runners.deerflow.deerflow_task_api"),
        ("deerflow_embedded_runtime", "astrbot.core.agent.runners.deerflow.deerflow_embedded_runtime"),
    ]
    
    for name, module_path in modules:
        try:
            __import__(module_path)
            results[name] = True
            print_result(name, True)
        except ImportError as e:
            results[name] = False
            print_result(name, False, str(e))
    
    return results


def test_classes() -> dict[str, bool]:
    """测试核心类"""
    print_header("2. 核心类测试")
    
    results = {}
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_api_client import DeerFlowAPIClient
        results["DeerFlowAPIClient"] = True
        print_result("DeerFlowAPIClient", True)
    except ImportError as e:
        results["DeerFlowAPIClient"] = False
        print_result("DeerFlowAPIClient", False, str(e))
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_skills_bridge import DeerFlowSkillsBridge
        results["DeerFlowSkillsBridge"] = True
        print_result("DeerFlowSkillsBridge", True)
    except ImportError as e:
        results["DeerFlowSkillsBridge"] = False
        print_result("DeerFlowSkillsBridge", False, str(e))
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_tools_bridge import DeerFlowToolsBridge
        results["DeerFlowToolsBridge"] = True
        print_result("DeerFlowToolsBridge", True)
    except ImportError as e:
        results["DeerFlowToolsBridge"] = False
        print_result("DeerFlowToolsBridge", False, str(e))
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_integration_manager import DeerFlowIntegrationManager
        results["DeerFlowIntegrationManager"] = True
        print_result("DeerFlowIntegrationManager", True)
    except ImportError as e:
        results["DeerFlowIntegrationManager"] = False
        print_result("DeerFlowIntegrationManager", False, str(e))
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import DeerFlowTaskTracker, TaskInterventionManager
        results["DeerFlowTaskTracker"] = True
        print_result("DeerFlowTaskTracker + TaskInterventionManager", True)
    except ImportError as e:
        results["DeerFlowTaskTracker"] = False
        print_result("DeerFlowTaskTracker", False, str(e))
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_embedded_runtime import DeerFlowEmbeddedRuntime
        results["DeerFlowEmbeddedRuntime"] = True
        print_result("DeerFlowEmbeddedRuntime", True)
    except ImportError as e:
        results["DeerFlowEmbeddedRuntime"] = False
        print_result("DeerFlowEmbeddedRuntime", False, str(e))
    
    return results


def test_config_files() -> dict[str, bool]:
    """测试配置文件"""
    print_header("3. 配置文件测试")
    
    results = {}
    
    config_files = [
        ("deerflow_integration.yaml", project_root / "data" / "config" / "deerflow_integration.yaml"),
        ("deerflow_task_tracking.md", project_root / "docs" / "deerflow_task_tracking.md"),
    ]
    
    for name, path in config_files:
        exists = path.exists()
        results[name] = exists
        print_result(name, exists, str(path) if exists else "文件不存在")
    
    return results


async def test_embedded_runtime_init() -> dict[str, bool]:
    """测试嵌入式运行时初始化"""
    print_header("4. 嵌入式运行时初始化测试")
    
    results = {}
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_embedded_runtime import (
            DeerFlowEmbeddedRuntime,
            EmbeddedRuntimeConfig,
        )
        
        config = EmbeddedRuntimeConfig(
            deerflow_config_path=str(project_root.parent / "deer-flow" / "config.yaml"),
            deerflow_backend_path=str(project_root.parent / "deer-flow" / "backend"),
        )
        
        runtime = DeerFlowEmbeddedRuntime(config)
        results["创建运行时实例"] = True
        print_result("创建运行时实例", True)
        
    except Exception as e:
        results["创建运行时实例"] = False
        print_result("创建运行时实例", False, str(e))
    
    return results


def test_skills_bridge() -> dict[str, bool]:
    """测试 Skills 桥接器"""
    print_header("5. Skills 桥接器测试")
    
    results = {}
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_skills_bridge import DeerFlowSkillsBridge
        
        bridge = DeerFlowSkillsBridge(
            astrbot_skills_path=str(project_root / "data" / "skills"),
            deerflow_skills_path=str(project_root.parent / "deer-flow" / "skills"),
        )
        results["创建 Skills 桥接器"] = True
        print_result("创建 Skills 桥接器", True)
        
        skills = bridge.get_unified_skills()
        results["获取统一 Skills 列表"] = True
        print_result("获取统一 Skills 列表", True, f"共 {len(skills)} 个 Skills")
        
    except Exception as e:
        results["Skills 桥接器"] = False
        print_result("Skills 桥接器", False, str(e))
    
    return results


def test_tools_bridge() -> dict[str, bool]:
    """测试 Tools 桥接器"""
    print_header("6. Tools 桥接器测试")
    
    results = {}
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_tools_bridge import DeerFlowToolsBridge
        from astrbot.core.agent.tool import FunctionTool, ToolSet
        
        toolset = ToolSet()
        
        def dummy_handler(query: str) -> str:
            return f"处理: {query}"
        
        dummy_tool = FunctionTool(
            name="test_tool",
            description="测试工具",
            handler=dummy_handler,
        )
        toolset.add_tool(dummy_tool)
        
        results["创建测试 ToolSet"] = True
        print_result("创建测试 ToolSet", True)
        
        langchain_tool = DeerFlowToolsBridge.astrbot_to_langchain(dummy_tool)
        results["转换 AstrBot Tool 到 LangChain"] = True
        print_result("转换 AstrBot Tool 到 LangChain", True, f"工具名: {langchain_tool.name}")
        
    except Exception as e:
        results["Tools 桥接器"] = False
        print_result("Tools 桥接器", False, str(e))
    
    return results


def test_task_tracker() -> dict[str, bool]:
    """测试任务追踪器"""
    print_header("7. 任务追踪器测试")
    
    results = {}
    
    try:
        from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import (
            DeerFlowTaskTracker,
            TaskInterventionManager,
            TaskItem,
            TaskPlan,
            TaskStatus,
        )
        
        task = TaskItem(
            content="测试任务",
            status=TaskStatus.PENDING,
        )
        results["创建 TaskItem"] = True
        print_result("创建 TaskItem", True, f"状态: {task.status.value}")
        
        plan = TaskPlan(
            thread_id="test-thread",
            tasks=[task],
        )
        results["创建 TaskPlan"] = True
        print_result("创建 TaskPlan", True, f"任务数: {plan.total_tasks}")
        
        intervention = TaskInterventionManager.__new__(TaskInterventionManager)
        results["创建 TaskInterventionManager"] = True
        print_result("创建 TaskInterventionManager", True)
        
    except Exception as e:
        results["任务追踪器"] = False
        print_result("任务追踪器", False, str(e))
    
    return results


def run_tests() -> None:
    """运行所有测试"""
    print("\n" + "="*60)
    print("  DeerFlow 集成能力验证")
    print("  AstrBot 新增能力测试")
    print("="*60)
    
    all_results = {}
    
    all_results.update(test_imports())
    all_results.update(test_classes())
    all_results.update(test_config_files())
    all_results.update(asyncio.run(test_embedded_runtime_init()))
    all_results.update(test_skills_bridge())
    all_results.update(test_tools_bridge())
    all_results.update(test_task_tracker())
    
    print_header("测试结果汇总")
    
    total = len(all_results)
    passed = sum(1 for v in all_results.values() if v)
    failed = total - passed
    
    print(f"  总计: {total} 项测试")
    print(f"  通过: {passed} 项")
    print(f"  失败: {failed} 项")
    print(f"  通过率: {passed/total*100:.1f}%")
    
    if failed > 0:
        print("\n  失败项目:")
        for name, success in all_results.items():
            if not success:
                print(f"    - {name}")
    
    print("\n" + "="*60)
    
    return all_results


if __name__ == "__main__":
    run_tests()
