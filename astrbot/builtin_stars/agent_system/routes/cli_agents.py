"""CLI Agent facade routes."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from quart import Response as QuartResponse
from quart import request

from astrbot.core import logger
from astrbot.dashboard.routes.route import Response

if TYPE_CHECKING:
    from ..main import AgentSystemPlugin

_plugin_ref: AgentSystemPlugin | None = None


def register_cli_agent_routes(plugin: AgentSystemPlugin) -> None:
    global _plugin_ref
    _plugin_ref = plugin
    routes = [
        ("/cli-agents/detect", _detect_agents, ["GET"], "检测可用 CLI Agent"),
        ("/cli-agents/clients", _list_clients, ["GET"], "CLI Agent 客户端列表"),
        ("/cli-agents/clients", _create_client, ["POST"], "创建 CLI Agent 客户端"),
        (
            "/cli-agents/clients/check-all",
            _check_all_clients,
            ["POST"],
            "检测全部 CLI Agent 客户端",
        ),
        (
            "/cli-agents/clients/<client_id>",
            _get_client,
            ["GET"],
            "获取 CLI Agent 客户端",
        ),
        (
            "/cli-agents/clients/<client_id>",
            _update_client,
            ["PATCH"],
            "更新 CLI Agent 客户端",
        ),
        (
            "/cli-agents/clients/<client_id>",
            _delete_client,
            ["DELETE"],
            "停用 CLI Agent 客户端",
        ),
        (
            "/cli-agents/clients/<client_id>/check",
            _check_client,
            ["POST"],
            "检测 CLI Agent 客户端",
        ),
        ("/cli-agents/workspaces", _list_workspaces, ["GET"], "CLI Agent 工作区列表"),
        (
            "/cli-agents/workspaces",
            _create_workspace,
            ["POST"],
            "创建 CLI Agent 工作区",
        ),
        (
            "/cli-agents/workspaces/<workspace_id>",
            _get_workspace,
            ["GET"],
            "获取 CLI Agent 工作区",
        ),
        (
            "/cli-agents/workspaces/<workspace_id>",
            _update_workspace,
            ["PATCH"],
            "更新 CLI Agent 工作区",
        ),
        (
            "/cli-agents/workspaces/<workspace_id>",
            _delete_workspace,
            ["DELETE"],
            "归档 CLI Agent 工作区",
        ),
        ("/cli-agents/sessions", _list_sessions, ["GET"], "CLI Agent 会话列表"),
        ("/cli-agents/sessions", _create_session, ["POST"], "创建 CLI Agent 会话"),
        (
            "/cli-agents/sessions/<session_id>",
            _get_session,
            ["GET"],
            "获取 CLI Agent 会话",
        ),
        (
            "/cli-agents/sessions/<session_id>",
            _update_session,
            ["PATCH"],
            "更新 CLI Agent 会话",
        ),
        (
            "/cli-agents/sessions/<session_id>",
            _delete_session,
            ["DELETE"],
            "归档 CLI Agent 会话",
        ),
        (
            "/cli-agents/sessions/<session_id>/messages",
            _list_messages,
            ["GET"],
            "CLI Agent 会话消息列表",
        ),
        (
            "/cli-agents/sessions/<session_id>/messages",
            _send_message,
            ["POST"],
            "发送 CLI Agent 会话消息",
        ),
        (
            "/cli-agents/sessions/<session_id>/send",
            _send_message_stream,
            ["POST"],
            "流式发送 CLI Agent 会话消息",
        ),
        (
            "/cli-agents/sessions/<session_id>/stream",
            _stream_session,
            ["GET"],
            "CLI Agent SSE 流",
        ),
        (
            "/cli-agents/sessions/<session_id>/events",
            _session_events,
            ["GET"],
            "CLI Agent 会话事件流",
        ),
        (
            "/cli-agents/sessions/<session_id>/stop",
            _stop_session,
            ["POST"],
            "停止 CLI Agent 会话",
        ),
        (
            "/cli-agents/sessions/<session_id>/model",
            _set_model,
            ["POST"],
            "切换 CLI Agent 模型",
        ),
        (
            "/cli-agents/sessions/<session_id>/mode",
            _set_mode,
            ["POST"],
            "切换 CLI Agent 模式",
        ),
        (
            "/cli-agents/permissions",
            _list_permissions,
            ["GET"],
            "CLI Agent 权限请求列表",
        ),
        (
            "/cli-agents/permissions/<permission_id>/respond",
            _respond_permission,
            ["POST"],
            "响应 CLI Agent 权限请求",
        ),
    ]
    for path, handler, methods, desc in routes:
        plugin.context.register_web_api(path, handler, methods, desc)
    logger.info("CLI Agent API routes registered")


def _get_service():
    from ..database import get_database
    from ..services.cli_agent_service import CliAgentService

    return CliAgentService(get_database())


async def _detect_agents():
    try:
        from ..services.cli_agent_detector import detect_installed_agents

        return Response().ok(await detect_installed_agents()).__dict__
    except Exception as e:
        logger.error(f"Failed to detect CLI Agents: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_clients():
    try:
        include_disabled = request.args.get("include_disabled") == "1"
        return Response().ok(_get_service().list_clients(include_disabled)).__dict__
    except Exception as e:
        logger.error(f"Failed to list CLI Agent clients: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_client():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().create_client(data), "CLI Agent 客户端创建成功")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create CLI Agent client: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_client(client_id: str):
    try:
        return Response().ok(_get_service().get_client(client_id)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to get CLI Agent client {client_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _update_client(client_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().update_client(client_id, data), "CLI Agent 客户端已更新")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to update CLI Agent client {client_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _delete_client(client_id: str):
    try:
        if not _get_service().delete_client(client_id):
            return Response().error(f"CLI Agent 客户端 '{client_id}' 不存在").__dict__
        return Response().ok({"success": True}, "CLI Agent 客户端已停用").__dict__
    except Exception as e:
        logger.error(
            f"Failed to delete CLI Agent client {client_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _check_client(client_id: str):
    try:
        return (
            Response()
            .ok(_get_service().check_client(client_id), "CLI Agent 检测完成")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__


async def _check_all_clients():
    try:
        results = _get_service().check_all_clients()
        return (
            Response()
            .ok({"checked": len(results), "results": results}, "CLI Agent 检测完成")
            .__dict__
        )
    except Exception as e:
        logger.error("Failed to check all CLI Agent clients", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_workspaces():
    try:
        include_inactive = request.args.get("include_inactive") == "1"
        return Response().ok(_get_service().list_workspaces(include_inactive)).__dict__
    except Exception as e:
        logger.error(f"Failed to list CLI Agent workspaces: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_workspace():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().create_workspace(data), "CLI Agent 工作区创建成功")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create CLI Agent workspace: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_workspace(workspace_id: str):
    try:
        return Response().ok(_get_service().get_workspace(workspace_id)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to get CLI Agent workspace {workspace_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _update_workspace(workspace_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(
                _get_service().update_workspace(workspace_id, data),
                "CLI Agent 工作区已更新",
            )
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to update CLI Agent workspace {workspace_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _delete_workspace(workspace_id: str):
    try:
        if not _get_service().delete_workspace(workspace_id):
            return (
                Response().error(f"CLI Agent 工作区 '{workspace_id}' 不存在").__dict__
            )
        return Response().ok({"success": True}, "CLI Agent 工作区已归档").__dict__
    except Exception as e:
        logger.error(
            f"Failed to delete CLI Agent workspace {workspace_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _list_sessions():
    try:
        return (
            Response()
            .ok(
                _get_service().list_sessions(
                    client_id=request.args.get("client_id"),
                    workspace_id=request.args.get("workspace_id"),
                )
            )
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list CLI Agent sessions: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _create_session():
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().create_session(data), "CLI Agent 会话创建成功")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to create CLI Agent session: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _get_session(session_id: str):
    try:
        return Response().ok(_get_service().get_session(session_id)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to get CLI Agent session {session_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _update_session(session_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(_get_service().update_session(session_id, data), "CLI Agent 会话已更新")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to update CLI Agent session {session_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _delete_session(session_id: str):
    try:
        if not _get_service().delete_session(session_id):
            return Response().error(f"CLI Agent 会话 '{session_id}' 不存在").__dict__
        return Response().ok({"success": True}, "CLI Agent 会话已归档").__dict__
    except Exception as e:
        logger.error(
            f"Failed to delete CLI Agent session {session_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _list_messages(session_id: str):
    try:
        return Response().ok(_get_service().list_messages(session_id)).__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to list CLI Agent messages {session_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _send_message(session_id: str):
    return await _send_message_stream(session_id)


async def _send_message_stream(session_id: str):
    try:
        data = await request.get_json() or {}
        content = str(data.get("content") or "").strip()
        if not content:
            raise ValueError("消息内容不能为空")
        from ..database import get_database
        from ..services.cli_agent_orchestrator import get_orchestrator

        runtime = await get_orchestrator(get_database()).ensure_session(session_id)
        asyncio.create_task(_background_send(runtime, content, session_id))
        return (
            Response()
            .ok(
                {"status": "accepted", "session_id": session_id}, "CLI Agent 消息已发送"
            )
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to send CLI Agent message {session_id}: {e}", exc_info=True
        )
        return Response().error(str(e)).__dict__


async def _background_send(runtime, content: str, session_id: str) -> None:
    try:
        await runtime.send_message(content)
    except Exception as e:
        logger.error(
            f"CLI Agent background send failed {session_id}: {e}", exc_info=True
        )


async def _stream_session(session_id: str):
    try:
        from ..database import get_database
        from ..services.cli_agent_orchestrator import get_orchestrator

        orchestrator = get_orchestrator(get_database())
        runtime = orchestrator.get_session(session_id)
        if runtime is None:
            runtime = await orchestrator.ensure_session(session_id)
        last_event_id = (
            request.headers.get("Last-Event-ID") or request.args.get("after_seq") or "0"
        )
        try:
            after_seq = int(last_event_id)
        except (TypeError, ValueError):
            after_seq = 0
        live_only = request.args.get("live") == "1" and after_seq <= 0

        async def event_stream():
            subscriber = runtime.subscribe(after_seq=after_seq, live_only=live_only)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            subscriber.__anext__(),
                            timeout=25,
                        )
                        yield _sse_message(event)
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            except asyncio.CancelledError:
                raise
            except StopAsyncIteration:
                return
            except Exception as e:
                yield _sse_message({"seq": 0, "type": "error", "message": str(e)})

        response = QuartResponse(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        response.timeout = None
        return response
    except ValueError as e:
        return _sse_error_response(str(e))
    except Exception as e:
        logger.error(
            f"Failed to stream CLI Agent session {session_id}: {e}", exc_info=True
        )
        return _sse_error_response(str(e))


async def _stop_session(session_id: str):
    try:
        return (
            Response()
            .ok(await _get_service().stop_session(session_id), "CLI Agent 会话已停止")
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__


async def _set_model(session_id: str):
    try:
        data = await request.get_json() or {}
        model_id = str(data.get("model_id") or data.get("modelId") or "").strip()
        if not model_id:
            raise ValueError("model_id 不能为空")
        from ..database import get_database
        from ..services.cli_agent_orchestrator import get_orchestrator

        runtime = await get_orchestrator(get_database()).ensure_session(session_id)
        return Response().ok(await runtime.set_model(model_id), "模型已切换").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to set CLI Agent model {session_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _set_mode(session_id: str):
    try:
        data = await request.get_json() or {}
        mode_id = str(data.get("mode_id") or data.get("modeId") or "").strip()
        if not mode_id:
            raise ValueError("mode_id 不能为空")
        from ..database import get_database
        from ..services.cli_agent_orchestrator import get_orchestrator

        runtime = await get_orchestrator(get_database()).ensure_session(session_id)
        return Response().ok(await runtime.set_mode(mode_id), "模式已切换").__dict__
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(f"Failed to set CLI Agent mode {session_id}: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _list_permissions():
    try:
        return (
            Response()
            .ok(_get_service().list_permissions(request.args.get("session_id")))
            .__dict__
        )
    except Exception as e:
        logger.error(f"Failed to list CLI Agent permissions: {e}", exc_info=True)
        return Response().error(str(e)).__dict__


async def _respond_permission(permission_id: str):
    try:
        data = await request.get_json() or {}
        return (
            Response()
            .ok(
                _get_service().respond_permission(permission_id, data), "权限响应已提交"
            )
            .__dict__
        )
    except ValueError as e:
        return Response().error(str(e)).__dict__
    except Exception as e:
        logger.error(
            f"Failed to respond CLI Agent permission {permission_id}: {e}",
            exc_info=True,
        )
        return Response().error(str(e)).__dict__


async def _session_events(session_id: str):
    async def event_generator():
        service = _get_service()
        after_seq = request.args.get("after_seq", type=int) or 0
        for _ in range(3600):
            try:
                events = service.list_events(session_id, after_seq=after_seq, limit=200)
                for event in events:
                    after_seq = max(after_seq, int(event.get("seq") or 0))
                    yield _sse(event.get("event_type") or "event", event)
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                break
            await asyncio.sleep(1)
        yield _sse("heartbeat", {})

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


def _sse_message(data: dict) -> str:
    seq = int(data.get("seq") or 0)
    prefix = f"id: {seq}\n" if seq else ""
    return f"{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_error_response(message: str) -> QuartResponse:
    async def event_stream():
        yield _sse_message({"seq": 0, "type": "error", "message": message})
        yield "data: [DONE]\n\n"

    response = QuartResponse(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    response.timeout = None
    return response
