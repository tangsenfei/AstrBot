from typing import Any, Generic

from .agent import Agent
from .run_context import TContext
from .tool import FunctionTool


class HandoffTool(FunctionTool, Generic[TContext]):
    """Handoff tool for delegating tasks to another agent."""

    def __init__(
        self,
        agent: Agent[TContext],
        parameters: dict | None = None,
        tool_description: str | None = None,
        **kwargs,
    ) -> None:
        description = tool_description or self.default_description(agent.name)
        super().__init__(
            name=f"transfer_to_{agent.name}",
            parameters=parameters or self.default_parameters(),
            description=description,
            **kwargs,
        )

        self.provider_id: str | None = None
        self.agent = agent

    def default_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The input to be handed off to another agent. This should be a clear and concise request or task.",
                },
                "image_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: An array of image sources (public HTTP URLs or local file paths) used as references in multimodal tasks such as video generation.",
                },
                "background_task": {
                    "type": "boolean",
                    "description": (
                        "Defaults to false. "
                        "Set to true if the task may take noticeable time, involves external tools, or the user does not need to wait. "
                        "Use false only for quick, immediate tasks."
                    ),
                },
            },
        }

    def default_description(self, agent_name: str | None) -> str:
        agent_name = agent_name or "another"
        return f"Delegate tasks to {agent_name} agent to handle the request."


class MeetingHandoffTool(HandoffTool[TContext]):
    """Handoff tool that triggers a meeting graph instead of a regular agent loop.

    When the main agent hands off to a meeting-type sub-agent, this tool
    invokes ``build_meeting_graph()`` and returns the structured meeting
    result (minutes + round summaries) as text injected into the main
    conversation.
    """

    def __init__(
        self,
        agent: Agent[TContext],
        meeting_config: dict[str, Any] | None = None,
        parameters: dict | None = None,
        tool_description: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            agent=agent,
            parameters=parameters or self.default_parameters(),
            tool_description=tool_description,
            **kwargs,
        )
        self.meeting_config: dict[str, Any] = meeting_config or {}

    def default_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The meeting topic or question to discuss. This will be used as the meeting topic.",
                },
                "image_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: An array of image sources used as references.",
                },
                "background_task": {
                    "type": "boolean",
                    "description": (
                        "Defaults to true for meetings since they take time. "
                        "Set to false only if the user needs to wait for the meeting result."
                    ),
                    "default": True,
                },
            },
        }

    def default_description(self, agent_name: str | None) -> str:
        agent_name = agent_name or "meeting"
        return f"Trigger a multi-agent meeting discussion via {agent_name}. The meeting will involve multiple participants discussing the given topic and producing structured minutes."
