from __future__ import annotations

from typing import Any

from openjiuwen.core.multi_agent import AgentGroupConfig, ControllerGroup
from openjiuwen.core.controller.group_controller import BaseGroupController

from registration_agent.agents.doctor_triage_agent import DoctorTriageAgent
from registration_agent.agents.intake_agent import IntakeAgent
from registration_agent.agents.primary_triage_agent import PrimaryTriageAgent
from registration_agent.agents.secondary_triage_agent import SecondaryTriageAgent


class RegistrationGroupController(BaseGroupController):
    async def handle_event(self, event, session) -> Any:
        # This group controller is called by the MCP server wrapper, so we keep the pipeline deterministic.
        user_query = event.get_display_content()
        payload = getattr(event.content, "payload", None) if hasattr(event, "content") else None
        if isinstance(payload, dict) and payload.get("user_query"):
            user_query = payload["user_query"]
        return {"output": user_query}


def build_group() -> ControllerGroup:
    cfg = AgentGroupConfig(group_id="registration_group")
    controller = RegistrationGroupController()
    group = ControllerGroup(config=cfg, group_controller=controller)

    group.add_agent("intake", IntakeAgent())
    group.add_agent("primary_triage", PrimaryTriageAgent())
    group.add_agent("secondary_triage", SecondaryTriageAgent())
    group.add_agent("doctor_triage", DoctorTriageAgent())

    return group


class Orchestrator:
    def __init__(self):
        self.group = build_group()
