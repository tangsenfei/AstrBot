from __future__ import annotations

import json
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.tools.registry import builtin_tool

_plan_cache: dict[str, list[dict[str, Any]]] = {}

SUBMIT_PLAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "description": "一级步骤列表，3-7个，按依赖顺序排列。每个步骤必须包含标题、说明和前置依赖序号。",
            "minItems": 3,
            "maxItems": 7,
            "items": {
                "type": "object",
                "required": ["title", "description", "dependencies"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "步骤标题，简洁明确，不超过40字",
                        "maxLength": 40,
                    },
                    "description": {
                        "type": "string",
                        "description": "步骤详细说明，包含交付物描述",
                        "maxLength": 300,
                    },
                    "dependencies": {
                        "type": "array",
                        "description": "前置步骤序号列表（从1开始），首步骤为空数组 []",
                        "items": {"type": "integer", "minimum": 1},
                    },
                    "children": {
                        "type": "array",
                        "description": "二级子任务列表，每个一级步骤最多3个子任务",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "required": ["title", "description"],
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "子任务标题",
                                    "maxLength": 60,
                                },
                                "description": {
                                    "type": "string",
                                    "description": "子任务详细说明",
                                    "maxLength": 200,
                                },
                            },
                        },
                    },
                },
            },
        }
    },
    "required": ["steps"],
}


def validate_plan_steps(steps: list[Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(steps, list):
        return ["steps 必须是数组"]
    if len(steps) < 3:
        errors.append("至少需要3个一级步骤")
    if len(steps) > 7:
        errors.append("最多7个一级步骤")
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            errors.append(f"步骤{i}必须是对象")
            continue
        if not step.get("title") or not str(step["title"]).strip():
            errors.append(f"步骤{i}缺少 title（步骤标题）")
        if not step.get("description") or not str(step["description"]).strip():
            errors.append(f"步骤{i}缺少 description（步骤说明）")
        deps = step.get("dependencies", [])
        if not isinstance(deps, list):
            errors.append(f"步骤{i}的 dependencies 必须是数组")
        else:
            for d in deps:
                if not isinstance(d, int) or d < 1 or d > len(steps):
                    errors.append(f"步骤{i}的依赖序号 {d} 超出有效范围(1-{len(steps)})")
        children = step.get("children") or []
        if len(children) > 3:
            errors.append(f"步骤{i}的子任务不能超过3个")
        for j, child in enumerate(children, 1):
            if not isinstance(child, dict):
                errors.append(f"步骤{i}的子任务{j}必须是对象")
                continue
            if not child.get("title") or not str(child["title"]).strip():
                errors.append(f"步骤{i}的子任务{j}缺少 title")
    return errors


@builtin_tool
@dataclass
class SubmitWorkPlanTool(FunctionTool[AstrAgentContext]):
    name: str = "submit_work_plan"
    description: str = (
        "提交结构化的任务执行计划。你必须调用此工具来提交计划，不要直接输出文本。\n\n"
        "参数格式示例：\n"
        '{"steps": [{"title": "步骤标题", "description": "步骤说明和交付物", "dependencies": [], "children": [{"title": "子任务标题", "description": "子任务说明"}]}]}\n\n'
        "关键规则：\n"
        "- steps 必须是数组（方括号 [] 包裹），包含 3-7 个步骤对象\n"
        "- 每个步骤必须有 title、description、dependencies 三个字段\n"
        "- dependencies 是整数数组，表示前置步骤序号（从1开始），首步骤为空数组 []\n"
        "- children 是可选的子任务数组，每个子任务有 title 和 description\n"
        "- 格式校验不通过时会返回错误和正确示例，请根据错误修正后重新调用"
    )
    parameters: dict[str, Any] = Field(default_factory=lambda: SUBMIT_PLAN_TOOL_SCHEMA)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        steps_data = kwargs.get("steps", [])
        errors = validate_plan_steps(steps_data)
        if errors:
            error_msg = (
                "计划格式校验失败，请修正以下问题：\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\n\n正确格式示例：\n"
                '{"steps": [{"title": "明确需求", "description": "确认任务目标和交付标准", "dependencies": []}, '
                '{"title": "执行核心工作", "description": "完成主要任务并形成阶段结果", "dependencies": [1]}, '
                '{"title": "整理交付物", "description": "汇总结果并标注关键结论", "dependencies": [2]}]}\n\n'
                "请严格按照此格式重新调用 submit_work_plan 工具。"
            )
            return json.dumps(
                {"success": False, "errors": errors, "message": error_msg},
                ensure_ascii=False,
            )
        session_id = kwargs.get("_session_id", "") or getattr(
            context.context, "session_id", ""
        )
        _plan_cache[session_id] = steps_data
        return json.dumps(
            {
                "success": True,
                "step_count": len(steps_data),
                "message": "计划已提交成功",
            },
            ensure_ascii=False,
        )


def get_cached_plan(session_id: str) -> list[dict[str, Any]] | None:
    return _plan_cache.pop(session_id, None)
