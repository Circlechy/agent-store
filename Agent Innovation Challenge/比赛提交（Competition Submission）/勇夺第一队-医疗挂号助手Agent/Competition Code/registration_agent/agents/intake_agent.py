from __future__ import annotations

import json
from typing import Any

from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.agent.agent import BaseAgent

from registration_agent.utils.llm import llm_chat_json


class IntakeAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(id="intake_agent", description="总挂号助手：判断是否需要回问补充"))

    async def invoke(self, inputs: dict, runtime=None) -> dict:
        payload_raw = inputs.get("query")
        if isinstance(payload_raw, str):
            try:
                payload = json.loads(payload_raw) if payload_raw.strip().startswith("{") else {"user_text": payload_raw}
            except Exception:
                payload = {"user_text": payload_raw}
        elif isinstance(payload_raw, dict):
            payload = payload_raw
        else:
            payload = {}

        user_text = str(payload.get("user_text", "") or "")
        qa = payload.get("qa") or []
        if not isinstance(qa, list):
            qa = []
        return await self._run(user_text=user_text, qa=qa)

    async def stream(self, inputs: dict, runtime=None):
        yield await self.invoke(inputs, runtime=runtime)

    async def _run(self, *, user_text: str, qa: list[dict[str, str]]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是总挂号助手。你的任务是判断信息是否足够进入分诊。\n"
                    "如果信息不足以判断分诊科室，请返回 need_clarify=true 并提出最多1个关键问题。\n"
                    "如果信息足够，请返回 need_clarify=false。\n"
                    "只返回JSON：{\"need_clarify\": true/false, \"question\": \"...\"(可选)}"
                ),
            },
            {
                "role": "user",
                "content": f"用户描述：{user_text}\n\n历史问答：{qa}",
            },
        ]
        data = await llm_chat_json(messages=messages)
        need = bool((data or {}).get("need_clarify", False))
        q = str((data or {}).get("question", "")).strip()
        if need and not q:
            q = "请补充：主要症状、持续时间、部位/诱因，以及是否发热/外伤/怀孕等关键信息。"
        return {"need_clarify": need, "question": q}
