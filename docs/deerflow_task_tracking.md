# DeerFlow 任务追踪模块使用指南

## 概述

任务追踪模块提供对 DeerFlow 任务拆解情况的实时追踪，支持人工介入调整和执行进展监控。

## 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AstrBot 任务追踪系统                                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      DeerFlowTaskTracker                               │  │
│  │  - fetch_tasks_from_deerflow()  从 DeerFlow 获取任务                   │  │
│  │  - update_task_status()         更新任务状态                           │  │
│  │  - add_task() / remove_task()   添加/删除任务                          │  │
│  │  - sync_tasks_to_deerflow()     同步回 DeerFlow                        │  │
│  │  - watch_task_progress()        实时监控进度                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    TaskInterventionManager                              │  │
│  │  - modify_task_content()        修改任务内容                           │  │
│  │  - split_task()                 拆分任务                               │  │
│  │  - merge_tasks()                合并任务                               │  │
│  │  - request_intervention()       请求人工介入                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      REST API Endpoints                                 │  │
│  │  GET  /deerflow/tasks/{thread_id}              获取任务计划            │  │
│  │  GET  /deerflow/tasks/{thread_id}/progress     获取进度报告            │  │
│  │  POST /deerflow/tasks/{thread_id}/tasks        添加任务                │  │
│  │  PATCH /deerflow/tasks/{thread_id}/tasks/{i}   更新状态                │  │
│  │  POST /deerflow/tasks/{thread_id}/sync         同步到 DeerFlow         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP/SSE
                                      ▼
                           ┌─────────────────────┐
                           │  LangGraph Server   │
                           │  (DeerFlow 核心)    │
                           │                     │
                           │  - write_todos 工具 │
                           │  - TodoMiddleware   │
                           └─────────────────────┘
```

## 快速开始

### 1. 初始化任务追踪器

```python
from astrbot.core.agent.runners.deerflow.deerflow_api_client import DeerFlowAPIClient
from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import DeerFlowTaskTracker
from astrbot.core.agent.runners.deerflow.deerflow_task_api import init_task_tracker

# 创建 API 客户端
api_client = DeerFlowAPIClient(base_url="http://127.0.0.1:2024")

# 创建任务追踪器
task_tracker = DeerFlowTaskTracker(
    api_client=api_client,
    storage_path="data/task_plans",  # 可选：持久化存储路径
)

# 初始化 API
init_task_tracker(task_tracker)
```

### 2. 获取任务计划

```python
# 从 DeerFlow 获取任务列表
thread_id = "your-thread-id"
plan = await task_tracker.fetch_tasks_from_deerflow(thread_id)

print(f"总任务数: {plan.total_tasks}")
print(f"已完成: {plan.completed_tasks}")
print(f"进度: {plan.progress_percentage}%")

# 打印所有任务
for i, task in enumerate(plan.tasks):
    print(f"[{i}] [{task.status.value}] {task.content}")
```

### 3. 监控任务进度

```python
# 定义进度变化回调
async def on_progress_update(plan: TaskPlan):
    print(f"进度更新: {plan.completed_tasks}/{plan.total_tasks}")
    for task in plan.tasks:
        if task.status == TaskStatus.IN_PROGRESS:
            print(f"  正在执行: {task.content}")

# 开始监控
await task_tracker.watch_task_progress(
    thread_id=thread_id,
    callback=on_progress_update,
    interval=5.0,  # 每 5 秒检查一次
)
```

## 人工介入操作

### 1. 修改任务内容

```python
from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import TaskInterventionManager

intervention_manager = TaskInterventionManager(task_tracker)

# 修改任务内容
success = await intervention_manager.modify_task_content(
    thread_id=thread_id,
    task_index=0,
    new_content="修改后的任务内容",
)
```

### 2. 拆分任务

```python
# 将一个任务拆分为多个子任务
success = await intervention_manager.split_task(
    thread_id=thread_id,
    task_index=0,
    subtasks=[
        "子任务 1: 分析需求",
        "子任务 2: 设计方案",
        "子任务 3: 实现代码",
    ],
)
```

### 3. 合并任务

```python
# 合并多个任务
success = await intervention_manager.merge_tasks(
    thread_id=thread_id,
    task_indices=[1, 2, 3],  # 要合并的任务索引
    merged_content="合并后的任务内容",
)
```

### 4. 添加/删除任务

```python
# 添加新任务
task = await task_tracker.add_task(
    thread_id=thread_id,
    content="新增的任务",
    position=0,  # 可选：插入位置
)

# 删除任务
success = await task_tracker.remove_task(
    thread_id=thread_id,
    task_index=2,
)
```

### 5. 更新任务状态

```python
# 更新任务状态
task = await task_tracker.update_task_status(
    thread_id=thread_id,
    task_index=0,
    new_status=TaskStatus.COMPLETED,
)

# 标记任务失败
task = await task_tracker.update_task_status(
    thread_id=thread_id,
    task_index=1,
    new_status=TaskStatus.FAILED,
    error_message="执行出错: XXX",
)
```

### 6. 同步回 DeerFlow

```python
# 将修改后的任务列表同步回 DeerFlow
success = await task_tracker.sync_tasks_to_deerflow(thread_id)
```

## REST API 使用

### 获取任务计划

```bash
GET /deerflow/tasks/{thread_id}
```

响应：
```json
{
  "thread_id": "xxx",
  "tasks": [
    {"content": "任务1", "status": "completed"},
    {"content": "任务2", "status": "in_progress"},
    {"content": "任务3", "status": "pending"}
  ],
  "summary": {
    "total": 3,
    "completed": 1,
    "pending": 1,
    "in_progress": 1,
    "progress_percentage": 33.33
  }
}
```

### 获取进度报告

```bash
GET /deerflow/tasks/{thread_id}/progress
```

### 添加任务

```bash
POST /deerflow/tasks/{thread_id}/tasks
Content-Type: application/json

{
  "content": "新任务内容",
  "position": 0
}
```

### 更新任务状态

```bash
PATCH /deerflow/tasks/{thread_id}/tasks/0
Content-Type: application/json

{
  "status": "completed"
}
```

### 同步到 DeerFlow

```bash
POST /deerflow/tasks/{thread_id}/sync
```

## 与 AstrBot 集成

### 在 Agent Runner 中使用

```python
from astrbot.core.agent.runners.deerflow.deerflow_agent_runner import DeerFlowAgentRunner
from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import DeerFlowTaskTracker

class EnhancedDeerFlowAgentRunner(DeerFlowAgentRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_tracker = DeerFlowTaskTracker(
            api_client=self.api_client,
            storage_path="data/task_plans",
        )
    
    async def on_message(self, message: ProviderRequest) -> None:
        # 获取当前任务进度
        plan = await self.task_tracker.fetch_tasks_from_deerflow(
            thread_id=self.thread_id
        )
        
        # 如果有进行中的任务，显示进度
        if plan and plan.in_progress_tasks > 0:
            progress_msg = f"当前进度: {plan.completed_tasks}/{plan.total_tasks}"
            await self.send_message(progress_msg)
        
        # 继续正常处理
        await super().on_message(message)
    
    async def on_task_update(self, task_update: dict) -> None:
        """任务更新回调"""
        task_index = task_update.get("task_index")
        new_status = task_update.get("status")
        
        # 更新本地追踪
        await self.task_tracker.update_task_status(
            thread_id=self.thread_id,
            task_index=task_index,
            new_status=new_status,
        )
        
        # 通知用户
        if new_status == "completed":
            await self.send_message(f"✅ 任务 {task_index + 1} 已完成")
```

## 任务状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 待执行 |
| `in_progress` | 执行中 |
| `completed` | 已完成 |
| `failed` | 执行失败 |
| `cancelled` | 已取消 |

## 最佳实践

### 1. 启用 Plan Mode

在 DeerFlow 中启用 Plan Mode 以获得更好的任务追踪：

```python
# 在调用 DeerFlow 时启用 plan mode
config = {
    "configurable": {
        "thread_id": thread_id,
        "is_plan_mode": True,  # 启用任务追踪
    }
}
```

### 2. 定期同步

```python
# 设置定期同步任务
async def periodic_sync():
    while True:
        await asyncio.sleep(60)  # 每分钟同步一次
        await task_tracker.sync_tasks_to_deerflow(thread_id)
```

### 3. 进度通知

```python
# 在聊天中显示进度
async def notify_progress(thread_id: str, chat_id: str):
    report = await task_tracker.get_progress_report(thread_id)
    
    message = f"""📊 任务进度报告
    
总任务: {report['total_tasks']}
已完成: {report['completed']}
进行中: {report['in_progress']}
待执行: {report['pending']}
进度: {report['progress_percentage']}%
"""
    await send_to_chat(chat_id, message)
```

## 文件结构

```
astrbot/core/agent/runners/deerflow/
├── deerflow_task_tracker.py      # 任务追踪核心模块
├── deerflow_task_api.py          # REST API 端点
├── deerflow_skills_bridge.py     # Skills 桥接器
├── deerflow_tools_bridge.py      # Tools 桥接器
├── deerflow_integration_manager.py # 统一集成管理器
├── deerflow_agent_runner.py      # Agent 运行器
└── deerflow_api_client.py        # API 客户端
```
