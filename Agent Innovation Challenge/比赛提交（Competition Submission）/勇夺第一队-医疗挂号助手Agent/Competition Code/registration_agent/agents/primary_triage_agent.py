from __future__ import annotations

import json
from typing import Any

from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import BaseAgent

from registration_agent.agents.clinic_index import format_list, format_qa
from registration_agent.utils.llm import llm_chat_json


class PrimaryTriageAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(id="primary_triage_agent", description="一级分诊助手：选1个一级门诊，必要时回问"))

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
        primaries = payload.get("primaries") or []
        if not isinstance(qa, list):
            qa = []
        if not isinstance(primaries, list):
            primaries = []
        return await self._run(patient_text=patient_text, qa=qa, primaries=[str(x) for x in primaries])

    async def stream(self, inputs: dict, runtime=None):
        yield await self.invoke(inputs, runtime=runtime)

    async def _run(self, *, patient_text: str, qa: list[dict[str, str]], primaries: list[str]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一级分诊助手。你必须在给定的一级门诊列表里做选择。\n"
                    "只有当缺少的信息会导致一级门诊选择可能不同，才允许提问。\n"
                    "不要问诊断细节/病因/疼痛评分/具体哪一颗牙等不影响一级门诊归类的问题。\n"
                    "如果需要提问，问题必须用于‘在候选一级门诊之间做区分’，并尽量设计为让用户在2-4个候选方向中选择。\n"
                    "如果你已经能把症状归类到某个系统/部位对应的一类门诊，就直接选择，不要提问。\n"
                    "提问必须让普通用户容易回答：避免专业术语，不要让用户在多个科室名之间做选择。\n"
                    "当 need_clarify=true 时，question 字符串允许前面有1-2行提示信息，但最后一行必须是一个单独问题，并以“请回答：”开头。\n"
                    "如果无法判断，请返回 need_clarify=true 并提出最多1个关键问题。\n"
                    "如果可以判断，请返回 need_clarify=false 且给出 primary。\n"
                    "只返回JSON：{\"need_clarify\": true/false, \"question\": \"...\"(可选), \"primary\": \"一级门诊\"(可选)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"患者描述：{patient_text}\n\n历史问答：\n{format_qa(qa)}\n\n一级门诊列表：\n{format_list(primaries)}"
                ),
            },
        ]
        data = await llm_chat_json(messages=messages)
        need = bool((data or {}).get("need_clarify", False))
        q = str((data or {}).get("question", "")).strip()
        primary_raw = (data or {}).get("primary", "")
        primary = str(primary_raw).strip() if primary_raw is not None else ""
        if not need and primary not in set(primaries):
            primary = primaries[0] if primaries else ""
        if need and not q:
            q = "提示：我需要先确定你主要属于哪一类问题（例如皮肤/消化/呼吸/妇产/儿科等）。\n请回答：最主要的不舒服在身体哪个部位？（一句话即可）"
        return {"need_clarify": need, "question": q, "primary": primary}
