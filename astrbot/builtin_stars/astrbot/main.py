import json
import traceback

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.core import logger
from astrbot.core.memory.pipeline_hooks import (
    on_agent_reply,
    on_tool_call,
    on_user_message,
)

from .long_term_memory import LongTermMemory


class Main(star.Star):
    def __init__(self, context: star.Context) -> None:
        self.context = context
        self.ltm = None
        try:
            self.ltm = LongTermMemory(self.context.astrbot_config_mgr, self.context)
        except BaseException as e:
            logger.error(f"聊天增强 err: {e}")

    def ltm_enabled(self, event: AstrMessageEvent):
        ltmse = self.context.get_config(umo=event.unified_msg_origin)[
            "provider_ltm_settings"
        ]
        return ltmse["group_icl_enable"] or ltmse["active_reply"]["enable"]

    @filter.platform_adapter_type(filter.PlatformAdapterType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """群聊记忆增强"""
        has_image_or_plain = False
        for comp in event.message_obj.message:
            if isinstance(comp, Plain) or isinstance(comp, Image):
                has_image_or_plain = True
                break

        if self.ltm_enabled(event) and self.ltm and has_image_or_plain:
            need_active = await self.ltm.need_active_reply(event)

            group_icl_enable = self.context.get_config(umo=event.unified_msg_origin)[
                "provider_ltm_settings"
            ]["group_icl_enable"]
            if group_icl_enable:
                """记录对话"""
                try:
                    await self.ltm.handle_message(event)
                except BaseException as e:
                    logger.error(e)

            if need_active:
                """主动回复"""
                provider = self.context.get_using_provider(event.unified_msg_origin)
                if not provider:
                    logger.error("未找到任何 LLM 提供商。请先配置。无法主动回复")
                    return
                try:
                    conv = None
                    session_curr_cid = await self.context.conversation_manager.get_curr_conversation_id(
                        event.unified_msg_origin,
                    )

                    if not session_curr_cid:
                        logger.error(
                            "当前未处于对话状态，无法主动回复，请确保 平台设置->会话隔离(unique_session) 未开启，并使用 /switch 序号 切换或者 /new 创建一个会话。",
                        )
                        return

                    conv = await self.context.conversation_manager.get_conversation(
                        event.unified_msg_origin,
                        session_curr_cid,
                    )

                    prompt = event.message_str

                    if not conv:
                        logger.error("未找到对话，无法主动回复")
                        return

                    yield event.request_llm(
                        prompt=prompt,
                        session_id=event.session_id,
                        conversation=conv,
                    )
                except BaseException as e:
                    logger.error(traceback.format_exc())
                    logger.error(f"主动回复失败: {e}")

    @filter.on_llm_request()
    async def decorate_llm_req(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        """在请求 LLM 前注入人格信息、Identifier、时间、回复内容等 System Prompt"""
        if self.ltm and self.ltm_enabled(event):
            try:
                await self.ltm.on_req_llm(event, req)
            except BaseException as e:
                logger.error(f"ltm: {e}")

    @filter.on_llm_response()
    async def record_llm_resp_to_ltm(
        self, event: AstrMessageEvent, resp: LLMResponse
    ) -> None:
        """在 LLM 响应后记录对话"""
        if self.ltm and self.ltm_enabled(event):
            try:
                await self.ltm.after_req_llm(event, resp)
            except Exception as e:
                logger.error(f"ltm: {e}")

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent) -> None:
        """消息发送后处理"""
        if self.ltm and self.ltm_enabled(event):
            try:
                clean_session = event.get_extra("_clean_ltm_session", False)
                if clean_session:
                    await self.ltm.remove_session(event)
            except Exception as e:
                logger.error(f"ltm: {e}")

    @filter.platform_adapter_type(filter.PlatformAdapterType.ALL)
    async def record_user_msg_for_memory(self, event: AstrMessageEvent) -> None:
        """记录用户消息到记忆系统"""
        if event.message_str and event.message_str.strip():
            on_user_message(
                agent_id=event.get_platform_name(),
                content=event.message_str,
                user_id=event.get_sender_id(),
            )

    @filter.on_llm_response()
    async def record_llm_resp_for_memory(
        self, event: AstrMessageEvent, resp: LLMResponse
    ) -> None:
        """记录 LLM 响应到记忆系统"""
        if resp.completion_text:
            on_agent_reply(
                agent_id=event.get_platform_name(),
                content=resp.completion_text,
            )

    @filter.on_llm_tool_respond()
    async def record_tool_call_for_memory(
        self, event: AstrMessageEvent, tool, tool_args, tool_result
    ) -> None:
        """记录工具调用到记忆系统"""
        try:
            tool_name = getattr(tool, "name", str(tool))
            params_str = json.dumps(tool_args or {}, ensure_ascii=False)
            success = not (tool_result and getattr(tool_result, "isError", False))

            result_text = ""
            if tool_result and hasattr(tool_result, "content") and tool_result.content:
                first_item = tool_result.content[0]
                if hasattr(first_item, "text"):
                    result_text = first_item.text
                else:
                    result_text = str(first_item)

            on_tool_call(
                agent_id=event.get_platform_name(),
                tool_name=tool_name,
                params=params_str,
                result=result_text,
                success=success,
            )
        except Exception as e:
            logger.warning(f"Memory: record tool call err: {e}")
