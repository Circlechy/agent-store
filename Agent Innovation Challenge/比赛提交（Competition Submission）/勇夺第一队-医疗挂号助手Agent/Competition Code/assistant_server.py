import json

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from pydantic import BaseModel

from registration_agent.orchestrator import Orchestrator
from registration_agent.agents.clinic_index import build_clinic_index
from registration_agent.utils.paths import assistant_dir
from registration_agent.utils.io import read_json


mcp = FastMCP(
    "registration-assistant",
    host="127.0.0.1",
    port=8000,
    json_response=False,
    stateless_http=False,
)


USER_PROFILE_PATH = assistant_dir() / "user_profile.json"


class AdditionalInfoResponse(BaseModel):
    result: str

_orchestrator = Orchestrator()


def _load_profile_text() -> tuple[str, dict]:
    if not USER_PROFILE_PATH.exists():
        return "", {"空闲时间": "任意时间"}
    data = read_json(USER_PROFILE_PATH)
    lines = [f"{k}：{v}" for k, v in data.items()]
    return "用户档案：\n" + "\n".join(lines), data


@mcp.tool()
async def process_user_query(user_query: str, ctx: Context[ServerSession, None]) -> str:
    # profile: no privacy/permission layer, use real profile directly
    profile_text, profile_data = _load_profile_text()
    available_time = str(profile_data.get("空闲时间", ""))

    description = user_query
    if profile_text:
        description = f"{user_query}\n\n{profile_text}"

    qa: list[dict[str, str]] = []
    next_stage = "intake"

    intake = _orchestrator.group.agents["intake"]  # type: ignore
    primary_triage = _orchestrator.group.agents["primary_triage"]  # type: ignore
    secondary_triage = _orchestrator.group.agents["secondary_triage"]  # type: ignore
    doctor_triage = _orchestrator.group.agents["doctor_triage"]  # type: ignore

    idx = build_clinic_index()
    primaries = sorted(idx.keys())
    if not primaries:
        return "doctor_data 为空或不存在"

    selected_primary = ""
    selected_secondaries: list[str] = []
    selected_doctor: dict = {}

    # iterate stages with LLM-driven optional clarify
    for _ in range(8):
        if next_stage == "intake":
            r = await intake.run(user_text=description, qa=qa)
            if r.get("need_clarify"):
                payload = json.dumps({"type": "clarify", "question": r.get("question", "")}, ensure_ascii=False)
                res = await ctx.elicit(message=payload, schema=AdditionalInfoResponse)
                ans = ""
                if res.action == "accept" and getattr(res, "data", None) is not None:
                    ans = str(res.data.result or "")
                qa.append({"q": str(r.get("question", "")), "a": ans})
                next_stage = "intake"
                continue
            next_stage = "primary"

        if next_stage == "primary":
            r = await primary_triage.run(patient_text=description, qa=qa, primaries=primaries)
            if r.get("need_clarify"):
                payload = json.dumps({"type": "clarify", "question": r.get("question", "")}, ensure_ascii=False)
                res = await ctx.elicit(message=payload, schema=AdditionalInfoResponse)
                ans = ""
                if res.action == "accept" and getattr(res, "data", None) is not None:
                    ans = str(res.data.result or "")
                qa.append({"q": str(r.get("question", "")), "a": ans})
                next_stage = "primary"
                continue
            selected_primary = str(r.get("primary", "")).strip()
            next_stage = "secondary"

        if next_stage == "secondary":
            secondaries = sorted((idx.get(selected_primary) or {}).keys())
            if not secondaries:
                return f"一级门诊 {selected_primary} 下没有二级门诊"
            r = await secondary_triage.run(
                patient_text=description,
                qa=qa,
                primary=selected_primary,
                secondaries=secondaries,
            )
            if r.get("need_clarify"):
                payload = json.dumps({"type": "clarify", "question": r.get("question", "")}, ensure_ascii=False)
                res = await ctx.elicit(message=payload, schema=AdditionalInfoResponse)
                ans = ""
                if res.action == "accept" and getattr(res, "data", None) is not None:
                    ans = str(res.data.result or "")
                qa.append({"q": str(r.get("question", "")), "a": ans})
                next_stage = "secondary"
                continue
            selected_secondaries = list(r.get("secondaries", []) or [])
            next_stage = "doctor"

        if next_stage == "doctor":
            pool: list[dict] = []
            for s in selected_secondaries:
                pool.extend((idx.get(selected_primary, {}).get(s) or []))

            seen: set[tuple[str, str]] = set()
            uniq: list[dict] = []
            for d in pool:
                key = (str(d.get("hospital_id", "")), str(d.get("id", "")))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(d)
            if not uniq:
                return "所选二级门诊下没有医生数据"

            r = await doctor_triage.run(patient_text=description, qa=qa, doctors=uniq[:200], available_time=available_time)
            if r.get("need_clarify"):
                payload = json.dumps({"type": "clarify", "question": r.get("question", "")}, ensure_ascii=False)
                res = await ctx.elicit(message=payload, schema=AdditionalInfoResponse)
                ans = ""
                if res.action == "accept" and getattr(res, "data", None) is not None:
                    ans = str(res.data.result or "")
                qa.append({"q": str(r.get("question", "")), "a": ans})
                next_stage = "doctor"
                continue

            selected_doctor = r.get("selected_doctor") or {}
            break

    doctor = selected_doctor

    lines = [""]
    lines.append(f"医院: {doctor.get('hospital_name', doctor.get('hospital', '未提供'))}")
    lines.append(f"医生: {doctor.get('name', '未提供')}")
    lines.append(
        f"科室: {doctor.get('primary_department', '未提供')} / {doctor.get('secondary_department', '未提供')}"
    )
    lines.append(f"挂号时间: {doctor.get('appointment_time', '未提供')}")
    if doctor.get("reason"):
        lines.append(f"推荐理由: {doctor.get('reason')}")
    if doctor.get("appointment_url"):
        lines.append(f"挂号链接: {doctor.get('appointment_url')}")
    if doctor.get("profile_url"):
        lines.append(f"医生主页: {doctor.get('profile_url')}")
    final_response = "\n".join(lines).strip()

    return final_response


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
