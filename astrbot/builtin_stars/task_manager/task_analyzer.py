import json
from typing import Any
from astrbot import logger


class TaskAnalyzer:
    PLANNER_PROMPT = """你是一个任务分析与规划专家。对于给定的用户任务，请分析并生成执行计划。

任务：{query}

请输出 JSON 格式的执行计划：
{{
    "task_type": "research|report|analysis|coding|general",
    "complexity": "low|medium|high|very_high",
    "estimated_steps": 数字,
    "need_subagent": true|false,
    "max_concurrent": 数字,
    "stages": [
        {{
            "name": "阶段名称",
            "description": "阶段描述",
            "skills": ["需要的技能"],
            "tools": ["需要的工具"]
        }}
    ],
    "skills": ["整体需要的技能列表"],
    "tools": ["整体需要的工具列表"],
    "estimated_time": "预估时间"
}}

要求：
1. 根据任务复杂度选择合适的执行模式
2. 复杂任务需要分解为多个阶段
3. 每个阶段需要指定需要的技能和工具
4. 返回有效的 JSON，不要添加额外说明
"""

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    async def analyze_and_plan(self, query: str) -> dict[str, Any]:
        prompt = self.PLANNER_PROMPT.format(query=query)

        if self.llm_client:
            try:
                response = await self.llm_client.chat([
                    {"role": "system", "content": prompt}
                ])
                plan = self._parse_response(response)
            except Exception as e:
                logger.warning(f"LLM planning failed, using fallback: {e}")
                plan = self._fallback_plan(query)
        else:
            plan = self._fallback_plan(query)

        return plan

    def _parse_response(self, response: Any) -> dict[str, Any]:
        content = ""
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, str):
            content = response

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._fallback_plan("")

    def _fallback_plan(self, query: str) -> dict[str, Any]:
        return {
            "task_type": "general",
            "complexity": "medium",
            "estimated_steps": 3,
            "need_subagent": True,
            "max_concurrent": 3,
            "stages": [
                {
                    "name": "execute",
                    "description": f"执行任务: {query[:50]}...",
                    "skills": [],
                    "tools": []
                }
            ],
            "skills": [],
            "tools": [],
            "estimated_time": "unknown"
        }

    def select_execution_mode(self, plan: dict[str, Any]) -> str:
        complexity = plan.get("complexity", "medium")
        need_subagent = plan.get("need_subagent", False)
        stages_count = len(plan.get("stages", []))

        if complexity == "low":
            return "direct"
        elif complexity == "medium":
            return "stream" if not need_subagent else "subagent"
        elif complexity == "high":
            return "stage" if stages_count > 1 else "subagent"
        else:
            return "hybrid"

    def should_enable_subagent(self, plan: dict[str, Any]) -> bool:
        return plan.get("need_subagent", False)

    def should_enable_plan_mode(self, plan: dict[str, Any]) -> bool:
        return plan.get("task_type") in ["research", "analysis"]