"""Meeting mode routes."""
from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from quart import Response as QuartResponse
from quart import request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_ref: AgentSystemPlugin | None = None
_runtime = None


def register_meeting_routes(plugin: AgentSystemPlugin) -> None:
    global _plugin_ref
    _plugin_ref = plugin
    routes = [
        ("/meeting/types", _list_types, ["GET"], "会议类型列表"),
        ("/meeting/meetings", _list_meetings, ["GET"], "会议列表"),
        ("/meeting/meetings/summaries", _list_meeting_summaries, ["GET"], "会议摘要列表"),
        ("/meeting/meetings", _create_meeting, ["POST"], "创建会议"),
        ("/meeting/meetings/<meeting_id>", _get_meeting, ["GET"], "会议详情"),
        ("/meeting/meetings/<meeting_id>", _update_meeting, ["PATCH"], "更新会议"),
        ("/meeting/meetings/<meeting_id>/start", _start_meeting, ["POST"], "启动会议"),
        ("/meeting/meetings/<meeting_id>/cancel", _cancel_meeting, ["POST"], "取消会议"),
        ("/meeting/meetings/<meeting_id>/events", _meeting_events, ["GET"], "会议事件流"),
        ("/meeting/meetings/<meeting_id>/input", _submit_input, ["POST"], "会议用户发言"),
        ("/meeting/meetings/<meeting_id>/hitl", _respond_hitl, ["POST"], "会议 HITL 响应"),
        ("/meeting/meetings/<meeting_id>/continue", _continue_meeting, ["POST"], "续会"),
        ("/meeting/meetings/<meeting_id>/artifacts", _list_artifacts, ["GET"], "会议交付物"),
    ]
    for path, handler, methods, desc in routes:
        plugin.context.register_web_api(path, handler, methods, desc)
    logger.info("Meeting mode API routes registered")


def _get_meeting_service():
    from ..database import get_database
    from ..services.meeting_service import MeetingService

    db = get_database()
    return MeetingService(db, _plugin_ref.context if _plugin_ref else None)


def _get_meeting_runtime():
    global _runtime
    if _runtime is None:
        from ..services.meeting_runtime import MeetingRuntime

        _runtime = MeetingRuntime(max_concurrent=3)
    return _runtime


async def _list_types():
    try:
        return Response().ok(_get_meeting_service().list_types()).__dict__
    except Exception as e:
        logger.error(f"Failed to list meeting types: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_meetings():
    try:
        return Response().ok(_get_meeting_service().list_meetings(dict(request.args))).__dict__
    except Exception as e:
        logger.error(f"Failed to list meetings: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_meeting_summaries():
    try:
        return Response().ok({"meetings": _get_meeting_service().list_meeting_summaries(_ids_from_request())}).__dict__
    except Exception as e:
        logger.error(f"Failed to list meeting summaries: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_meeting():
    try:
        data = await request.get_json() or {}
        meeting = _get_meeting_service().create_meeting(data)
        await _get_meeting_runtime().start(meeting["id"], _get_meeting_service)
        return Response().ok(meeting, "会议创建成功，已自动启动").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_meeting(meeting_id: str):
    try:
        include_events = request.args.get("include_events") == "1"
        events_limit = request.args.get("events_limit", type=int) or 500
        return Response().ok(
            _get_meeting_service().get_meeting(
                meeting_id,
                include_events=include_events,
                events_limit=events_limit,
            )
        ).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to get meeting {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_meeting(meeting_id: str):
    try:
        data = await request.get_json() or {}
        return Response().ok(_get_meeting_service().update_meeting(meeting_id, data), "会议已更新").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to update meeting {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _start_meeting(meeting_id: str):
    try:
        result = await _get_meeting_runtime().start(meeting_id, _get_meeting_service)
        return Response().ok(result, "会议已启动").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__


async def _cancel_meeting(meeting_id: str):
    try:
        result = await _get_meeting_runtime().cancel(meeting_id, _get_meeting_service)
        return Response().ok(result, "会议已取消").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to cancel meeting {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to start meeting {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _submit_input(meeting_id: str):
    try:
        data = await request.get_json() or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return Response().error("发言内容不能为空").__dict__
        return Response().ok(_get_meeting_service().submit_input(meeting_id, text), "发言已提交").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to submit meeting input {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _respond_hitl(meeting_id: str):
    try:
        data = await request.get_json() or {}
        return Response().ok(await _get_meeting_service().respond_hitl(meeting_id, data), "已提交人工确认").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to respond meeting HITL {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _continue_meeting(meeting_id: str):
    try:
        data = await request.get_json() or {}
        meeting = _get_meeting_service().continue_meeting(meeting_id, data)
        await _get_meeting_runtime().start(meeting_id, _get_meeting_service)
        return Response().ok(meeting, "续会已创建，已自动启动").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to continue meeting {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_artifacts(meeting_id: str):
    try:
        return Response().ok(_get_meeting_service().list_artifacts(meeting_id)).__dict__
    except Exception as e:
        logger.error(f"Failed to list meeting artifacts {meeting_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _meeting_events(meeting_id: str):
    if request.args.get("stream") == "0" or request.headers.get("accept", "").find("text/event-stream") < 0:
        try:
            limit = request.args.get("limit", type=int) or 300
            after_seq = request.args.get("after_seq", type=int)
            tail = request.args.get("tail") == "1"
            events = _get_meeting_service().list_events(meeting_id, limit=limit, after_seq=after_seq, tail=tail)
            return Response().ok({"events": events}).__dict__
        except Exception as e:
            logger.error(f"Failed to list meeting events {meeting_id}: {e}", exc_info=True)
            return Response().error(str(e)).__dict__

    requested_after_seq = request.args.get("after_seq", type=int) or 0

    async def event_generator():
        service = _get_meeting_service()
        runtime = _get_meeting_runtime()
        live_queue = runtime.subscribe(meeting_id)
        after_seq = requested_after_seq
        last_status = ""
        last_snapshot_at = 0.0
        last_db_poll_at = 0.0
        try:
            meeting = service.get_meeting_status(meeting_id)
            last_status = meeting.get("status", "")
            yield _sse("phase", {"status": last_status, "stage": meeting.get("stage"), "progress": meeting.get("progress", 0)})
        except Exception:
            pass

        try:
            for tick in range(3600):
                try:
                    now = time.monotonic()
                    if now - last_db_poll_at >= 1:
                        last_db_poll_at = now
                        for event in service.list_events(meeting_id, limit=300, after_seq=after_seq):
                            after_seq = max(after_seq, int(event.get("seq") or 0))
                            yield _sse(event.get("event_type") or "log", event)

                    if now - last_snapshot_at >= 2:
                        last_snapshot_at = now
                        meeting = service.get_meeting_status(meeting_id)
                        if meeting.get("status") != last_status:
                            last_status = meeting.get("status", "")
                            yield _sse("phase", {"status": last_status, "stage": meeting.get("stage"), "progress": meeting.get("progress", 0)})

                    try:
                        live_event = await asyncio.wait_for(live_queue.get(), timeout=1.0)
                        event_name = live_event.get("event_type") or "log"
                        if event_name == "done":
                            yield _sse("done", live_event.get("payload") or {"status": last_status})
                            break
                        if event_name == "phase":
                            payload = live_event.get("payload") or {}
                            if payload.get("status"):
                                last_status = payload.get("status")
                        yield _sse(event_name, live_event)
                    except asyncio.TimeoutError:
                        if tick % 15 == 0:
                            yield _sse("heartbeat", {})

                    if last_status in ("completed", "failed", "cancelled"):
                        yield _sse("done", {"status": last_status})
                        break
                except Exception as e:
                    yield _sse("error", {"message": str(e)})
                    break
        finally:
            runtime.unsubscribe(meeting_id, live_queue)

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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ids_from_request() -> list[str]:
    values = request.args.getlist("ids")
    if not values:
        values = [request.args.get("ids", "")]
    ids: list[str] = []
    for value in values:
        ids.extend(item.strip() for item in str(value).split(",") if item.strip())
    return list(dict.fromkeys(ids))
