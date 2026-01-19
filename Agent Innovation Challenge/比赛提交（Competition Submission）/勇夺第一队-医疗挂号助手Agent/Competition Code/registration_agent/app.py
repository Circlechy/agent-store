import uuid
from dataclasses import dataclass, field
from typing import Any

from registration_agent.orchestrator import Orchestrator
from registration_agent.agents.clinic_index import build_clinic_index
from registration_agent.utils.io import read_json
from registration_agent.utils.paths import assistant_dir


USER_PROFILE_PATH = assistant_dir() / "user_profile.json"


@dataclass
class ConversationState:
    stage: str = "start"
    user_query: str = ""
    profile_data: dict[str, Any] = field(default_factory=lambda: {"空闲时间": "任意时间"})
    profile_text: str = ""
    qa: list[dict[str, str]] = field(default_factory=list)
    pending_question: str = ""
    asked: set[str] = field(default_factory=set)
    selected_primary: str = ""
    selected_secondaries: list[str] = field(default_factory=list)
    selected_doctor: dict[str, Any] = field(default_factory=dict)
    time_slots: list[str] = field(default_factory=list)
    recommended_doctors: list[dict[str, Any]] = field(default_factory=list)


class RegistrationApp:
    def __init__(self):
        self._orch = Orchestrator()
        self._sessions: dict[str, ConversationState] = {}

    def new_session(self) -> str:
        sid = uuid.uuid4().hex
        self._sessions[sid] = ConversationState()
        return sid

    def get(self, session_id: str) -> ConversationState:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState()
        return self._sessions[session_id]

    def _load_profile(self) -> tuple[str, dict[str, Any]]:
        if not USER_PROFILE_PATH.exists():
            return "", {"空闲时间": "任意时间"}
        data = read_json(USER_PROFILE_PATH)
        lines = [f"{k}：{v}" for k, v in data.items()]
        return "用户档案：\n" + "\n".join(lines), data

    async def step(self, *, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        st = self.get(session_id)
        messages: list[str] = []

        def _with_messages(obj: dict[str, Any]) -> dict[str, Any]:
            if messages:
                obj = dict(obj)
                obj["messages"] = list(messages)
            return obj

        def _pick_doctor_by_rule(doctors: list[dict[str, Any]]) -> dict[str, Any]:
            if not doctors:
                return {}
            for d in doctors:
                if str(d.get("appointment_url", "")).strip():
                    return dict(d)
            for d in doctors:
                if str(d.get("profile_url", "")).strip():
                    return dict(d)
            return dict(doctors[0])

        def _extract_time_slots(doc: dict[str, Any]) -> list[str]:
            raw = str(doc.get("consultation_time", "") or "").strip()
            if not raw:
                return []
            # Common separators in scraped text
            for sep in ["\r", "\n", "；", ";", "|", "，", ",", "、"]:
                raw = raw.replace(sep, "\n")
            parts = [p.strip() for p in raw.split("\n") if p.strip()]
            # de-dup while preserving order
            out: list[str] = []
            for p in parts:
                if p not in out:
                    out.append(p)
            return out[:12]

        def _build_three_doctor_options(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
            # prefer doctors with consultation_time
            with_time: list[dict[str, Any]] = []
            no_time: list[dict[str, Any]] = []
            for d in candidates:
                slots = _extract_time_slots(d)
                if slots:
                    dd = dict(d)
                    dd["time_slots"] = slots
                    with_time.append(dd)
                else:
                    no_time.append(dict(d))

            picked: list[dict[str, Any]] = []
            used_slots: set[str] = set()

            for d in with_time:
                if len(picked) >= 3:
                    break
                slots = list(d.get("time_slots") or [])
                unique_slot = ""
                for s in slots:
                    if s not in used_slots:
                        unique_slot = s
                        break
                if not unique_slot:
                    continue
                d["appointment_time"] = unique_slot
                used_slots.add(unique_slot)
                picked.append(d)

            for d in with_time:
                if len(picked) >= 3:
                    break
                if any(str(x.get("id")) == str(d.get("id")) and str(x.get("hospital_id")) == str(d.get("hospital_id")) for x in picked):
                    continue
                slots = list(d.get("time_slots") or [])
                if slots:
                    d["appointment_time"] = slots[0]
                picked.append(d)

            for d in no_time:
                if len(picked) >= 3:
                    break
                if any(str(x.get("id")) == str(d.get("id")) and str(x.get("hospital_id")) == str(d.get("hospital_id")) for x in picked):
                    continue
                picked.append(d)

            return picked[:3]

        if st.stage == "start":
            st.user_query = str(payload.get("user_query", "")).strip()
            if not st.user_query:
                return {"status": "error", "message": "missing user_query"}
            profile_text, profile_data = self._load_profile()
            st.profile_data = profile_data
            st.profile_text = profile_text

            st.qa = []
            st.asked = set()
            st.selected_primary = ""
            st.selected_secondaries = []
            st.selected_doctor = {}
            st.time_slots = []
            st.recommended_doctors = []

            st.stage = "intake"

        if st.stage == "clarify":
            answer = str(payload.get("answer", "")).strip()
            if not answer:
                return _with_messages({"status": "need_input", "type": "clarify", "question": st.pending_question})
            st.qa.append({"q": st.pending_question, "a": answer})
            st.pending_question = ""
            st.stage = str(payload.get("next_stage", "intake"))

        if st.stage == "choose_time":
            chosen = str(payload.get("selected_time", "")).strip()
            if chosen:
                st.selected_doctor["appointment_time"] = chosen
                st.stage = "done"
            else:
                # still waiting user selection
                return _with_messages({
                    "status": "need_input",
                    "type": "time_select",
                    "doctor": st.selected_doctor,
                    "time_slots": st.time_slots,
                })

        if st.stage == "choose_doctor_time":
            try:
                idx = int(payload.get("selected_index", -1))
            except Exception:
                idx = -1
            if idx < 0 or idx >= len(st.recommended_doctors):
                return _with_messages({
                    "status": "need_input",
                    "type": "doctor_time_select",
                    "options": st.recommended_doctors,
                })
            st.selected_doctor = dict(st.recommended_doctors[idx])
            st.stage = "done"

        if st.stage in {"intake", "primary", "secondary", "doctor"}:
            merged_description = st.user_query
            if st.profile_text:
                merged_description = f"{st.user_query}\n\n{st.profile_text}"

            primary_triage = self._orch.group.agents["primary_triage"]  # type: ignore
            secondary_triage = self._orch.group.agents["secondary_triage"]  # type: ignore
            doctor_triage = self._orch.group.agents["doctor_triage"]  # type: ignore

            idx = build_clinic_index()
            primaries = sorted(idx.keys())
            if not primaries:
                st.stage = "done"
                messages.append("无法找到一级门诊")
                return _with_messages({"status": "done", "final_response": "doctor_data 为空或不存在"})

            if st.stage == "intake":
                # Skip intake questioning entirely to avoid redundant or low-value questions.
                st.stage = "primary"

            if st.stage == "primary":
                r = await primary_triage.run(patient_text=merged_description, qa=st.qa, primaries=primaries)
                if r.get("need_clarify"):
                    if "primary" in st.asked:
                        st.selected_primary = primaries[0] if primaries else ""
                        if st.selected_primary:
                            messages.append(f"已确认一级门诊：{st.selected_primary}")
                        st.stage = "secondary"
                    else:
                        st.asked.add("primary")
                        st.pending_question = f"【确认一级门诊】{str(r.get('question', '')).strip()}"
                        st.stage = "clarify"
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st.pending_question,
                            "next_stage": "primary",
                        })
                else:
                    st.selected_primary = str(r.get("primary", "")).strip() or (primaries[0] if primaries else "")
                    if st.selected_primary:
                        messages.append(f"已确认一级门诊：{st.selected_primary}")
                    st.stage = "secondary"

            if st.stage == "secondary":
                secondaries = sorted((idx.get(st.selected_primary) or {}).keys())
                if not secondaries:
                    st.stage = "done"
                    messages.append("无法找到二级门诊")
                    return _with_messages({"status": "done", "final_response": f"一级门诊 {st.selected_primary} 下没有二级门诊"})

                r = await secondary_triage.run(
                    patient_text=merged_description,
                    qa=st.qa,
                    primary=st.selected_primary,
                    secondaries=secondaries,
                )
                if r.get("need_clarify"):
                    if "secondary" in st.asked:
                        st.selected_secondaries = secondaries[:2]
                        if st.selected_secondaries:
                            messages.append("已确认二级门诊：" + ", ".join(st.selected_secondaries))
                        st.stage = "doctor"
                    else:
                        st.asked.add("secondary")
                        st.pending_question = f"【确认二级门诊】{str(r.get('question', '')).strip()}"
                        st.stage = "clarify"
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st.pending_question,
                            "next_stage": "secondary",
                        })
                else:
                    st.selected_secondaries = list(r.get("secondaries", []) or [])
                    if st.selected_secondaries:
                        messages.append("已确认二级门诊：" + ", ".join(st.selected_secondaries))
                    st.stage = "doctor"

            if st.stage == "doctor":
                pool: list[dict[str, Any]] = []
                for s in st.selected_secondaries:
                    pool.extend((idx.get(st.selected_primary, {}).get(s) or []))

                # de-dup by (hospital_id, doctor_id)
                seen: set[tuple[str, str]] = set()
                uniq: list[dict[str, Any]] = []
                for d in pool:
                    key = (str(d.get("hospital_id", "")), str(d.get("id", "")))
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(d)

                if not uniq:
                    st.stage = "done"
                    return _with_messages({"status": "done", "final_response": "所选二级门诊下没有医生数据"})

                # Recommend top-3 doctors to reduce decision fatigue and increase time availability.
                st.recommended_doctors = _build_three_doctor_options(uniq)
                if len(st.recommended_doctors) >= 2:
                    messages.append("已为你筛选 3 位医生候选，请选择其一")
                    st.stage = "choose_doctor_time"
                    return _with_messages({
                        "status": "need_input",
                        "type": "doctor_time_select",
                        "options": st.recommended_doctors,
                    })

                # fallback to single doctor path (LLM chooses if possible)
                r = await doctor_triage.run(
                    patient_text=merged_description,
                    qa=st.qa,
                    doctors=uniq[:200],
                    available_time=str(st.profile_data.get("空闲时间", "")),
                )
                if r.get("need_clarify"):
                    if "doctor" in st.asked:
                        st.selected_doctor = _pick_doctor_by_rule(uniq)
                        st.stage = "done"
                    else:
                        st.asked.add("doctor")
                        st.pending_question = str(r.get("question", "")).strip()
                        st.pending_question = f"【确认医生/时间偏好】{st.pending_question}"
                        st.stage = "clarify"
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st.pending_question,
                            "next_stage": "doctor",
                        })
                else:
                    st.selected_doctor = r.get("selected_doctor") or {}
                    st.time_slots = _extract_time_slots(st.selected_doctor)
                    if st.time_slots and len(st.time_slots) > 1:
                        st.stage = "choose_time"
                        return _with_messages({
                            "status": "need_input",
                            "type": "time_select",
                            "doctor": st.selected_doctor,
                            "time_slots": st.time_slots,
                        })
                    st.stage = "done"

        if st.stage == "done":
            doc = st.selected_doctor
            final_lines = [""]
            final_lines.append(f"一级门诊: {st.selected_primary or '未提供'}")
            if st.selected_secondaries:
                final_lines.append("二级门诊: " + ", ".join(st.selected_secondaries))
            final_lines.append(f"医院: {doc.get('hospital_name', doc.get('hospital', '未提供'))}")
            final_lines.append(f"医生: {doc.get('name', '未提供')}")
            final_lines.append(
                f"科室: {doc.get('primary_department', st.selected_primary) or '未提供'} / {doc.get('secondary_department', '未提供')}"
            )
            final_lines.append(f"挂号时间: {doc.get('appointment_time', '未提供')}")
            reason = str(doc.get("reason", "")).strip()
            if reason and "信息不足" not in reason:
                final_lines.append(f"推荐理由: {reason}")
            if doc.get("appointment_url"):
                final_lines.append(f"挂号链接: {doc.get('appointment_url')}")
            if doc.get("profile_url"):
                final_lines.append(f"医生主页: {doc.get('profile_url')}")
            final_response = "\n".join(final_lines).strip()
            return _with_messages({"status": "done", "final_response": final_response})

        return {"status": "error", "message": f"unknown stage: {st.stage}"}
