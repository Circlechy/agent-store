from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional



@dataclass
class AgentCardLite:
    name: str
    description: str


class SimpleAgent:
    def __init__(self, card: AgentCardLite):
        self.card = card

    async def invoke(self, inputs: Any, session: Optional[Any] = None) -> Any:
        raise NotImplementedError

    async def stream(self, inputs: Any, session: Optional[Any] = None, stream_modes=None) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, session=session)


def make_card(*, name: str, description: str) -> AgentCardLite:
    return AgentCardLite(name=name, description=description)
