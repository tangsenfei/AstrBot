from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CardField:
    key: str
    label: str
    field_type: Literal["text", "textarea", "select", "multiselect"]
    required: bool = False
    default: str | None = None
    options: list[str] | None = None


@dataclass
class CardAction:
    key: str
    label: str
    style: Literal["primary", "danger", "default"] = "default"


@dataclass
class InteractionCard:
    interaction_id: str
    type: Literal[
        "task_confirm",
        "plan_approval",
        "workflow_human",
        "error_recovery",
        "clarification",
        "permission",
        "info_request",
    ]
    title: str
    body: str
    fields: list[CardField] = field(default_factory=list)
    actions: list[CardAction] = field(default_factory=list)
    timeout_seconds: int = 300
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def _field_dict(f):
            if isinstance(f, dict):
                return f
            return {
                "key": f.key,
                "label": f.label,
                "field_type": f.field_type,
                "required": f.required,
                "default": f.default,
                "options": f.options,
            }

        def _action_dict(a):
            if isinstance(a, dict):
                return a
            return {"key": a.key, "label": a.label, "style": a.style}

        return {
            "interaction_id": self.interaction_id,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "fields": [_field_dict(f) for f in self.fields],
            "actions": [_action_dict(a) for a in self.actions],
            "timeout_seconds": self.timeout_seconds,
            "meta": self.meta,
        }


@dataclass
class InteractionResponse:
    interaction_id: str
    action_key: str
    field_values: dict[str, Any]
    responded_at: float


@dataclass
class InteractionState:
    interaction_id: str
    thread_id: str
    channel: str
    card: InteractionCard
    created_at: float
    resolved: bool = False
    response: InteractionResponse | None = None
    channel_message_id: str | None = None
    channel_chat_id: str | None = None

    def mark_resolved(self, response: InteractionResponse) -> None:
        self.resolved = True
        self.response = response
        self.responded_at = time.time()


@dataclass
class ResolvedCardUpdate:
    interaction_id: str
    status: Literal["confirmed", "cancelled", "rejected", "modified"]
    message: str
