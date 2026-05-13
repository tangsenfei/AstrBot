from __future__ import annotations

import json
import time
import uuid
from typing import Any

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph

from astrbot.core import logger
from astrbot.core.langgraph.interaction import CardAction, CardField, InteractionCard
from astrbot.core.langgraph.interaction_manager import get_interaction_manager
from astrbot.core.langgraph.operators import AgentOperator
from astrbot.core.langgraph.state import GraphRunContext, MeetingState, StreamEvent

_agent_operator = AgentOperator()

IMPLEMENTED_STRATEGIES = {
    "exploration",
    "diagnosis",
    "solution_design",
    "review_decision",
    "alignment_debate",
    "retrospective",
}

MEETING_TYPE_GUIDANCE: dict[str, dict[str, str]] = {
    "exploration": {
        "name": "发散探索会",
        "host_style": "鼓励发散、延迟评判，持续打开候选方向，再进行轻量聚类。",
        "participant_prompt": "优先提出可能性、类比、反直觉机会和可继续探索的问题，暂不急于否定。",
        "final_output": "候选想法池、主题分组、优先探索方向、下一步验证建议",
    },
    "diagnosis": {
        "name": "诊断分析会",
        "host_style": "推动事实、假设、证据分离，要求每个判断说明依据和待验证缺口。",
        "participant_prompt": "优先补充事实、症状、因果链、反例和证据缺口。",
        "final_output": "问题结构、关键原因、证据链、待验证项",
    },
    "solution_design": {
        "name": "方案设计会",
        "host_style": "从目标和约束出发，收敛到 1-3 套可执行方案，并检查资源与风险。",
        "participant_prompt": "优先给出方案路径、关键取舍、资源需求、风险和落地步骤。",
        "final_output": "方案草案、执行路径、资源需求、风险预案",
    },
    "review_decision": {
        "name": "评审决策会",
        "host_style": "先明确评审标准，再组织打分、异议、修改意见和最终决策。",
        "participant_prompt": "优先基于标准提出评价、风险、异议、通过条件和修改建议。",
        "final_output": "评审结论、通过或不通过原因、修改要求、责任人与时限",
    },
    "alignment_debate": {
        "name": "对齐辩论会",
        "host_style": "让不同立场充分陈述和交叉质询，区分已达成共识和待裁决分歧。",
        "participant_prompt": "优先表达立场、依据、反驳点、可妥协边界和需要裁决的问题。",
        "final_output": "共识、分歧保留项、裁决路径、下一步行动",
    },
    "retrospective": {
        "name": "复盘改进会",
        "host_style": "引导事实回顾、成败原因、经验沉淀，并形成可追踪改进行动。",
        "participant_prompt": "优先补充事实、做得好的地方、失败原因、经验和改进行动。",
        "final_output": "复盘报告、经验沉淀、改进行动项",
    },
}


def _get_run_ctx(config: RunnableConfig) -> GraphRunContext | None:
    return config.get("configurable", {}).get("run_ctx")


def _guidance(state: MeetingState) -> dict[str, str]:
    strategy = state.get("strategy") or state.get("meeting_type") or "solution_design"
    return MEETING_TYPE_GUIDANCE.get(strategy, MEETING_TYPE_GUIDANCE["solution_design"])


def _emit(run_ctx: GraphRunContext | None, event: str, data: dict[str, Any], node_id: str) -> None:
    if run_ctx is None or run_ctx.writer is None:
        return
    run_ctx.writer({"event": event, "data": data, "timestamp": time.time(), "node_id": node_id})


def _emit_phase(run_ctx: GraphRunContext | None, stage: str, progress: int, content: str, **extra: Any) -> None:
    _emit(
        run_ctx,
        "phase",
        {"stage": stage, "phase": stage, "progress": progress, "content": content, **extra},
        stage,
    )


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def _meeting_llm_input_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "system_prompt",
        "user_prompt",
        "messages",
        "compact_context",
        "func_tools",
    )
    return {key: _json_safe(payload.get(key)) for key in allowed_keys if key in payload}


def _wrap_writer(
    run_ctx: GraphRunContext,
    agent: dict[str, Any],
    agent_name: str,
    current_round: int,
    call_id: str,
    call_attempt: int,
):
    original_writer = run_ctx.writer
    last_lane = {"value": "reasoning"}

    def wrapped_writer(event: StreamEvent):
        if original_writer is None:
            return
        data = dict(event.get("data", {}))
        event_type = str(event.get("event") or "")
        if event_type == "reasoning":
            last_lane["value"] = "reasoning"
            data.setdefault("lane", "reasoning")
        elif event_type == "text_delta":
            last_lane["value"] = "output"
            data.setdefault("lane", "output")
        elif event_type in {"tool_call", "tool_result"}:
            data.setdefault("lane", last_lane["value"] or "reasoning")
            data.setdefault("tool_call_id", data.get("id") or data.get("call_id") or "")
        data["call_id"] = call_id
        data["call_attempt"] = call_attempt
        data["agent_id"] = agent.get("id") or ""
        data["agent_label"] = agent_name
        data["agent_name"] = agent_name
        data["round"] = current_round
        original_writer({**event, "data": data})

    return wrapped_writer


async def _agent_call(
    state: MeetingState,
    run_ctx: GraphRunContext,
    agent: dict[str, Any],
    prompt: str,
    *,
    speaker_name: str,
    current_round: int,
    node_id: str = "agent_operator",
) -> str:
    call_id = uuid.uuid4().hex
    call_attempt = 1
    call_started_at = time.monotonic()
    saved_writer = run_ctx.writer
    agent_state = {
        "system_prompt": agent.get("system_prompt", ""),
        "user_prompt": prompt,
        "messages": [],
        "provider_id": agent.get("provider_id") or state.get("provider_id"),
        "session_id": state.get("session_id", ""),
        "model": agent.get("model") or agent.get("model_name"),
        "trace_context": {
            "call_id": call_id,
            "call_attempt": call_attempt,
            "agent_id": agent.get("id") or "",
            "agent_label": speaker_name,
            "agent_name": speaker_name,
            "round": current_round,
            "stage_id": node_id,
        },
    }
    _emit(
        run_ctx,
        "agent_call_start",
        {
            "call_id": call_id,
            "call_attempt": call_attempt,
            "agent_call_status": "running",
            "agent_id": agent.get("id") or "",
            "agent_label": speaker_name,
            "agent_name": speaker_name,
            "round": current_round,
            "provider_id": agent_state.get("provider_id") or "",
            "model": agent_state.get("model") or "",
            "func_tools": _json_safe(agent_state.get("func_tools") or []),
            "input_payload": _meeting_llm_input_payload(agent_state),
        },
        node_id,
    )
    run_ctx.writer = _wrap_writer(
        run_ctx, agent, speaker_name, current_round, call_id, call_attempt
    )
    try:
        result = await _agent_operator.execute(agent_state, run_ctx, write_stream=True)
    except Exception as exc:
        _emit(
            run_ctx,
            "agent_call_end",
            {
                "call_id": call_id,
                "call_attempt": call_attempt,
                "agent_call_status": "failed",
                "duration_ms": int((time.monotonic() - call_started_at) * 1000),
                "agent_id": agent.get("id") or "",
                "agent_label": speaker_name,
                "agent_name": speaker_name,
                "round": current_round,
                "message": str(exc),
            },
            node_id,
        )
        raise
    finally:
        run_ctx.writer = saved_writer
    if result.get("error"):
        _emit(
            run_ctx,
            "agent_call_end",
            {
                "call_id": call_id,
                "call_attempt": call_attempt,
                "agent_call_status": "failed",
                "duration_ms": int((time.monotonic() - call_started_at) * 1000),
                "agent_id": agent.get("id") or "",
                "agent_label": speaker_name,
                "agent_name": speaker_name,
                "round": current_round,
                "message": str(result["error"]),
            },
            node_id,
        )
        return f"[{speaker_name} 执行失败: {result['error']}]"
    final_text = result.get("final_text", "")
    if final_text:
        _emit(
            run_ctx,
            "assistant_message",
            {
                "content": final_text,
                "agent_id": agent.get("id") or "",
                "agent_label": speaker_name,
                "agent_name": speaker_name,
                "round": current_round,
                "call_id": call_id,
                "call_attempt": call_attempt,
            },
            node_id,
        )
    _emit(
        run_ctx,
        "agent_call_end",
        {
            "call_id": call_id,
            "call_attempt": call_attempt,
            "agent_call_status": "completed",
            "duration_ms": int((time.monotonic() - call_started_at) * 1000),
            "agent_id": agent.get("id") or "",
            "agent_label": speaker_name,
            "agent_name": speaker_name,
            "round": current_round,
        },
        node_id,
    )
    return final_text


def _material_text(materials: dict[str, Any] | None) -> str:
    if not materials:
        return "暂无用户上传材料。"
    parts = []
    for key, value in materials.items():
        if value in (None, "", [], {}):
            continue
        parts.append(f"{key}: {value}")
    return "\n".join(parts) if parts else "暂无用户上传材料。"


def _discussion_context(state: MeetingState, limit: int = 12) -> str:
    results = state.get("round_results", [])
    return "\n".join(results[-limit:]) if results else "暂无会议讨论记录。"


def _persist_meeting_updates(state: MeetingState, updates: dict[str, Any]) -> None:
    meeting_id = state.get("meeting_id")
    if not meeting_id or not updates:
        return
    try:
        from astrbot.builtin_stars.agent_system.database import get_database

        get_database().update("meetings", updates, where="id = ?", where_params=(meeting_id,))
    except Exception as e:
        logger.warning(f"Failed to persist meeting updates: {e}")


async def _maybe_goal_hitl(state: MeetingState, run_ctx: GraphRunContext) -> dict[str, Any]:
    settings = state.get("settings") or {}
    needs_confirmation = bool(settings.get("require_goal_confirmation"))
    if not needs_confirmation:
        return {}

    meeting_id = state.get("meeting_id", "")
    task_id = state.get("task_id", "")
    guidance = _guidance(state)
    goal = state.get("goal") or state.get("topic") or ""
    expected_output = state.get("expected_output") or guidance["final_output"]
    material_summary = _material_text(state.get("materials"))
    if len(material_summary) > 240:
        material_summary = f"{material_summary[:240]}..."
    card = InteractionCard(
        interaction_id=f"meeting_goal_{uuid.uuid4().hex[:10]}",
        type="clarification",
        title=f"确认「{guidance['name']}」目标与产出",
        body=(
            "会议开始前请确认本次会议的核心信息。\n"
            f"会议目标：{goal or '待补充'}\n"
            f"预期产出：{expected_output or '待补充'}\n"
            f"已提供材料：{material_summary}"
        ),
        fields=[
            CardField("goal", "会议目标", "textarea", required=True, default=goal),
            CardField("expected_output", "预期产出", "textarea", required=True, default=expected_output),
            CardField("extra_context", "补充上下文", "textarea", required=False, default="", description="可补充边界、约束、材料位置或希望重点讨论的问题。"),
        ],
        actions=[
            CardAction("confirm", "确认继续", "primary"),
            CardAction("modify", "带修改继续", "default"),
            CardAction("cancel", "取消会议", "danger"),
        ],
        timeout_seconds=900,
        meta={"scope": "meeting", "meeting_id": meeting_id, "task_id": task_id, "stage": "goal"},
    )
    card_payload = card.to_dict()
    _emit(run_ctx, "interaction", {"content": card.title, **card_payload}, "goal")

    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.hitl_service import HITLService

        HITLService(get_database()).upsert_from_card(
            card,
            task_id=task_id,
            session_id=meeting_id,
            scope="meeting",
            channel="meeting",
            metadata={"meeting_id": meeting_id, "stage": "goal"},
        )
    except Exception as e:
        logger.warning(f"Failed to persist meeting HITL card: {e}")

    response = await get_interaction_manager().send_and_wait(
        card,
        thread_id=task_id or meeting_id,
        channel="meeting",
        channel_extra={"meeting_id": meeting_id},
    )
    if response.action_key == "cancel":
        return {"round_results": state.get("round_results", []) + ["[用户确认] 用户取消了会议目标确认。"]}

    fields = response.field_values or {}
    updates: dict[str, Any] = {}
    if fields.get("goal"):
        updates["goal"] = str(fields["goal"]).strip()
        updates["topic"] = updates["goal"]
    if fields.get("expected_output"):
        updates["expected_output"] = str(fields["expected_output"]).strip()
    if updates:
        db_updates = {k: v for k, v in updates.items() if k in {"goal", "expected_output"}}
        if db_updates:
            _persist_meeting_updates(state, db_updates)
    note = f"[用户确认] action={response.action_key}; 补充上下文：{fields.get('extra_context') or '无'}"
    updates["round_results"] = state.get("round_results", []) + [note]
    return updates


def _consume_user_inputs(state: MeetingState) -> dict[str, Any]:
    meeting_id = state.get("meeting_id")
    if not meeting_id:
        return {}
    last_seq = int(state.get("last_user_event_seq") or 0)
    try:
        from astrbot.builtin_stars.agent_system.database import get_database
        from astrbot.builtin_stars.agent_system.services.meeting_service import MeetingService

        inputs = MeetingService(get_database()).recent_user_inputs(meeting_id, after_seq=last_seq)
    except Exception as e:
        logger.warning(f"Failed to consume meeting user inputs: {e}")
        return {}
    if not inputs:
        return {}
    round_results = list(state.get("round_results", []))
    for item in inputs:
        round_results.append(f"[用户发言] {item.get('content', '')}")
        last_seq = max(last_seq, int(item.get("seq") or last_seq))
    return {"round_results": round_results, "last_user_event_seq": last_seq}


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "")
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
        except Exception:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_host_decision(text: str) -> dict[str, Any]:
    parsed = _extract_first_json_object(text)
    if not parsed:
        return {"action": "continue", "reason": "主持人决策解析失败，默认继续。"}
    action = str(
        parsed.get("action")
        or parsed.get("decision")
        or parsed.get("next_action")
        or ""
    ).strip().lower()
    if action not in {"continue", "finalize"}:
        action = "continue"
    return {
        "action": action,
        "reason": str(parsed.get("reason") or parsed.get("rationale") or ""),
        "next_round_focus": str(
            parsed.get("next_round_focus") or parsed.get("focus") or ""
        ),
    }


async def goal_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    guidance = _guidance(state)
    host = state.get("host")
    _emit_phase(run_ctx, "goal", 10, "会议助理正在确认会议目标、输入和预期产出。", speaker="会议助理")

    updates = await _maybe_goal_hitl(state, run_ctx)
    merged = {**state, **updates}
    if not host:
        return updates

    prompt = (
        f"会议类型：{guidance['name']}\n"
        f"主持策略：{guidance['host_style']}\n"
        f"会议目标：{merged.get('goal') or merged.get('topic')}\n"
        f"预期产出：{merged.get('expected_output') or guidance['final_output']}\n"
        f"用户材料：\n{_material_text(merged.get('materials'))}\n\n"
        "请用简洁开场确认本次会议目标、边界、输入和成功标准。"
    )
    text = await _agent_call(
        merged,
        run_ctx,
        host,
        prompt,
        speaker_name=host.get("name", "会议助理"),
        current_round=0,
        node_id="goal",
    )
    return {
        **updates,
        "round_results": updates.get("round_results", state.get("round_results", [])) + [f"[目标确定] {text}"],
    }


async def materials_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    host = state.get("host")
    guidance = _guidance(state)
    _emit_phase(run_ctx, "materials", 30, "会议助理正在整理会议材料和关键上下文。", speaker="会议助理")
    if not host:
        return {}

    prompt = (
        f"会议目标：{state.get('goal') or state.get('topic')}\n"
        f"会议类型：{guidance['name']}\n"
        f"目标产出：{state.get('expected_output') or guidance['final_output']}\n"
        f"用户材料：\n{_material_text(state.get('materials'))}\n"
        f"已有上下文：\n{_discussion_context(state, 6)}\n\n"
        "请形成会议材料简报：关键事实、参考信息、已知约束、缺口和会议中要重点校准的问题。"
    )
    brief = await _agent_call(
        state,
        run_ctx,
        host,
        prompt,
        speaker_name=host.get("name", "会议助理"),
        current_round=0,
        node_id="materials",
    )
    _emit(run_ctx, "artifact", {"title": "会议材料简报", "artifact_type": "brief", "content": brief}, "materials")
    return {
        "materials_brief": brief,
        "round_results": state.get("round_results", []) + [f"[材料简报] {brief}"],
    }


async def opening_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    host = state.get("host")
    if not host:
        return {"current_round": 1}

    guidance = _guidance(state)
    current_round = 1
    _emit_phase(run_ctx, "running", 45, "会议助理开始主持会议讨论。", speaker=host.get("name", "会议助理"), round=current_round)
    prompt = (
        f"会议类型：{guidance['name']}\n"
        f"主持策略：{guidance['host_style']}\n"
        f"会议目标：{state.get('goal') or state.get('topic')}\n"
        f"材料简报：\n{state.get('materials_brief') or '暂无'}\n\n"
        "请宣布会议进入讨论阶段，给出第一轮讨论问题和发言顺序。"
    )
    opening_text = await _agent_call(
        state,
        run_ctx,
        host,
        prompt,
        speaker_name=host.get("name", "会议助理"),
        current_round=current_round,
        node_id="running",
    )
    return {"current_round": current_round, "round_results": state.get("round_results", []) + [f"[开场] {opening_text}"]}


async def agent_speak_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    consumed = _consume_user_inputs(state)
    merged = {**state, **consumed}
    participants = merged.get("participants", [])
    current_round = merged.get("current_round", 1)
    round_results = list(merged.get("round_results", []))
    guidance = _guidance(merged)

    if not participants:
        round_results.append("[会议助理] 当前没有配置参会专家，会议助理将基于用户材料继续推进。")
        return {"round_results": round_results, "current_round": current_round + 1, **({"last_user_event_seq": consumed["last_user_event_seq"]} if "last_user_event_seq" in consumed else {})}

    for participant in participants:
        context = "\n".join(round_results[-10:])
        prompt = (
            f"会议目标：{merged.get('goal') or merged.get('topic')}\n"
            f"会议类型：{guidance['name']}\n"
            f"当前轮次：{current_round}\n"
            f"会议助理要求：{guidance['participant_prompt']}\n"
            f"材料简报：\n{merged.get('materials_brief') or '暂无'}\n"
            f"讨论上下文：\n{context}\n\n"
            "请以参会专家身份发表观点，回应前文，并提出对会议目标有帮助的判断。"
        )
        agent_name = participant.get("name", "Agent")
        speech = await _agent_call(
            merged,
            run_ctx,
            participant,
            prompt,
            speaker_name=agent_name,
            current_round=current_round,
            node_id="running",
        )
        round_results.append(f"[{agent_name}] {speech}")

    result = {"round_results": round_results, "current_round": current_round + 1}
    if "last_user_event_seq" in consumed:
        result["last_user_event_seq"] = consumed["last_user_event_seq"]
    return result


async def host_integrate_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}
    consumed = _consume_user_inputs(state)
    merged = {**state, **consumed}
    host = merged.get("host")
    if not host:
        return consumed

    guidance = _guidance(merged)
    round_results = merged.get("round_results", [])
    current_round = max(1, int(merged.get("current_round", 1)) - 1)
    progress = min(85, 45 + current_round * 20)
    _emit_phase(run_ctx, "running", progress, "会议助理正在总结本轮讨论并决定下一步主持动作。", speaker=host.get("name", "会议助理"), round=current_round)
    prompt = (
        f"会议类型：{guidance['name']}\n"
        f"主持策略：{guidance['host_style']}\n"
        f"会议目标：{merged.get('goal') or merged.get('topic')}\n"
        f"预期产出：{merged.get('expected_output') or guidance['final_output']}\n"
        f"最近讨论：\n{_discussion_context(merged, 14)}\n\n"
        "请总结本轮要点，指出已形成的结论、分歧、风险和下一轮需要追问的问题。\n"
        "最后必须单独输出一个 JSON 对象用于系统路由，格式如下：\n"
        '{"action":"continue|finalize","reason":"继续或结束的原因","next_round_focus":"下一轮焦点，结束时可为空"}'
    )
    summary = await _agent_call(
        merged,
        run_ctx,
        host,
        prompt,
        speaker_name=host.get("name", "会议助理"),
        current_round=current_round,
        node_id="running",
    )
    decision = _parse_host_decision(summary)
    result = {
        "round_results": round_results + [f"[主持总结] {summary}"],
        "host_decision": decision,
        "next_round_focus": decision.get("next_round_focus", ""),
    }
    if "last_user_event_seq" in consumed:
        result["last_user_event_seq"] = consumed["last_user_event_seq"]
    return result


async def finalize_node(state: MeetingState, config: RunnableConfig) -> dict:
    run_ctx = _get_run_ctx(config)
    if run_ctx is None:
        return {}

    consumed = _consume_user_inputs(state)
    merged = {**state, **consumed}
    host = merged.get("host")
    guidance = _guidance(merged)
    round_results = merged.get("round_results", [])
    all_discussion = "\n".join(round_results)
    topic = merged.get("goal") or merged.get("topic", "")
    current_round = merged.get("current_round", 0)
    finalizer = host or {"name": "会议助理", "system_prompt": "你是一个会议纪要生成助手。"}

    _emit_phase(run_ctx, "finalizing", 92, "会议助理正在生成会议纪要和会议报告。", speaker=finalizer.get("name", "会议助理"))
    minutes_prompt = (
        f"会议类型：{guidance['name']}\n"
        f"会议目标：{topic}\n"
        f"预期产出：{merged.get('expected_output') or guidance['final_output']}\n"
        f"材料简报：\n{merged.get('materials_brief') or '暂无'}\n"
        f"完整讨论：\n{all_discussion}\n\n"
        "请生成结构化会议纪要，包含：目标、参会观点摘要、关键讨论、共识、分歧、决策、行动项。"
    )
    final_text = await _agent_call(
        merged,
        run_ctx,
        finalizer,
        minutes_prompt,
        speaker_name=finalizer.get("name", "会议助理"),
        current_round=current_round,
        node_id="finalizing",
    )
    logger.info("meeting finalize_node: round_results=%s, final_text_len=%s", len(round_results), len(final_text))

    report_prompt = (
        f"会议类型：{guidance['name']}\n"
        f"会议目标：{topic}\n"
        f"目标产出格式：{guidance['final_output']}\n"
        f"预期产出补充：{merged.get('expected_output') or '无'}\n"
        f"会议纪要：\n{final_text}\n"
        f"完整讨论：\n{all_discussion}\n\n"
        "请直接生成面向业务落地的会议报告，突出结论、依据、下一步和风险，不要写额外说明。"
    )
    deliverable_text = await _agent_call(
        merged,
        run_ctx,
        finalizer,
        report_prompt,
        speaker_name=finalizer.get("name", "会议助理"),
        current_round=current_round,
        node_id="finalizing",
    )
    result = {"final_minutes": final_text, "deliverable_output": deliverable_text}
    if "last_user_event_seq" in consumed:
        result["last_user_event_seq"] = consumed["last_user_event_seq"]
    return result


def meeting_router(state: MeetingState) -> str:
    current = int(state.get("current_round") or 0)
    max_rounds = max(1, int(state.get("max_rounds") or 2))
    if current > max_rounds:
        return "finalize"
    decision = state.get("host_decision") or {}
    if str(decision.get("action") or "").strip().lower() == "finalize":
        return "finalize"
    return "next_agent"


def _after_speak_router(state: MeetingState) -> str:
    if state.get("host"):
        return "host_integrate"
    return meeting_router(state)


def build_meeting_graph(
    strategy: str = "solution_design",
    config: dict | None = None,
    checkpointer=None,
) -> StateGraph:
    if strategy not in IMPLEMENTED_STRATEGIES:
        strategy = "solution_design"

    builder = StateGraph(MeetingState)
    builder.add_node("goal", goal_node)
    builder.add_node("materials", materials_node)
    builder.add_node("opening", opening_node)
    builder.add_node("agent_speak", agent_speak_node)
    builder.add_node("host_integrate", host_integrate_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("goal")
    builder.add_edge("goal", "materials")
    builder.add_edge("materials", "opening")
    builder.add_edge("opening", "agent_speak")
    builder.add_conditional_edges(
        "host_integrate",
        meeting_router,
        {
            "next_agent": "agent_speak",
            "finalize": "finalize",
        },
    )
    builder.add_conditional_edges(
        "agent_speak",
        _after_speak_router,
        {
            "host_integrate": "host_integrate",
            "next_agent": "agent_speak",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
