"""Work runtime configuration service."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any

WORK_CONFIG_KEY = "daily_work"


DEFAULT_WORK_CONFIG: dict[str, Any] = {
    "daily": {
        "clarification": {
            "standard": {
                "agent_id": "agent_nicebot_work_assistant",
                "system_prompt": "你是 NiceBot Work 任务助手，负责根据用户任务目标生成精准、可操作的需求确认项。你必须只返回合法 JSON，不要输出解释、Markdown 或代码块。",
                "prompt": (
                    "请为 Work 任务生成 2-5 个需求确认项。\n\n"
                    "任务名称：{task_name}\n"
                    "任务描述：{task_desc}\n\n"
                    "工作上下文：\n{work_context}\n\n"
                    "{interrogation_summary}\n"
                    "请只返回如下 JSON 对象，不要包含 markdown 代码块：\n"
                    "{\n"
                    '  "confirmation_items": [\n'
                    "    {\n"
                    '      "key": "字段英文key",\n'
                    '      "label": "字段中文标签",\n'
                    '      "description": "为什么需要确认这个信息",\n'
                    '      "field_type": "select 或 multiselect 或 textarea",\n'
                    '      "required": true,\n'
                    '      "recommended": "推荐：结合任务内容给出的默认值",\n'
                    '      "options": ["推荐：选项A", "选项B", "选项C"],\n'
                    '      "allow_custom": true,\n'
                    '      "custom_placeholder": "用户选择自定义时的填写提示"\n'
                    "    }\n"
                    "  ]\n"
                    "}\n\n"
                    "生成要求：\n"
                    "1. 确认项必须贴合任务，不要使用泛化的固定字段。\n"
                    "2. 优先确认会影响交付质量的信息，例如目标对象、范围边界、偏好、约束、交付格式、完成标准。\n"
                    "3. 有明确互斥选项时用 select；可多选维度用 multiselect；需要用户自由描述时用 textarea。\n"
                    "4. select/multiselect 必须提供 3-6 个 options，且至少一个选项以「推荐：」开头。\n"
                    "5. 每个 select/multiselect 都必须设置 allow_custom 为 true。\n"
                    "6. key 使用稳定英文小写蛇形命名。"
                ),
            },
            "interrogation": {
                "agent_id": "agent_nicebot_work_assistant",
                "system_prompt": "你是 NiceBot Work 的需求拷问助手。你的目标是判断需求是否值得做、目标是否清楚、约束是否足够，而不是迎合用户直接开始执行。",
                "prompt": (
                    "请评估以下 Work 任务是否已经具备明确价值和可执行需求。\n\n"
                    "任务名称：{task_name}\n"
                    "任务描述：{task_desc}\n\n"
                    "工作上下文：\n{work_context}\n\n"
                    "已完成质询记录：\n{interrogation_history}\n\n"
                    "只返回 JSON：\n"
                    "{\n"
                    '  "status": "ask 或 ready",\n'
                    '  "value_assessment": "对需求价值、合理性、风险的简短判断",\n'
                    '  "questions": ["还必须追问的问题"],\n'
                    '  "summary": "status 为 ready 时给出已明确需求摘要"\n'
                    "}\n"
                    "如果需求价值、范围、验收标准仍不清晰，status 必须为 ask。"
                ),
                "max_rounds": 5,
            },
        },
        "planning": {
            "quick": {
                "agent_id": "agent_nicebot_work_assistant",
                "system_prompt": "你是 NiceBot Work 的快速规划智能体。请围绕一个可直接执行的交付单元完成任务拆解、依赖设计和资源分配。",
                "prompt": "",
            },
            "normal": {
                "agent_id": "agent_nicebot_work_assistant",
                "system_prompt": "你是 NiceBot Work 的资源感知规划智能体。你需要按一级步骤完成任务拆解、依赖设计和执行资源分配，并输出可校验的执行树。",
                "prompt": "",
            },
            "deep": {
                "agent_id": "agent_nicebot_work_assistant",
                "system_prompt": "你是 NiceBot Work 的深度规划智能体。你需要按叶子步骤细粒度设计执行树，并结合研究、执行、审查、汇报资源完成分工。",
                "prompt": "",
            },
        },
        "deliverable": {
            "reporter_agent_id": "agent_nicebot_report_expert",
            "system_prompt": "你是 NiceBot Work 的汇报专家（{reporter_id}）。请只整理最终交付物，不混入过程日志。",
            "prompt": "请将以下任务执行结果整理成最终交付物。\n\n任务：{task_name}\n\n{results_text}",
            "artifact_type": "markdown",
        },
    }
}


class WorkConfigService:
    def __init__(self, db) -> None:
        self.db = db

    def get_config(self) -> dict[str, Any]:
        row = self.db.select_one(
            "work_config", where="key = ?", where_params=(WORK_CONFIG_KEY,)
        )
        if not row:
            config = self._initial_config()
            self._save(config)
            return config
        try:
            raw = json.loads(row.get("value") or "{}")
        except json.JSONDecodeError:
            raw = {}
        return self._merge_defaults(raw)

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        current = self.get_config()
        merged = self._deep_merge(current, data or {})
        merged = self._normalize(merged)
        self._save(merged)
        return merged

    def reset_config(self) -> dict[str, Any]:
        config = copy.deepcopy(DEFAULT_WORK_CONFIG)
        self._save(config)
        return config

    def _save(self, config: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        value = json.dumps(self._normalize(config), ensure_ascii=False)
        existing = self.db.select_one(
            "work_config", where="key = ?", where_params=(WORK_CONFIG_KEY,)
        )
        if existing:
            self.db.update(
                "work_config",
                {"value": value, "updated_at": now},
                where="key = ?",
                where_params=(WORK_CONFIG_KEY,),
            )
        else:
            self.db.insert(
                "work_config",
                {"key": WORK_CONFIG_KEY, "value": value, "updated_at": now},
            )

    def _merge_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._normalize(self._deep_merge(copy.deepcopy(DEFAULT_WORK_CONFIG), data))

    def _initial_config(self) -> dict[str, Any]:
        config = copy.deepcopy(DEFAULT_WORK_CONFIG)
        try:
            from .flow_service import BUILTIN_DAILY_WORK_FLOW_ID, FlowService
            from .work_service import WorkService

            FlowService(self.db).ensure_builtin_daily_work_flow()
            work_service = WorkService(self.db)
            definition = work_service._get_flow_definition(BUILTIN_DAILY_WORK_FLOW_ID)
            runtime = work_service._extract_work_flow_runtime_config(definition)
            flow_config = self._config_from_flow_runtime(runtime)
            config = self._deep_merge(config, flow_config)
        except Exception:
            pass
        return self._normalize(config)

    def _config_from_flow_runtime(
        self, runtime: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        clarification = runtime.get("clarification_config") or {}
        plan = runtime.get("plan_config") or {}
        executor = runtime.get("executor_config") or {}
        review = runtime.get("review_config") or {}
        planning_agent = (
            plan.get("agent_id")
            or executor.get("assistant_agent_id")
            or "agent_nicebot_work_assistant"
        )
        planning_system = plan.get("system_prompt") or ""
        planning_prompt = plan.get("prompt_template") or plan.get("prompt") or ""
        config: dict[str, Any] = {
            "daily": {
                "clarification": {
                    "standard": {
                        "agent_id": clarification.get("content_provider_agent_id")
                        or "agent_nicebot_work_assistant",
                        "system_prompt": clarification.get("content_system_prompt") or "",
                        "prompt": clarification.get("content_prompt") or "",
                    }
                },
                "planning": {},
                "deliverable": {
                    "reporter_agent_id": executor.get("reporter_agent_id")
                    or "agent_nicebot_report_expert",
                    "system_prompt": executor.get("finalize_system_prompt") or "",
                    "prompt": executor.get("finalize_prompt_template") or "",
                    "artifact_type": executor.get("artifact_type") or "markdown",
                },
            }
        }
        for mode in ("quick", "normal", "deep"):
            config["daily"]["planning"][mode] = {
                "agent_id": planning_agent,
                "system_prompt": planning_system,
                "prompt": planning_prompt,
            }
        if review.get("reviewer_id"):
            config["daily"]["reviewer_agent_id"] = review["reviewer_id"]
        return config

    def _normalize(self, config: dict[str, Any]) -> dict[str, Any]:
        daily = config.setdefault("daily", {})
        clarification = daily.setdefault("clarification", {})
        clarification.setdefault("standard", {})
        interrogation = clarification.setdefault("interrogation", {})
        try:
            interrogation["max_rounds"] = max(
                1, min(10, int(interrogation.get("max_rounds") or 5))
            )
        except (TypeError, ValueError):
            interrogation["max_rounds"] = 5
        planning = daily.setdefault("planning", {})
        for mode in ("quick", "normal", "deep"):
            planning.setdefault(mode, {})
        daily.setdefault("deliverable", {})
        return config

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in (override or {}).items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = copy.deepcopy(value)
        return base
