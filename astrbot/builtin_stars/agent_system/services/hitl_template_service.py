from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class HITLTemplateService:
    """Reusable HITL card templates for flow nodes and Work tasks."""

    REQUIREMENT_TEMPLATE_ID = "builtin_work_requirement_clarification"
    PLAN_APPROVAL_TEMPLATE_ID = "builtin_work_plan_approval"

    def __init__(self, db) -> None:
        self.db = db

    def ensure_builtin_templates(self) -> None:
        for template in self._builtin_templates():
            existing = self.db.select_one("hitl_templates", where="id = ?", where_params=(template["id"],))
            if existing:
                old_meta = self._parse(existing.get("metadata"), {})
                new_meta = template.get("metadata", {})
                old_version = old_meta.get("schema_version", 0)
                new_version = new_meta.get("schema_version", 0)
                if new_version > old_version:
                    self._upsert_template(template, preserve_user_edits=False)
                else:
                    self._upsert_template(template, preserve_user_edits=True)
            else:
                self._upsert_template(template, preserve_user_edits=False)

    def list_templates(self, template_type: str | None = None) -> list[dict[str, Any]]:
        self.ensure_builtin_templates()
        where = "1=1"
        params: tuple[Any, ...] = ()
        if template_type:
            where = "template_type = ?"
            params = (template_type,)
        rows = self.db.select_all("hitl_templates", where=where, where_params=params, order_by="created_at ASC")
        return [self._row_to_template(row) for row in rows]

    def get_template(self, template_id: str) -> dict[str, Any] | None:
        self.ensure_builtin_templates()
        row = self.db.select_one("hitl_templates", where="id = ?", where_params=(template_id,))
        return self._row_to_template(row) if row else None

    def save_template(self, data: dict[str, Any]) -> dict[str, Any]:
        template_id = data.get("id") or f"hitl_tpl_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()
        existing = self.db.select_one("hitl_templates", where="id = ?", where_params=(template_id,))
        row = {
            "id": template_id,
            "name": data.get("name") or data.get("title") or "HITL 模板",
            "template_type": data.get("template_type") or data.get("type") or "clarification",
            "title": data.get("title") or data.get("name") or "人工确认",
            "body": data.get("body", ""),
            "fields": data.get("fields", []),
            "actions": data.get("actions", []),
            "metadata": data.get("metadata", {}),
            "is_builtin": int(bool(data.get("is_builtin", False))),
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        if existing:
            self.db.update("hitl_templates", {k: v for k, v in row.items() if k != "id"}, where="id = ?", where_params=(template_id,))
        else:
            self.db.insert("hitl_templates", row)
        return self.get_template(template_id) or row

    def reset_builtin_template(self, template_id: str) -> dict[str, Any] | None:
        for template in self._builtin_templates():
            if template["id"] == template_id:
                self._upsert_template(template, preserve_user_edits=False)
                return self.get_template(template_id)
        return None

    def _upsert_template(self, template: dict[str, Any], *, preserve_user_edits: bool) -> None:
        existing = self.db.select_one("hitl_templates", where="id = ?", where_params=(template["id"],))
        now = datetime.now().isoformat()
        row = {
            **template,
            "is_builtin": 1,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        if existing:
            if preserve_user_edits:
                self.db.update(
                    "hitl_templates",
                    {"is_builtin": 1, "metadata": {**self._parse(existing.get("metadata"), {}), **template.get("metadata", {})}},
                    where="id = ?",
                    where_params=(template["id"],),
                )
            else:
                self.db.update("hitl_templates", {k: v for k, v in row.items() if k != "id"}, where="id = ?", where_params=(template["id"],))
        else:
            self.db.insert("hitl_templates", row)

    def _builtin_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "id": self.REQUIREMENT_TEMPLATE_ID,
                "name": "需求确认模板",
                "template_type": "clarification",
                "title": "需求确认",
                "body": "请确认以下信息。默认已选推荐项，如不合适可改选或填写自定义补充。",
                "fields": [],
                "actions": [
                    {"key": "confirm", "label": "确认", "style": "primary"},
                    {"key": "clarify_more", "label": "补充信息", "style": "default"},
                    {"key": "cancel", "label": "取消", "style": "danger"},
                ],
                "metadata": {
                    "is_builtin": True,
                    "supports_custom_input": True,
                    "schema_template": True,
                    "schema_version": 3,
                    "description": "Generic clarification/confirmation template. Fields are populated by the caller via content_payload.confirmation_items.",
                },
            },
            {
                "id": self.PLAN_APPROVAL_TEMPLATE_ID,
                "name": "Work 计划审批模板",
                "template_type": "plan_approval",
                "title": "Work 执行计划审批",
                "body": "请确认执行计划。",
                "fields": [
                    {"key": "modify_text", "label": "修改意见", "field_type": "textarea", "required": False, "default": ""},
                ],
                "actions": [
                    {"key": "approve", "label": "批准执行", "style": "primary"},
                    {"key": "modify", "label": "调整计划", "style": "default"},
                    {"key": "reject", "label": "拒绝", "style": "danger"},
                ],
                "metadata": {"is_builtin": True, "schema_version": 1},
            },
        ]

    def _row_to_template(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "name": row.get("name", ""),
            "template_type": row.get("template_type", "clarification"),
            "title": row.get("title", ""),
            "body": row.get("body", ""),
            "fields": self._parse(row.get("fields"), []),
            "actions": self._parse(row.get("actions"), []),
            "metadata": self._parse(row.get("metadata"), {}),
            "is_builtin": bool(row.get("is_builtin", 0)),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _parse(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        import json

        try:
            return json.loads(value)
        except Exception:
            return fallback
