"""
圆桌会议策略模式

提供10种会议类型的执行策略
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from astrbot.core import logger

if TYPE_CHECKING:
    from astrbot.core.agent.models import Agent
    from .roundtable_service import RoundtableService


class MeetingStrategy(ABC):
    """会议策略基类"""

    def __init__(self, service: "RoundtableService") -> None:
        self.service = service

    @abstractmethod
    def get_name(self) -> str:
        """获取策略名称"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """获取策略描述"""
        pass

    @abstractmethod
    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
        previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        """执行会议策略

        Args:
            previous_context: 续会时之前讨论的上下文列表

        Returns:
            {"discussion_rounds": [...], "summary": str, "deliverable": str}
        """
        pass

    def _build_materials_context(self, materials: dict[str, Any]) -> str:
        """构建材料上下文"""
        if not materials:
            return ""
        parts = ["\n【会议参考资料】"]
        mtype = materials.get("type", "")
        if mtype == "url":
            parts.append(f"参考链接：{materials.get('content', '')}")
        elif mtype == "file":
            parts.append(f"参考文件：{materials.get('filename', '已上传文件')}")
            if materials.get("content"):
                parts.append(f"文件内容摘要：{materials['content'][:500]}")
        elif mtype == "manual":
            parts.append("用户补充信息：")
            for item in materials.get("items", []):
                parts.append(f"- {item.get('question', '')}: {item.get('answer', '')}")
        return "\n".join(parts)

    async def _call_host_stream(
        self,
        host_agent: Any,
        prompt: str,
        result: dict[str, Any],
        event_callback: Any,
        round_num: int,
        speech_type: str,
    ) -> str:
        """调用主持人流式输出"""
        if not host_agent:
            return ""
        return await self.service._call_agent_stream(
            host_agent, prompt, result["tokens"], event_callback, round_num, speech_type
        )

    async def _call_agent_stream(
        self,
        agent: Any,
        prompt: str,
        result: dict[str, Any],
        event_callback: Any,
        round_num: int,
        speech_type: str,
    ) -> str:
        """调用参会者流式输出"""
        return await self.service._call_agent_stream(
            agent, prompt, result["tokens"], event_callback, round_num, speech_type
        )

    def _save_records(
        self,
        roundtable_id: str,
        discussion_records: list[dict],
        current_round: int,
        current_speaker: str,
    ) -> None:
        """保存讨论记录"""
        self.service._save_discussion_records(
            roundtable_id, discussion_records, current_round, current_speaker
        )


class StandardStrategy(MeetingStrategy):
    """标准研讨策略"""

    def get_name(self) -> str:
        return "standard"

    def get_description(self) -> str:
        return "标准研讨，通用深度讨论"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
        previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)

        for round_num in range(1, rounds + 1):
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": rounds})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": "开场", "stage": f"round_{round_num}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 开场
            if round_num == 1:
                opening_speaker = host_agent.name if host_agent else "系统"
                if host_agent:
                    opening = await self._call_host_stream(
                        host_agent,
                        self._build_standard_opening(host_agent, topic, deliverable, agents, materials_ctx),
                        result, event_callback, round_num, "opening"
                    )
                else:
                    opening = await self.service._call_system_opening(topic, deliverable, agents, result["tokens"])
                round_result["opening"] = opening
                context_history.append(f"【开场】{opening}")
                discussion_records.append({"round": round_num, "speaker": opening_speaker, "content": opening, "type": "opening"})
                self._save_records(roundtable_id, discussion_records, round_num, "开场")
                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": opening_speaker, "type": "opening", "content": opening})

            # 每轮每个参会者发言（带回应链：每个 Agent 回应前一个发言者）
            for agent_idx, agent in enumerate(agents):
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                # 确定回应对象：第一个回应主持人/开场，其他回应前一个发言者
                if agent_idx == 0:
                    respond_to = host_agent.name if host_agent else (round_result["opening"][:20] + "..." if round_result["opening"] else "")
                else:
                    respond_to = agents[agent_idx - 1].name

                speech = await self._call_agent_stream(
                    agent,
                    self._build_standard_speech(agent, topic, deliverable, context_history, round_num, materials_ctx, respond_to=respond_to),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            # 每轮总结
            summary_speaker = host_agent.name if host_agent else "系统"
            if host_agent:
                summary = await self._call_host_stream(
                    host_agent,
                    self._build_standard_summary(host_agent, topic, deliverable, round_result["speeches"], round_num, rounds),
                    result, event_callback, round_num, "summary"
                )
            else:
                summary = await self.service._call_system_summary(topic, deliverable, round_result["speeches"], round_num, rounds, result["tokens"])
            round_result["summary"] = summary
            context_history.append(f"【第{round_num}轮总结】{summary}")
            discussion_records.append({"round": round_num, "speaker": summary_speaker, "content": summary, "type": "summary"})
            self._save_records(roundtable_id, discussion_records, round_num, "总结")

            if event_callback:
                event_callback("speaker_end", {"round": round_num, "speaker": summary_speaker, "type": "summary", "content": summary})
                event_callback("round_end", {"round": round_num, "total": rounds})

            discussion_rounds.append(round_result)

        # 最终纪要
        if host_agent:
            final_summary = await self._call_host_stream(
                host_agent,
                self._build_standard_final_summary(host_agent, topic, deliverable, discussion_rounds, materials_ctx),
                result, event_callback, rounds, "final_summary"
            )
        else:
            final_summary = await self.service._call_system_final_summary(topic, deliverable, discussion_rounds, result["tokens"])

        return {"discussion_rounds": discussion_rounds, "summary": final_summary, "deliverable": final_summary}

    def _build_standard_opening(self, host, topic, deliverable, agents, materials_ctx="") -> str:
        agent_names = ", ".join([a.name for a in agents if a.id != host.id])
        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"参会者：{agent_names}\n"
            f"{materials_ctx}\n\n"
            f"请作为主持人，为这场圆桌会议做一个简短的开场，"
            f"介绍讨论主题、预期产出，并引导各位参会者开始发言。"
            f"请控制在 200 字以内。"
        )

    def _build_standard_speech(self, agent, topic, deliverable, context_history, round_num, materials_ctx="", respond_to: str = "") -> str:
        context_text = "\n".join(context_history[-6:])
        respond_hint = f"\n6. 请特别回应 {respond_to} 的观点，表达赞同、补充或提出不同看法" if respond_to else ""
        return (
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num} 轮讨论。\n\n"
            f"之前的讨论：\n{context_text}\n\n"
            f"【发言要求】\n"
            f"1. 你的发言必须围绕会议主题和预期产出\n"
            f"2. 请回应或补充之前参会者的观点，不要完全自说自话\n"
            f"3. 提出建设性意见，推动讨论向产出目标前进\n"
            f"4. 如果之前的观点有不足，请礼貌地指出并补充\n"
            f"5. 控制在 250 字以内"
            f"{respond_hint}"
        )

    def _build_standard_summary(self, host, topic, deliverable, speeches, round_num, total_rounds) -> str:
        speech_text = "\n".join([f"- {s['agent_name']}：{s['content']}" for s in speeches])
        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"当前是第 {round_num}/{total_rounds} 轮讨论。\n\n"
            f"本轮发言：\n{speech_text}\n\n"
            f"请对本轮讨论进行简要总结，并引导下一轮讨论的方向。"
            f"请控制在 200 字以内。"
        )

    def _build_standard_final_summary(self, host, topic, deliverable, discussion_rounds, materials_ctx="") -> str:
        rounds_text = ""
        for r in discussion_rounds:
            rounds_text += f"\n第 {r['round']} 轮：\n"
            if r.get("opening"):
                rounds_text += f"开场：{r['opening']}\n"
            for s in r.get("speeches", []):
                rounds_text += f"- {s['agent_name']}：{s['content']}\n"
            if r.get("summary"):
                rounds_text += f"总结：{r['summary']}\n"
        return (
            f"你是这场圆桌会议的主持人。\n"
            f"讨论主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n\n"
            f"以下是全部讨论记录：\n{rounds_text}\n\n"
            f"请生成一份完整的会议纪要，包括：\n"
            f"1. 讨论背景与目标\n"
            f"2. 各方主要观点\n"
            f"3. 达成的共识\n"
            f"4. 待进一步讨论的问题\n"
            f"5. 行动建议\n"
        )


class BrainstormStrategy(MeetingStrategy):
    """头脑风暴策略"""

    def get_name(self) -> str:
        return "brainstorm"

    def get_description(self) -> str:
        return "头脑风暴，强发散，主持人引导发散并筛选保留"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        all_ideas: list[str] = []

        for round_num in range(1, rounds + 1):
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": rounds, "phase": "发散"})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": "发散引导", "stage": f"round_{round_num}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 主持人引导发散
            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    self._build_brainstorm_guide(host_agent, topic, round_num, rounds, all_ideas, materials_ctx),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【发散引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, "发散引导")

            # 每个参会者发散发言
            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    self._build_brainstorm_speech(agent, topic, context_history, round_num, materials_ctx),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                # 提取创意点
                all_ideas.append(f"{agent.name}: {speech}")

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            # 主持人筛选保留
            if host_agent:
                filter_result = await self._call_host_stream(
                    host_agent,
                    self._build_brainstorm_filter(host_agent, topic, round_result["speeches"], all_ideas, round_num, rounds),
                    result, event_callback, round_num, "filter"
                )
                round_result["summary"] = filter_result
                context_history.append(f"【筛选保留】{filter_result}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": filter_result, "type": "filter"})
                self._save_records(roundtable_id, discussion_records, round_num, "筛选保留")

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": rounds})
            discussion_rounds.append(round_result)

        # 最终创意清单
        final_deliverable = ""
        if host_agent:
            final_deliverable = await self._call_host_stream(
                host_agent,
                self._build_brainstorm_final(host_agent, topic, deliverable, all_ideas, discussion_rounds, materials_ctx),
                result, event_callback, rounds, "final_deliverable"
            )
        else:
            final_deliverable = "\n".join([f"- {idea}" for idea in all_ideas])

        summary = f"头脑风暴完成，共收集 {len(all_ideas)} 条创意，最终保留的创意清单如下：\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}

    def _build_brainstorm_guide(self, host, topic, round_num, total_rounds, all_ideas, materials_ctx="") -> str:
        ideas_ctx = "\n".join([f"- {idea}" for idea in all_ideas[-10:]]) if all_ideas else "暂无"
        return (
            f"你是头脑风暴会议的主持人。\n"
            f"主题：{topic}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num}/{total_rounds} 轮。\n"
            f"已收集的创意：\n{ideas_ctx}\n\n"
            f"请引导参会者进行发散思考，鼓励提出更多、更新颖的创意。"
            f"可以提出启发性问题或从不同角度引导。控制在 150 字以内。"
        )

    def _build_brainstorm_speech(self, agent, topic, context_history, round_num, materials_ctx="") -> str:
        context_text = "\n".join(context_history[-8:])
        return (
            f"头脑风暴主题：{topic}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num} 轮。\n\n"
            f"之前的讨论：\n{context_text}\n\n"
            f"请尽可能多地提出创意和想法，不要自我审查，大胆发散。"
            f"请控制在 250 字以内。"
        )

    def _build_brainstorm_filter(self, host, topic, speeches, all_ideas, round_num, total_rounds) -> str:
        speech_text = "\n".join([f"- {s['agent_name']}：{s['content']}" for s in speeches])
        return (
            f"你是头脑风暴会议的主持人。\n"
            f"主题：{topic}\n"
            f"当前是第 {round_num}/{total_rounds} 轮。\n\n"
            f"本轮发言：\n{speech_text}\n\n"
            f"请从本轮发言中筛选出有价值的创意点，进行简要点评和保留。"
            f"说明为什么这些创意值得保留。控制在 200 字以内。"
        )

    def _build_brainstorm_final(self, host, topic, deliverable, all_ideas, discussion_rounds, materials_ctx="") -> str:
        return (
            f"你是头脑风暴会议的主持人。\n"
            f"主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n\n"
            f"以下是全部收集到的创意（共 {len(all_ideas)} 条）：\n"
            + "\n".join([f"{i+1}. {idea}" for i, idea in enumerate(all_ideas)])
            + "\n\n请整理出一份最终的创意清单，按价值分类（高价值/待验证/有趣但暂不实施），"
            f"并对每个创意做简要说明。"
        )


class ParliamentStrategy(MeetingStrategy):
    """议会投票策略"""

    def get_name(self) -> str:
        return "parliament"

    def get_description(self) -> str:
        return "议会投票，多轮观点阐述+投票，直到全票当选"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        vote_history: list[dict] = []

        for round_num in range(1, rounds + 1):
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "votes": []}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": rounds, "phase": "阐述"})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": "观点阐述", "stage": f"round_{round_num}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 主持人引导
            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    self._build_parliament_guide(host_agent, topic, round_num, rounds, vote_history, materials_ctx),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【投票引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, "观点阐述")

            # 每个参会者阐述观点/方案
            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    self._build_parliament_speech(agent, topic, context_history, round_num, materials_ctx),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            # 投票环节
            if event_callback:
                event_callback("phase_change", {"round": round_num, "phase": "投票"})

            votes = []
            for agent in agents:
                vote_prompt = (
                    f"你是议会投票的参会者。\n"
                    f"议题：{topic}\n\n"
                    f"本轮各方案阐述：\n"
                    + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in round_result["speeches"]])
                    + "\n\n请投票给你认为最好的方案，只能选择一个。请直接回复你选择的人名。"
                )
                vote = await self._call_agent_stream(agent, vote_prompt, result, event_callback, round_num, "vote")
                votes.append({"agent_id": agent.id, "agent_name": agent.name, "vote": vote.strip()})
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": f"投票给: {vote.strip()}", "type": "vote"})

            round_result["votes"] = votes
            vote_history.append({"round": round_num, "votes": votes})
            self._save_records(roundtable_id, discussion_records, round_num, "投票中")

            # 统计票数
            vote_count: dict[str, int] = {}
            for v in votes:
                name = v["vote"]
                vote_count[name] = vote_count.get(name, 0) + 1

            # 主持人宣布投票结果
            if host_agent:
                vote_result_text = "\n".join([f"- {name}: {count} 票" for name, count in vote_count.items()])
                winner = max(vote_count, key=vote_count.get) if vote_count else ""
                is_unanimous = vote_count.get(winner, 0) == len(agents)

                result_announce = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是议会投票主持人。\n"
                        f"第 {round_num} 轮投票结果：\n{vote_result_text}\n\n"
                        f"{'该方案已获得全票通过！' if is_unanimous else '尚未获得全票，请继续讨论和补充。'}"
                        f"请宣布结果并引导下一步。"
                    ),
                    result, event_callback, round_num, "vote_result"
                )
                round_result["summary"] = result_announce
                context_history.append(f"【投票结果】{result_announce}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": result_announce, "type": "vote_result"})
                self._save_records(roundtable_id, discussion_records, round_num, "投票结果")

                if is_unanimous:
                    if event_callback:
                        event_callback("phase_change", {"round": round_num, "phase": "全票当选"})
                    break

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": rounds})
            discussion_rounds.append(round_result)

        # 最终决策结果
        final_deliverable = ""
        if host_agent:
            final_deliverable = await self._call_host_stream(
                host_agent,
                self._build_parliament_final(host_agent, topic, deliverable, vote_history, discussion_rounds, materials_ctx),
                result, event_callback, rounds, "final_deliverable"
            )
        else:
            final_deliverable = "投票结束，最终决策结果已产生。"

        summary = f"议会投票完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}

    def _build_parliament_guide(self, host, topic, round_num, total_rounds, vote_history, materials_ctx="") -> str:
        history = ""
        if vote_history:
            history = "\n".join([f"第 {v['round']} 轮投票：" + ", ".join([f"{x['agent_name']}投{x['vote']}" for x in v["votes"]]) for v in vote_history])
        return (
            f"你是议会投票主持人。\n"
            f"议题：{topic}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num}/{total_rounds} 轮。\n"
            f"{history}\n\n"
            f"请引导参会者阐述自己的方案或观点，并鼓励大家为自己拉票。"
            f"控制在 150 字以内。"
        )

    def _build_parliament_speech(self, agent, topic, context_history, round_num, materials_ctx="") -> str:
        context_text = "\n".join(context_history[-6:])
        return (
            f"议会投票议题：{topic}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num} 轮。\n\n"
            f"之前的讨论：\n{context_text}\n\n"
            f"请阐述你的方案/观点，并说明为什么你的方案是最好的，为自己拉票。"
            f"请控制在 300 字以内。"
        )

    def _build_parliament_final(self, host, topic, deliverable, vote_history, discussion_rounds, materials_ctx="") -> str:
        vote_text = ""
        for v in vote_history:
            vote_text += f"\n第 {v['round']} 轮：\n"
            for x in v["votes"]:
                vote_text += f"- {x['agent_name']} 投给 {x['vote']}\n"
        return (
            f"你是议会投票主持人。\n"
            f"议题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n\n"
            f"投票历史：\n{vote_text}\n\n"
            f"请生成最终的决策结果文档，包括：\n"
            f"1. 最终当选方案\n"
            f"2. 各方案得票情况\n"
            f"3. 决策理由\n"
            f"4. 后续执行建议\n"
        )


class ConvergenceStrategy(MeetingStrategy):
    """方案收敛策略"""

    def get_name(self) -> str:
        return "convergence"

    def get_description(self) -> str:
        return "方案收敛，强收敛，主持人引导形成可落地方案"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        converged_plan = ""

        for round_num in range(1, rounds + 1):
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": rounds, "phase": "收敛"})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": "收敛引导", "stage": f"round_{round_num}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 主持人引导收敛
            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    self._build_convergence_guide(host_agent, topic, round_num, rounds, converged_plan, materials_ctx),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【收敛引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, "收敛引导")

            # 参会者围绕收敛方向发言
            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    self._build_convergence_speech(agent, topic, deliverable, context_history, round_num, converged_plan, materials_ctx),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            # 主持人整合形成更完整的方案
            if host_agent:
                integration = await self._call_host_stream(
                    host_agent,
                    self._build_convergence_integration(host_agent, topic, deliverable, round_result["speeches"], converged_plan, round_num, rounds),
                    result, event_callback, round_num, "integration"
                )
                round_result["summary"] = integration
                converged_plan = integration
                context_history.append(f"【方案整合】{integration}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": integration, "type": "integration"})
                self._save_records(roundtable_id, discussion_records, round_num, "方案整合")

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": rounds})
            discussion_rounds.append(round_result)

        # 最终落地方案
        final_deliverable = ""
        if host_agent:
            final_deliverable = await self._call_host_stream(
                host_agent,
                self._build_convergence_final(host_agent, topic, deliverable, converged_plan, discussion_rounds, materials_ctx),
                result, event_callback, rounds, "final_deliverable"
            )
        else:
            final_deliverable = converged_plan

        summary = f"方案收敛完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}

    def _build_convergence_guide(self, host, topic, round_num, total_rounds, converged_plan, materials_ctx="") -> str:
        plan_ctx = f"当前已整合的方案框架：\n{converged_plan}\n\n" if converged_plan else ""
        return (
            f"你是方案收敛会议的主持人。\n"
            f"主题：{topic}\n"
            f"{materials_ctx}\n"
            f"当前是第 {round_num}/{total_rounds} 轮。\n"
            f"{plan_ctx}"
            f"请引导讨论向更具体、更可落地的方向收敛。"
            f"控制在 150 字以内。"
        )

    def _build_convergence_speech(self, agent, topic, deliverable, context_history, round_num, converged_plan, materials_ctx="") -> str:
        context_text = "\n".join(context_history[-6:])
        plan_ctx = f"当前方案框架：\n{converged_plan}\n\n" if converged_plan else ""
        return (
            f"方案收敛主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n"
            f"{plan_ctx}"
            f"当前是第 {round_num} 轮。\n\n"
            f"之前的讨论：\n{context_text}\n\n"
            f"请提出具体的、可落地的建议和补充，让方案更加完善。"
            f"请控制在 300 字以内。"
        )

    def _build_convergence_integration(self, host, topic, deliverable, speeches, converged_plan, round_num, total_rounds) -> str:
        speech_text = "\n".join([f"- {s['agent_name']}：{s['content']}" for s in speeches])
        plan_ctx = f"上一轮方案框架：\n{converged_plan}\n\n" if converged_plan else ""
        return (
            f"你是方案收敛会议的主持人。\n"
            f"主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"当前是第 {round_num}/{total_rounds} 轮。\n\n"
            f"{plan_ctx}"
            f"本轮发言：\n{speech_text}\n\n"
            f"请将本轮发言整合进现有方案框架，形成更完整的方案。"
            f"控制在 300 字以内。"
        )

    def _build_convergence_final(self, host, topic, deliverable, converged_plan, discussion_rounds, materials_ctx="") -> str:
        return (
            f"你是方案收敛会议的主持人。\n"
            f"主题：{topic}\n"
            f"预期产出：{deliverable}\n"
            f"{materials_ctx}\n\n"
            f"最终方案框架：\n{converged_plan}\n\n"
            f"请生成一份完整的、可落地的方案文档，包括：\n"
            f"1. 方案概述\n"
            f"2. 具体执行步骤\n"
            f"3. 行动项（含责任人和时间线）\n"
            f"4. 风险评估和应对措施\n"
            f"5. 成功标准\n"
        )


class SixHatStrategy(MeetingStrategy):
    """六顶思考帽策略"""

    HATS = [
        ("白帽", "事实与数据", "请基于客观事实和数据发表看法，不要加入主观判断"),
        ("红帽", "情感与直觉", "请表达你的情感反应和直觉感受，不需要理由"),
        ("黑帽", "风险与问题", "请批判性地思考，指出潜在的风险、问题和缺点"),
        ("黄帽", "收益与价值", "请思考积极的一面，指出收益、价值和可行性"),
        ("绿帽", "创意与替代", "请提出新的创意、替代方案和可能性"),
        ("蓝帽", "控制与总结", "请控制讨论节奏，进行总结和决策"),
    ]

    def get_name(self) -> str:
        return "six_hat"

    def get_description(self) -> str:
        return "六顶思考帽，按白/红/黑/黄/绿/蓝六角色顺序发言"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        hat_results = []

        for hat_idx, (hat_name, hat_desc, hat_prompt) in enumerate(self.HATS):
            round_num = hat_idx + 1
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "hat": hat_name}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": 6, "phase": hat_name})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": f"{hat_name}思考", "stage": f"hat_{hat_name}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 主持人引导
            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是六顶思考帽会议的主持人。\n"
                        f"主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"现在进入【{hat_name}】阶段 - {hat_desc}。\n"
                        f"请引导参会者从这个角度思考问题。控制在 100 字以内。"
                    ),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【{hat_name}引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{hat_name}思考")

            # 每个参会者从该角度发言
            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    (
                        f"六顶思考帽讨论主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"当前阶段：【{hat_name}】{hat_desc}\n"
                        f"{hat_prompt}。\n\n"
                        f"之前的思考：\n{' '.join(context_history[-5:])}\n\n"
                        f"请控制在 200 字以内。"
                    ),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{hat_name}-{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            hat_results.append({"hat": hat_name, "speeches": round_result["speeches"]})
            discussion_rounds.append(round_result)

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": 6})

        # 最终综合结论
        final_deliverable = ""
        if host_agent:
            hat_summary = "\n".join([f"\n【{h['hat']}】\n" + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in h["speeches"]]) for h in hat_results])
            final_deliverable = await self._call_host_stream(
                host_agent,
                (
                    f"你是六顶思考帽会议的主持人。\n"
                    f"主题：{topic}\n"
                    f"预期产出：{deliverable}\n"
                    f"{materials_ctx}\n\n"
                    f"六顶思考帽各阶段发言：\n{hat_summary}\n\n"
                    f"请综合六顶思考帽的分析结果，生成一份全面的结论报告，包括：\n"
                    f"1. 各角度分析总结\n"
                    f"2. 综合判断和建议\n"
                    f"3. 后续行动方向\n"
                ),
                result, event_callback, 6, "final_deliverable"
            )
        else:
            final_deliverable = "六顶思考帽分析完成。"

        summary = f"六顶思考帽分析完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


class FishboneStrategy(MeetingStrategy):
    """鱼骨图分析策略"""

    DIMENSIONS = ["人", "机", "料", "法", "环", "测"]

    def get_name(self) -> str:
        return "fishbone"

    def get_description(self) -> str:
        return "鱼骨图分析，从人/机/料/法/环/测维度分析根因"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        dimension_results = []

        for dim_idx, dimension in enumerate(self.DIMENSIONS):
            round_num = dim_idx + 1
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "dimension": dimension}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": len(self.DIMENSIONS), "phase": dimension})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": f"{dimension}维度", "stage": f"dim_{dimension}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 主持人引导该维度
            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是鱼骨图分析会议的主持人。\n"
                        f"问题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"现在分析【{dimension}】维度。\n"
                        f"请引导参会者从该维度挖掘可能的根因。控制在 100 字以内。"
                    ),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【{dimension}引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{dimension}维度")

            # 参会者从该维度发言
            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    (
                        f"鱼骨图分析问题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"当前维度：【{dimension}】\n"
                        f"请从{dimension}的角度分析问题可能的根因。\n\n"
                        f"已分析维度：{', '.join(self.DIMENSIONS[:dim_idx])}\n\n"
                        f"请控制在 200 字以内。"
                    ),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{dimension}-{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            dimension_results.append({"dimension": dimension, "speeches": round_result["speeches"]})
            discussion_rounds.append(round_result)

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": len(self.DIMENSIONS)})

        # 最终根因分析报告
        final_deliverable = ""
        if host_agent:
            dim_summary = "\n".join([f"\n【{d['dimension']}】\n" + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in d["speeches"]]) for d in dimension_results])
            final_deliverable = await self._call_host_stream(
                host_agent,
                (
                    f"你是鱼骨图分析会议的主持人。\n"
                    f"问题：{topic}\n"
                    f"预期产出：{deliverable}\n"
                    f"{materials_ctx}\n\n"
                    f"各维度分析结果：\n{dim_summary}\n\n"
                    f"请生成鱼骨图结构的根因分析报告，包括：\n"
                    f"1. 问题描述\n"
                    f"2. 各维度根因分析（人/机/料/法/环/测）\n"
                    f"3. 关键根因识别\n"
                    f"4. 改进建议\n"
                ),
                result, event_callback, len(self.DIMENSIONS), "final_deliverable"
            )
        else:
            final_deliverable = "鱼骨图分析完成。"

        summary = f"鱼骨图分析完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


class SwotStrategy(MeetingStrategy):
    """SWOT 分析策略"""

    DIMENSIONS = [
        ("S", "优势 Strengths", "请分析内部优势"),
        ("W", "劣势 Weaknesses", "请分析内部劣势"),
        ("O", "机会 Opportunities", "请分析外部机会"),
        ("T", "威胁 Threats", "请分析外部威胁"),
    ]

    def get_name(self) -> str:
        return "swot"

    def get_description(self) -> str:
        return "SWOT 战略分析，四维度分析"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)
        dim_results = []

        for dim_idx, (code, name, prompt) in enumerate(self.DIMENSIONS):
            round_num = dim_idx + 1
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "dimension": code}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": 4, "phase": name})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": f"{code}分析", "stage": f"swot_{code}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是 SWOT 分析会议的主持人。\n"
                        f"主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"现在进行【{name}】分析。\n"
                        f"请引导参会者分析。控制在 100 字以内。"
                    ),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                context_history.append(f"【{code}引导】{guide}")
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{code}分析")

            for agent in agents:
                self.service.db.update(
                    "roundtables",
                    {"current_speaker": agent.name, "updated_at": datetime.now().isoformat()},
                    where="id = ?", where_params=(roundtable_id,)
                )
                if event_callback:
                    event_callback("speaker_start", {"round": round_num, "speaker": agent.name, "speaker_id": agent.id, "type": "speech"})

                speech = await self._call_agent_stream(
                    agent,
                    (
                        f"SWOT 分析主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"当前维度：【{name}】\n"
                        f"{prompt}。\n\n"
                        f"已分析：{', '.join([d[1] for d in self.DIMENSIONS[:dim_idx]]) or '无'}\n\n"
                        f"请控制在 200 字以内。"
                    ),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                context_history.append(f"【{code}-{agent.name}】{speech}")
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

                if event_callback:
                    event_callback("speaker_end", {"round": round_num, "speaker": agent.name, "type": "speech", "content": speech})

            dim_results.append({"dimension": code, "name": name, "speeches": round_result["speeches"]})
            discussion_rounds.append(round_result)

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": 4})

        # 最终 SWOT 矩阵和战略建议
        final_deliverable = ""
        if host_agent:
            dim_summary = "\n".join([f"\n【{d['dimension']} - {d['name']}】\n" + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in d["speeches"]]) for d in dim_results])
            final_deliverable = await self._call_host_stream(
                host_agent,
                (
                    f"你是 SWOT 分析会议的主持人。\n"
                    f"主题：{topic}\n"
                    f"预期产出：{deliverable}\n"
                    f"{materials_ctx}\n\n"
                    f"各维度分析结果：\n{dim_summary}\n\n"
                    f"请生成 SWOT 矩阵和战略建议报告，包括：\n"
                    f"1. SWOT 矩阵（四象限整理）\n"
                    f"2. SO 战略（优势+机会）\n"
                    f"3. WO 战略（劣势+机会）\n"
                    f"4. ST 战略（优势+威胁）\n"
                    f"5. WT 战略（劣势+威胁）\n"
                ),
                result, event_callback, 4, "final_deliverable"
            )
        else:
            final_deliverable = "SWOT 分析完成。"

        summary = f"SWOT 分析完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


class OkrStrategy(MeetingStrategy):
    """OKR 拆解会策略"""

    def get_name(self) -> str:
        return "okr"

    def get_description(self) -> str:
        return "OKR 拆解会，目标到关键结果到行动计划"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        context_history = list(previous_context) if previous_context else []
        materials_ctx = self._build_materials_context(roundtable.materials)

        # 第一轮：确定 Objective
        round_num = 1
        round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "phase": "目标确定"}

        if event_callback:
            event_callback("round_start", {"round": round_num, "total": 3, "phase": "目标确定"})

        self.service.db.update(
            "roundtables",
            {"current_round": round_num, "current_speaker": "目标讨论", "stage": "okr_objective", "updated_at": datetime.now().isoformat()},
            where="id = ?", where_params=(roundtable_id,)
        )

        if host_agent:
            guide = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"主题：{topic}\n"
                    f"预期产出：{deliverable}\n"
                    f"{materials_ctx}\n"
                    f"第一阶段：确定 Objective（目标）。\n"
                    f"请引导讨论，明确一个清晰、有挑战性的目标。"
                ),
                result, event_callback, round_num, "guide"
            )
            round_result["opening"] = guide
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
            self._save_records(roundtable_id, discussion_records, round_num, "目标讨论")

        for agent in agents:
            speech = await self._call_agent_stream(
                agent,
                (
                    f"OKR 拆解主题：{topic}\n"
                    f"{materials_ctx}\n"
                    f"当前阶段：确定 Objective（目标）\n\n"
                    f"请提出你认为的目标应该是什么，要清晰、可衡量、有挑战性。"
                    f"控制在 200 字以内。"
                ),
                result, event_callback, round_num, "speech"
            )
            round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
            discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
            self._save_records(roundtable_id, discussion_records, round_num, agent.name)

        # 主持人确定最终 Objective
        objective = ""
        if host_agent:
            objective = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"主题：{topic}\n"
                    f"参会者关于目标的发言：\n"
                    + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in round_result["speeches"]])
                    + "\n\n请综合以上意见，确定一个最终的 Objective（目标），要简洁有力。"
                ),
                result, event_callback, round_num, "objective"
            )
            round_result["summary"] = objective
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": objective, "type": "objective"})
            self._save_records(roundtable_id, discussion_records, round_num, "目标确定")

        discussion_rounds.append(round_result)
        if event_callback:
            event_callback("round_end", {"round": round_num, "total": 3})

        # 第二轮：确定 Key Results
        round_num = 2
        round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "phase": "关键结果"}

        if event_callback:
            event_callback("round_start", {"round": round_num, "total": 3, "phase": "关键结果"})

        self.service.db.update(
            "roundtables",
            {"current_round": round_num, "current_speaker": "KR讨论", "stage": "okr_krs", "updated_at": datetime.now().isoformat()},
            where="id = ?", where_params=(roundtable_id,)
        )

        if host_agent:
            guide = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"已确定目标：{objective}\n"
                    f"第二阶段：确定 Key Results（关键结果）。\n"
                    f"请引导讨论，确定 3-5 个可衡量的关键结果。"
                ),
                result, event_callback, round_num, "guide"
            )
            round_result["opening"] = guide
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
            self._save_records(roundtable_id, discussion_records, round_num, "KR讨论")

        for agent in agents:
            speech = await self._call_agent_stream(
                agent,
                (
                    f"OKR 拆解\n"
                    f"目标：{objective}\n"
                    f"当前阶段：确定 Key Results\n\n"
                    f"请提出你认为的关键结果，要具体、可衡量、可验证。"
                    f"控制在 200 字以内。"
                ),
                result, event_callback, round_num, "speech"
            )
            round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
            discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
            self._save_records(roundtable_id, discussion_records, round_num, agent.name)

        krs = ""
        if host_agent:
            krs = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"目标：{objective}\n"
                    f"参会者关于 KR 的发言：\n"
                    + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in round_result["speeches"]])
                    + "\n\n请综合以上意见，确定 3-5 个最终的关键结果（KR），每个 KR 要有衡量标准。"
                ),
                result, event_callback, round_num, "krs"
            )
            round_result["summary"] = krs
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": krs, "type": "krs"})
            self._save_records(roundtable_id, discussion_records, round_num, "KR确定")

        discussion_rounds.append(round_result)
        if event_callback:
            event_callback("round_end", {"round": round_num, "total": 3})

        # 第三轮：行动计划
        round_num = 3
        round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "phase": "行动计划"}

        if event_callback:
            event_callback("round_start", {"round": round_num, "total": 3, "phase": "行动计划"})

        self.service.db.update(
            "roundtables",
            {"current_round": round_num, "current_speaker": "行动计划", "stage": "okr_actions", "updated_at": datetime.now().isoformat()},
            where="id = ?", where_params=(roundtable_id,)
        )

        if host_agent:
            guide = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"目标：{objective}\n"
                    f"关键结果：\n{krs}\n"
                    f"第三阶段：制定行动计划。\n"
                    f"请引导讨论，将每个 KR 拆解为具体的行动项。"
                ),
                result, event_callback, round_num, "guide"
            )
            round_result["opening"] = guide
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
            self._save_records(roundtable_id, discussion_records, round_num, "行动计划")

        for agent in agents:
            speech = await self._call_agent_stream(
                agent,
                (
                    f"OKR 拆解\n"
                    f"目标：{objective}\n"
                    f"关键结果：\n{krs}\n"
                    f"当前阶段：制定行动计划\n\n"
                    f"请提出具体的行动建议，包括责任人和时间节点。"
                    f"控制在 200 字以内。"
                ),
                result, event_callback, round_num, "speech"
            )
            round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
            discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
            self._save_records(roundtable_id, discussion_records, round_num, agent.name)

        actions = ""
        if host_agent:
            actions = await self._call_host_stream(
                host_agent,
                (
                    f"你是 OKR 拆解会的主持人。\n"
                    f"目标：{objective}\n"
                    f"关键结果：\n{krs}\n"
                    f"参会者关于行动计划的发言：\n"
                    + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in round_result["speeches"]])
                    + "\n\n请综合以上意见，制定完整的行动计划。"
                ),
                result, event_callback, round_num, "actions"
            )
            round_result["summary"] = actions
            discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": actions, "type": "actions"})
            self._save_records(roundtable_id, discussion_records, round_num, "行动计划确定")

        discussion_rounds.append(round_result)
        if event_callback:
            event_callback("round_end", {"round": round_num, "total": 3})

        final_deliverable = (
            f"# OKR 文档\n\n"
            f"## Objective（目标）\n{objective}\n\n"
            f"## Key Results（关键结果）\n{krs}\n\n"
            f"## 行动计划\n{actions}"
        )
        summary = f"OKR 拆解完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


class RetrospectiveStrategy(MeetingStrategy):
    """项目复盘策略"""

    PHASES = [
        ("回顾", "回顾项目/迭代的整体情况"),
        ("做得好", "总结哪些方面做得好，值得保持"),
        ("待改进", "分析哪些方面需要改进"),
        ("行动项", "提炼具体的行动项和改进措施"),
    ]

    def get_name(self) -> str:
        return "retrospective"

    def get_description(self) -> str:
        return "项目复盘，回顾+改进"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        materials_ctx = self._build_materials_context(roundtable.materials)
        phase_results = []

        for phase_idx, (phase_name, phase_desc) in enumerate(self.PHASES):
            round_num = phase_idx + 1
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "phase": phase_name}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": len(self.PHASES), "phase": phase_name})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": f"{phase_name}讨论", "stage": f"retro_{phase_name}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            if host_agent:
                guide = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是项目复盘会议的主持人。\n"
                        f"复盘主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"当前阶段：【{phase_name}】{phase_desc}\n"
                        f"请引导参会者发言。控制在 100 字以内。"
                    ),
                    result, event_callback, round_num, "guide"
                )
                round_result["opening"] = guide
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": guide, "type": "guide"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{phase_name}讨论")

            for agent in agents:
                speech = await self._call_agent_stream(
                    agent,
                    (
                        f"项目复盘主题：{topic}\n"
                        f"{materials_ctx}\n"
                        f"当前阶段：【{phase_name}】{phase_desc}\n\n"
                        f"请发表你的看法。控制在 200 字以内。"
                    ),
                    result, event_callback, round_num, "speech"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": speech})
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": speech, "type": "speech"})
                self._save_records(roundtable_id, discussion_records, round_num, agent.name)

            phase_results.append({"phase": phase_name, "speeches": round_result["speeches"]})
            discussion_rounds.append(round_result)

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": len(self.PHASES)})

        # 最终复盘报告
        final_deliverable = ""
        if host_agent:
            phase_summary = "\n".join([f"\n## {p['phase']}\n" + "\n".join([f"- {s['agent_name']}：{s['content']}" for s in p["speeches"]]) for p in phase_results])
            final_deliverable = await self._call_host_stream(
                host_agent,
                (
                    f"你是项目复盘会议的主持人。\n"
                    f"复盘主题：{topic}\n"
                    f"预期产出：{deliverable}\n"
                    f"{materials_ctx}\n\n"
                    f"各阶段发言：\n{phase_summary}\n\n"
                    f"请生成一份完整的复盘报告，包括：\n"
                    f"1. 项目/迭代概述\n"
                    f"2. 做得好的方面（继续保持）\n"
                    f"3. 待改进的方面\n"
                    f"4. 具体行动项（含责任人和时间）\n"
                    f"5. 意外发现/洞察\n"
                ),
                result, event_callback, len(self.PHASES), "final_deliverable"
            )
        else:
            final_deliverable = "复盘完成。"

        summary = f"项目复盘完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


class InterviewStrategy(MeetingStrategy):
    """模拟面试策略"""

    DIMENSIONS = ["技术能力", "项目经验", "团队协作", "学习能力", "文化匹配"]

    def get_name(self) -> str:
        return "interview"

    def get_description(self) -> str:
        return "模拟面试，多面试官多维度考察"

    async def execute(
        self,
        roundtable_id: str,
        roundtable: Any,
        agents: list[Any],
        host_agent: Any,
        topic: str,
        deliverable: str,
        rounds: int,
        result: dict[str, Any],
        event_callback: Any,
    previous_context: list[str] | None = None,
    ) -> dict[str, Any]:
        discussion_records: list[dict] = []
        discussion_rounds = []
        materials_ctx = self._build_materials_context(roundtable.materials)
        evaluations = []

        # 主持人设定岗位和考察维度
        job_desc = ""
        if host_agent:
            job_desc = await self._call_host_stream(
                host_agent,
                (
                    f"你是模拟面试的主持人（HR/面试官负责人）。\n"
                    f"面试岗位：{topic}\n"
                    f"{materials_ctx}\n"
                    f"请设定该岗位的职责描述和考察维度，并做简短开场。"
                ),
                result, event_callback, 1, "opening"
            )
            discussion_records.append({"round": 1, "speaker": host_agent.name, "content": job_desc, "type": "opening"})
            self._save_records(roundtable_id, discussion_records, 1, "岗位设定")

        for dim_idx, dimension in enumerate(self.DIMENSIONS):
            round_num = dim_idx + 1
            round_result = {"round": round_num, "opening": None, "speeches": [], "summary": None, "dimension": dimension}

            if event_callback:
                event_callback("round_start", {"round": round_num, "total": len(self.DIMENSIONS), "phase": dimension})

            self.service.db.update(
                "roundtables",
                {"current_round": round_num, "current_speaker": f"{dimension}考察", "stage": f"interview_{dimension}", "updated_at": datetime.now().isoformat()},
                where="id = ?", where_params=(roundtable_id,)
            )

            # 面试官提问
            for agent in agents:
                question = await self._call_agent_stream(
                    agent,
                    (
                        f"你是面试官，负责考察候选人的{dimension}。\n"
                        f"面试岗位：{topic}\n"
                        f"岗位描述：{job_desc}\n"
                        f"{materials_ctx}\n"
                        f"请提出 1-2 个针对{dimension}的面试问题。"
                    ),
                    result, event_callback, round_num, "question"
                )
                round_result["speeches"].append({"agent_id": agent.id, "agent_name": agent.name, "content": question, "role": "question"})
                discussion_records.append({"round": round_num, "speaker": agent.name, "content": question, "type": "question"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{dimension}提问")

                # 模拟候选人回答（由主持人或其他 agent 模拟）
                answer = ""
                if host_agent:
                    answer = await self._call_host_stream(
                        host_agent,
                        (
                            f"你是候选人，正在面试{topic}岗位。\n"
                            f"面试官问题：{question}\n"
                            f"请模拟一个优秀候选人的回答。控制在 150 字以内。"
                        ),
                        result, event_callback, round_num, "answer"
                    )
                round_result["speeches"].append({"agent_id": "candidate", "agent_name": "候选人", "content": answer, "role": "answer"})
                discussion_records.append({"round": round_num, "speaker": "候选人", "content": answer, "type": "answer"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{dimension}回答")

            # 面试官评估
            eval_text = ""
            if host_agent:
                qa_text = "\n".join([f"Q: {s['content']}" if s.get('role') == 'question' else f"A: {s['content']}" for s in round_result["speeches"]])
                eval_text = await self._call_host_stream(
                    host_agent,
                    (
                        f"你是面试官负责人。\n"
                        f"面试岗位：{topic}\n"
                        f"考察维度：{dimension}\n"
                        f"问答记录：\n{qa_text}\n\n"
                        f"请对该维度给出评估（优秀/良好/一般/需考察），并说明理由。"
                    ),
                    result, event_callback, round_num, "evaluation"
                )
                round_result["summary"] = eval_text
                discussion_records.append({"round": round_num, "speaker": host_agent.name, "content": eval_text, "type": "evaluation"})
                self._save_records(roundtable_id, discussion_records, round_num, f"{dimension}评估")

            evaluations.append({"dimension": dimension, "evaluation": eval_text})
            discussion_rounds.append(round_result)

            if event_callback:
                event_callback("round_end", {"round": round_num, "total": len(self.DIMENSIONS)})

        # 最终综合评估报告
        final_deliverable = ""
        if host_agent:
            eval_summary = "\n".join([f"- {e['dimension']}：{e['evaluation']}" for e in evaluations])
            final_deliverable = await self._call_host_stream(
                host_agent,
                (
                    f"你是面试官负责人。\n"
                    f"面试岗位：{topic}\n"
                    f"{materials_ctx}\n\n"
                    f"各维度评估：\n{eval_summary}\n\n"
                    f"请生成综合评估报告，包括：\n"
                    f"1. 各维度评估汇总\n"
                    f"2. 候选人综合评分\n"
                    f"3. 录用建议（强烈推荐/推荐/待定/不推荐）\n"
                    f"4. 后续安排建议\n"
                ),
                result, event_callback, len(self.DIMENSIONS), "final_deliverable"
            )
        else:
            final_deliverable = "模拟面试完成。"

        summary = f"模拟面试完成。\n\n{final_deliverable}"
        return {"discussion_rounds": discussion_rounds, "summary": summary, "deliverable": final_deliverable}


# 策略注册表
STRATEGY_REGISTRY: dict[str, type[MeetingStrategy]] = {
    "standard": StandardStrategy,
    "brainstorm": BrainstormStrategy,
    "parliament": ParliamentStrategy,
    "convergence": ConvergenceStrategy,
    "six_hat": SixHatStrategy,
    "fishbone": FishboneStrategy,
    "swot": SwotStrategy,
    "okr": OkrStrategy,
    "retrospective": RetrospectiveStrategy,
    "interview": InterviewStrategy,
}


def get_strategy(meeting_type: str, service: "RoundtableService") -> MeetingStrategy:
    """获取会议策略实例"""
    strategy_class = STRATEGY_REGISTRY.get(meeting_type, StandardStrategy)
    return strategy_class(service)


def get_strategy_info() -> list[dict[str, str]]:
    """获取所有策略信息"""
    return [
        {"type": key, "name": cls(None).get_name(), "description": cls(None).get_description()}
        for key, cls in STRATEGY_REGISTRY.items()
    ]
