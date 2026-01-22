from __future__ import annotations

import json
from typing import Any

from openjiuwen.core.agent.controller.group_controller import BaseGroupController
from openjiuwen.core.agent.message.message import Message
from openjiuwen.core.agent_group.agent_group import AgentGroupConfig, ControllerGroup

from registration_agent.agents.doctor_triage_agent import DoctorTriageAgent
from registration_agent.agents.intake_agent import IntakeAgent
from registration_agent.agents.primary_triage_agent import PrimaryTriageAgent
from registration_agent.agents.secondary_triage_agent import SecondaryTriageAgent
from registration_agent.agents.clinic_index import build_clinic_index
from registration_agent.utils.io import read_json
from registration_agent.utils.paths import assistant_dir


USER_PROFILE_PATH = assistant_dir() / "user_profile.json"


class RegistrationGroupController(BaseGroupController):
    async def handle_message(self, message, runtime) -> Any:
        messages: list[str] = []

        def _with_messages(obj: dict[str, Any]) -> dict[str, Any]:
            if messages:
                obj = dict(obj)
                obj["messages"] = list(messages)
            return obj

        def _load_profile() -> tuple[str, dict[str, Any]]:
            if not USER_PROFILE_PATH.exists():
                return "", {"空闲时间": "任意时间"}
            data = read_json(USER_PROFILE_PATH)
            lines = [f"{k}：{v}" for k, v in data.items()]
            return "用户档案：\n" + "\n".join(lines), data

        def _extract_time_slots(doc: dict[str, Any]) -> list[str]:
            raw = str(doc.get("consultation_time", "") or "").strip()
            if not raw:
                return []
            for sep in ["\r", "\n", "；", ";", "|", "，", ",", "、"]:
                raw = raw.replace(sep, "\n")
            parts = [p.strip() for p in raw.split("\n") if p.strip()]
            out: list[str] = []
            for p in parts:
                if p not in out:
                    out.append(p)
            return out[:12]

        def _build_three_doctor_options(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

        raw = message.content.get_query()
        try:
            payload = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
        except Exception:
            payload = {"user_query": raw}

        # Load or init state from openjiuwen runtime (per conversation_id)
        st = runtime.get_state("registration_state") or {}
        if not isinstance(st, dict):
            st = {}

        def _init_state(user_query: str):
            profile_text, profile_data = _load_profile()
            st.update({
                "stage": "intake",
                "user_query": user_query,
                "profile_text": profile_text,
                "profile_data": profile_data,
                "qa": [],
                "pending_question": "",
                "asked": [],
                "selected_primary": "",
                "selected_secondaries": [],
                "selected_doctor": {},
                "time_slots": [],
                "recommended_doctors": [],
            })

        stage = str(st.get("stage") or "start")
        user_query_in = str(payload.get("user_query", "") or "").strip()
        if stage == "start":
            if not user_query_in:
                return {"status": "error", "message": "missing user_query"}
            _init_state(user_query_in)
            stage = "intake"

        # Resume from user interaction
        if stage == "clarify":
            answer = str(payload.get("answer", "") or "").strip()
            if not answer:
                return _with_messages({
                    "status": "need_input",
                    "type": "clarify",
                    "question": str(st.get("pending_question", "")),
                    "next_stage": str(st.get("next_stage", "intake")),
                })
            qa = st.get("qa") or []
            if not isinstance(qa, list):
                qa = []
            qa.append({"q": str(st.get("pending_question", "")), "a": answer})
            st["qa"] = qa
            st["pending_question"] = ""
            stage = str(payload.get("next_stage", st.get("next_stage", "intake")))

        if stage == "choose_time":
            chosen = str(payload.get("selected_time", "") or "").strip()
            if not chosen:
                return _with_messages({
                    "status": "need_input",
                    "type": "time_select",
                    "doctor": st.get("selected_doctor") or {},
                    "time_slots": st.get("time_slots") or [],
                })
            doc = st.get("selected_doctor") or {}
            if isinstance(doc, dict):
                doc["appointment_time"] = chosen
            st["selected_doctor"] = doc
            stage = "done"

        if stage == "choose_doctor_time":
            opts = st.get("recommended_doctors") or []
            if not isinstance(opts, list):
                opts = []
            try:
                idx = int(payload.get("selected_index", -1))
            except Exception:
                idx = -1
            if idx < 0 or idx >= len(opts):
                return _with_messages({
                    "status": "need_input",
                    "type": "doctor_time_select",
                    "options": opts,
                })
            st["selected_doctor"] = dict(opts[idx])
            stage = "done"

        # Main pipeline stages
        if stage in {"intake", "primary", "secondary", "doctor"}:
            merged = str(st.get("user_query", ""))
            profile_text = str(st.get("profile_text", "") or "")
            if profile_text:
                merged = f"{merged}\n\n{profile_text}"

            idx = build_clinic_index()
            primaries = sorted(idx.keys())
            if not primaries:
                stage = "done"
                runtime.update_state({"registration_state": {**st, "stage": stage}})
                return _with_messages({"status": "done", "final_response": "doctor_data 为空或不存在"})

            asked = st.get("asked") or []
            if not isinstance(asked, list):
                asked = []

            if stage == "intake":
                req = {
                    "user_text": merged,
                    "qa": st.get("qa") or [],
                }
                m = Message.create_user_message(
                    content=json.dumps(req, ensure_ascii=False),
                    conversation_id=message.context.conversation_id,
                )
                r = await self.send_to_agent(m, "intake", runtime)
                # Generic policy: do not clarify at intake.
                # If agent asks, we still proceed to primary stage.
                stage = "primary"

            if stage == "primary":
                req = {
                    "patient_text": merged,
                    "qa": st.get("qa") or [],
                    "primaries": primaries,
                }
                m = Message.create_user_message(content=json.dumps(req, ensure_ascii=False), conversation_id=message.context.conversation_id)
                r = await self.send_to_agent(m, "primary_triage", runtime)
                primary = str((r or {}).get("primary", "")).strip() if isinstance(r, dict) else ""
                has_valid_primary = bool(primary and primary in set(primaries))
                need_clarify = bool(isinstance(r, dict) and r.get("need_clarify"))

                # Generic policy: only clarify when we truly cannot proceed.
                # If model asks to clarify but still provides a usable primary, accept it and continue.
                if need_clarify and not has_valid_primary:
                    if "primary" not in asked:
                        asked.append("primary")
                        st["asked"] = asked
                        q = str((r or {}).get("question", "")).strip()
                        if not q:
                            q = "为了更准确选择一级门诊，请补充：主要不适部位/系统（例如腹部/胸部/皮肤/泌尿等）。"
                        st["pending_question"] = f"【一级分诊澄清】{q}"
                        st["next_stage"] = "primary"
                        st["stage"] = "clarify"
                        runtime.update_state({"registration_state": st})
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st["pending_question"],
                            "next_stage": "primary",
                        })

                if not has_valid_primary:
                    primary = primaries[0] if primaries else ""
                st["selected_primary"] = primary
                if primary:
                    messages.append(f"已确认一级门诊：{primary}")
                stage = "secondary"

            if stage == "secondary":
                primary = str(st.get("selected_primary", "") or "")
                secondaries = sorted((idx.get(primary) or {}).keys())
                if not secondaries:
                    stage = "done"
                    runtime.update_state({"registration_state": {**st, "stage": stage}})
                    return _with_messages({"status": "done", "final_response": f"一级门诊 {primary} 下没有二级门诊"})

                req = {
                    "patient_text": merged,
                    "qa": st.get("qa") or [],
                    "primary": primary,
                    "secondaries": secondaries,
                }
                m = Message.create_user_message(content=json.dumps(req, ensure_ascii=False), conversation_id=message.context.conversation_id)
                r = await self.send_to_agent(m, "secondary_triage", runtime)
                secs = list((r or {}).get("secondaries", []) or []) if isinstance(r, dict) else []
                # Filter to valid candidates
                secs = [s for s in secs if str(s) in set(secondaries)]
                need_clarify = bool(isinstance(r, dict) and r.get("need_clarify"))

                # Clarify only when model requests and we have no usable selection.
                if need_clarify and not secs:
                    if "secondary" not in asked:
                        asked.append("secondary")
                        st["asked"] = asked
                        q = str((r or {}).get("question", "")).strip()
                        if not q:
                            q = "为了更准确选择二级门诊，请补充：具体部位/性质/伴随症状（如是否发热、呕吐、腹泻等）。"
                        st["pending_question"] = f"【二级分诊澄清】{q}"
                        st["next_stage"] = "secondary"
                        st["stage"] = "clarify"
                        runtime.update_state({"registration_state": st})
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st["pending_question"],
                            "next_stage": "secondary",
                        })

                if not secs:
                    secs = secondaries[:2]
                st["selected_secondaries"] = secs
                if secs:
                    messages.append("已确认二级门诊：" + ", ".join([str(x) for x in secs]))
                stage = "doctor"

            if stage == "doctor":
                primary = str(st.get("selected_primary", "") or "")
                selected_secs = st.get("selected_secondaries") or []
                if not isinstance(selected_secs, list):
                    selected_secs = []

                pool: list[dict[str, Any]] = []
                for s in selected_secs:
                    pool.extend((idx.get(primary, {}).get(str(s)) or []))

                seen: set[tuple[str, str]] = set()
                uniq: list[dict[str, Any]] = []
                for d in pool:
                    key = (str(d.get("hospital_id", "")), str(d.get("id", "")))
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(d)

                if not uniq:
                    stage = "done"
                    runtime.update_state({"registration_state": {**st, "stage": stage}})
                    return _with_messages({"status": "done", "final_response": "所选二级门诊下没有医生数据"})

                st["recommended_doctors"] = _build_three_doctor_options(uniq)
                if len(st["recommended_doctors"]) >= 2:
                    messages.append("已为你筛选 3 位医生候选，请选择其一")
                    st["stage"] = "choose_doctor_time"
                    runtime.update_state({"registration_state": st})
                    return _with_messages({
                        "status": "need_input",
                        "type": "doctor_time_select",
                        "options": st["recommended_doctors"],
                    })

                req = {
                    "patient_text": merged,
                    "qa": st.get("qa") or [],
                    "doctors": uniq[:200],
                    "available_time": str((st.get("profile_data") or {}).get("空闲时间", "")),
                }
                m = Message.create_user_message(content=json.dumps(req, ensure_ascii=False), conversation_id=message.context.conversation_id)
                r = await self.send_to_agent(m, "doctor_triage", runtime)
                chosen = (r or {}).get("selected_doctor") if isinstance(r, dict) else None
                need_clarify = bool(isinstance(r, dict) and r.get("need_clarify"))

                # If model needs clarifying and cannot provide a doctor, ask once.
                if need_clarify and not (isinstance(chosen, dict) and chosen):
                    if "doctor" not in asked:
                        asked.append("doctor")
                        st["asked"] = asked
                        q = str((r or {}).get("question", "")).strip()
                        if not q:
                            q = "为了更准确推荐医生，请补充：期望就诊时间（工作日/周末/上午/下午）或医院偏好。"
                        st["pending_question"] = f"【医生选择澄清】{q}"
                        st["next_stage"] = "doctor"
                        st["stage"] = "clarify"
                        runtime.update_state({"registration_state": st})
                        return _with_messages({
                            "status": "need_input",
                            "type": "clarify",
                            "question": st["pending_question"],
                            "next_stage": "doctor",
                        })

                st["selected_doctor"] = chosen if isinstance(chosen, dict) and chosen else _pick_doctor_by_rule(uniq)
                st["time_slots"] = _extract_time_slots(st["selected_doctor"])
                if st["time_slots"] and len(st["time_slots"]) > 1:
                    st["stage"] = "choose_time"
                    runtime.update_state({"registration_state": st})
                    return _with_messages({
                        "status": "need_input",
                        "type": "time_select",
                        "doctor": st["selected_doctor"],
                        "time_slots": st["time_slots"],
                    })
                stage = "done"

        if stage == "done":
            doc = st.get("selected_doctor") or {}
            primary = str(st.get("selected_primary") or "未提供")
            secs = st.get("selected_secondaries") or []
            if not isinstance(secs, list):
                secs = []
            final_lines = [""]
            final_lines.append(f"一级门诊: {primary}")
            if secs:
                final_lines.append("二级门诊: " + ", ".join([str(x) for x in secs]))
            final_lines.append(f"医院: {doc.get('hospital_name', doc.get('hospital', '未提供'))}")
            final_lines.append(f"医生: {doc.get('name', '未提供')}")
            final_lines.append(
                f"科室: {doc.get('primary_department', primary) or '未提供'} / {doc.get('secondary_department', '未提供')}"
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
            st["stage"] = "done"
            runtime.update_state({"registration_state": st})
            return _with_messages({"status": "done", "final_response": final_response})

        st["stage"] = stage
        runtime.update_state({"registration_state": st})
        return {"status": "error", "message": f"unknown stage: {stage}"}


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
