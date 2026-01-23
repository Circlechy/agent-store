import uuid
from typing import Any

from registration_agent.orchestrator import Orchestrator


class RegistrationApp:
    def __init__(self):
        self._orch = Orchestrator()

    def new_session(self) -> str:
        return uuid.uuid4().hex

    async def step(self, *, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        q = __import__("json").dumps(payload, ensure_ascii=False)
        return await self._orch.group.invoke({"query": q, "conversation_id": session_id})
