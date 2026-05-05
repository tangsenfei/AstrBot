from __future__ import annotations

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import AgentGraphState, GraphRunContext

_agent_operator = AgentOperator()

MAX_RETRY_LOOPS = 100


class PlanPhaseState(AgentGraphState, total=False):
    task_id: str
    task_name: str
    task_desc: str
    explore_result: str
    design_result: str
    plan_steps: list[dict]
    human_approved: bool
    reject_feedback: str
    retry_count: int


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


EXPLORE_PROMPT = """
你现在处于规划阶段——探索需求。这是一个只读的分析阶段，不要执行任何步骤。

## 探索阶段
1. 深入分析用户任务需求，理解背景、目标和约束条件
2. 检查是否有类似的已有功能或模式可以复用
3. 识别实现中可能遇到的关键难点和风险点
4. 如果需要更多信息来明确方案，优先向用户提问澄清

完成后，进入设计阶段。
"""

DESIGN_PROMPT = """
你现在处于规划阶段——设计方案。基于前一步的探索结果设计实现方案。

## 设计阶段
1. 提出至少两种实现路径，对比各自的优劣
2. 选择最优路径，说明选择理由
3. 描述整体架构：涉及哪些模块、数据如何流转
4. 指出关键决策点和为什么这样选择

## 驳回重生成规则（如有驳回意见）
- 逐条分析用户驳回意见
- 调整设计方案，重点解决驳回意见中指出的问题
- 在方案中标注为解决驳回意见所做的修改

{feedback_section}

完成后，进入步骤拆解阶段。
"""

WRITE_PLAN_PROMPT = """
你现在处于规划阶段——编写执行计划。将设计方案拆解为具体的、可追踪的执行步骤。

## 拆解规则
1. 每个步骤必须是独立可验证的：有明确的输入、操作和预期输出
2. 步骤数控制在 3-7 个
3. 步骤之间如有依赖关系请标明
4. 每个步骤应包含验证方法
5. 用祈使句描述，方便追踪

## 输出格式
请按以下 JSON 格式输出步骤列表：
```json
{
  "steps": [
    {
      "content": "分析现有认证流程",
      "activeForm": "正在分析现有认证流程",
      "dependencies": []
    },
    {
      "content": "实现JWT token生成",
      "activeForm": "正在实现JWT token生成",
      "dependencies": [1]
    }
  ]
}
```

{design_context}

驳回意见: {reject_context}

完成后，提交用户审批。
"""

PLAN_REJECTION_PROMPT = """
[用户驳回了以下方案的审批]

驳回方案摘要：
{plan_summary}

用户驳回意见：
{feedback}

请根据驳回意见重新设计方案。注意：
1. 逐条分析用户驳回意见，每条都要有对应的调整
2. 重新拆解步骤，确保新方案覆盖驳回意见的所有要求
3. 完成后重新提交审批
"""


async def explore_node(state: PlanPhaseState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    prompt = (
        f"{EXPLORE_PROMPT}\n\n"
        f"任务名称：{task_name}\n"
        f"任务描述：{task_desc}"
    )
    agent_state = {
        "system_prompt": "你是一个任务规划助手。请分析任务需求。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )
    return {"explore_result": result.get("final_text", "")}


async def design_node(state: PlanPhaseState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    task_name = state.get("task_name", "")
    task_desc = state.get("task_desc", "")
    explore_result = state.get("explore_result", "")
    reject_feedback = state.get("reject_feedback", "")

    feedback_section = ""
    if reject_feedback:
        feedback_section = f"""
## 用户驳回意见
{PLAN_REJECTION_PROMPT.format(
    plan_summary=state.get("design_result", "")[:500],
    feedback=reject_feedback,
)}
"""

    prompt = DESIGN_PROMPT.format(feedback_section=feedback_section)
    prompt += f"\n\n任务名称：{task_name}\n任务描述：{task_desc}\n\n探索结果：\n{explore_result}"
    agent_state = {
        "system_prompt": "你是一个系统架构师。请设计实现方案。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )
    return {"design_result": result.get("final_text", "")}


async def write_plan_node(
    state: PlanPhaseState, config: RunnableConfig
) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    design_result = state.get("design_result", "")
    reject_feedback = state.get("reject_feedback", "")
    reject_context = reject_feedback if reject_feedback else "无"

    prompt = WRITE_PLAN_PROMPT.format(
        design_context=design_result,
        reject_context=reject_context,
    )
    agent_state = {
        "system_prompt": "你是一个任务规划助手。请将方案拆解为执行步骤。请严格按 JSON 格式输出。",
        "user_prompt": prompt,
        "messages": [],
        "provider_id": state.get("provider_id"),
        "session_id": state.get("session_id", ""),
    }
    result = await _agent_operator.execute(
        agent_state, run_ctx, write_stream=True
    )

    plan_text = result.get("final_text", "")
    steps = _parse_steps_from_text(plan_text)
    if not steps:
        steps = [
            {
                "content": state.get("task_name", "执行任务"),
                "activeForm": f"正在执行{state.get('task_name', '任务')}",
                "dependencies": [],
                "status": "pending",
            }
        ]

    return {"plan_steps": steps, "reject_feedback": ""}


def _parse_steps_from_text(text: str) -> list[dict]:
    import json
    import re

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            steps = data.get("steps", [])
            for s in steps:
                s.setdefault("status", "pending")
                s.setdefault("activeForm", s.get("content", ""))
                s.setdefault("dependencies", [])
                s.setdefault("result", "")
            return steps
        except json.JSONDecodeError:
            pass

    steps = []
    for line in text.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("- ") or line.startswith("* ")):
            desc = line.lstrip("0123456789.-*) ").strip()
            if desc:
                steps.append({
                    "content": desc,
                    "activeForm": f"正在{desc[:30]}",
                    "dependencies": [],
                    "status": "pending",
                    "result": "",
                })
    return steps


async def approve_plan_node(
    state: PlanPhaseState, config: RunnableConfig
) -> dict:
    from astrbot.core.langgraph.interaction import CardAction, InteractionCard
    from astrbot.core.langgraph.interaction_manager import get_interaction_manager

    plan_steps = state.get("plan_steps", [])
    retry_count = state.get("retry_count", 0)

    steps_text = "\n".join(
        f"  {i + 1}. {s.get('content', s.get('description', ''))}"
        for i, s in enumerate(plan_steps)
    )

    title = "执行计划审批"
    if retry_count > 0:
        title = f"执行计划审批（第 {retry_count} 次修改）"

    card = InteractionCard(
        interaction_id=f"plan_approve_{state.get('task_id', '')}",
        type="plan_approval",
        title=title,
        body=f"以下执行计划已生成，请审批：\n\n{steps_text}",
        fields=[
            {
                "key": "feedback",
                "label": "修改意见",
                "field_type": "textarea",
                "required": False,
            }
        ],
        actions=[
            CardAction(key="approve", label="通过", style="primary"),
            CardAction(key="modify", label="修改", style="default"),
            CardAction(key="reject", label="取消", style="danger"),
        ],
    )
    mgr = get_interaction_manager()
    response = await mgr.send_and_wait(card, thread_id="", channel="chatui")

    action_key = response.action_key
    if action_key == "approve":
        return {
            "human_approved": True,
            "reject_feedback": "",
            "retry_count": 0,
        }
    elif action_key == "modify":
        feedback = response.field_values.get("feedback", "") or "需要修改方案"
        return {
            "human_approved": False,
            "reject_feedback": feedback,
            "retry_count": retry_count + 1,
        }
    else:
        return {
            "human_approved": False,
            "reject_feedback": "cancelled",
            "retry_count": 0,
        }


async def cancel_node(
    state: PlanPhaseState, config: RunnableConfig
) -> dict:
    return {"human_approved": False}


def after_approval(state: PlanPhaseState) -> str:
    if state.get("human_approved", False):
        return "execute"
    feedback = state.get("reject_feedback", "")
    retry = state.get("retry_count", 0)
    if feedback == "cancelled":
        return "cancel"
    if retry < MAX_RETRY_LOOPS:
        return "retry"
    return "cancel"


def build_plan_phase_graph(
    config: dict | None = None, checkpointer=None
) -> StateGraph:
    builder = StateGraph(PlanPhaseState)

    builder.add_node("explore", explore_node)
    builder.add_node("design", design_node)
    builder.add_node("write_plan", write_plan_node)
    builder.add_node("approve_plan", approve_plan_node)
    builder.add_node("cancel", cancel_node)

    builder.set_entry_point("explore")
    builder.add_edge("explore", "design")
    builder.add_edge("design", "write_plan")
    builder.add_edge("write_plan", "approve_plan")

    builder.add_conditional_edges("approve_plan", after_approval, {
        "execute": END,
        "cancel": "cancel",
        "retry": "design",
    })
    builder.add_edge("cancel", END)

    return builder.compile(checkpointer=checkpointer)
