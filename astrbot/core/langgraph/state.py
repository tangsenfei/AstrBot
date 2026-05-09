from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, NotRequired, TypedDict


class StreamEvent(TypedDict):
    event: Literal[
        "text_delta",
        "tool_call",
        "tool_result",
        "reasoning",
        "error",
        "phase",
        "interrupt",
        "artifact",
        "token",
        "interaction",
    ]
    data: dict[str, Any]
    timestamp: float
    node_id: str


@dataclass
class GraphRunContext:
    provider: Any
    tool_executor: Any
    hooks: Any
    astr_event: Any
    config: dict[str, Any]
    writer: Any = None
    interrupt_event: Any = None


class AgentGraphState(TypedDict, total=False):
    system_prompt: str
    user_prompt: str
    messages: list[dict[str, Any]]
    image_urls: list[str]
    func_tools: NotRequired[list[str]]
    session_id: str
    provider_id: NotRequired[str]
    model: NotRequired[str]


class AgentGraphResult(TypedDict, total=False):
    final_text: str
    reasoning_text: NotRequired[str]
    tool_calls: list[dict[str, Any]]
    error: NotRequired[str]
    stats: NotRequired[dict[str, Any]]


class MeetingState(AgentGraphState):
    meeting_id: NotRequired[str]
    task_id: NotRequired[str]
    topic: str
    goal: NotRequired[str]
    expected_output: NotRequired[str]
    meeting_type: NotRequired[str]
    materials: NotRequired[dict[str, Any]]
    settings: NotRequired[dict[str, Any]]
    materials_brief: NotRequired[str]
    last_user_event_seq: NotRequired[int]
    participants: list[dict[str, Any]]
    host: NotRequired[dict[str, Any]]
    strategy: str
    max_rounds: int
    current_round: int
    round_results: list[str]
    final_minutes: NotRequired[str]
    deliverable_output: NotRequired[str]


class PlanExecuteState(AgentGraphState):
    task: str
    planning_effort: str
    plan_steps: NotRequired[list[dict]]
    current_step_index: int
    step_results: list[dict]
    human_approved: NotRequired[bool]


class WorkflowState(AgentGraphState, total=False):
    flow_definition: dict[str, Any]
    node_results: dict[str, Any]
    current_node_id: str


@dataclass
class HITLOption:
    value: str
    label: str
    description: str
    modify_prompt: str = ""


@dataclass
class TaskCard:
    task_type: str
    task_type_label: str
    summary: str
    steps_preview: list[str]
    estimated_duration: str
    agent_count: int
    tools_preview: list[str]


@dataclass
class HITLInteraction:
    interaction_id: str
    type: Literal[
        "task_confirm",
        "plan_approval",
        "workflow_human_node",
        "error_recovery",
        "clarification",
    ]
    prompt: str
    task_card: TaskCard | None
    options: list[HITLOption]
    default_option: str
    timeout_seconds: int = 300


class TaskStatus(str, Enum):
    CREATED = "created"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMING = "resuming"
    WAITING_FEEDBACK = "waiting_feedback"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    session_id: str
    thread_id: str
    status: TaskStatus
    config: dict
    hitl_context: dict | None
    result: dict | None
    error: str | None
    created_at: float
    updated_at: float
    stream_callback: Any = None
    run_ctx: Any = None
    progress: int = 0
    result_text: str = ""
    steps: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    interaction_id: str = ""
    interaction_text: str = ""
    _started_at_db_set: bool = field(default=False, repr=False)


@dataclass
class GraphTriggerRequest:
    graph_type: Literal[
        "meeting", "plan_execute", "workflow", "crew", "work_task", "agent_with_checkpoint"
    ]
    state: dict[str, Any]
    session_id: str
    thread_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


@dataclass
class GraphTriggerResponse:
    status: Literal["completed", "background", "awaiting_input"]
    thread_id: str
    result: dict[str, Any] | None = None
    interrupt_data: dict[str, Any] | None = None
