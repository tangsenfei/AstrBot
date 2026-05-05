from __future__ import annotations

import uuid
from typing import Any

from astrbot.core.langgraph.interaction import CardAction, CardField, InteractionCard


def build_hitl_card(
    *,
    template: dict[str, Any] | None = None,
    template_id: str | None = None,
    content_payload: dict[str, Any] | None = None,
    task_id: str = "",
    session_id: str = "",
    interaction_type: str = "clarification",
    meta: dict[str, Any] | None = None,
) -> InteractionCard:
    """Build an InteractionCard from a HITL template and content payload.

    The template defines the *schema* (title, body, actions, field structure).
    The content_payload provides the *data* (confirmation_items with labels,
    options, defaults, etc.) that fills the schema.

    Args:
        template: Template dict from hitl_templates table (or inline).
        template_id: If template is None, used as fallback identifier.
        content_payload: Dict with optional keys:
            - title: Override card title.
            - body: Override card body.
            - confirmation_items: List of dicts, each with:
                key, label, description, recommended, options,
                allow_custom, custom_placeholder, required, default, field_type
            - actions: Override actions list.
        task_id: Task ID for meta.
        session_id: Session ID for meta.
        interaction_type: Card type string.
        meta: Extra metadata.

    Returns:
        InteractionCard ready for send_and_wait.
    """
    payload = content_payload or {}

    tpl_title = ""
    tpl_body = ""
    tpl_fields: list[dict[str, Any]] = []
    tpl_actions: list[dict[str, Any]] = []

    if template:
        tpl_title = template.get("title", "")
        tpl_body = template.get("body", "")
        tpl_fields = template.get("fields", [])
        tpl_actions = template.get("actions", [])

    title = payload.get("title") or tpl_title or "人工确认"
    body = payload.get("body") or tpl_body or ""

    fields = _build_fields(tpl_fields, payload.get("confirmation_items", []))
    actions = _build_actions(payload.get("actions") or tpl_actions)

    card_meta: dict[str, Any] = {
        "task_id": task_id,
        "session_id": session_id,
    }
    if template_id:
        card_meta["template_id"] = template_id
    if meta:
        card_meta.update(meta)

    return InteractionCard(
        interaction_id=f"hitl_{uuid.uuid4().hex[:12]}",
        type=interaction_type,
        title=title,
        body=body,
        fields=fields,
        actions=actions,
        meta=card_meta,
    )


def _build_fields(
    tpl_fields: list[dict[str, Any]],
    confirmation_items: list[dict[str, Any]],
) -> list[CardField]:
    """Merge template field schema with content payload confirmation items.

    If confirmation_items is non-empty, it takes priority and each item
    is converted to a CardField.  Template fields are used as fallback
    when confirmation_items is empty.
    """
    if confirmation_items:
        result = []
        for item in confirmation_items:
            result.append(CardField(
                key=item.get("key", f"field_{len(result) + 1}"),
                label=item.get("label", ""),
                field_type=item.get("field_type", "select"),
                required=item.get("required", False),
                default=item.get("default") or item.get("recommended"),
                options=item.get("options"),
                description=item.get("description"),
                recommended=item.get("recommended"),
                allow_custom=item.get("allow_custom", False),
                custom_placeholder=item.get("custom_placeholder"),
            ))
        return result

    return [_dict_to_card_field(f) for f in tpl_fields]


def _build_actions(actions_data: list[dict[str, Any]]) -> list[CardAction]:
    if not actions_data:
        return [
            CardAction(key="confirm", label="确认", style="primary"),
            CardAction(key="cancel", label="取消", style="danger"),
        ]
    return [
        CardAction(
            key=a.get("key", "confirm"),
            label=a.get("label", "确认"),
            style=a.get("style", "default"),
        )
        for a in actions_data
    ]


def _dict_to_card_field(d: dict[str, Any]) -> CardField:
    return CardField(
        key=d.get("key", ""),
        label=d.get("label", ""),
        field_type=d.get("field_type", "text"),
        required=d.get("required", False),
        default=d.get("default"),
        options=d.get("options"),
        description=d.get("description"),
        recommended=d.get("recommended"),
        allow_custom=d.get("allow_custom", False),
        custom_placeholder=d.get("custom_placeholder"),
    )
