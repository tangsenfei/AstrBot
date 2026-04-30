"""
crewAI 集成模块

提供 AstrBot Provider 到 CrewAI 的桥接能力，包括：
1. AstrBotLLMAdapter: AstrBot Provider → CrewAI LLM
2. AstrBotToolAdapter: AstrBot FunctionTool → CrewAI Tool
3. CrewAIAgentFactory: 统一创建 CrewAI Agent/Crew/Task
4. MemoryProvider: 记忆系统（CrewAI Memory / SQLite 降级）
5. PlanningProvider: 规划系统（CrewAI PlanningConfig / Prompt 降级）

核心原则：所有底层执行走 CrewAI，AstrBot Provider 仅读取 LLM 模型配置。
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.core.star.context import Context
    from ..database import Database

logger = logging.getLogger("astrbot")
logger = logging.LoggerAdapter(logger, {"plugin_tag": "[Plug]"})

CREWAI_AVAILABLE = False
PLANNING_CONFIG_AVAILABLE = False
MEMORY_AVAILABLE = False

try:
    from crewai import Agent as CrewAIAgent
    from crewai import Crew as CrewAICrew
    from crewai import LLM as CrewAILLM
    from crewai import Process as CrewAIProcess
    from crewai import Task as CrewAITask
    from crewai.tools import BaseTool as CrewAIBaseTool
    from crewai.tools import tool as crewai_tool_decorator
    CREWAI_AVAILABLE = True
    logger.info("crewAI is available for agent execution")
except ImportError:
    logger.info("crewAI not available, using built-in lightweight implementations")

try:
    from crewai import PlanningConfig
    PLANNING_CONFIG_AVAILABLE = True
except ImportError:
    pass

try:
    from crewai.memory.unified_memory import Memory
    MEMORY_AVAILABLE = True
except ImportError:
    pass

PLANNING_EFFORT_MAP = {
    "low": {
        "reasoning_effort": "low",
        "max_steps": 5,
        "max_replans": 1,
        "prompt_template": "请简要列出完成以下任务的关键步骤（1-3步）：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n1. [步骤1]\n2. [步骤2]\n...",
    },
    "medium": {
        "reasoning_effort": "medium",
        "max_steps": 15,
        "max_replans": 3,
        "prompt_template": "请为以下任务制定详细的执行计划，包含具体步骤和预期结果：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n### 步骤1: [标题]\n- 描述: ...\n- 预期输出: ...\n\n### 步骤2: [标题]\n- 描述: ...\n- 预期输出: ...\n...",
    },
    "high": {
        "reasoning_effort": "high",
        "max_steps": 30,
        "max_replans": 5,
        "prompt_template": "请为以下任务制定非常详细的执行计划，包含问题分析、信息收集策略、详细执行步骤（含子步骤）、每步预期输出和风险评估：\n\n任务：{message}\n\n请按以下格式输出：\n## 执行计划\n\n### 问题分析\n- 核心问题: ...\n- 关键约束: ...\n\n### 信息收集\n- 需要的信息: ...\n- 获取方式: ...\n\n### 执行步骤\n#### 步骤1: [标题]\n- 描述: ...\n- 子步骤:\n  1.1. ...\n  1.2. ...\n- 预期输出: ...\n- 风险: ...\n- 备选方案: ...\n\n#### 步骤2: [标题]\n...\n\n### 总结\n- 预计总步骤数: ...\n- 关键里程碑: ...\n",
    },
}

PROVIDER_TYPE_TO_LITELLM_PREFIX = {
    "openai_chat_completion": "openai",
    "openai": "openai",
    "azure_chat_completion": "azure",
    "azure": "azure",
    "groq_chat_completion": "groq",
    "groq": "groq",
    "openrouter_chat_completion": "openrouter",
    "openrouter": "openrouter",
    "aihubmix_chat_completion": "openai",
    "aihubmix": "openai",
    "xai_chat_completion": "xai",
    "xai": "xai",
    "ollama_chat_completion": "ollama",
    "ollama": "ollama",
    "gemini_chat_completion": "gemini",
    "gemini": "gemini",
    "anthropic_chat_completion": "anthropic",
    "anthropic": "anthropic",
    "deepseek_chat_completion": "openai",
    "deepseek": "openai",
    "volcengine_chat_completion": "openai",
    "volcengine": "openai",
    "moonshot_chat_completion": "openai",
    "moonshot": "openai",
    "zhipu_chat_completion": "openai",
    "zhipu": "openai",
    "dashscope_chat_completion": "openai",
    "dashscope": "openai",
    "fastgpt_chat_completion": "openai",
    "fastgpt": "openai",
    "doubao_chat_completion": "openai",
    "doubao": "openai",
    "siliconflow_chat_completion": "openai",
    "siliconflow": "openai",
    "minimax_chat_completion": "openai",
    "minimax": "openai",
    "stepfun_chat_completion": "openai",
    "stepfun": "openai",
    "yi_chat_completion": "openai",
    "yi": "openai",
    "baichuan_chat_completion": "openai",
    "baichuan": "openai",
    "sensenova_chat_completion": "openai",
    "sensenova": "openai",
    "hunyuan_chat_completion": "openai",
    "hunyuan": "openai",
    "spark_chat_completion": "openai",
    "spark": "openai",
    "lingyi_chat_completion": "openai",
    "lingyi": "openai",
    "coze_chat_completion": "openai",
    "coze": "openai",
}


class AstrBotLLMAdapter:
    """将 AstrBot Provider 配置转换为 CrewAI LLM 实例

    读取 AstrBot Provider 的 provider_config（api_key, api_base, model 等），
    构造 CrewAI 的 LLM 对象。CrewAI 使用 litellm 格式的 model 名称，
    如 "openai/gpt-4o", "anthropic/claude-3" 等。
    """

    @staticmethod
    def create_llm(provider_id: str, model_name: str | None = None, context: "Context | None" = None) -> "CrewAILLM | None":
        """从 AstrBot Provider 创建 CrewAI LLM

        Args:
            provider_id: AstrBot Provider ID
            model_name: 模型名称（覆盖 Provider 默认模型）
            context: AstrBot Context 实例

        Returns:
            CrewAI LLM 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            logger.warning("CrewAI not available, cannot create LLM")
            return None

        if not context:
            logger.warning("Context not available, cannot create LLM")
            return None

        try:
            provider = context.get_provider_by_id(provider_id)
            if not provider:
                logger.warning(f"Provider '{provider_id}' not found")
                return None

            config = provider.provider_config

            api_keys = config.get("key", [])
            if isinstance(api_keys, list) and api_keys:
                api_key = api_keys[0]
            elif isinstance(api_keys, str):
                api_key = api_keys
            else:
                api_key = ""

            if api_key and api_key.startswith("$"):
                import os
                env_key = api_key[1:]
                if env_key.startswith("{") and env_key.endswith("}"):
                    env_key = env_key[1:-1]
                api_key = os.environ.get(env_key, "")

            api_base = config.get("api_base", None)

            provider_type = config.get("type", "openai_chat_completion")
            litellm_prefix = PROVIDER_TYPE_TO_LITELLM_PREFIX.get(provider_type, "openai")

            effective_model = model_name or config.get("model", "") or provider.get_model()
            if not effective_model or effective_model == "unknown":
                effective_model = "gpt-4o"

            if "/" in effective_model:
                crewai_model = effective_model
            else:
                crewai_model = f"{litellm_prefix}/{effective_model}"

            llm_kwargs = {
                "model": crewai_model,
            }

            if api_key:
                llm_kwargs["api_key"] = api_key
            if api_base:
                llm_kwargs["base_url"] = api_base

            api_version = config.get("api_version")
            if api_version:
                llm_kwargs["api_version"] = api_version

            timeout = config.get("timeout", 120)
            if timeout:
                llm_kwargs["timeout"] = timeout

            proxy = config.get("proxy")
            if proxy:
                llm_kwargs["additional_params"] = {"proxy": proxy}

            custom_headers = config.get("custom_headers")
            if custom_headers:
                if "additional_params" not in llm_kwargs:
                    llm_kwargs["additional_params"] = {}
                llm_kwargs["additional_params"]["default_headers"] = custom_headers

            llm = CrewAILLM(**llm_kwargs)
            logger.debug(f"Created CrewAI LLM: model={crewai_model}, base_url={api_base}")
            return llm

        except Exception as e:
            logger.error(f"Failed to create CrewAI LLM from provider '{provider_id}': {e}")
            return None

    @staticmethod
    def create_llm_from_provider(provider: Any, model_name: str | None = None) -> "CrewAILLM | None":
        """直接从 AstrBot Provider 实例创建 CrewAI LLM

        Args:
            provider: AstrBot Provider 实例
            model_name: 模型名称（覆盖 Provider 默认模型）

        Returns:
            CrewAI LLM 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            return None

        try:
            config = provider.provider_config
            provider_id = config.get("id", "")

            api_keys = config.get("key", [])
            if isinstance(api_keys, list) and api_keys:
                api_key = api_keys[0]
            elif isinstance(api_keys, str):
                api_key = api_keys
            else:
                api_key = ""

            if api_key and api_key.startswith("$"):
                import os
                env_key = api_key[1:]
                if env_key.startswith("{") and env_key.endswith("}"):
                    env_key = env_key[1:-1]
                api_key = os.environ.get(env_key, "")

            api_base = config.get("api_base", None)

            provider_type = config.get("type", "openai_chat_completion")
            litellm_prefix = PROVIDER_TYPE_TO_LITELLM_PREFIX.get(provider_type, "openai")

            effective_model = model_name or config.get("model", "") or provider.get_model()
            if not effective_model or effective_model == "unknown":
                effective_model = "gpt-4o"

            if "/" in effective_model:
                crewai_model = effective_model
            else:
                crewai_model = f"{litellm_prefix}/{effective_model}"

            llm_kwargs = {"model": crewai_model}
            if api_key:
                llm_kwargs["api_key"] = api_key
            if api_base:
                llm_kwargs["base_url"] = api_base

            api_version = config.get("api_version")
            if api_version:
                llm_kwargs["api_version"] = api_version

            timeout = config.get("timeout", 120)
            if timeout:
                llm_kwargs["timeout"] = timeout

            return CrewAILLM(**llm_kwargs)

        except Exception as e:
            logger.error(f"Failed to create CrewAI LLM from provider instance: {e}")
            return None


class AstrBotToolAdapter:
    """将 AstrBot FunctionTool 转换为 CrewAI Tool

    AstrBot 的工具需要 AstrMessageEvent 参数，CrewAI 的工具不需要。
    此适配器在调用时自动注入 MockEvent，使 AstrBot 工具可以在 CrewAI Agent 中使用。
    """

    @staticmethod
    def convert_tool(func_tool: Any, context: "Context | None" = None) -> "CrewAIBaseTool | None":
        """将单个 AstrBot FunctionTool 转换为 CrewAI Tool

        Args:
            func_tool: AstrBot FunctionTool 实例
            context: AstrBot Context 实例

        Returns:
            CrewAI BaseTool 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            return None

        try:
            tool_name = func_tool.name
            tool_desc = func_tool.description or f"Tool: {tool_name}"
            tool_params = func_tool.parameters or {}

            properties = tool_params.get("properties", {})
            required = tool_params.get("required", [])

            from pydantic import BaseModel, create_model

            field_definitions = {}
            for param_name, param_info in properties.items():
                param_type = str
                param_desc = param_info.get("description", "")
                default_val = ... if param_name in required else None
                field_definitions[param_name] = (param_type, default_val)

            if not field_definitions:
                field_definitions["_input"] = (str, "")

            ArgsModel = create_model(f"{tool_name}_args", **field_definitions)

            handler = func_tool.handler
            needs_event = False
            if handler:
                import inspect
                sig = inspect.signature(handler)
                params = list(sig.parameters.keys())
                if params and params[0] in ('event', 'AstrMessageEvent'):
                    needs_event = True

            @crewai_tool_decorator(name=tool_name, description=tool_desc, args_schema=ArgsModel)
            def adapted_tool(self, **kwargs) -> str:
                return ""

            class _ToolWrapper:
                def __init__(self, handler_fn, needs_event_flag, ctx):
                    self._handler = handler_fn
                    self._needs_event = needs_event_flag
                    self._context = ctx

                async def run(self, **kwargs) -> str:
                    if not self._handler:
                        return f"Tool '{tool_name}' has no handler"

                    try:
                        if "_input" in kwargs:
                            kwargs.pop("_input")

                        if self._needs_event:
                            mock_event = _create_mock_event("")
                            result = await self._handler(mock_event, **kwargs)
                        else:
                            result = await self._handler(**kwargs)

                        if result is None:
                            return ""
                        return str(result)
                    except Exception as e:
                        return f"Tool execution error: {e}"

            wrapper = _ToolWrapper(handler, needs_event, context)

            class _CrewAIToolImpl(CrewAIBaseTool):
                name: str = tool_name
                description: str = tool_desc
                args_schema: type = ArgsModel
                _wrapper: Any = None

                def _run(self, **kwargs) -> str:
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                self._wrapper.run(**kwargs)
                            )
                            return future.result(timeout=300)
                    except RuntimeError:
                        return asyncio.run(self._wrapper.run(**kwargs))

            tool_instance = _CrewAIToolImpl()
            tool_instance._wrapper = wrapper
            return tool_instance

        except Exception as e:
            logger.error(f"Failed to convert AstrBot tool '{getattr(func_tool, 'name', 'unknown')}': {e}")
            return None

    @staticmethod
    def convert_tools(tool_ids: list[str], context: "Context | None" = None) -> list["CrewAIBaseTool"]:
        """批量转换 AstrBot 工具为 CrewAI Tool

        Args:
            tool_ids: 工具 ID 列表
            context: AstrBot Context 实例

        Returns:
            CrewAI Tool 列表
        """
        if not CREWAI_AVAILABLE or not context:
            return []

        tools = []
        try:
            tool_manager = context.get_llm_tool_manager()
            if not tool_manager:
                return []

            for tool_id in tool_ids:
                func_tool = tool_manager.get_func(tool_id)
                if func_tool:
                    crewai_tool = AstrBotToolAdapter.convert_tool(func_tool, context)
                    if crewai_tool:
                        tools.append(crewai_tool)
        except Exception as e:
            logger.error(f"Failed to convert tools: {e}")

        return tools


class CrewAIAgentFactory:
    """统一创建 CrewAI Agent/Crew/Task 的工厂类

    所有智能体系统的底层执行都通过此工厂创建 CrewAI 对象，
    确保统一使用 AstrBot Provider 的 LLM 配置。
    """

    @staticmethod
    def create_agent(
        agent_model: Any,
        context: "Context | None" = None,
        extra_tools: list["CrewAIBaseTool"] | None = None,
        disable_planning: bool = False,
    ) -> "CrewAIAgent | None":
        """从 Agent 数据模型创建 CrewAI Agent

        Args:
            agent_model: Agent 数据模型（来自 models.py）
            context: AstrBot Context 实例
            extra_tools: 额外的 CrewAI 工具
            disable_planning: 禁用 planning（对话场景下建议禁用，避免无限规划循环）

        Returns:
            CrewAI Agent 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            logger.warning("CrewAI not available, cannot create Agent")
            return None

        try:
            llm = None
            if agent_model.provider_id and context:
                llm = AstrBotLLMAdapter.create_llm(
                    provider_id=agent_model.provider_id,
                    model_name=agent_model.model_name,
                    context=context,
                )

            tools = []
            if agent_model.tools and context:
                tools = AstrBotToolAdapter.convert_tools(agent_model.tools, context)
            if extra_tools:
                tools.extend(extra_tools)

            agent_kwargs = {
                "role": agent_model.role or agent_model.name,
                "goal": agent_model.goal or "",
                "backstory": agent_model.backstory or "",
                "max_iter": agent_model.max_iter or 20,
                "allow_delegation": agent_model.allow_delegation or False,
                "verbose": agent_model.verbose or False,
                "tools": tools,
            }

            if llm:
                agent_kwargs["llm"] = llm

            if agent_model.planning and not disable_planning:
                planning_effort = "medium"
                if hasattr(agent_model, 'planning_effort') and agent_model.planning_effort:
                    planning_effort = agent_model.planning_effort.value if hasattr(agent_model.planning_effort, 'value') else str(agent_model.planning_effort)

                if PLANNING_CONFIG_AVAILABLE:
                    agent_kwargs["planning"] = True
                    agent_kwargs["planning_config"] = PlanningConfig(
                        planning_effort=planning_effort,
                    )
                else:
                    agent_kwargs["planning"] = True

            if hasattr(agent_model, 'memory_config') and agent_model.memory_config and agent_model.memory_config.get("enabled"):
                agent_kwargs["memory"] = True

            if agent_model.max_rpm:
                agent_kwargs["max_rpm"] = agent_model.max_rpm

            agent = CrewAIAgent(**agent_kwargs)
            logger.debug(f"Created CrewAI Agent: role={agent_model.role}, llm={'set' if llm else 'default'}")
            return agent

        except Exception as e:
            logger.error(f"Failed to create CrewAI Agent '{getattr(agent_model, 'id', 'unknown')}': {e}")
            return None

    @staticmethod
    def create_task(
        task_model: Any,
        agent: "CrewAIAgent | None" = None,
        context_tasks: list["CrewAITask"] | None = None,
    ) -> "CrewAITask | None":
        """从 CrewTask 数据模型创建 CrewAI Task

        Args:
            task_model: CrewTask 数据模型
            agent: 负责的 CrewAI Agent
            context_tasks: 依赖的 CrewAI Task 列表

        Returns:
            CrewAI Task 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            return None

        try:
            task_kwargs = {
                "description": task_model.description or "",
                "expected_output": task_model.expected_output or "",
            }

            if agent:
                task_kwargs["agent"] = agent

            if context_tasks:
                task_kwargs["context"] = context_tasks

            if hasattr(task_model, 'async_execution') and task_model.async_execution:
                task_kwargs["async_execution"] = True

            if hasattr(task_model, 'human_input') and task_model.human_input:
                task_kwargs["human_input"] = True

            if hasattr(task_model, 'name') and task_model.name:
                task_kwargs["name"] = task_model.name

            return CrewAITask(**task_kwargs)

        except Exception as e:
            logger.error(f"Failed to create CrewAI Task: {e}")
            return None

    @staticmethod
    def create_crew(
        crew_model: Any,
        agents: list["CrewAIAgent"],
        tasks: list["CrewAITask"],
        context: "Context | None" = None,
    ) -> "CrewAICrew | None":
        """从 Crew 数据模型创建 CrewAI Crew

        Args:
            crew_model: Crew 数据模型
            agents: CrewAI Agent 列表
            tasks: CrewAI Task 列表
            context: AstrBot Context 实例

        Returns:
            CrewAI Crew 实例，失败返回 None
        """
        if not CREWAI_AVAILABLE:
            return None

        try:
            from ..models import ProcessType

            process = CrewAIProcess.sequential
            if crew_model.process == ProcessType.HIERARCHICAL:
                process = CrewAIProcess.hierarchical

            crew_kwargs = {
                "agents": agents,
                "tasks": tasks,
                "process": process,
                "verbose": crew_model.verbose or False,
            }

            if crew_model.memory:
                crew_kwargs["memory"] = True

            if crew_model.cache:
                crew_kwargs["cache"] = True

            if crew_model.max_rpm:
                crew_kwargs["max_rpm"] = crew_model.max_rpm

            if process == CrewAIProcess.hierarchical:
                if crew_model.manager_llm:
                    if context:
                        manager_llm = AstrBotLLMAdapter.create_llm(
                            provider_id=crew_model.manager_llm,
                            context=context,
                        )
                        if manager_llm:
                            crew_kwargs["manager_llm"] = manager_llm
                    else:
                        crew_kwargs["manager_llm"] = crew_model.manager_llm
                elif agents and agents[0].llm:
                    crew_kwargs["manager_llm"] = agents[0].llm

            crew = CrewAICrew(**crew_kwargs)
            logger.debug(f"Created CrewAI Crew: name={crew_model.name}, process={process.value}")
            return crew

        except Exception as e:
            logger.error(f"Failed to create CrewAI Crew: {e}")
            return None


def _create_mock_event(message: str = ""):
    """创建模拟 AstrMessageEvent 用于工具调用"""
    class MockEvent:
        def __init__(self, msg=""):
            self.unified_msg_origin = "agent_test:private:test_session"
            self.message_str = msg
            self.role = "admin"
            self.is_wake = True
            self.is_at_or_wake_command = True
            self._result = None
            self._extras = {}
            self._has_send_oper = False
            self.call_llm = False
            self._temporary_local_files = []
            self.plugins_name = None

            from astrbot.core.platform.message_session import MessageSession
            from astrbot.core.platform.message_type import MessageType
            self.session = MessageSession(
                platform_name="agent_test",
                message_type=MessageType.FRIEND_MESSAGE,
                session_id="test_session",
            )

            from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
            from astrbot.core.platform.platform_metadata import PlatformMetadata
            from astrbot.core.platform.message_type import MessageType as MsgType
            self.platform_meta = PlatformMetadata(name="agent_test", description="Agent Test", id="agent_test")
            self.platform = self.platform_meta

            self.message_obj = AstrBotMessage()
            self.message_obj.message = []
            self.message_obj.message_str = msg
            self.message_obj.session_id = "test_session"
            self.message_obj.self_id = "agent_test"
            self.message_obj.message_id = "test_msg_id"
            self.message_obj.sender = MessageMember(user_id="test_user", nickname="Tester")
            self.message_obj.type = MsgType.FRIEND_MESSAGE
            self.message_obj.raw_message = msg

        def get_result(self): return self._result
        def set_result(self, result): self._result = result
        def clear_result(self): self._result = None
        def stop_event(self): pass
        def continue_event(self): pass
        def is_stopped(self): return False
        def should_call_llm(self, call_llm): self.call_llm = call_llm
        def set_extra(self, key, value): self._extras[key] = value
        def get_extra(self, key=None, default=None):
            if key is None: return self._extras
            return self._extras.get(key, default)
        def clear_extra(self): self._extras = {}
        def get_platform_name(self): return "agent_test"
        def get_platform_id(self): return "agent_test"
        def get_message_str(self): return self.message_str
        def get_session_id(self): return "test_session"
        def get_group_id(self): return ""
        def get_self_id(self): return "agent_test"
        def get_sender_id(self): return "test_user"
        def get_sender_name(self): return "Tester"
        async def send(self, chain): self._has_send_oper = True
        async def send_streaming(self, generator, use_fallback=False): pass
        async def send_typing(self): pass
        async def stop_typing(self): pass
        def track_temporary_local_file(self, path): self._temporary_local_files.append(path)
        def cleanup_temporary_local_files(self): pass

    return MockEvent(message)


class MemoryProvider:
    """记忆提供者基类"""

    def store(self, agent_id: str, role: str, content: str, summary: str = "", **kwargs) -> None:
        raise NotImplementedError

    def retrieve(self, agent_id: str, query: str, memory_type: str = "short_term", max_items: int = 20) -> list[dict]:
        raise NotImplementedError


class CrewAIMemoryProvider(MemoryProvider):
    """基于 crewAI Memory 的记忆提供者"""

    def __init__(self):
        if not MEMORY_AVAILABLE:
            raise ImportError("crewai.memory.unified_memory.Memory not available")
        self._memory = Memory()
        self._initialized = True

    def store(self, agent_id: str, role: str, content: str, summary: str = "", **kwargs) -> None:
        memory_type = kwargs.get("memory_type", "short_term")
        importance = kwargs.get("importance", 0.8 if memory_type == "long_term" else 0.5)
        store_content = summary if summary else content
        scope = f"/agents/{agent_id}/{memory_type}"

        self._memory.remember(
            content=store_content,
            scope=scope,
            categories=[role] if role else None,
            metadata={
                "agent_id": agent_id,
                "role": role,
                "memory_type": memory_type,
                "full_content": content[:2000],
                "summary": summary[:500] if summary else "",
            },
            importance=importance,
            source="nicebot_agent",
        )

    def retrieve(self, agent_id: str, query: str, memory_type: str = "short_term", max_items: int = 20) -> list[dict]:
        scope = f"/agents/{agent_id}/{memory_type}"
        results = self._memory.recall(
            query=query,
            scope=scope,
            limit=max_items,
            depth="deep" if memory_type == "long_term" else "shallow",
        )

        memories = []
        for match in results:
            if hasattr(match, 'record'):
                record = match.record
                metadata = getattr(record, 'metadata', None) or {}
                memories.append({
                    "role": metadata.get("role", ""),
                    "content": metadata.get("full_content") or getattr(record, 'content', ''),
                    "summary": getattr(record, 'content', ''),
                    "score": getattr(match, 'score', 0),
                    "importance": getattr(record, 'importance', 0.5),
                })
            elif isinstance(match, dict):
                memories.append({
                    "role": match.get("metadata", {}).get("role", ""),
                    "content": match.get("content", ""),
                    "summary": match.get("content", ""),
                })
        return memories


class BuiltinMemoryProvider(MemoryProvider):
    """基于 SQLite 的内置记忆提供者"""

    def __init__(self, db):
        self._db = db

    def store(self, agent_id: str, role: str, content: str, summary: str = "", **kwargs) -> None:
        import uuid
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        self._db.insert("agent_memories", {
            "id": memory_id,
            "agent_id": agent_id,
            "role": role,
            "content": content[:2000],
            "summary": summary[:500] if summary else content[:200],
            "scope": kwargs.get("scope", "default"),
            "importance": kwargs.get("importance", 0.5),
        })

    def retrieve(self, agent_id: str, query: str, memory_type: str = "short_term", max_items: int = 20) -> list[dict]:
        if memory_type == "short_term":
            rows = self._db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="created_at DESC",
                limit=max_items,
            )
        else:
            rows = self._db.select_all(
                "agent_memories",
                where="agent_id = ?",
                where_params=(agent_id,),
                order_by="importance DESC, created_at DESC",
                limit=max_items,
            )
        memories = []
        for row in reversed(rows):
            memories.append({
                "role": row.get("role", ""),
                "content": row.get("summary") or row.get("content", ""),
            })
        return memories


class PlanningProvider:
    """规划提供者基类"""

    async def generate_plan(self, system_prompt: str, message: str, provider: Any, contexts: list, planning_effort: str = "medium") -> str | None:
        raise NotImplementedError


class CrewAIPlanningProvider(PlanningProvider):
    """基于 crewAI PlanningConfig 的规划提供者"""

    async def generate_plan(self, system_prompt: str, message: str, provider: Any, contexts: list, planning_effort: str = "medium") -> str | None:
        try:
            effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
            planning_prompt = effort_config["prompt_template"].format(message=message)

            planning_system = system_prompt
            if PLANNING_CONFIG_AVAILABLE:
                planning_system += "\n\n你正在使用结构化规划模式。请严格按照指定的格式输出执行计划，确保每个步骤清晰、可执行。"

            response = await provider.text_chat(
                prompt=planning_prompt,
                system_prompt=planning_system,
                contexts=contexts,
            )
            return response.completion_text
        except Exception as e:
            logger.error(f"CrewAI planning failed: {e}")
            return None


class BuiltinPlanningProvider(PlanningProvider):
    """基于 Prompt 的内置规划提供者"""

    async def generate_plan(self, system_prompt: str, message: str, provider: Any, contexts: list, planning_effort: str = "medium") -> str | None:
        try:
            effort_config = PLANNING_EFFORT_MAP.get(planning_effort, PLANNING_EFFORT_MAP["medium"])
            planning_prompt = effort_config["prompt_template"].format(message=message)

            response = await provider.text_chat(
                prompt=planning_prompt,
                system_prompt=system_prompt,
                contexts=contexts,
            )
            return response.completion_text
        except Exception as e:
            logger.error(f"Builtin planning failed: {e}")
            return None


def get_memory_provider(db=None) -> MemoryProvider:
    """获取记忆提供者实例"""
    if CREWAI_AVAILABLE:
        try:
            provider = CrewAIMemoryProvider()
            provider.store("__test__", "system", "__init_test__")
            logger.info("CrewAI Memory provider initialized successfully")
            return provider
        except Exception as e:
            logger.warning(f"CrewAI Memory provider unavailable, falling back to builtin: {e}")
    if db:
        return BuiltinMemoryProvider(db)
    raise ValueError("Database instance required for builtin memory provider")


def get_planning_provider() -> PlanningProvider:
    """获取规划提供者实例"""
    if CREWAI_AVAILABLE:
        try:
            return CrewAIPlanningProvider()
        except Exception as e:
            logger.warning(f"Failed to create CrewAI planning provider, falling back to builtin: {e}")
    return BuiltinPlanningProvider()
