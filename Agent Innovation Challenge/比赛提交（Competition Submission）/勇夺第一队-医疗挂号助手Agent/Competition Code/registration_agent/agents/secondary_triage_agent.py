from __future__ import annotations

import json
from typing import Any

from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import BaseAgent

from registration_agent.agents.clinic_index import format_list, format_qa
from registration_agent.utils.llm import llm_chat_json


class SecondaryTriageAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(id="secondary_triage_agent", description="二级分诊助手：选3个二级门诊，必要时回问"))

    async def invoke(self, inputs: dict, runtime=None) -> dict:
        payload_raw = inputs.get("query")
        if isinstance(payload_raw, str):
            try:
                payload = json.loads(payload_raw)
            except Exception:
                payload = {}
        elif isinstance(payload_raw, dict):
            payload = payload_raw
        else:
            payload = {}

        patient_text = str(payload.get("patient_text", "") or "")
        qa = payload.get("qa") or []
        primary = str(payload.get("primary", "") or "")
        secondaries = payload.get("secondaries") or []
        if not isinstance(qa, list):
            qa = []
        if not isinstance(secondaries, list):
            secondaries = []

        return await self._run(
            patient_text=patient_text,
            qa=qa,
            primary=primary,
            secondaries=[str(x) for x in secondaries],
        )

    async def stream(self, inputs: dict, runtime=None):
        yield await self.invoke(inputs, runtime=runtime)

    async def _run(self, *, patient_text: str, qa: list[dict[str, str]], primary: str, secondaries: list[str]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是二级分诊助手。你必须在给定的二级门诊列表里选择3个最相关的（按相关性排序）。\n"
                    "只有当缺少的信息会导致二级门诊选择可能不同，才允许提问。\n"
                    "不要问诊断细节（病因、疼痛评分、是否蛀牙等）如果这些不影响二级门诊选择。\n"
                    "如果需要提问，问题必须能直接用于在‘给定二级门诊列表’中做区分，最好让用户从候选二级门诊名称中选最匹配的1-2个，或补充一个关键部位/症状类型来映射到列表。\n"
                    "如果你已经可以从描述把问题映射到某些二级门诊，就直接给出 secondaries，不要提问。\n"
                    "提问必须让普通用户容易回答：避免专业术语。\n"
                    "当 need_clarify=true 时，question 字符串允许前面有1-2行提示信息，但最后一行必须是一个单独问题，并以“请回答：”开头。\n"
                    "如果无法判断，请返回 need_clarify=true 并提出最多1个关键问题。\n"
                    "如果可以判断，请返回 need_clarify=false 并给出 secondaries（数组，最多3个）。\n"
                    "只返回JSON：{\"need_clarify\": true/false, \"question\": \"...\"(可选), \"secondaries\": [\"二级门诊1\",\"二级门诊2\",\"二级门诊3\"](可选)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"患者描述：{patient_text}\n\n历史问答：\n{format_qa(qa)}\n\n已选一级门诊：{primary}\n\n二级门诊列表：\n{format_list(secondaries)}"
                ),
            },
        ]
        data = await llm_chat_json(messages=messages)
        need = bool((data or {}).get("need_clarify", False))
        q = str((data or {}).get("question", "")).strip()
        recs = (data or {}).get("secondaries", [])
        if not isinstance(recs, list):
            recs = []
        out: list[str] = []
        sec_set = set(secondaries)
        for r in recs:
            s = str(r).strip()
            if s and s in sec_set and s not in out:
                out.append(s)
        if not need and not out:
            out = secondaries[:3]
        if need and not q:
            q = "提示：我需要把问题更细分到合适的二级门诊。\n请回答：具体是哪一块最不舒服？（例如左/右，哪个关节/哪个位置，一句话即可）"
        return {"need_clarify": need, "question": q, "secondaries": out[:3]}
