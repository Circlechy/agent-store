import json

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from pydantic import BaseModel

from registration_agent.orchestrator import Orchestrator


mcp = FastMCP(
    "registration-assistant",
    host="127.0.0.1",
    port=8000,
    json_response=False,
    stateless_http=False,
)

class AdditionalInfoResponse(BaseModel):
    result: str

_orchestrator = Orchestrator()
@mcp.tool()
async def process_user_query(user_query: str, ctx: Context[ServerSession, None]) -> str:
    # Use openjiuwen ControllerGroup.invoke for the full flow.
    # Keep a stable conversation_id for the whole interactive session.
    conversation_id = getattr(ctx, "session_id", None)
    if conversation_id is None:
        conversation_id = "mcp_session"

    payload: dict = {"user_query": user_query}

    for _ in range(12):
        res = await _orchestrator.group.invoke(
            {
                "query": json.dumps(payload, ensure_ascii=False),
                "conversation_id": str(conversation_id),
            }
        )

        if not isinstance(res, dict):
            return str(res)

        if res.get("status") == "done":
            return str(res.get("final_response", ""))

        if res.get("status") != "need_input":
            return json.dumps(res, ensure_ascii=False)

        t = str(res.get("type", ""))
        if t == "clarify":
            msg = json.dumps({"type": "clarify", "question": res.get("question", "")}, ensure_ascii=False)
            r = await ctx.elicit(message=msg, schema=AdditionalInfoResponse)
            ans = ""
            if r.action == "accept" and getattr(r, "data", None) is not None:
                ans = str(r.data.result or "")
            payload = {"answer": ans, "next_stage": res.get("next_stage", "intake")}
            continue

        if t == "doctor_time_select":
            msg = json.dumps(
                {
                    "type": "doctor_time_select",
                    "question": "请回复医生编号（1-3）：",
                    "options": res.get("options", []),
                },
                ensure_ascii=False,
            )
            r = await ctx.elicit(message=msg, schema=AdditionalInfoResponse)
            pick = ""
            if r.action == "accept" and getattr(r, "data", None) is not None:
                pick = str(r.data.result or "")
            try:
                idx = int(pick.strip()) - 1
            except Exception:
                idx = -1
            payload = {"selected_index": idx}
            continue

        if t == "time_select":
            msg = json.dumps(
                {
                    "type": "time_select",
                    "question": "请回复时间编号：",
                    "doctor": res.get("doctor", {}),
                    "time_slots": res.get("time_slots", []),
                },
                ensure_ascii=False,
            )
            r = await ctx.elicit(message=msg, schema=AdditionalInfoResponse)
            pick = ""
            if r.action == "accept" and getattr(r, "data", None) is not None:
                pick = str(r.data.result or "")
            slots = list(res.get("time_slots") or [])
            try:
                idx = int(pick.strip()) - 1
            except Exception:
                idx = -1
            chosen = slots[idx] if 0 <= idx < len(slots) else ""
            payload = {"selected_time": chosen}
            continue

        return json.dumps(res, ensure_ascii=False)

    return "对话轮次过多，已停止。"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
