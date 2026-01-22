from __future__ import annotations

import json
from typing import Any

from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import BaseAgent

from registration_agent.agents.clinic_index import format_doctors, format_qa
from registration_agent.utils.llm import llm_chat_json


class DoctorTriageAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(id="doctor_triage_agent", description="医生选择助手：从医生池选择最终1名医生"))

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
        doctors = payload.get("doctors") or []
        available_time = str(payload.get("available_time", "") or "")
        if not isinstance(qa, list):
            qa = []
        if not isinstance(doctors, list):
            doctors = []

        return await self._run(
            patient_text=patient_text,
            qa=qa,
            doctors=doctors,
            available_time=available_time,
        )

    async def stream(self, inputs: dict, runtime=None):
        yield await self.invoke(inputs, runtime=runtime)

    async def _run(self, *, patient_text: str, qa: list[dict[str, str]], doctors: list[dict[str, Any]], available_time: str) -> dict[str, Any]:
        doctors_text = format_doctors(doctors)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是医生选择助手。根据患者描述、历史问答、空闲时间，从医生列表选择1名最合适的。\n"
                    "只有当缺少的信息会导致医生/时间选择可能不同，才允许提问。\n"
                    "不要问与‘从列表中选人/选时间’无关的诊断细节；优先直接选择。\n"
                    "如果需要提问，聚焦于：就诊时间偏好、医院偏好（如有）、最想优先解决的症状点（影响专长匹配）。\n"
                    "提问必须让普通用户容易回答：避免专业术语。\n"
                    "当 need_clarify=true 时，question 字符串允许前面有1-2行提示信息，但最后一行必须是一个单独问题，并以“请回答：”开头。\n"
                    "如果信息不足导致无法选，请返回 need_clarify=true 并提出最多1个关键问题。\n"
                    "如果可以选择，请返回 need_clarify=false 且给出 index(从1开始) 与 reason 与 appointment_time(单一具体时间点)。\n"
                    "只返回JSON：{\"need_clarify\": true/false, \"question\": \"...\"(可选), \"index\": 1, \"reason\": \"...\", \"appointment_time\": \"周二 15:00\"}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"患者描述：{patient_text}\n\n历史问答：\n{format_qa(qa)}\n\n患者空闲时间：{available_time}\n\n医生列表：\n{doctors_text}"
                ),
            },
        ]
        data = await llm_chat_json(messages=messages)
        need = bool((data or {}).get("need_clarify", False))
        q = str((data or {}).get("question", "")).strip()
        if need and not q:
            q = "提示：我需要在候选医生里做最终选择。\n请回答：你更希望‘尽快能约到’还是‘更匹配擅长/经验’？"

        idx = -1
        try:
            idx = int((data or {}).get("index", 0)) - 1
        except Exception:
            idx = -1

        if need:
            return {"need_clarify": True, "question": q}

        if idx < 0 or idx >= len(doctors):
            idx = 0 if doctors else -1

        chosen = dict(doctors[idx]) if idx >= 0 else {}
        chosen["reason"] = str((data or {}).get("reason", "")).strip()
        chosen["appointment_time"] = str((data or {}).get("appointment_time", "")).strip()
        return {"need_clarify": False, "selected_doctor": chosen}
