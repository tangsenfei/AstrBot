"""GenericAgent workbench API routes."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from quart import Response as QuartResponse
from quart import g, request

from astrbot.core import logger
from astrbot.core.utils.datetime_utils import to_utc_isoformat
from astrbot.dashboard.routes.route import Response

from ..services.generic_agent_runtime import get_generic_agent_service

_plugin_ref = None


def register_generic_agent_routes(plugin) -> None:
    global _plugin_ref
    _plugin_ref = plugin
    routes = [
        ("/generic-agent/config", _get_config, ["GET"], "获取 GenericAgent 配置"),
        ("/generic-agent/config", _update_config, ["POST"], "更新 GenericAgent 配置"),
        ("/generic-agent/chat/send", _chat_send, ["POST"], "GenericAgent Chat 发送"),
        ("/generic-agent/runs", _list_runs, ["GET"], "GenericAgent 运行列表"),
        (
            "/generic-agent/runs/summaries",
            _list_run_summaries,
            ["GET"],
            "GenericAgent 运行摘要",
        ),
        ("/generic-agent/runs", _create_run, ["POST"], "创建 GenericAgent 运行"),
        (
            "/generic-agent/runs/<run_id>",
            _get_run,
            ["GET"],
            "获取 GenericAgent 运行详情",
        ),
        (
            "/generic-agent/runs/<run_id>/events",
            _list_events,
            ["GET"],
            "GenericAgent 运行事件",
        ),
        (
            "/generic-agent/runs/<run_id>/stop",
            _stop_run,
            ["POST"],
            "停止 GenericAgent 运行",
        ),
        ("/generic-agent/tools", _list_tools, ["GET"], "GenericAgent 工具策略"),
        (
            "/generic-agent/tools",
            _update_tools,
            ["PATCH"],
            "更新 GenericAgent 工具策略",
        ),
        (
            "/generic-agent/skill-reviews",
            _list_skill_reviews,
            ["GET"],
            "GenericAgent 技能审核列表",
        ),
        (
            "/generic-agent/skill-reviews/<review_id>/approve",
            _approve_skill_review,
            ["POST"],
            "批准 GenericAgent 技能审核",
        ),
        (
            "/generic-agent/skill-reviews/<review_id>/reject",
            _reject_skill_review,
            ["POST"],
            "拒绝 GenericAgent 技能审核",
        ),
    ]
    for path, handler, methods, desc in routes:
        plugin.context.register_web_api(path, handler, methods, desc)
    logger.info("GenericAgent API routes registered")


def _get_service():
    from ..database import get_database

    context = _plugin_ref.context if _plugin_ref else None
    return get_generic_agent_service(get_database(), context)


def _get_history_manager():
    context = _plugin_ref.context if _plugin_ref else None
    return getattr(context, "message_history_manager", None)


async def _chat_send():
    try:
        data = await request.get_json() or {}
    except Exception:
        data = {}

    session_id = str(data.get("session_id") or "").strip()
    if not session_id:
        return Response().error("session_id 不能为空").__dict__

    message_parts = _normalize_chat_message_parts(data.get("message"))
    goal = _message_parts_to_goal(message_parts).strip()
    if not goal:
        return Response().error("message 不能为空").__dict__

    message_id = str(data.get("message_id") or uuid.uuid4())
    llm_checkpoint_id = str(data.get("_llm_checkpoint_id") or uuid.uuid4())
    username = g.get("username", "guest")
    history_manager = _get_history_manager()
    saved_user_record = None
    if history_manager:
        saved_user_record = await history_manager.insert(
            platform_id="webchat",
            user_id=session_id,
            content={"type": "user", "message": message_parts},
            sender_id=username,
            sender_name=username,
            llm_checkpoint_id=llm_checkpoint_id,
        )

    async def event_generator():
        service = _get_service()
        run_id = ""
        after_seq = 0
        try:
            yield _chat_sse(
                {
                    "type": "session_id",
                    "data": None,
                    "session_id": session_id,
                }
            )
            if saved_user_record:
                yield _chat_sse(
                    {
                        "type": "user_message_saved",
                        "data": {
                            "id": saved_user_record.id,
                            "created_at": to_utc_isoformat(saved_user_record.created_at),
                            "llm_checkpoint_id": llm_checkpoint_id,
                        },
                    }
                )

            run = await service.enqueue_run(
                {
                    "source": "chat",
                    "goal": goal,
                    "workspace_path": str(data.get("workspace_path") or "").strip(),
                    "constraints": _chat_constraints(data),
                    "expected_outputs": data.get("expected_outputs") or [
                        "在聊天中给出最终结果",
                        "如生成或修改文件，请列出路径",
                    ],
                    "parent_task_id": f"chat:{session_id}:{message_id}",
                }
            )
            run_id = run["id"]
            yield _chat_sse({"type": "generic_agent_run", "data": run})
            yield _chat_sse(
                {
                    "type": "plain",
                    "chain_type": "reasoning",
                    "streaming": True,
                    "data": f"GenericAgent 运行已加入队列：{run_id}\n",
                }
            )

            while True:
                run = service.get_run(run_id)
                for event in service.list_events(run_id, after_seq=after_seq, limit=200):
                    after_seq = max(after_seq, int(event.get("seq") or 0))
                    text = _event_to_chat_reasoning(event)
                    if text:
                        yield _chat_sse(
                            {
                                "type": "plain",
                                "chain_type": "reasoning",
                                "streaming": True,
                                "data": text,
                            }
                        )

                if run.get("status") in {"completed", "failed", "cancelled"}:
                    final_text = _run_final_text(run, run_id)
                    if final_text:
                        yield _chat_sse(
                            {
                                "type": "plain",
                                "streaming": True,
                                "data": final_text,
                            }
                        )
                    saved_bot_record = None
                    if history_manager:
                        saved_bot_record = await history_manager.insert(
                            platform_id="webchat",
                            user_id=session_id,
                            content={
                                "type": "bot",
                                "message": [{"type": "plain", "text": final_text}],
                                "refs": {"generic_agent_run_id": run_id},
                            },
                            sender_id="bot",
                            sender_name="GenericAgent",
                            llm_checkpoint_id=llm_checkpoint_id,
                        )
                    if saved_bot_record:
                        yield _chat_sse(
                            {
                                "type": "message_saved",
                                "data": {
                                    "id": saved_bot_record.id,
                                    "created_at": to_utc_isoformat(
                                        saved_bot_record.created_at
                                    ),
                                    "llm_checkpoint_id": llm_checkpoint_id,
                                    "refs": {"generic_agent_run_id": run_id},
                                },
                            }
                        )
                    yield _chat_sse({"type": "end", "data": ""})
                    break

                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"GenericAgent chat stream failed: {e}", exc_info=True)
            yield _chat_sse({"type": "error", "data": str(e)})
            if run_id:
                yield _chat_sse({"type": "end", "data": ""})

    response = QuartResponse(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    response.timeout = None
    return response


async def _get_config():
    try:
        return Response().ok(_get_service().get_config()).__dict__
    except Exception as e:
        logger.error(f"Failed to get GenericAgent config: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_config():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().update_config(data), "GenericAgent 配置已更新")
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to update GenericAgent config: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_runs():
    try:
        status = request.args.get("status")
        if request.args.get("page") or request.args.get("page_size"):
            page = int(request.args.get("page") or 1)
            page_size = int(request.args.get("page_size") or 30)
            return (
                Response()
                .ok(
                    _get_service().list_runs_page(
                        status=status,
                        source=request.args.get("source"),
                        q=request.args.get("q"),
                        page=page,
                        page_size=page_size,
                    )
                )
                .__dict__
            )
        limit = int(request.args.get("limit") or 100)
        return (
            Response().ok(_get_service().list_runs(status=status, limit=limit)).__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list GenericAgent runs: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_run_summaries():
    try:
        ids = _ids_from_request()
        return Response().ok({"runs": _get_service().list_run_summaries(ids)}).__dict__
    except Exception as e:
        logger.error(f"Failed to list GenericAgent run summaries: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_run():
    try:
        data = await request.get_json() or {}
        run = await _get_service().enqueue_run(data)
        return Response().ok(run, "GenericAgent 任务已加入队列").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create GenericAgent run: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_run(run_id: str):
    try:
        return Response().ok(_get_service().get_run(run_id)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to get GenericAgent run {run_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_events(run_id: str):
    if request.args.get("stream") != "0" and request.headers.get("accept", "").find("text/event-stream") >= 0:
        return await _stream_events(run_id)
    try:
        after_seq = int(request.args.get("after_seq") or 0)
        limit = int(request.args.get("limit") or 500)
        return (
            Response()
            .ok(_get_service().list_events(run_id, after_seq=after_seq, limit=limit))
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to list GenericAgent events {run_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _stream_events(run_id: str):
    requested_after_seq = request.args.get("after_seq", type=int) or 0

    async def event_generator():
        service = _get_service()
        after_seq = requested_after_seq
        last_status = ""
        try:
            run = service.get_run(run_id)
            last_status = run.get("status", "")
            yield _sse("phase", _run_phase(run))
        except Exception as e:
            yield _sse("error", {"message": str(e)})
            return

        for tick in range(3600):
            try:
                run = service.get_run(run_id)
                if run.get("status") != last_status:
                    last_status = run.get("status", "")
                    yield _sse("phase", _run_phase(run))

                for event in service.list_events(run_id, after_seq=after_seq, limit=500):
                    after_seq = max(after_seq, int(event.get("seq") or 0))
                    yield _sse(event.get("event_type") or "log", event)

                if last_status in {"completed", "failed", "cancelled"}:
                    yield _sse("done", _run_phase(run))
                    break

                if tick % 15 == 0:
                    yield _sse("heartbeat", {})
                await asyncio.sleep(1)
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                break

    response = QuartResponse(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    response.timeout = None
    return response


async def _stop_run(run_id: str):
    try:
        return (
            Response()
            .ok(await _get_service().stop_run(run_id), "GenericAgent 停止请求已处理")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to stop GenericAgent run {run_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_tools():
    try:
        return Response().ok(_get_service().get_tool_policies()).__dict__
    except Exception as e:
        logger.error(f"Failed to list GenericAgent tools: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_tools():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(
                _get_service().update_tool_policies(data), "GenericAgent 工具策略已更新"
            )
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to update GenericAgent tools: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_skill_reviews():
    try:
        status = request.args.get("status")
        return Response().ok(_get_service().list_skill_reviews(status=status)).__dict__
    except Exception as e:
        logger.error(f"Failed to list GenericAgent skill reviews: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _approve_skill_review(review_id: str):
    try:
        return (
            Response()
            .ok(
                _get_service().approve_skill_review(review_id),
                "GenericAgent 技能已同步到 NiceBot 技能库",
            )
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__


async def _reject_skill_review(review_id: str):
    try:
        return (
            Response()
            .ok(
                _get_service().reject_skill_review(review_id),
                "GenericAgent 技能审核已拒绝",
            )
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to reject GenericAgent skill review {review_id}: {e}",
            exc_info=True,
        )
        return Response().error(str(e)).__dict__


def _ids_from_request() -> list[str]:
    values = request.args.getlist("ids")
    if not values:
        values = [request.args.get("ids", "")]
    ids: list[str] = []
    for value in values:
        ids.extend(item.strip() for item in str(value).split(",") if item.strip())
    return list(dict.fromkeys(ids))


def _run_phase(run: dict) -> dict:
    return {
        "id": run.get("id"),
        "status": run.get("status", ""),
        "progress": int(run.get("progress") or 0),
        "queue_position": run.get("queue_position"),
        "summary": run.get("summary", ""),
        "error": run.get("error", ""),
        "artifacts": run.get("artifacts", []),
        "updated_at": run.get("updated_at"),
        "completed_at": run.get("completed_at"),
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chat_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _normalize_chat_message_parts(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        text = raw.strip()
        return [{"type": "plain", "text": text}] if text else []
    if not isinstance(raw, list):
        return []
    parts: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            text = str(item or "").strip()
            if text:
                parts.append({"type": "plain", "text": text})
            continue
        part_type = str(item.get("type") or "plain")
        if part_type == "plain":
            text = str(item.get("text") or item.get("content") or "").strip()
            if text:
                parts.append({"type": "plain", "text": text})
            continue
        copied = {
            "type": part_type,
            "attachment_id": item.get("attachment_id"),
            "filename": item.get("filename"),
        }
        parts.append({key: value for key, value in copied.items() if value})
    return parts


def _message_parts_to_goal(parts: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    attachments: list[str] = []
    for part in parts:
        if part.get("type") == "plain":
            if text := str(part.get("text") or "").strip():
                lines.append(text)
        elif filename := part.get("filename"):
            attachments.append(str(filename))
    if attachments:
        lines.append("附件: " + ", ".join(attachments))
    return "\n".join(lines)


def _chat_constraints(data: dict[str, Any]) -> str:
    constraints = str(data.get("constraints") or "").strip()
    base = "来自 Chat 的 GenericAgent 请求；遵守全局工具开关；最终回复要适合直接展示给用户。"
    return f"{base}\n{constraints}" if constraints else base


def _event_to_chat_reasoning(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "")
    title = str(event.get("title") or "").strip()
    payload = event.get("payload") or {}
    if event_type in {"completed", "failed", "cancelled"}:
        return ""
    if event_type == "llm_chunk":
        text = str(payload.get("text") or "").strip()
        return f"{text}\n" if text else ""
    if event_type == "terminal":
        text = str(payload.get("text") or "").strip()
        return f"\n[终端] {text}\n" if text else ""
    if event_type == "tool_call":
        tool_name = payload.get("tool_name") or title
        return f"\n[工具] {tool_name}\n" if tool_name else ""
    if title:
        return f"\n[{event_type or '事件'}] {title}\n"
    return ""


def _run_final_text(run: dict[str, Any], run_id: str) -> str:
    artifacts = run.get("artifacts") or []
    final_text = ""
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            if artifact.get("artifact_type") == "final_output":
                final_text = str(artifact.get("content") or "").strip()
                break
    if not final_text:
        final_text = str(run.get("summary") or run.get("error") or "GenericAgent 运行已结束").strip()
    link = f"/generic-agent?run={run_id}"
    if run.get("status") == "failed":
        final_text = f"GenericAgent 运行失败：{final_text}"
    elif run.get("status") == "cancelled":
        final_text = f"GenericAgent 运行已停止：{final_text}"
    return f"{final_text}\n\n[查看 GenericAgent 运行记录]({link})"
