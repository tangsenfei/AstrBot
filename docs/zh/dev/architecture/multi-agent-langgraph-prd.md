# LangGraph 多智能体升级 PRD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan phase-by-phase.

**Goal:** 抛弃 CrewAI，集成 LangGraph Graph API，统一核心 Subagent 与 Agent System 两套多智能体子系统为单一架构。

**Architecture:** ToolLoopAgentRunner 保留为单步引擎（不变）。LangGraph Graph API 负责多步编排（会议/规划/工作流），`@task` 负责并行执行，`interrupt()` 提供人类审批介入。核心新增 `astrbot/core/langgraph/` 模块作为编排层，约 600 行业务代码。

**Tech Stack:** Python 3.12+, LangGraph >=1.0, asyncio, SqliteSaver (checkpoint), 不再依赖 CrewAI。

---

## 一、现状与问题

### 1.1 当前架构

```
┌─ 核心 Chat 流程 ─────────────────────┐
│ MainAgent → ToolLoopAgentRunner       │  单 Agent 循环（优秀）
│   └─ HandoffTool → ctx.tool_loop_agent()  │  子 Agent 委托（单层）
└───────────────────────────────────────┘
                    ╳ 无连接
┌─ Agent System (builtin_stars) ───────┐
│ RoundtableService + 10 MeetingStrategies │  圆桌讨论（1716 行，大量重复）
│ FlowService (DAG 工作流)              │  手写拓扑排序，AND/OR 是空壳
│ CrewService (CrewAI 代理)             │  500MB 依赖，降级方案无工具无上下文
│ crewai_integration.py (897 行)        │  桥接层，Planning/Memory 从未启用
└──────────────────────────────────────┘
```

### 1.2 核心缺陷

| 问题 | 影响 |
|------|------|
| 两套多 Agent 系统互不通信 | Chat 无法发起会议，会议无法委托子 Agent |
| CrewAI 500MB+ 依赖但核心能力禁用 | 磁盘浪费 + 启动慢 + 安全攻击面 |
| MeetingStrategies 1716 行复制粘贴 | 加第 11 种策略需复制 150 行循环代码 |
| FlowService AND/OR 空壳 | 声称支持并行但实际串行 |
| 测试仪表盘独立实现 Agent Loop | 测试与生产行为不一致 |
| 无检查点/恢复机制 | 后台子 Agent 崩溃后无法从断点继续 |
| 无人类审批介入 | 规划→执行全自动，不可干预 |

---

## 二、核心动线：从用户消息到任务完成

这是整个系统的主交互循环。所有多智能体能力都围绕这条动线展开。

### 2.1 完整流程图

```
用户消息
  │
  ▼
┌─ 主 Agent（ToolLoopAgentRunner）──────────────────────┐
│  system_prompt 包含：                                  │
│    "你是一个任务调度助手。收到用户需求后,首先判断:       │
│     1. 简单问答 → 直接回答                              │
│     2. 需要异步处理的任务 → 理解需求后调用 confirm_task  │
│        工具向用户确认,确认后调用 create_task 创建任务"    │
│                                                        │
│  可用工具：                                             │
│    - confirm_task(task_type, summary, detail)          │
│    - create_task(task_type, config)                    │
│    - get_task_status(task_id)                          │
│    - transfer_to_*（子 Agent 委托）                     │
│    - transfer_to_meeting（发起会议）                    │
│    - transfer_to_plan_execute（发起规划执行）            │
│    - 其他日常工具...                                    │
└────────────────────────────────────────────────────────┘
  │
  ├─ 简单问答 ──► 直接流式回复用户 ──► 结束
  │
  └─ 异步任务 ──► 调用 confirm_task 工具
        │
        ▼
      ┌─ HITL 确认（LangGraph interrupt）─────────────┐
      │  系统向用户展示:                                 │
      │    "已理解你的需求,将创建以下任务:                 │
      │     类型: 深度调研                                │
      │     摘要: 分析 LangGraph 在 AstrBot 中的集成方案   │
      │     详情: [步骤1: 源码分析, 步骤2: 架构对比...]     │
      │     预计时长: ~5 分钟                             │
      │     是否确认? (确认 / 修改需求 / 取消)"            │
      │                                                  │
      │  HITLInteraction 协议:                            │
      │    - text: 展示给用户的确认信息                     │
      │    - task_card: 任务卡片（结构化数据）              │
      │    - options: ["confirm", "modify", "cancel"]    │
      │    - modify_prompt: "请描述你需要调整的部分"        │
      └──────────────────────────────────────────────────┘
        │
        │ 用户确认 (confirm)
        ▼
      ┌─ 任务中心 (TaskCenter) ──────────────────────┐
      │  create_task(task_type, config, session_id)   │
      │    → task_id = "task_20260502_001"             │
      │    → 状态: CREATED                             │
      │    → 通知用户: "任务已创建 [#001],正在执行..."  │
      │                                                │
      │  dispatch(task)                                │
      │    → 根据 task_type 选择执行器:                  │
      │                                                │
      │  ┌─ 执行器注册表 ─────────────────────────┐    │
      │  │ task_type       → 执行器                │    │
      │  │ "plan_execute"  → PlanExecuteGraph      │    │
      │  │ "meeting"       → MeetingGraph           │    │
      │  │ "workflow"      → WorkflowGraph           │    │
      │  │ "crew"          → CrewGraph               │    │
      │  │ "deep_research" → DeepResearchGraph        │    │
      │  └────────────────────────────────────────┘    │
      │                                                │
      │  执行过程: 流式推送状态给用户                     │
      │    - 用户看到实时进度:                            │
      │      "🔍 [任务 #001] 正在分析源码..."            │
      │      "🔍 [任务 #001] 正在对比架构..."            │
      │      "✅ [任务 #001] 已完成"                     │
      │    - 结果以 MessageChain 形式推送                │
      │                                                │
      │  任务生命周期:                                   │
      │    CREATED → DISPATCHED → RUNNING → DONE/FAILED │
      │    任意状态可 → PAUSED (checkpoint) → RESUMED    │
      └────────────────────────────────────────────────┘
        │
        ▼
      执行器内部（LangGraph StateGraph）
        │
        ├─ 每个 Step = AgentOperator → ToolLoopAgentRunner
        ├─ 流式输出经 StreamEvent 协议回传给用户
        ├─ 任意节点可 interrupt() 暂停等待人类输入
        └─ 完成/失败 → 更新 TaskCenter 状态
```

### 2.2 主 Agent 的 Triage Logic

主 Agent 的判断逻辑通过 **system prompt + 专用工具** 实现，不硬编码分类器：

```python
# 注入主 Agent system prompt 的任务调度指令
MAIN_AGENT_TRIAGE_PROMPT = """
## Task Scheduling

You are a task scheduling assistant. When you receive a user request:

1. **Simple Q&A**: If the request can be answered in a single response without multi-step
   research, analysis, or external operations → answer directly.

2. **Async Task**: If the request requires multi-step execution (deep research, code analysis,
   batch operations, multi-agent meetings, workflow execution) → follow this flow:
   
   a. Use `confirm_task` to summarize your understanding and ask the user to confirm.
   b. Once confirmed, use `create_task` to create the task. The task will be executed
      asynchronously and the user will receive progress updates.
   c. The user can check status with `get_task_status` at any time.

**When to use async tasks:**
- Multi-step research or analysis ("帮我调研...", "分析一下...")
- Batch operations ("把所有这些文件...", "批量处理...")
- Multi-agent collaboration ("开个会讨论...", "让多个角色评估...")
- Long-running operations ("扫描整个项目...", "生成完整报告...")

**When NOT to use async tasks:**
- Quick questions ("今天天气?", "这个函数怎么用?")
- Single-turn code generation ("写一个排序函数")
- Simple explanations ("解释一下这段代码")
"""
```

### 2.3 HITL 统一交互协议

所有需要人工确认/审批/修改的场景，使用同一套 `HITLInteraction` 协议：

```python
@dataclass
class HITLInteraction:
    """统一的 Human-in-the-Loop 交互协议。
    
    用途：任务确认、审批暂停、需求修改、中断介入。
    所有 HITL 场景复用此结构，前端据此渲染交互 UI。
    """
    interaction_id: str            # 唯一 ID，用于 resume 时匹配
    type: Literal[
        "task_confirm",            # 任务创建确认
        "plan_approval",           # 执行计划审批
        "workflow_human_node",     # 工作流人工节点
        "error_recovery",          # 错误后人工决策
        "clarification",           # 需求澄清
    ]
    prompt: str                    # 展示给用户的提示信息
    task_card: TaskCard | None     # 任务卡片（任务相关场景时携带）
    
    options: list[HITLOption]      # 用户可选操作
    default_option: str            # 默认选中
    timeout_seconds: int = 300     # 超时（秒），超时走默认选项

@dataclass
class HITLOption:
    value: str                     # "confirm" | "modify" | "cancel" | ...
    label: str                     # "确认" | "修改需求" | "取消"
    description: str               # 选项说明
    modify_prompt: str = ""        # 仅 modify 选项：引导用户输入修改内容

@dataclass
class TaskCard:
    """任务卡片 — 创建任务前的预览信息。"""
    task_type: str                 # "plan_execute" | "meeting" | "workflow" | ...
    task_type_label: str           # "深度调研" | "圆桌会议" | "工作流" | ...
    summary: str                   # 一句话摘要
    steps_preview: list[str]       # 步骤预览（最多 5 步）
    estimated_duration: str        # "~3 分钟" | "~10 分钟" | "较长"
    agent_count: int               # 涉及的 Agent 数量
    tools_preview: list[str]       # 涉及的工具预览
```

### 2.4 TaskCenter 核心设计

```python
# astrbot/core/langgraph/task_center.py

from enum import Enum
from dataclasses import dataclass, field
from langgraph.graph import StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
import uuid, time, asyncio
from typing import Callable, Awaitable

class TaskStatus(str, Enum):
    CREATED = "created"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    PAUSED = "paused"          # interrupt() 暂停
    RESUMING = "resuming"      # 用户恢复中
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    session_id: str
    thread_id: str             # LangGraph checkpoint thread_id
    status: TaskStatus
    config: dict               # 任务配置（图 State 初始化数据）
    hitl_context: dict | None  # 暂停时的 HITLInteraction 上下文
    result: dict | None
    error: str | None
    created_at: float
    updated_at: float
    
    # 进度推送回调
    stream_callback: Callable[[StreamEvent], Awaitable[None]] | None


class TaskCenter:
    """任务中心：创建、调度、跟踪、恢复异步任务。
    
    职责：
    1. 接收 create_task 请求，创建 TaskRecord
    2. 根据 task_type 选择执行器（graph builder）
    3. 在 asyncio.Task 中运行 LangGraph graph
    4. 将 StreamEvent 通过 stream_callback 推送给用户
    5. 管理任务生命周期和 checkpoint 持久化
    """
    
    EXECUTOR_REGISTRY: dict[str, Callable[..., StateGraph]] = {}
    
    def __init__(self, checkpointer: BaseCheckpointSaver):
        self._checkpointer = checkpointer
        self._tasks: dict[str, TaskRecord] = {}
        self._running_graphs: dict[str, asyncio.Task] = {}
    
    @classmethod
    def register_executor(cls, task_type: str, builder: Callable[..., StateGraph]):
        """注册执行器。各 graph 模块在初始化时调用。"""
        cls.EXECUTOR_REGISTRY[task_type] = builder
    
    async def create_task(
        self,
        task_type: str,
        config: dict,
        session_id: str,
        stream_callback: Callable[[StreamEvent], Awaitable[None]],
    ) -> TaskRecord:
        """创建任务并立即异步调度执行。"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        thread_id = f"{session_id}:{task_id}"
        
        task = TaskRecord(
            task_id=task_id,
            task_type=task_type,
            session_id=session_id,
            thread_id=thread_id,
            status=TaskStatus.CREATED,
            config=config,
            hitl_context=None,
            result=None,
            error=None,
            created_at=time.time(),
            updated_at=time.time(),
            stream_callback=stream_callback,
        )
        self._tasks[task_id] = task
        
        # 异步启动执行
        asyncio.create_task(self._run_task(task))
        return task
    
    async def _run_task(self, task: TaskRecord):
        """内部：运行任务图。"""
        builder = self.EXECUTOR_REGISTRY.get(task.task_type)
        if not builder:
            task.status = TaskStatus.FAILED
            task.error = f"Unknown task_type: {task.task_type}"
            return
        
        graph = builder(config=task.config, checkpointer=self._checkpointer)
        task.status = TaskStatus.RUNNING
        
        try:
            async for event in graph.astream_events(
                task.config,
                config={"configurable": {"thread_id": task.thread_id}},
                version="v2",
            ):
                if event["event"] == "on_custom_event":
                    stream_event = event["data"]
                    if task.stream_callback:
                        await task.stream_callback(stream_event)
                
                elif event["event"] == "on_interrupt":
                    task.status = TaskStatus.PAUSED
                    task.hitl_context = event["data"]
                    return  # 等待 resume_task() 调用
            
            task.status = TaskStatus.DONE
            task.result = {"output": "Task completed"}
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
    
    async def resume_task(self, task_id: str, resume_value: Any):
        """恢复暂停的任务。"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            raise ValueError(f"Task {task_id} is not paused")
        
        task.status = TaskStatus.RESUMING
        builder = self.EXECUTOR_REGISTRY[task.task_type]
        graph = builder(config=task.config, checkpointer=self._checkpointer)
        
        from langgraph.types import Command
        async for event in graph.astream_events(
            Command(resume=resume_value),
            config={"configurable": {"thread_id": task.thread_id}},
            version="v2",
        ):
            # ... same event handling
            pass
    
    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)
    
    def list_tasks(self, session_id: str) -> list[TaskRecord]:
        return [t for t in self._tasks.values() if t.session_id == session_id]
```

### 2.5 confirm_task / create_task 工具

这两个工具是主 Agent 与 TaskCenter 的桥梁，注册为 FunctionTool：

```python
# astrbot/core/langgraph/task_tools.py

def confirm_task_tool(
    task_type: str,       # "plan_execute" | "meeting" | "workflow" | "crew"
    summary: str,         # 一句话摘要
    detail: str,          # 详细描述
    estimated_steps: int = 3,
) -> HITLInteraction:
    """主 Agent 调用此工具向用户发起任务确认。
    
    此工具内部调用 LangGraph 的 interrupt() 机制暂停当前对话，
    展示任务预览卡片，等待用户确认/修改/取消。
    确认后由调用方继续执行 create_task。
    """
    ...

def create_task_tool(
    task_type: str,
    config: dict,          # 任务配置（对应于 State 初始化数据）
    session_id: str,
) -> TaskRecord:
    """主 Agent 调用此工具在 TaskCenter 中创建异步任务。
    
    返回 TaskRecord，主 Agent 据此告知用户任务已创建。
    后续用户可通过 get_task_status 查询进度。
    """
    ...
```

### 2.6 对比：当前 vs 目标

| 环节 | 当前（无统一动线） | 目标（LangGraph 后） |
|------|-------------------|---------------------|
| 任务识别 | 无，用户需手动在 UI 选择 Meeting/Crew/Flow | 主 Agent 自动判断，对话中自然触发 |
| 需求确认 | 无 HITL，直接执行 | `confirm_task` → `interrupt()` → 用户确认/修改 |
| 任务创建 | 各自 Service 直接执行 | 统一 `TaskCenter.create_task()` |
| 任务调度 | 各自为政，无统一入口 | `TaskCenter` 统一管理生命周期 |
| 状态推送 | Roundtable 有 SSE，其他无 | 所有执行器统一通过 `StreamEvent` 推送 |
| 暂停恢复 | 不支持 | `interrupt()` + checkpoint 全场景支持 |
| 取消任务 | 不支持 | `TaskCenter.cancel_task()` |
| 历史查询 | DB 中有 AgentTask 记录但无统一视图 | `TaskCenter.list_tasks()` + task 状态查询 |

---

## 三、目标架构

```
用户消息
  │
  ▼
┌─ 主 Agent（ToolLoopAgentRunner）────────────────────────┐
│  功能：意图识别 + 简单问答 + 任务调度                      │
│  工具：confirm_task, create_task, get_task_status,       │
│        transfer_to_*, 日常工具...                         │
└──────────────────────────────────────────────────────────┘
  │                        │
  │ 简单问答                │ 异步任务
  ▼                        ▼
 直接回复          ┌─ HITL 确认 ──────────────────────────┐
 完成              │  interrupt() → 用户 confirm/modify     │
                   └──────────────────────────────────────┘
                        │ 用户确认
                        ▼
                   ┌─ 任务中心 (TaskCenter) ──────────────┐
                   │  create → dispatch → track → resume  │
                   │                                        │
                   │  ┌─ 执行器注册表 ────────────────┐    │
                   │  │ plan_execute → PlanExecuteGraph│    │
                   │  │ meeting      → MeetingGraph    │    │
                   │  │ workflow     → WorkflowGraph   │    │
                   │  │ crew         → CrewGraph       │    │
                   │  │ deep_research→ ResearchGraph   │    │
                   │  └───────────────────────────────┘    │
                   └──────────────────────────────────────┘
                        │
                        ▼
                   LangGraph StateGraph（执行器）
                        │
                        ├─ 每个节点 → AgentOperator → ToolLoopAgentRunner
                        ├─ 流式输出 → StreamEvent → 推送用户
                        ├─ 任意点 → interrupt() → 暂停等待人类
                        └─ 完成 → TaskCenter.update_status(DONE)
```

**关键不变项：**
- ToolLoopAgentRunner 所有 1433 行原封不动，作为 AgentOperator 的单步引擎
- 现有 Pipeline（`InternalAgentSubStage` → `run_agent()`）保持不变，处理主 Agent 的简单问答
- `SubAgentOrchestrator` 保留，其 HandoffTool 继续在主 Agent toolset 中工作

**新增顶层概念：**
- **TaskCenter**：统一的任务生命周期管理器，取代各 Service 各自管理执行的方式
- **HITL 协议**：所有需要人类参与的交互点（确认/审批/修改/澄清）复用同一套 `HITLInteraction`
- **StreamEvent**：所有执行器的输出统一为此协议，前端只需对接一套格式

---

## 三、新增模块结构

```
astrbot/core/langgraph/                    # 新增模块，~1000 行
├── __init__.py                            # 公开 API
├── state.py                               # State / StreamEvent / HITLInteraction (~200 行)
├── operators.py                           # AgentOperator / HumanOperator (~120 行)
├── adapters.py                            # Provider / ToolSet → callable (~80 行)
├── checkpoint.py                          # SqliteSaver 工厂 (~40 行)
├── task_center.py                         # 任务中心 + 执行器注册表 (~200 行)
├── task_tools.py                          # confirm_task / create_task 工具 (~100 行)
└── graphs/
    ├── __init__.py
    ├── meeting.py                         # 会议图构建器 (~150 行)
    ├── plan_execute.py                    # 规划→执行→审批图 (~120 行)
    ├── workflow.py                        # 工作流 DAG 构建器 (~130 行)
    └── crew.py                            # Crew 编排图 (~80 行)
```

**新增文件说明：** `task_center.py` 和 `task_tools.py` 是实现用户消息 → HITL确认 → 任务调度 → 异步执行 这条核心动线的关键组件。

---

## 四、核心交互协议: AgentResponseStream

### 4.1 问题

LangGraph 的 `StreamWriter` 和 ToolLoopAgentRunner 的 `AgentResponse` 数据结构不兼容，需要一个统一的流式协议让图的节点能回传：

- 流式文本 chunk（给用户看）
- 工具调用状态（"正在使用 xx 工具..."）
- 工具调用结果
- 思考过程（reasoning）
- 错误 / 中断信号

### 4.2 设计

```python
# astrbot/core/langgraph/state.py

from typing import TypedDict, Literal, NotRequired, Any
from dataclasses import dataclass, field
import time
import uuid


# ============================================================
# 流式事件协议 — LangGraph 节点与外部世界的通信管道
# ============================================================

class StreamEvent(TypedDict):
    """LangGraph custom stream event, carried via writer()."""
    event: Literal[
        "text_delta",       # 流式文本片段
        "tool_call",        # 工具调用开始
        "tool_result",      # 工具调用结果
        "reasoning",        # 思考过程
        "error",            # 节点级错误
        "phase",            # 阶段切换（规划→执行→总结）
        "interrupt",        # 等待人类输入
    ]
    data: dict[str, Any]
    timestamp: float
    node_id: str            # 来源节点，前端可按节点分组渲染


@dataclass
class GraphRunContext:
    """LangGraph 图运行时上下文 — 携带 AstrBot 的 Provider/ToolExecutor/Hooks。"""
    provider: Any           # astrbot.core.provider.provider.Provider
    tool_executor: Any      # astrbot.core.astr_agent_tool_exec.FunctionToolExecutor
    hooks: Any              # astrbot.core.agent.hooks.BaseAgentRunHooks
    astr_event: Any         # astrbot.core.platform.astr_message_event.AstrMessageEvent
    config: dict[str, Any]  # runner_kwargs: max_steps, streaming, tool_schema_mode, ...

    # LangGraph 相关
    writer: Any = None      # langgraph.types.StreamWriter，在节点调用时注入
    interrupt_event: Any = None  # 当 graph 暂停时用于等待用户输入


# ============================================================
# 图节点 State 定义
# ============================================================

class AgentGraphState(TypedDict, total=False):
    """单 Agent 图的基础 State。"""
    system_prompt: str
    user_prompt: str
    messages: list[dict[str, Any]]      # {"role": "...", "content": "..."}
    image_urls: list[str]
    func_tools: NotRequired[list[str]]  # 工具名列表（在 Operator 内解析为 ToolSet）


class AgentGraphResult(TypedDict, total=False):
    """Agent 节点运行结果。"""
    final_text: str
    tool_calls: list[dict[str, Any]]
    error: NotRequired[str]
    stats: NotRequired[dict[str, Any]]  # AgentStats.to_dict()


class MeetingState(AgentGraphState):
    """会议图 State。"""
    topic: str
    participants: list[dict[str, Any]]   # [{id, name, system_prompt, provider_id, tools}]
    host: NotRequired[dict[str, Any]]
    strategy: str                        # "standard"|"brainstorm"|"parliament"|...
    max_rounds: int
    current_round: int
    round_results: list[str]
    final_minutes: NotRequired[str]


class PlanExecuteState(AgentGraphState):
    """规划→执行图 State。"""
    task: str
    planning_effort: str                 # "low"|"medium"|"high"
    plan_steps: NotRequired[list[dict]]  # [{step_id, description, agent, tools}]
    current_step_index: int
    step_results: list[dict]
    human_approved: NotRequired[bool]


class WorkflowState(AgentGraphState, total=False):
    """工作流图 State。"""
    flow_definition: dict[str, Any]      # Flow JSON 定义
    node_results: dict[str, Any]         # node_id → result
    current_node_id: str


# ============================================================
# 统一入口：图触发请求
# ============================================================

@dataclass
class GraphTriggerRequest:
    """从 HandoffTool / API / Chat 触发 LangGraph 图执行的统一请求。"""
    graph_type: Literal["meeting", "plan_execute", "workflow", "crew", "agent_with_checkpoint"]
    state: dict[str, Any]                # 对应 State 的初始化数据
    session_id: str                      # 用于 checkpoint 持久化的会话 ID
    thread_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


@dataclass
class GraphTriggerResponse:
    """图执行响应 — 区分同步完成、后台运行、等待输入三种模式。"""
    status: Literal["completed", "background", "awaiting_input"]
    thread_id: str
    result: dict[str, Any] | None = None
    interrupt_data: dict[str, Any] | None = None  # 暂停时携带用户提示信息
```

---

## 五、核心组件：AgentOperator

### 5.1 设计

AgentOperator 是 LangGraph 图节点与 ToolLoopAgentRunner 之间的唯一桥梁。**每个需要 LLM + 工具的图节点，最终都通过 AgentOperator 执行。** 它在节点函数内部被调用，负责：

1. 从 State 构造 `ProviderRequest`
2. 创建并 reset `ToolLoopAgentRunner`
3. 迭代 `step_until_done()`，将 `AgentResponse` 转为 `StreamEvent` 并通过 `writer()` 发出
4. 返回 `AgentGraphResult` 作为节点输出

```python
# astrbot/core/langgraph/operators.py

from langgraph.types import StreamWriter
from astrbot.core.agent.runners.tool_loop_agent_runner import ToolLoopAgentRunner
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.hooks import BaseAgentRunHooks
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.provider.func_tool_manager import FunctionToolManager

from .state import AgentGraphState, AgentGraphResult, GraphRunContext, StreamEvent
from .adapters import resolve_provider, resolve_tools


class AgentOperator:
    """将 ToolLoopAgentRunner 的一次完整运行封装为 LangGraph 图节点调用的可复用组件。

    使用方式（在图节点内）:
        operator = AgentOperator()
        result = await operator.execute(state, ctx)
    """

    DEFAULT_MAX_STEPS = 30

    async def execute(
        self,
        state: AgentGraphState,
        run_ctx: GraphRunContext,
        *,
        max_steps: int | None = None,
        write_stream: bool = True,
    ) -> AgentGraphResult:
        """执行一次完整的 Agent 循环。"""
        if max_steps is None:
            max_steps = run_ctx.config.get("max_agent_step", self.DEFAULT_MAX_STEPS)

        # 1. 构造 ProviderRequest
        provider = resolve_provider(state, run_ctx)
        req = ProviderRequest(
            prompt=state.get("user_prompt"),
            system_prompt=state.get("system_prompt"),
            contexts=state.get("messages", []),
            image_urls=state.get("image_urls", []),
            func_tool=resolve_tools(state, run_ctx),
            session_id=state.get("session_id", ""),
            model=state.get("model"),
        )

        # 2. 创建 Runner
        runner = ToolLoopAgentRunner()
        runner.reset(
            provider=provider,
            request=req,
            run_context=ContextWrapper(
                context=run_ctx.astr_event,
                tool_call_timeout=run_ctx.config.get("tool_call_timeout", 60),
            ),
            tool_executor=run_ctx.tool_executor,
            agent_hooks=run_ctx.hooks or _NoopHooks(),
            streaming=run_ctx.config.get("streaming_response", False),
            enforce_max_turns=run_ctx.config.get("enforce_max_turns", -1),
            tool_schema_mode=run_ctx.config.get("tool_schema_mode", "full"),
            fallback_providers=run_ctx.config.get("fallback_providers", []),
            tool_result_overflow_dir=run_ctx.config.get("tool_result_overflow_dir"),
        )

        # 3. 执行循环，流式输出
        tool_calls = []
        final_text = ""
        writer = run_ctx.writer

        async for resp in runner.step_until_done(max_steps):
            event = self._to_stream_event(resp)
            if write_stream and writer and event:
                writer(event)

            if resp.type == "tool_call":
                tool_calls.append(resp.data)
            elif resp.type == "llm_result":
                chain = resp.data.get("chain")
                if chain:
                    final_text = chain.get_plain_text(with_other_comps_mark=True)

        # 4. 返回结果
        return AgentGraphResult(
            final_text=final_text,
            tool_calls=tool_calls,
            stats=runner.stats.to_dict() if runner.stats else {},
        )

    @staticmethod
    def _to_stream_event(resp) -> StreamEvent | None:
        """将 AgentResponse 转为 StreamEvent。"""
        import time
        if resp.type == "streaming_delta":
            chain = resp.data.get("chain")
            if chain and chain.type == "reasoning":
                return StreamEvent(
                    event="reasoning",
                    data={"text": chain.get_plain_text()},
                    timestamp=time.time(),
                    node_id="",
                )
            return StreamEvent(
                event="text_delta",
                data={"text": chain.get_plain_text() if chain else ""},
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "tool_call":
            return StreamEvent(
                event="tool_call",
                data=resp.data,
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "tool_call_result":
            return StreamEvent(
                event="tool_result",
                data=resp.data,
                timestamp=time.time(),
                node_id="",
            )
        if resp.type == "err":
            return StreamEvent(
                event="error",
                data={"message": resp.data.get("chain", {}).get_plain_text() if hasattr(resp.data.get("chain", {}), "get_plain_text") else str(resp.data)},
                timestamp=time.time(),
                node_id="",
            )
        return None


class _NoopHooks(BaseAgentRunHooks):
    """空 Hook 实现，当未提供 hooks 时使用。"""
    pass
```

### 5.2 HumanOperator 设计

```python
class HumanOperator:
    """人类审批节点 — 使用 LangGraph interrupt() 暂停图执行。"""

    @staticmethod
    async def request_approval(
        state: PlanExecuteState,
        run_ctx: GraphRunContext,
        *,
        prompt: str,
    ) -> PlanExecuteState:
        """暂停图执行，等待人类批准。"""
        from langgraph.types import interrupt

        # interrupt() 会暂停图，将控制权返回给调用方
        # 调用方通过 Command(resume=...) 携带批准结果继续执行
        approved = interrupt({
            "type": "human_approval",
            "prompt": prompt,
            "plan": state.get("plan_steps", []),
            "options": ["approve", "reject", "modify"],
        })

        state["human_approved"] = (approved == "approve")
        return state
```

---

## 六、适配器层

```python
# astrbot/core/langgraph/adapters.py

def resolve_provider(state: dict, run_ctx: "GraphRunContext") -> "Provider":
    """从 state 或 run_ctx 解析 Provider。"""
    provider_id = state.get("provider_id") or run_ctx.config.get("provider_id")
    if provider_id:
        from astrbot.core import db_helper
        return db_helper.get_provider_by_id(provider_id)
    return run_ctx.provider


def resolve_tools(state: dict, run_ctx: "GraphRunContext") -> "ToolSet | None":
    """从 state 的工具名列表解析 ToolSet。"""
    tool_names = state.get("func_tools")
    if not tool_names:
        return None

    from astrbot.core.agent.tool import ToolSet
    tool_manager = FunctionToolManager.get_instance()
    tool_set = ToolSet()
    for name in tool_names:
        tool = tool_manager.get_func(name)
        if tool:
            tool_set.add_tool(tool)
    return tool_set if not tool_set.empty() else None
```

---

## 七、检查点层

```python
# astrbot/core/langgraph/checkpoint.py

from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path

def create_checkpointer(db_path: str | Path | None = None) -> SqliteSaver:
    """创建 SqliteSaver 实例用于 LangGraph checkpoint 持久化。"""
    if db_path is None:
        from astrbot.core.utils.path_utils import get_astrbot_data_dir
        db_path = Path(get_astrbot_data_dir()) / "langgraph_checkpoints.db"
    return SqliteSaver.from_conn_string(str(db_path))
```

---

## 八、Phase 0: 基础设施 + 核心动线（第 1-3 周）

> **目标：** LangGraph 集成 + TaskCenter + HITL 协议 + 主 Agent 任务调度能力跑通。

### Task 0.1: 添加 LangGraph 依赖

**修改文件：** `requirements.txt`

- [ ] 添加 `langgraph>=1.0,<2.0`
- [ ] 移除 `crewai>=0.86.0`
- [ ] 运行 `uv sync` 验证安装
- [ ] 运行 `uv run -c "import langgraph; print(langgraph.__version__)"` 确认

### Task 0.2: 创建 `astrbot/core/langgraph/` 模块骨架

**创建文件：**

- `astrbot/core/langgraph/__init__.py`
  ```python
  from .state import (StreamEvent, GraphRunContext, AgentGraphState,
      AgentGraphResult, MeetingState, PlanExecuteState, WorkflowState,
      HITLInteraction, HITLOption, TaskCard, TaskRecord, TaskStatus,
      GraphTriggerRequest, GraphTriggerResponse)
  from .operators import AgentOperator, HumanOperator
  from .adapters import resolve_provider, resolve_tools
  from .checkpoint import create_checkpointer
  from .task_center import TaskCenter
  from .task_tools import confirm_task_tool, create_task_tool, get_task_status_tool
  ```

- `astrbot/core/langgraph/state.py` — 全部 State 定义（含 HITLInteraction/TaskCard/TaskRecord）
- `astrbot/core/langgraph/operators.py` — AgentOperator / HumanOperator
- `astrbot/core/langgraph/adapters.py` — resolve_provider / resolve_tools
- `astrbot/core/langgraph/checkpoint.py` — create_checkpointer
- `astrbot/core/langgraph/task_center.py` — TaskCenter + EXECUTOR_REGISTRY
- `astrbot/core/langgraph/task_tools.py` — confirm_task / create_task / get_task_status
- `astrbot/core/langgraph/graphs/__init__.py`

### Task 0.3: 主 Agent 注入任务调度能力

**修改文件：** `astrbot/core/astr_main_agent.py`

- [ ] 在 `build_main_agent()` 中注入 `MAIN_AGENT_TRIAGE_PROMPT` 到 system_prompt
- [ ] 将 `confirm_task_tool`、`create_task_tool`、`get_task_status_tool` 注册到主 Agent 的 func_tool
- [ ] `confirm_task_tool` 内部调用 LangGraph `interrupt()` 实现 HITL 确认
- [ ] `create_task_tool` 内部调用 `TaskCenter.create_task()` 创建异步任务

### Task 0.4: TaskCenter 与主 Pipeline 对接

**修改文件：** `astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py`

- [ ] 在 `InternalAgentSubStage.initialize()` 中初始化全局 `TaskCenter` 单例
- [ ] 当主 Agent 通过 `create_task_tool` 触发任务创建时，`TaskCenter` 启动异步 graph 执行
- [ ] graph 执行过程中的 `StreamEvent` 通过 `AstrMessageEvent.send()` 推送给用户

### Task 0.5: 核心动线集成测试

- [ ] `tests/test_langgraph_core_flow.py` — 模拟用户消息 → 主 Agent triage → HITL 确认 → TaskCenter 调度 → 简单执行器完成
- [ ] `tests/test_langgraph_state.py` — State 序列化/反序列化
- [ ] `tests/test_langgraph_operators.py` — AgentOperator 集成测试
- [ ] `tests/test_langgraph_adapters.py` — resolve_provider / resolve_tools
- [ ] `tests/test_langgraph_checkpoint.py` — SqliteSaver 读写
- [ ] `tests/test_langgraph_task_center.py` — 任务创建/调度/恢复生命周期

---

## 九、Phase 1: 清理与统一（第 2-4 周）

### Task 1.1: 移除 CrewAI 依赖

**修改文件：**
- `requirements.txt`: 删除 `crewai>=0.86.0`
- `astrbot/builtin_stars/agent_system/services/crewai_integration.py`: 完全删除
- `astrbot/builtin_stars/agent_system/services/crewai_skill_adapter.py`: 完全删除

**修改文件（移除 import）：**
- `astrbot/builtin_stars/agent_system/services/agent_service.py`: 移除 `CREWAI_AVAILABLE` 和所有 `_test_agent_with_crewai` 分支
- `astrbot/builtin_stars/agent_system/services/roundtable_service.py`: 移除 `CREWAI_AVAILABLE` 和 CrewAI agent 调用分支
- `astrbot/builtin_stars/agent_system/services/crew_service.py`: 移除 CrewAI import 和 `_execute_with_crewai()`
- `astrbot/builtin_stars/agent_system/services/flow_service.py`: 移除 CrewAI import
- `astrbot/builtin_stars/agent_system/services/crewai_integration.py` 的所有引用

### Task 1.2: 统一测试仪表盘 Agent Loop

**修改文件：** `astrbot/builtin_stars/agent_system/services/agent_service.py`

- [ ] 删除 `_test_agent_with_provider()` (lines 486-668, ~182 行)
- [ ] 删除 `_test_agent_stream_with_provider()` (lines 727-1005, ~280 行)
- [ ] 新增 `_test_agent_with_graph()` — 使用 `AgentOperator` 包装 ToolLoopAgentRunner
- [ ] 新增 `_test_agent_stream_with_graph()` — 同上，streaming=True
- [ ] 修改 `test_agent()` 和 `test_agent_stream()` 调用新方法

### Task 1.3: 后台 Subagent 添加检查点能力

**修改文件：** `astrbot/core/astr_agent_tool_exec.py`

- [ ] 在 `_execute_handoff_background()` 中，将 `ctx.tool_loop_agent()` 包装为带 SqliteSaver checkpoint 的 LangGraph entrypoint
- [ ] 添加 `resume_background_handoff(thread_id)` 方法用于中断后恢复
- [ ] 添加 `cancel_background_handoff(thread_id)` 方法

---

## 十、Phase 2: 会议图（第 4-6 周）

### 架构：策略工厂 → Graph Builder

当前 10 种 MeetingStrategy 的重复代码模式：

```python
# 当前（重复 10 次）:
for round in range(max_rounds):
    for agent in agents:
        response = call_agent(agent, context)
        context.append(response)
    context = host_summarize(context)
```

改为 LangGraph 的编译期路由：

```python
# LangGraph 后（每种策略 ~60 行）:
def build_meeting_graph(strategy: str, config: dict) -> StateGraph:
    builder = StateGraph(MeetingState)

    # 所有策略共享的节点
    builder.add_node("opening", opening_node)
    builder.add_node("agent_speak", agent_speak_node)
    builder.add_node("host_integrate", host_node)

    # 策略特定路由
    router = STRATEGY_ROUTERS[strategy]
    builder.add_conditional_edges("host_integrate", router, {
        "next_agent": "agent_speak",
        "next_round": "opening",
        "finalize": "finalize",
    })
    builder.add_node("finalize", finalize_node)
    builder.add_edge("finalize", END)

    return builder.compile()
```

### Task 2.1: 实现会议图核心

**创建文件：** `astrbot/core/langgraph/graphs/meeting.py`

- [ ] `build_meeting_graph(strategy, config)` — 编译会议 StateGraph
- [ ] `opening_node(state, ctx)` — 主持人开场
- [ ] `agent_speak_node(state, ctx)` — 参与者发言（内部调用 AgentOperator）
- [ ] `host_integrate_node(state, ctx)` — 主持人总结本轮
- [ ] `finalize_node(state, ctx)` — 生成最终纪要
- [ ] 策略路由器: `standard_router`, `brainstorm_router`, `parliament_router` 等

### Task 2.2: 替换 RoundtableService

**修改文件：** `astrbot/builtin_stars/agent_system/services/roundtable_service.py`

- [ ] `execute_roundtable()` → 创建 `GraphRunContext` + 异步消费 `astream_events()`
- [ ] 流式事件 → SSE 回调（保持现有 SSE 接口兼容）
- [ ] 删除 `_call_agent()` / `_call_agent_stream()` 等内部辅助方法
- [ ] 删除 `meeting_strategies.py`（1716 行 → 由 meeting.py 中的路由函数替代）

### Task 2.3: 会议触发桥接

**新建 HandoffTool：** 注册 `transfer_to_meeting` 工具到主 Agent 的 toolset

- [ ] 在 `SubAgentOrchestrator` 中识别 `type: "meeting"` 的子 Agent 配置
- [ ] 创建特殊的 MeetingHandoffTool → 触发 `build_meeting_graph()` 执行
- [ ] 会议结果作为结构化文本注入主 Agent 对话

---

## 十一、Phase 3: 规划执行图（第 6-8 周）

### 架构：Plan → Human Approval → Execute → Summarize

```
[START] → generate_plan → [interrupt: 审批] → execute_step_1 → ... → execute_step_N → summarize → [END]
                                                      │
                                          人类修改/批准/拒绝
```

### Task 3.1: 实现规划执行图

**创建文件：** `astrbot/core/langgraph/graphs/plan_execute.py`

- [ ] `build_plan_execute_graph(config)` → 编译 StateGraph
- [ ] `generate_plan_node(state, ctx)` → 调用 AgentOperator 生成步骤列表
- [ ] `human_approval_node(state, ctx)` → `interrupt()` 暂停等待审批
- [ ] `execute_step_node(state, ctx)` → 调用 AgentOperator 执行单步
- [ ] `summarize_node(state, ctx)` → 汇总所有步骤结果

### Task 3.2: 替换 CrewService 执行路径

**修改文件：** `astrbot/builtin_stars/agent_system/services/crew_service.py`

- [ ] `execute_crew()` → 解析 crew tasks → 构造 `PlanExecuteState` → 调用 `build_plan_execute_graph()`
- [ ] 删除 `_execute_with_crewai()` / `_execute_sequential()` / `_execute_single_task()`
- [ ] Crew 模板保持不变（模板定义的是 Agent+Task 配置，不是执行引擎）

### Task 3.3: 规划提供者适配

**修改文件：** 现有的 PlanningProvider（`crewai_integration.py` 中的 `BuiltinPlanningProvider` / `CrewAIPlanningProvider` 需要迁移）

- [ ] 将 `BuiltinPlanningProvider` 逻辑迁移到 `plan_execute.py` 的 `generate_plan_node` 中
- [ ] 保留三种 effort level 的 prompt 模板，但不再通过 CrewAI 调用

---

## 十二、Phase 4: 工作流图（第 8-10 周）

### 架构：Flow JSON → 动态 StateGraph

FlowService 中每个 Flow 是一个 JSON DAG 定义。LangGraph 后，每个 Flow 编译为一张 StateGraph：

```python
def build_workflow_graph(flow_def: dict) -> StateGraph:
    builder = StateGraph(WorkflowState)
    for node in flow_def["nodes"]:
        node_operator = NODE_TYPE_MAP[node["type"]](node)
        builder.add_node(node["id"], node_operator)
    for edge in flow_def["edges"]:
        if edge.get("condition"):
            builder.add_conditional_edges(...)
        else:
            builder.add_edge(edge["source"], edge["target"])
    return builder.compile(checkpointer=create_checkpointer())
```

### Task 4.1: 节点类型实现

**创建文件：** `astrbot/core/langgraph/graphs/workflow.py`

- [ ] `NODE_TYPE_MAP` — 节点类型 → 可调用节点函数
- [ ] `crew_node(state, ctx)` → 调用 AgentOperator（替代 CREW 节点）
- [ ] `human_node(state, ctx)` → `interrupt()` 等待输入（替代 HUMAN 节点）
- [ ] `router_node(state, ctx)` → 条件路由实现
- [ ] `and_node(state, ctx)` → 使用 `Send()` API 并行 fan-out
- [ ] `or_node(state, ctx)` → 使用 reducer 合并多路输入
- [ ] `listen_node(state, ctx)` → 事件监听包装
- [ ] `start_node(state, ctx)` → 入口节点
- [ ] `build_workflow_graph(flow_def)` → 动态构建函数

### Task 4.2: 替换 FlowService

**修改文件：** `astrbot/builtin_stars/agent_system/services/flow_service.py`

- [ ] `execute_flow()` → 解析 flow JSON → `build_workflow_graph()` → `graph.astream_events()`
- [ ] 删除手写拓扑排序和 AND/OR 空壳代码
- [ ] 保留 Flow CRUD 和验证逻辑
- [ ] 保留 Flow 模拟（simulation）

---

## 十三、Phase 5: Crew 编排图（第 10-11 周）

### Task 5.1: 实现 Crew 图

**创建文件：** `astrbot/core/langgraph/graphs/crew.py`

- [ ] `build_crew_graph(crew_def)` → 编译 StateGraph
- [ ] `sequential_crew_router` → 顺序任务路由
- [ ] `hierarchical_crew_router` → 使用 LangGraph subgraph 实现 manager→worker 委托
- [ ] 每个 task 节点 → 内部调用 AgentOperator

### Task 5.2: 集成测试

- [ ] 端到端测试：Meeting → Plan → Execute 完整流程
- [ ] 测试 checkpoint 恢复：中断 Meeting 后从中间轮次继续
- [ ] 测试 HITL 审批：Plan 生成后拒绝，回退修改
- [ ] 测试 Workflow AND 并行：验证两个分支真正并发执行

---

## 十四、风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| LangGraph API break | 中（周更频率） | 锁定 `>=1.0,<2.0`，Phase 0 即写集成测试 |
| ToolLoopAgentRunner 异步与 LangGraph 冲突 | 低 | 两者都是 asyncio，AgentOperator 只在节点内 await |
| SSE 流式接口兼容性 | 中 | StreamEvent 协议设计时参照现有 SSE 格式 |
| 会议策略语义丢失 | 低 | Phase 2 保留 10 种策略的路由逻辑，只替换控制流 |
| Subagent 递归嵌套与 checkpoint 冲突 | 中 | Phase 1 先做后台 handoff checkpoint，验证后再推广 |

---

## 十五、成功指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 依赖体积 | 500MB+ (CrewAI) | <20MB (LangGraph only) |
| 多 Agent 代码总行数 | ~9,200 行 | ~3,500 行 |
| 核心动线完整性 | 无统一入口 | 用户消息 → Triage → HITL → TaskCenter → 异步执行 |
| 任务创建渠道 | UI/API 手动触发 | 主 Agent 对话中自然触发 + 手动触发 |
| MeetingStrategies 文件大小 | 1716 行 | 0（删除，~300 行路由函数替代） |
| CrewAI 桥接代码 | 897 行 | 0（删除） |
| 测试/生产 Agent Loop 一致性 | 不一致（两套实现） | 一致（AgentOperator 统一） |
| 后台子 Agent 中断恢复 | 不支持 | 支持（LangGraph checkpoint） |
| Plan 审批人工介入 | 不支持 | 支持（interrupt + HITL） |
| 统一 HITL 交互 | 无 | 所有确认/审批/修改复用 HITLInteraction |
| Flow AND 真正并行 | 不支持（串行空壳） | 支持（Send API） |
| 会议触发方式 | API/UI 显式调用 | Chat 中 HandoffTool 自然触发 |
| 任务状态推送 | 部分场景 SSE | 全场景 StreamEvent 统一推送 |
```

