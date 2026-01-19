from __future__ import annotations

from typing import Any

from registration_agent.utils.io import read_json
from registration_agent.utils.paths import doctor_data_dir


def build_clinic_index() -> dict[str, dict[str, list[dict[str, Any]]]]:
    root = doctor_data_dir()
    idx: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if not root.exists():
        return idx

    for p in root.rglob("*.json"):
        try:
            rel = p.relative_to(root)
        except Exception:
            continue

        parts = list(rel.parts)
        if len(parts) < 3:
            continue

        primary = str(parts[0])
        secondary = str(parts[1])
        try:
            data = read_json(p)
        except Exception:
            continue

        data.setdefault("primary_department", primary)
        data.setdefault("secondary_department", secondary)
        idx.setdefault(primary, {}).setdefault(secondary, []).append(data)

    return idx


def format_qa(qa: list[dict[str, str]]) -> str:
    if not qa:
        return "无"
    lines: list[str] = []
    for i, item in enumerate(qa, 1):
        q = str(item.get("q", "")).strip()
        a = str(item.get("a", "")).strip()
        if not q and not a:
            continue
        lines.append(f"{i}. Q: {q}\n   A: {a}")
    return "\n".join(lines) if lines else "无"


def format_list(items: list[str]) -> str:
    return "\n".join([f"- {x}" for x in items])


def format_doctors(doctors: list[dict[str, Any]], limit: int = 120) -> str:
    out: list[str] = []
    for i, d in enumerate(doctors[:limit], 1):
        out.append(f"{i}. {d.get('name','')}")
        out.append(f"   医院名称: {d.get('hospital_name','')}")
        out.append(f"   医院ID: {d.get('hospital_id','')}")
        out.append(f"   科室: {d.get('primary_department','')} / {d.get('secondary_department','')}")
        out.append(f"   职称: {d.get('title','')}")
        out.append(f"   咨询时间: {d.get('consultation_time','')}")
        out.append(f"   专长: {d.get('expertise','')}")
        out.append(f"   个人主页: {d.get('profile_url','')}")
        out.append(f"   挂号链接: {d.get('appointment_url','')}")
    return "\n".join(out)
