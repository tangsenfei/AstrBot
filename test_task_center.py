"""Standalone test to verify TaskCenter _run_task flow."""
import asyncio
import sys
import time

# Add AstrBot to path
sys.path.insert(0, ".")

async def test_run_task():
    from astrbot.core.langgraph.task_center import TaskCenter
    from astrbot.core.langgraph.task_tools import set_task_center
    from astrbot.core.langgraph.graphs.work_task import build_work_task_graph
    
    TaskCenter.register_executor("work_task", build_work_task_graph)
    
    tc = TaskCenter(checkpointer=None)
    set_task_center(tc)
    
    config = {
        "task_id": "test_task_001",
        "thread_id": "work:test_task_001",
        "task_name": "测试任务",
        "task_desc": "列出3部2026年5月电影",
        "work_task_kind": "single_agent",
        "plan_config": {"enabled": True, "effort": "medium"},
        "review_config": {"enabled": False},
        "executor_config": {"agent_id": "agent_65185663"},
        "input": {"goal": "列出3部2026年5月电影"},
        "session_id": "work",
    }
    
    print("Creating task...")
    record = await tc.create_task(
        task_type="work_task",
        config=config,
        session_id="work",
        run_ctx=None,
    )
    print(f"Task created: {record.task_id}, status: {record.status}")
    
    # Wait for task to run
    print("Waiting 10 seconds...")
    await asyncio.sleep(10)
    
    task = tc.get_task(record.task_id)
    print(f"Final status: {task.status}, error: {task.error}, progress: {task.progress}")
    print(f"Result text: {task.result_text}")

asyncio.run(test_run_task())
