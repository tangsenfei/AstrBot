# HITL 统一交互系统 & 任务管理升级 PRD

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan phase-by-phase.

**Goal:** 设计统一的人机交互（HITL）协议，第一期覆盖 ChatUI + 飞书两个渠道；升级任务管理为持久化 + Plan-Todo-Check 执行 + 右侧任务面板。

**Architecture:** InteractionCard 协议 → 渠道适配器分发（ChatUI SSE / 飞书交互卡片） → LangGraph `interrupt()` 暂停 → 用户响应 → `Command(resume)` 恢复。TaskManagerAgent 作为内置图执行日常任务。

**Tech Stack:** Python 3.12+, LangGraph interrupt/Command, lark-oapi (飞书), Vue 3 + Vuetify (ChatUI), SQLite。

---

## 一、现状与问题

### 1.1 HITL 现状

| 场景 | 当前实现 | 问题 |
|------|---------|------|
| `confirm_task` 确认 | 返回文本 dict，LLM 自觉处理 | 无强制等待机制，LLM 可能跳过确认直接调 `create_task` |
| `plan_execute` 审批 | `HumanOperator` 空壳 | 只在 LangGraph 图中调 `interrupt()`，但无人处理中断 |
| `workflow` 人工节点 | 同上 | 同上 |
| 多渠道 | 无 | ChatUI 和飞书用户无法在各自渠道完成交互 |

### 1.2 任务管理现状

| 模块 | 存储 | 问题 |
|------|------|------|
| `TaskCenter` | 内存 dict | 重启丢失，Dashboard 不可见 |
| `TaskService` | SQLite `agent_tasks` | Dashboard 可见，但与 `TaskCenter` 割裂 |
| 任务执行 | 各自 Service 内联 | 无统一执行引擎，无 HITL 支持 |
| 用户补充信息 | 不支持 | 任务执行中用户无法干预 |

---

## 二、InteractionCard 统一 HITL 协议

### 2.1 核心数据模型

```python
# astrbot/core/langgraph/interaction.py

from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass
class CardField:
    key: str                              # "additional_info" | "modify_text" ...
    label: str
    field_type: Literal["text", "textarea", "select", "multiselect"]
    required: bool = False
    default: str | None = None
    options: list[str] | None = None      # select/multiselect 的选项


@dataclass
class CardAction:
    key: str                               # "confirm" | "cancel" | "modify" | "retry" ...
    label: str                             # "确认" | "取消" | "修改需求" | "重试" ...
    style: Literal["primary", "danger", "default"] = "default"


@dataclass
class InteractionCard:
    interaction_id: str                    # 全局唯一，用于 resume 时匹配
    type: Literal[
        "task_confirm",                    # confirm_task 触发
        "plan_approval",                   # 执行计划审批
        "workflow_human",                  # 工作流人工节点
        "error_recovery",                  # 错误恢复决策
        "clarification",                   # 需求澄清追问
    ]
    title: str                             # 卡片标题
    body: str                              # Markdown 正文
    fields: list[CardField] = field(default_factory=list)
    actions: list[CardAction] = field(default_factory=list)
    timeout_seconds: int = 300             # 超时自动取消（0=不限）
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionResponse:
    interaction_id: str
    action_key: str                        # 用户点击的按钮 key
    field_values: dict[str, Any]           # 用户填写的表单值
    responded_at: float


@dataclass
class InteractionState:
    """存储在 InteractionManager 中的暂存状态"""
    interaction_id: str
    thread_id: str                         # LangGraph checkpoint thread_id
    channel: str                           # "chatui" | "feishu" | "unknown"
    card: InteractionCard
    created_at: float
    resolved: bool = False
    response: InteractionResponse | None = None
    feishu_message_id: str | None = None   # 飞书消息 ID（用于后续更新卡片）
    feishu_chat_id: str | None = None      # 飞书会话 ID
```

### 2.2 InteractionManager

```python
# astrbot/core/langgraph/interaction_manager.py

class InteractionManager:
    """统一 HITL 交互管理器"""
    
    def __init__(self):
        self._pending: dict[str, InteractionState] = {}
        self._adapters: dict[str, ChannelAdapter] = {}
    
    def register_adapter(self, channel: str, adapter: ChannelAdapter): ...
    
    async def send_and_wait(self, card: InteractionCard, thread_id: str, channel: str) -> InteractionResponse:
        """发送卡片并阻塞等待用户响应（图节点内调用）"""
        ...
    
    async def respond(self, interaction_id: str, response: InteractionResponse) -> bool:
        """用户提交响应（API 回调）"""
        ...
    
    def get_pending_by_thread(self, thread_id: str) -> InteractionState | None: ...
```

### 2.3 渠道适配器接口

```python
from abc import ABC, abstractmethod

class ChannelAdapter(ABC):
    @abstractmethod
    async def send_card(self, card: InteractionCard, extra: dict) -> str | None:
        """发送交互卡片，返回渠道消息 ID"""
        ...
    
    @abstractmethod
    async def update_card(self, card: InteractionCard, channel_msg_id: str) -> None:
        """更新已发送的卡片（如用户点击后替换为"已确认"状态）"""
        ...
    
    @abstractmethod
    async def dismiss_card(self, channel_msg_id: str) -> None:
        """撤销/移除卡片"""
        ...
```

### 2.4 ChatUI 渠道适配器

```
ChatUI 渠道适配器
  ├─ send_card()     → 在 SSE 流中推送 StreamEvent(type="interaction_card", data=card)
  ├─ update_card()   → 推送 StreamEvent(type="interaction_card_update", data={id, status})
  ├─ dismiss_card()  → 推送 StreamEvent(type="interaction_card_dismiss", data={id})
  └─ respond()       → POST /api/interaction/{id}/respond 接收用户响应
```

**前端渲染流程：**
```
SSE event: interaction_card
  ↓
ChatMessageList 检测到 interaction_card 事件
  ↓
在消息列表中插入 InteractionCardComponent（非气泡，独立卡片）
  ↓
用户点击按钮 / 填写表单 → POST /api/interaction/{id}/respond
  ↓
后端 InteractionManager.respond() → Command(resume=response)
  ↓
SSE 推送 interaction_card_update（卡片变为 "已确认" 状态）
```

**卡片样式参考 ChatUI 已有组件：**
```
┌─────────────────────────────────────────────┐
│  📋 任务确认                                 │
│                                              │
│  已理解你的需求，将创建以下任务：               │
│  类型：深度调研                                │
│  摘要：分析 LangGraph 集成方案                  │
│  详情：从源码分析、架构对比、性能评估            │
│  预计时长：~6 分钟                             │
│                                              │
│  [取消]    [修改需求 ▾]              [确认]    │
└─────────────────────────────────────────────┘
```

### 2.5 飞书渠道适配器

参考 Hermes Agent 飞书交互卡片设计 (`D:\allcode\everything\feishu_interactive_card_architecture.md`)。

**飞书交互卡片 JSON 格式（发送）：**
```json
{
  "config": {"wide_screen_mode": true},
  "header": {
    "title": {"content": "📋 任务确认", "tag": "plain_text"},
    "template": "blue"
  },
  "elements": [
    {
      "tag": "markdown",
      "content": "已理解你的需求，将创建以下任务：\n**类型**：深度调研\n**摘要**：分析 LangGraph 集成方案\n**详情**：从源码分析、架构对比等方面入手\n**预计时长**：~6 分钟"
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {"tag": "plain_text", "content": "确认"},
          "type": "primary",
          "value": {"action_key": "confirm", "interaction_id": "inter_abc123"}
        },
        {
          "tag": "button",
          "text": {"tag": "plain_text", "content": "修改需求"},
          "type": "default",
          "value": {"action_key": "modify", "interaction_id": "inter_abc123"}
        },
        {
          "tag": "button",
          "text": {"tag": "plain_text", "content": "取消"},
          "type": "danger",
          "value": {"action_key": "cancel", "interaction_id": "inter_abc123"}
        }
      ]
    }
  ]
}
```

**飞书卡片回调 → 响应更新后的卡片（同步返回）：**
```json
{
  "config": {"wide_screen_mode": true},
  "header": {
    "title": {"content": "✅ 已确认", "tag": "plain_text"},
    "template": "green"
  },
  "elements": [
    {
      "tag": "markdown",
      "content": "✅ **已确认** — 任务 `task_abc123` 开始执行"
    }
  ]
}
```

**飞书端配置要求：**
1. 订阅事件: `card.action.trigger`
2. 开启交互卡片能力: 应用功能 → 机器人 → 交互卡片 → 启用
3. WebSocket 模式下回调和卡片交互通过 WS 连接自动处理

**实现要点（源自 Hermes Agent 参考）：**
- `approval_id` → 我们的 `interaction_id`，嵌入按钮 `value` 中
- 回调入口 `_on_card_action_trigger()` → 解析 `action_key` + `interaction_id`
- **同步返回** `P2CardActionTriggerResponse`（含更新后卡片 JSON），异步调度 `_resolve_approval`
- 使用 `asyncio.run_coroutine_threadsafe` 处理 WS 线程到 asyncio 事件循环的跨线程调度
- 内存状态映射 `_interaction_state[interaction_id]` 存储 `thread_id` 等上下文

---

## 三、confirm_task 流程改造

### 3.1 新的 confirm_task 工具

```python
# task_tools.py

async def confirm_task(event, task_type, summary, detail, estimated_steps=3):
    """不再返回 dict。改为构造 InteractionCard 并走 HITL 暂停。"""
    
    # 1. 构造 InteractionCard
    card = InteractionCard(
        interaction_id=f"confirm_{uuid.uuid4().hex[:12]}",
        type="task_confirm",
        title="任务确认",
        body=f"已理解你的需求，将创建以下任务：\n\n"
             f"**类型**：{type_labels[task_type]}\n"
             f"**摘要**：{summary}\n"
             f"**详情**：{detail}\n\n"
             f"预计时长：~{estimated_steps * 2} 分钟",
        actions=[
            CardAction(key="confirm", label="确认", style="primary"),
            CardAction(key="modify", label="修改需求", style="default"),
            CardAction(key="cancel", label="取消", style="danger"),
        ],
    )
    
    # 2. 通过 InteractionManager 发送卡片并等待
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(card, channel=detect_channel(event))
    
    # 3. 返回用户选择结果
    if response.action_key == "confirm":
        return {"confirmed": True, "result": "confirmed"}
    elif response.action_key == "modify":
        return {"confirmed": False, "result": "modify", "modify_text": response.field_values.get("modify_text", "")}
    else:
        return {"confirmed": False, "result": "cancelled"}
```

### 3.2 完整对话流

```
用户: "分析一下langgraph集成方案"
  ↓
主Agent 调用 confirm_task(task_type="plan_execute", ...)
  ↓
confirm_task handler:
  ├─ 构造 InteractionCard
  ├─ 调用 InteractionManager.send_and_wait()
  │     ├─ 渠道 = ChatUI → SSE 推送 interaction_card 事件
  │     └─ 渠道 = 飞书   → 发送飞书交互卡片消息
  ├─ LangGraph interrupt() 暂停图执行
  │     ↓ (等待用户)
  ├─ 用户点击 "确认" 按钮
  │     ├─ ChatUI: POST /api/interaction/{id}/respond
  │     └─ 飞书:   card.action.trigger 回调 → P2CardActionTriggerResponse
  ├─ InteractionManager.respond() → Command(resume=response)
  └─ confirm_task 返回 {"confirmed": True}
  ↓
主Agent 收到工具结果 confirmed=True
  ↓
主Agent 调用 create_task(task_type="plan_execute", ...)
  ↓
TaskCenter 创建任务 + TaskManagerAgent 开始执行
  ↓
用户收到进度通知
```

---

## 四、任务持久化 + TaskManagerAgent

### 4.1 TaskStore 改造

**DB 字段扩展（在 `agent_tasks` 表上 ALTER）：**

| 新字段 | 类型 | 用途 |
|--------|------|------|
| `category` | TEXT | `"daily"`（聊天创建）/ `"crew"` / `"flow"` / `"meeting"` |
| `steps` | TEXT(JSON) | `[{"id":1, "desc":"...", "status":"pending|running|done|failed", "result":"..."}]` |
| `thread_id` | TEXT | LangGraph checkpoint thread_id |
| `pending_input` | TEXT | 用户补充信息文本 |
| `interaction_id` | TEXT | 当前活跃的 HITL 卡片 ID |

**创建链路：**
```python
# task_tools.py create_task handler
async def create_task(event, task_type, config, session_id):
    # 1. TaskCenter 创建（内存 + 执行引擎）
    task = await tc.create_task(task_type, config, session_id, run_ctx=run_ctx)
    
    # 2. 同步写 DB
    task_service = _get_task_service()
    db_task = task_service.create_task(
        name=config.get("summary", task_type),
        description=config.get("detail", ""),
        task_type=task_type,
        category="daily",
        thread_id=task.thread_id,
    )
    
    return {"task_id": db_task.id, "thread_id": task.thread_id, "status": "created"}
```

**状态同步回调：**
```python
# task_center.py - _run_task 中集成
async def _on_status_change(task: TaskRecord, old_status, new_status):
    """TaskCenter 状态变更 → 同步到 SQLite"""
    if self._db_callback:
        await self._db_callback(
            thread_id=task.thread_id,
            updates={
                "status": new_status.value,
                "progress": task.progress,
                "result": task.result_text,
                "steps": json.dumps(task.steps),
                "updated_at": datetime.now().isoformat(),
            }
        )
```

### 4.2 TaskManagerAgent（Plan-Todo-Check 图）

```python
# astrbot/core/langgraph/graphs/task_manager.py

class TaskManagerState(TypedDict):
    task_id: str
    task_name: str
    task_desc: str
    plan_steps: list[dict]          # [{"id":1, "desc":"...", "status":"pending"}]
    current_step_index: int
    step_results: list[dict]
    pending_input: str              # 用户补充信息
    check_pass: bool

def build_task_manager_graph(checkpointer=None):
    builder = StateGraph(TaskManagerState)
    
    # 节点
    builder.add_node("plan", plan_node)      # LLM 拆解任务为步骤
    builder.add_node("todo", todo_node)      # 执行当前步骤
    builder.add_node("check", check_node)    # 质量验证
    builder.add_node("finalize", finalize_node)
    
    # 边
    builder.set_entry_point("plan")
    builder.add_conditional_edges("plan", after_plan, {
        "approved": "todo",
        "rejected": END,
    })
    builder.add_conditional_edges("todo", after_todo, {
        "continue": "todo",
        "done": "check",
    })
    builder.add_conditional_edges("check", after_check, {
        "pass": "finalize",
        "retry": "plan",
    })
    builder.add_edge("finalize", END)
    
    return builder.compile(checkpointer=checkpointer)

# after_plan: 调用 interrupt(InteractionCard(type="plan_approval")) 
#             → 展示步骤列表 + 审批按钮 → 返回 approved/rejected
# todo_node: 检查 state.pending_input → 有则注入上下文 → 调 AgentOperator 执行步骤
# check_node: LLM 评估完成质量 → 不符合预期则 retry 回 plan_node
```

### 4.3 用户补充信息机制

```
任务执行中:
  ┌─────────────────────────────────────────────────┐
  │ 用户在右侧 TaskPanel 输入补充信息                    │
  │   ↓                                              │
  │ POST /api/tasks/{id}/input  {"text": "额外关注..."} │
  │   ↓                                              │
  │ task_service.set_pending_input(task_id, text)      │
  │   ↓                                              │
  │ TaskManagerAgent.todo_node:                       │
  │   if state.pending_input:                          │
  │     messages.insert(0, SystemMessage(              │
  │       content=f"[用户补充要求] {state.pending_input}" │
  │     ))                                             │
  │     state.pending_input = ""  # 消耗掉              │
  └─────────────────────────────────────────────────┘
```

---

## 五、ChatUI 改造

### 5.1 交互卡片组件

**新增文件：** `dashboard/src/components/chat/InteractionCardComponent.vue`

- 在 ChatMessageList 中检测 SSE `interaction_card` 事件
- 渲染为独立卡片（非气泡样式），包含：
  - 标题行（图标 + 标题文字 + HITL 类型标签）
  - Markdown 正文区
  - 输入字段（可选，textarea / select）
  - 操作按钮（`v-btn`，按 style 渲染不同颜色）
- 按钮点击 → `POST /api/interaction/{id}/respond`
- 响应后卡片切换为"已处理"状态（灰色禁用态）

### 5.2 右侧任务面板

**新增文件：** `dashboard/src/components/chat/TaskPanel.vue`

```
┌─────────────────────┐
│ 📋 任务              │
│                     │
│ ┌─────────────────┐ │
│ │ 分析langgraph    │ │
│ │ ████████░░ 66%   │ │ ← 进度条
│ │ 步骤 2/3         │ │
│ │ [查看详情]       │ │
│ └─────────────────┘ │
│                     │
│ ┌─────────────────┐ │
│ │ 周报生成         │ │
│ │ ░░░░░░░░ 0%      │ │
│ │ ⏸ 等待确认       │ │ ← HITL 状态
│ │ [查看详情]       │ │
│ └─────────────────┘ │
└─────────────────────┘
```

- 从 `GET /api/tasks?session_id=...` 拉取任务列表
- 每 5 秒轮询 + SSE `task_update` 事件双通道刷新
- HITL 状态的任务显示特殊标识，点击可直接跳转到确认操作

### 5.3 任务详情浮窗

**新增文件：** `dashboard/src/components/chat/TaskDetailOverlay.vue`

- 点击任务项 → 浮窗弹出
- 显示所有步骤及状态（✅完成 / 🔄执行中 / ⬜待执行）
- 如果任务处于 HITL 状态 → 内嵌 InteractionCardComponent
- 底部输入框 + "提交补充信息" 按钮 → `POST /api/tasks/{id}/input`

---

## 六、实施计划

### Phase 1: InteractionCard 核心 + ChatUI 渲染（第 1-2 周）

| 文件 | 动作 | 内容 |
|------|------|------|
| **新增** `langgraph/interaction.py` | Create | `InteractionCard`, `CardField`, `CardAction`, `InteractionResponse`, `InteractionState` |
| **新增** `langgraph/channel_adapter.py` | Create | `ChannelAdapter` 抽象基类 |
| **新增** `langgraph/interaction_manager.py` | Create | `InteractionManager` — 存储暂存、分发卡片、接收响应、`send_and_wait()` |
| **新增** `langgraph/chatui_adapter.py` | Create | ChatUI 渠道适配器 — SSE 推送卡片事件 |
| **新增** `api/routes/interaction.py` | Create | `POST /api/interaction/{id}/respond` 端点 |
| **修改** `task_tools.py` `confirm_task` | Modify | 构造 InteractionCard → 调用 `InteractionManager.send_and_wait()` → 返回 confirmed/修改/取消 |
| **新增** `dashboard/.../InteractionCardComponent.vue` | Create | 交互卡片 Vue 组件 |
| **修改** `ChatMessageList.vue` | Modify | 检测 `interaction_card` 事件，内联渲染卡片 |
| **测试** | | ChatUI 中模拟 confirm_task → 展示卡片 → 点击确认 → 链路打通 |

### Phase 2: 任务持久化 + TaskManagerAgent（第 2-3 周）

| 文件 | 动作 | 内容 |
|------|------|------|
| **修改** `database.py` | Modify | ALTER `agent_tasks` 加列 |
| **修改** `task_service.py` | Modify | 新增 `update_status()`, `set_pending_input()`, `update_steps()` |
| **修改** `task_center.py` | Modify | `create_task` 双写 DB；状态变更回调写 DB |
| **新增** `graphs/task_manager.py` | Create | `build_task_manager_graph()` — plan/todo/check/finalize |
| **修改** `task_tools.py` `create_task` | Modify | 双写 DB；dispatch 到 `task_manager` 执行器 |
| **修改** `core_lifecycle.py` | Modify | 注册 `task_manager` 执行器到 TaskCenter |
| **测试** | | 聊天触发任务创建 → TaskManagerAgent 执行 → plan→approve→todo→check |

### Phase 3: ChatUI 任务面板 + 补充信息（第 3-4 周）

| 文件 | 动作 | 内容 |
|------|------|------|
| **新增** `dashboard/.../TaskPanel.vue` | Create | 右侧任务列表面板 |
| **新增** `dashboard/.../TaskDetailOverlay.vue` | Create | 任务详情浮窗 |
| **修改** `Chat.vue` / `ChatPage.vue` | Modify | 右侧抽屉嵌入 TaskPanel |
| **新增** API endpoint | Create | `POST /api/tasks/{id}/input` 补充信息 |
| **修改** `task_manager.py` `todo_node` | Modify | 执行前检查 `pending_input` → 注入上下文 |
| **测试** | | 任务面板实时刷新 + HITL 确认 + 补充信息注入 |

### Phase 4: 飞书渠道 + 扩展 HITL 类型（第 4-5 周）

| 文件 | 动作 | 内容 |
|------|------|------|
| **新增** `langgraph/feishu_adapter.py` | Create | 飞书交互卡片发送 + `card.action.trigger` 回调处理 + `P2CardActionTriggerResponse` |
| **修改** `interaction_manager.py` | Modify | 注册飞书适配器 |
| **修改** `plan_execute.py` | Modify | `human_approval_node` 改用 InteractionCard |
| **修改** `workflow.py` | Modify | `human_node` 改用 InteractionCard |
| **飞书配置** | Config | 订阅 `card.action.trigger` 事件 + 开启交互卡片能力 |
| **测试** | | 飞书端触发任务 → 展示交互卡片 → 点击按钮 → 任务继续执行 |

---

## 七、成功指标

| 指标 | 当前 | 目标 |
|------|------|------|
| HITL 交互渠道 | 0（无交互） | 2（ChatUI + 飞书） |
| confirm_task 确认率 | N/A（无强制确认） | 100%（卡片强制等待） |
| 任务 Dashboard 可见 | 仅手动创建的任务 | 全部任务（聊天创建 + 手动创建） |
| 任务重启不丢失 | 聊天任务重启丢失 | 全部持久化到 SQLite |
| 用户补充信息 | 不支持 | 支持（任务面板输入 → 注入上下文） |
| Plan-Todo-Check 自动化 | 无 | TaskManagerAgent 内置执行 |
| 飞书交互卡片 | 无 | 支持（发送 + 回调 + 卡片更新） |
