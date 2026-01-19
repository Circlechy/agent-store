import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin


def _sanitize(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name


@dataclass(frozen=True)
class HospitalTarget:
    key: str
    hospital_id: str
    name: str
    departments_url: str


HOSPITALS: list[HospitalTarget] = [
    HospitalTarget(key="zheyi", hospital_id="597", name="浙一医院", departments_url="https://yyk.fh21.com.cn/hd_597.html"),
    HospitalTarget(key="erbao", hospital_id="608", name="儿保医院", departments_url="https://yyk.fh21.com.cn/hd_608.html"),
    HospitalTarget(key="fubao", hospital_id="615", name="妇保医院", departments_url="https://yyk.fh21.com.cn/hd_615.html"),
    HospitalTarget(key="shisan", hospital_id="617", name="市三医院", departments_url="https://yyk.fh21.com.cn/hd_617.html"),
    HospitalTarget(key="shiyi", hospital_id="601", name="市一医院", departments_url="https://yyk.fh21.com.cn/hd_601.html"),
]


def _ensure_deps():
    try:
        import requests  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing deps. Please install: pip install requests beautifulsoup4"
        ) from e


def _http_get(url: str, *, timeout: int = 20) -> str:
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _parse_departments_primary_secondary(html: str) -> list[tuple[str, str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str, str]] = []

    # Newer FH21 layout: 一级科室在 label.dpi-lab，二级科室链接在 a.dpi-link
    for item in soup.select("div.dp-item"):
        primary = item.select_one("label.dpi-lab")
        if not primary:
            continue
        primary_name = primary.get_text(" ", strip=True)
        if not primary_name:
            continue
        for a in item.select("a.dpi-link[href]"):
            secondary_text = a.get_text(" ", strip=True)
            # "消化内科 （15人）" -> "消化内科"
            secondary_name = re.sub(r"\s*（.*?）\s*", "", secondary_text).strip()
            if not secondary_name:
                continue
            url = urljoin("https://yyk.fh21.com.cn", a.get("href"))
            results.append((primary_name, secondary_name, url))

    # Older layout fallback: no primary/secondary, treat as primary==secondary
    if not results:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/hd_" not in href:
                continue
            if not re.search(r"/hd_\d+/(\d+)\.html", href):
                continue
            text = a.get_text(" ", strip=True)
            if not text:
                continue
            name = re.sub(r"\s*（.*?）\s*", "", text).strip()
            if not name:
                continue
            url = urljoin("https://yyk.fh21.com.cn", href)
            results.append((name, name, url))

    # de-dup
    seen: set[tuple[str, str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for p, s, u in results:
        key = (p, s, u)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _extract_title_from_name_and_title(s: str) -> tuple[str, str]:
    s = s.strip()
    titles = [
        "主任医师",
        "副主任医师",
        "主治医师",
        "住院医师",
        "副主任",
        "主任",
        "医师",
    ]
    for t in titles:
        if s.endswith(t) and len(s) > len(t):
            return s[: -len(t)].strip(), t
    return s, ""


def _slice_doctor_list_html(html: str) -> str:
    # 严格限制在“科室医生列表”附近的内容，避免把侧边栏/问答/科普里的医生抓进来。
    start_markers = ["科室医生列表", "科室医生", "医生列表"]
    end_markers = ["查看全部医生", "推荐医生", "推荐医院", "医院动态", "健康问答", "专家科普", "医生答疑"]

    start = -1
    for m in start_markers:
        idx = html.find(m)
        if idx != -1 and (start == -1 or idx < start):
            start = idx
    if start == -1:
        return html

    end = -1
    for m in end_markers:
        idx = html.find(m, start)
        if idx != -1 and (end == -1 or idx < end):
            end = idx
    if end == -1:
        end = min(len(html), start + 60000)
    return html[start:end]


def _parse_doctors_from_department(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    html = _slice_doctor_list_html(html)
    soup = BeautifulSoup(html, "html.parser")
    doctors: dict[str, dict] = {}

    # In the doctor list section, each doctor normally has a kspb link.
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href or "kspb.html" not in href or "/doctor/" not in href:
            continue
        appointment_url = urljoin("https://www.fh21.com.cn", href)
        m = re.search(r"/doctor/(\d+)/kspb\.html", appointment_url)
        if not m:
            continue
        doctor_id = m.group(1)

        container = a
        for _ in range(8):
            if container is None:
                break
            container = container.parent
            if not container:
                break
            txt = container.get_text("\n", strip=True)
            if txt and "擅长" in txt:
                break

        if not container:
            continue
        text = container.get_text("\n", strip=True)
        # The first non-empty line usually contains "姓名+职称"
        first_line = next((line.strip() for line in text.split("\n") if line.strip()), "")
        name, title = _extract_title_from_name_and_title(first_line)

        expertise = ""
        mexp = re.search(r"擅长[:：]\s*([^\n]{1,200})", text)
        if mexp:
            expertise = mexp.group(1).strip()

        # Try to find profile link within container
        profile_url = f"https://www.fh21.com.cn/doctor/{doctor_id}/"
        for a2 in container.find_all("a", href=True):
            href2 = urljoin("https://www.fh21.com.cn", a2.get("href"))
            if re.search(rf"/doctor/{doctor_id}/?$", href2):
                profile_url = href2
                break

        doctors[doctor_id] = {
            "id": doctor_id,
            "name": name,
            "title": title,
            "profile_url": profile_url,
            "expertise": expertise,
            "appointment_url": appointment_url,
            "consultation_time": "",
        }

    return list(doctors.values())


def _parse_consultation_time_from_kspb(html: str) -> str:
    # Fallback: extract strings like "周四上午" etc.
    matches = re.findall(r"周[一二三四五六日天](?:上午|下午|晚上)?", html)
    if not matches:
        return ""
    # keep unique order
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return "、".join(out[:10])


def _write_doctor(out_dir: Path, doctor: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # include hospital_id to avoid collisions when merging across hospitals
    hospital_id = str(doctor.get("hospital_id", ""))
    suffix = f"_{hospital_id}" if hospital_id else ""
    file_name = f"{doctor['id']}{suffix}_{_sanitize(doctor['name'])}.json"
    path = out_dir / file_name
    with path.open("w", encoding="utf-8") as f:
        json.dump(doctor, f, ensure_ascii=False, indent=2)


def scrape_hospital(target: HospitalTarget, output_root: Path, *, sleep_s: float = 0.4, max_departments: Optional[int] = None):
    _ensure_deps()

    dept_html = _http_get(target.departments_url)
    deps = _parse_departments_primary_secondary(dept_html)
    if max_departments is not None:
        deps = deps[:max_departments]

    for primary_name, secondary_name, dept_url in deps:
        time.sleep(sleep_s)
        dept_page = _http_get(dept_url)
        doctors = _parse_doctors_from_department(dept_page)

        out_dir = output_root / _sanitize(primary_name) / _sanitize(secondary_name)
        for d in doctors:
            d["hospital_id"] = target.hospital_id
            d["hospital_name"] = target.name
            d["primary_department"] = primary_name
            d["secondary_department"] = secondary_name
            d["source_department_url"] = dept_url

            appt = d.get("appointment_url") or ""
            if appt:
                try:
                    time.sleep(sleep_s)
                    kspb_html = _http_get(appt)
                    d["consultation_time"] = _parse_consultation_time_from_kspb(kspb_html)
                except Exception:
                    d["consultation_time"] = d.get("consultation_time", "")

            _write_doctor(out_dir, d)


def scrape_all(output_root: Path, *, sleep_s: float = 0.4, max_departments: Optional[int] = None):
    for h in HOSPITALS:
        scrape_hospital(h, output_root, sleep_s=sleep_s, max_departments=max_departments)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "doctor_data"
    scrape_all(root)
