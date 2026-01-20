# -*- coding: utf-8 -*-
"""Multi-agent short drama generator (no workflow).

Controller orchestrates 5 agents:
- showrunner: style bible + 10-beat outline
- writer: per-segment scripts
- shot: per-segment shot plan (continuity)
- prompt: Seedance tasks prompts
- editor: edit plan + subtitles

Then calls Ark Seedance (5-10s per segment) and ffmpeg to assemble final video.

Notes:
- ProducerAgent removed (no budget/scheduling outputs)
- EditorQA simplified (no compliance/quality auditing)
- Seedance can generate video+audio per segment; we still output SRT for platform upload flexibility.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List

import aiohttp
from pydantic import ValidationError

from openjiuwen.core.agent.controller.group_controller import BaseGroupController
from openjiuwen.core.agent.message.message import Message
from openjiuwen.core.common.logging import logger

from examples.short_drama_multiagent.short_drama.config import (
    load_project_settings,
    load_ark_seedance_settings,
    ProjectSettings,
)
from examples.short_drama_multiagent.short_drama.schemas import (
    ProjectState,
    StyleBible,
    Outline10,
    SegmentScriptPack,
    SegmentShotPack,
    GenTaskPack,
    RenderResult,
    EditPlan,
)
from examples.short_drama_multiagent.short_drama.tools.ark_seedance import (
    ArkSeedanceClient,
    build_seedance_payload,
    download_file,
    extract_tail_frame,
    _extract_status,
    _extract_video_url,
    _extract_last_frame_url,
    _is_success,
)
from examples.short_drama_multiagent.short_drama.tools.editor_ffmpeg import concat_videos, write_text


# -----------------------------
# Helpers
# -----------------------------

def _json_dumps(obj: Any) -> str:
    """JSON dumps that tolerates Path/WindowsPath etc."""
    return json.dumps(obj, ensure_ascii=False, default=str)


def _try_parse_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _extract_json_candidates(text: str) -> List[str]:
    """Extract possible JSON strings from an LLM output."""
    text = (text or "").strip()
    if not text:
        return []

    cands: List[str] = [text]

    # ```json { ... } ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        cands.append(m.group(1).strip())

    # first { ... last }
    i = text.find("{")
    j = text.rfind("}")
    if i != -1 and j != -1 and j > i:
        cands.append(text[i:j + 1].strip())

    # unique keep order
    seen = set()
    uniq: List[str] = []
    for c in cands:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq

def _dump_draft_preview(state, settings, out_dir):
    """Save a human/audit-friendly draft snapshot before spending credits."""
    draft = {
        "brief": state.brief,
        "style": state.style,
        "style_bible": state.style_bible.model_dump() if state.style_bible else None,
        "outline": state.outline.model_dump() if state.outline else None,
        "scripts": state.scripts.model_dump() if state.scripts else None,
        "shots": state.shots.model_dump() if state.shots else None,
        "gen_tasks": state.gen_tasks.model_dump() if state.gen_tasks else None,
        "project_settings": {
            "segments": settings.segments,
            "segment_duration_sec": settings.segment_duration_sec,
            "chain_mode": settings.chain_mode,
            "with_audio": settings.with_audio,
            "output_dir": str(out_dir),
        },
    }
    path = out_dir / "draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print_draft_preview(state):
    """Compact console preview."""
    print("\n================ DRAFT PREVIEW ================\n")
    if state.style_bible:
        chars = state.style_bible.characters or []
        print("[Style] ", state.style_bible.style)
        print("[Aspect]", state.style_bible.aspect_ratio)
        print("[Camera]", state.style_bible.camera_language)
        print("[Characters]")
        for c in chars:
            print(f"  - {c.name}: {c.role}; {c.appearance}; {c.outfit}")
        print()

    if state.outline:
        print("[Outline]")
        for b in state.outline.beats:
            print(f"  {b.idx}. ({b.seconds}s) {b.beat} | emotion={b.emotion_goal}")
        print()

    # Per segment preview
    for i in range(1, state.segments + 1):
        seg_script = None
        seg_shot = None
        seg_task = None

        if state.scripts:
            seg_script = next((s for s in state.scripts.segments if s.idx == i), None)
        if state.shots:
            seg_shot = next((s for s in state.shots.segments if s.idx == i), None)
        if state.gen_tasks:
            seg_task = next((t for t in state.gen_tasks.tasks if t.idx == i), None)

        print(f"--- SEG {i:02d} ---")
        if seg_script:
            lines = []
            if seg_script.narration:
                lines.append(f"[旁白] {seg_script.narration}")
            for d in (seg_script.dialogues or []):
                lines.append(f"{d.speaker}: {d.text} ({d.emotion}/{d.pace})")
            print("[Script]")
            print("  " + (" | ".join(lines) if lines else "(no dialogue)"))
            print(f"[Action] {seg_script.action}")
            if seg_script.ambience:
                print(f"[Ambience] {', '.join(seg_script.ambience)}")
            if seg_script.sfx:
                print(f"[SFX] {', '.join(seg_script.sfx)}")

        if seg_shot:
            print("[Shot]")
            print(f"  shot: {seg_shot.shot}")
            print(f"  blocking: {seg_shot.blocking}")
            print(f"  continuity: {seg_shot.continuity_tags}")
            print(f"  use_tail_frame: {seg_shot.use_tail_frame_as_next_first_frame}")

        if seg_task:
            print("[Seedance]")
            print(f"  mode: {seg_task.mode} | seconds: {seg_task.seconds} | with_audio: {seg_task.with_audio}")
            print("  prompt(head 300): " + (seg_task.prompt[:300].replace("\n", " ") + ("..." if len(seg_task.prompt) > 300 else "")))
            if seg_task.negative_prompt:
                print("  negative(head 200): " + (seg_task.negative_prompt[:200].replace("\n", " ") + ("..." if len(seg_task.negative_prompt) > 200 else "")))

        print()
    print("================================================\n")

def _json_soft_fix(s: str) -> str:
    """Lightweight fixes for common JSON issues from LLMs."""
    if s is None:
        return ""
    s = s.lstrip("\ufeff").strip()

    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Remove control chars except \n \r \t
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
    return s.strip()


def _parse_user_query(query: str) -> Tuple[str, str]:
    """Return (brief, style).

    Supported inputs:
    - JSON: {"brief": "...", "style": "..."}
    - Text with markers: "风格:xxx\n内容:yyy" or "style: xxx ..."
    - Plain text: treat as brief, style defaults to "写实".
    """
    query = (query or "").strip()
    if not query:
        return "", "写实"

    as_json = _try_parse_json(query)
    if as_json:
        brief = str(as_json.get("brief") or as_json.get("idea") or "").strip()
        style = str(as_json.get("style") or as_json.get("genre") or "写实").strip()
        return brief or query, style or "写实"

    m_style = re.search(r"(?:风格|类型|style)\s*[:：]\s*(.+)", query, flags=re.IGNORECASE)
    style = m_style.group(1).strip() if m_style else "写实"

    m_brief = re.search(r"(?:内容|剧情|想法|brief|idea)\s*[:：]\s*([\s\S]+)", query, flags=re.IGNORECASE)
    brief = m_brief.group(1).strip() if m_brief else query

    return brief, style


def _extract_agent_output(result: Any) -> str:
    """Best-effort extract textual output from openjiuwen agent result."""
    if isinstance(result, dict):
        for k in ("output", "content", "message", "text"):
            v = result.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # sometimes the dict itself is the payload
        return _json_dumps(result)
    if isinstance(result, str):
        return result.strip()
    return _json_dumps(result)


def _image_to_data_url(path: Path) -> str:
    b = path.read_bytes()
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _extract_names_from_text(text: str, known_names: list[str]) -> set[str]:
    if not text:
        return set()
    found: set[str] = set()
    for name in known_names:
        if name and name in text:
            found.add(name)
    return found


def _parse_on_screen_names(prompt: str, known_names: list[str]) -> set[str]:
    """Parse [ON_SCREEN] block and return a set of character names.

    We keep this intentionally strict: only names that match known_names are returned.
    If the block is missing or nothing matches, returns empty set.
    """
    if not prompt:
        return set()
    tag = "[ON_SCREEN]"
    start = prompt.find(tag)
    if start < 0:
        return set()
    after = prompt[start + len(tag):]
    # stop at next block header like "\n[SCENE]" etc
    m = re.search(r"\n\[[A-Z][A-Z_ /]*\]", after)
    block = after[: m.start()] if m else after
    names: set[str] = set()
    for name in known_names:
        if name and name in block:
            names.add(name)
    return names


# -----------------------------
# Controller
# -----------------------------

class ShortDramaGroupController(BaseGroupController):
    """Orchestrates 5 agents + Seedance render + ffmpeg edit."""

    def __init__(self):
        super().__init__(agent_group=None)

    async def handle_message(self, message: Message, runtime):
        settings: ProjectSettings = load_project_settings()
        out_dir = settings.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        # ===== RESUME MODE: only concat existing segments =====
        resume_edit = os.getenv("RESUME_EDIT", "").strip().lower() in {"1", "true", "yes", "y", "on"}
        if resume_edit:
            segs = []
            for i in range(1, settings.segments + 1):
                p = out_dir / f"seg_{i:02d}.mp4"
                if not p.exists():
                    raise RuntimeError(f"Missing segment file: {p}")
                segs.append(p)

            final_path = out_dir / "final.mp4"
            concat_videos(segs, final_path)

            srt_path = out_dir / "subtitles.srt"
            if not srt_path.exists():
                write_text(srt_path, "")

            return {
                "final_video_path": str(final_path),
                "subtitles_path": str(srt_path),
                "note": "RESUME_EDIT=true: skipped agents and Seedance; concatenated existing segments."
            }

        brief, style = _parse_user_query(message.content.get_query())
        state = ProjectState(
            brief=brief,
            style=style,
            segments=settings.segments,
            segment_duration_sec=settings.segment_duration_sec,
        )

        # 1) Showrunner
        showrunner_in = {
            "brief": state.brief,
            "style": state.style,
            "segments": state.segments,
            "segment_duration_sec": state.segment_duration_sec,
        }
        sr_raw = await self._call_agent_json(
            runtime, message, "showrunner", showrunner_in,
            expect_keys=["style_bible", "outline"],
            max_retries=int(os.getenv("AGENT_JSON_MAX_RETRIES", "4")),
        )
        try:
            state.style_bible = StyleBible.model_validate(sr_raw["style_bible"])
            state.outline = Outline10.model_validate(sr_raw["outline"])
        except ValidationError as e:
            raise RuntimeError(f"Showrunner output schema error: {e}\nraw={sr_raw}")

        # 2) Writer
        writer_in = {
            "style_bible": state.style_bible.model_dump(),
            "outline": state.outline.model_dump(),
        }
        wr_raw = await self._call_agent_json(
            runtime, message, "writer", writer_in,
            expect_keys=["scripts"],
            max_retries=int(os.getenv("AGENT_JSON_MAX_RETRIES", "4")),
        )
        try:
            state.scripts = SegmentScriptPack.model_validate(wr_raw["scripts"])
        except ValidationError as e:
            raise RuntimeError(f"Writer output schema error: {e}\nraw={wr_raw}")

        # 3) Shot
        shot_in = {
            "style_bible": state.style_bible.model_dump(),
            "scripts": state.scripts.model_dump(),
        }
        sh_raw = await self._call_agent_json(
            runtime, message, "shot", shot_in,
            expect_keys=["shots"],
            max_retries=int(os.getenv("AGENT_JSON_MAX_RETRIES", "4")),
        )
        try:
            state.shots = SegmentShotPack.model_validate(sh_raw["shots"])
        except ValidationError as e:
            raise RuntimeError(f"Shot output schema error: {e}\nraw={sh_raw}")

        # 4) Prompt (per-segment to reduce confusion & timeout)
        tasks = []
        for i in range(1, state.segments + 1):
            # 只取当前段的 script + shot
            seg_script = next((s for s in state.scripts.segments if s.idx == i), None)
            seg_shot = next((s for s in state.shots.segments if s.idx == i), None)
            if seg_script is None or seg_shot is None:
                raise RuntimeError(f"Missing script/shot for segment {i}")

            prompt_in_seg = {
                "style_bible": state.style_bible.model_dump(),
                # 这里保持 schema 不变，但只传 1 段
                "scripts": {"segments": [seg_script.model_dump()]},
                "shots": {"segments": [seg_shot.model_dump()]},
                "project_settings": asdict(settings),
                # 可选：告诉 PromptAgent 当前段 idx（便于它写 continuity）
                "current_idx": i,
            }

            pr_raw = await self._call_agent_json(
                runtime, message, "prompt", prompt_in_seg,
                expect_keys=["gen_tasks"],
                max_retries=int(os.getenv("AGENT_JSON_MAX_RETRIES", "4")),
            )

            # 这里期望返回的 gen_tasks.tasks 只有 1 条
            pack = GenTaskPack.model_validate(pr_raw["gen_tasks"])
            if not pack.tasks:
                raise RuntimeError(f"PromptAgent returned empty tasks for seg {i}")

            # 容错：如果它回了多条，只取 idx==i 的，否则取第一条
            t = next((x for x in pack.tasks if x.idx == i), pack.tasks[0])
            t.idx = i
            t.seconds = settings.segment_duration_sec
            tasks.append(t)

        state.gen_tasks = GenTaskPack(tasks=tasks)

        # ===== Draft confirm gate (before spending credits) =====
        require_confirm = os.getenv("REQUIRE_DRAFT_CONFIRM", "").strip().lower() in {"1","true","yes","y","on"}
        if require_confirm:
            draft_path = _dump_draft_preview(state, settings, out_dir)
            _print_draft_preview(state)
            print(f"[DRAFT] saved to: {draft_path}")

            mode = os.getenv("DRAFT_CONFIRM_MODE", "terminal").strip().lower()
            if mode == "auto":
                # Exit early, user reviews draft.json then rerun
                return {
                    "note": "Draft generated (DRAFT_CONFIRM_MODE=auto). Review outputs/draft.json then rerun to render.",
                    "draft_path": str(draft_path),
                }

            # terminal confirm
            ans = input("Proceed to render with Seedance? (y/N): ").strip().lower()
            if ans not in {"y", "yes"}:
                return {
                    "note": "User cancelled after draft preview. No rendering was performed.",
                    "draft_path": str(draft_path),
                }



        # 5) Render via Ark Seedance
        await self._render_all(state, settings)

        # 6) Editor
        editor_in = {
            "style_bible": state.style_bible.model_dump(),
            "scripts": state.scripts.model_dump(),
            "renders": [r.model_dump() for r in state.renders],
            "project_settings": asdict(settings),
        }
        ed_raw = await self._call_agent_json(
            runtime, message, "editor", editor_in,
            expect_keys=["edit_plan"],
            max_retries=int(os.getenv("AGENT_JSON_MAX_RETRIES", "4")),
        )
        try:
            state.edit_plan = EditPlan.model_validate(ed_raw["edit_plan"])
        except ValidationError as e:
            raise RuntimeError(f"Editor output schema error: {e}\nraw={ed_raw}")

        # 7) Apply edit plan (concat + subtitles)
        await self._apply_edit_plan(state, settings)

        return state.model_dump()

    async def _call_agent_json(
            self,
            runtime,
            root_message: Message,
            agent_id: str,
            payload: Dict[str, Any],
            *,
            expect_keys: Optional[List[str]] = None,
            max_retries: int = 4,
    ) -> Dict[str, Any]:
        """Call agent and robustly parse JSON output.

        IMPORTANT: use agent.invoke() (non-stream) to avoid empty output caused by streaming aggregation.
        """
        expect_keys = expect_keys or []
        conv_id = root_message.context.conversation_id or "default"
        user_id = root_message.source.user_id

        agent = self.agent_group.agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent not found: {agent_id}")

        last_text = ""
        last_err: Optional[Exception] = None

        def _extract_text(res: Any) -> str:
            # openjiuwen agent.invoke usually returns dict with "output"
            if isinstance(res, dict):
                # some impls may nest
                for k in ("output", "content", "text", "message"):
                    v = res.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                # if nothing, but dict itself might be the JSON
                return json.dumps(res, ensure_ascii=False, default=str)
            if isinstance(res, str):
                return res.strip()
            return json.dumps(res, ensure_ascii=False, default=str)

        for attempt in range(1, max_retries + 1):
            if attempt == 1:
                query_str = json.dumps(payload, ensure_ascii=False, default=str)
            else:
                repair = {
                    "instruction": (
                        "你必须只输出一个合法 JSON 对象（以 { 开头，以 } 结尾）。"
                        "不要解释，不要 Markdown，不要 ``` 代码块，不要多余文字。"
                        "所有字符串用双引号，不要尾逗号，不要 NaN/Infinity。"
                    ),
                    "expected_keys": expect_keys,
                    "previous_output": last_text,
                    "original_input": payload,
                }
                query_str = json.dumps(repair, ensure_ascii=False, default=str)

            # ✅ non-stream invoke
            res = await agent.invoke(
                {"query": query_str, "conversation_id": conv_id, "user_id": user_id},
                runtime
            )
            text = _extract_text(res)
            last_text = text

            # if truly empty, retry
            if not text or text.strip() == "{}":
                continue

            # parse candidates
            for cand in _extract_json_candidates(text):
                cand2 = _json_soft_fix(cand)
                try:
                    obj = json.loads(cand2)
                    if not isinstance(obj, dict):
                        continue
                    if all(k in obj for k in expect_keys):
                        return obj
                except Exception as e:
                    last_err = e
                    continue

        raise RuntimeError(
            f"Agent '{agent_id}' failed to produce valid JSON after {max_retries} tries. "
            f"Last error: {last_err}. Last output(head 500): {last_text[:500]}"
        )

    async def _render_all(self, state: ProjectState, settings: ProjectSettings) -> None:
        """Call Seedance to generate each segment (5-10s per segment)."""

        if os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
            logger.info("[Render] DRY_RUN enabled, skipping Seedance API calls.")
            return

        ark_settings = load_ark_seedance_settings()

        # ✅ model 兜底（防止 config 里没读到）
        if not getattr(ark_settings, "model", None):
            ark_settings.model = (os.getenv("ARK_SEEDANCE_MODEL") or "").strip()
        if not ark_settings.model:
            raise RuntimeError("Missing Seedance model: ark_settings.model / ARK_SEEDANCE_MODEL")

        ark_api_key = (os.getenv("ARK_API_KEY") or os.getenv("ARK_ACCESS_TOKEN") or os.getenv("ARK_TOKEN"))
        if not ark_api_key:
            raise RuntimeError("Missing ARK_API_KEY (or ARK_ACCESS_TOKEN / ARK_TOKEN) for Seedance calls")

        out_dir = settings.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # idx -> shot
        shot_by_idx = {s.idx: s for s in (state.shots.segments if state.shots else [])}

        timeout_sec = float(os.getenv("ARK_POLL_TIMEOUT_SEC", "1200"))
        interval_sec = float(os.getenv("ARK_POLL_INTERVAL_SEC", "2.0"))
        chain_mode = settings.chain_mode

        async with aiohttp.ClientSession() as session:
            client = ArkSeedanceClient(ark_settings, ark_api_key, session)

            # ✅ 用 last_frame_url 续帧（不依赖 ffmpeg）
            prev_last_frame_url: Optional[str] = None
            # 兜底：本地抽帧（只有 last_frame_url 不存在才会尝试）
            prev_tail_frame_path: Optional[Path] = None

            tasks_sorted = sorted(state.gen_tasks.tasks, key=lambda t: t.idx)

            _prev_on_screen: set[str] = set()

            for task in tasks_sorted:
                idx = task.idx
                seconds = task.seconds

                shot = shot_by_idx.get(idx)
                prev_shot = shot_by_idx.get(idx - 1) if idx and idx > 1 else None
                # Chain flag belongs to the *previous* segment: prev.use_tail_frame_as_next_first_frame -> current can i2v
                chain_requested = bool(chain_mode and idx > 1 and prev_shot and prev_shot.use_tail_frame_as_next_first_frame)

                # Safety guard: if role set changes (new characters appear) or prev tail is likely single-person close-up,
                # force t2v to avoid identity swap (e.g., 主角 -> 主持人).
                known_names = [c.name for c in (state.style_bible.characters if state.style_bible and state.style_bible.characters else [])]
                cur_on_screen = _parse_on_screen_names(task.prompt, known_names)
                prev_on_screen = _prev_on_screen
                names_in_prev_shot = _extract_names_from_text(prev_shot.shot if prev_shot else "", known_names)
                prev_tail_single_closeup = bool(prev_shot and ('特写' in (prev_shot.shot or '')) and ('同框' not in (prev_shot.shot or '')) and len(names_in_prev_shot) == 1)

                safe_chain = bool(chain_requested)
                if safe_chain:
                    # if we cannot parse on-screen sets, be conservative
                    if not prev_on_screen or not cur_on_screen:
                        safe_chain = False
                    # new characters appear -> unsafe
                    elif not cur_on_screen.issubset(prev_on_screen):
                        safe_chain = False
                    # prev tail likely a single-person close-up but current needs multiple people -> unsafe
                    elif prev_tail_single_closeup and len(cur_on_screen) > 1:
                        safe_chain = False

                # Prefer LLM-decided mode if provided, but never allow unsafe i2v
                mode = task.mode if task.mode in ('t2v', 'i2v') else ('i2v' if safe_chain else 't2v')
                if mode == 'i2v' and not safe_chain:
                    logger.warning(f"[Render] seg {idx}: unsafe chain detected; forcing t2v")
                    mode = 't2v'


                first_frame_data = None
                if mode == "i2v":
                    if prev_last_frame_url:
                        # ✅ 最推荐：直接传 URL 给 image_url
                        first_frame_data = prev_last_frame_url
                    elif prev_tail_frame_path and prev_tail_frame_path.exists():
                        # 兜底：内嵌 data URL（不一定被方舟接受，但可尝试）
                        first_frame_data = _image_to_data_url(prev_tail_frame_path)
                    else:
                        logger.warning("Chain requested but no prev tail frame; fallback to t2v")
                        mode = "t2v"

                payload = build_seedance_payload(
                    model=ark_settings.model,  # ✅ 必传
                    prompt=task.prompt,
                    seconds=seconds,
                    with_audio=bool(task.with_audio),
                    negative_prompt=task.negative_prompt or "",
                    mode=mode,
                    first_frame_url_or_b64=first_frame_data,
                    extra=task.extra,
                )

                logger.info(f"[Render] segment {idx} create_task mode={mode}...")
                task_id, _create_resp = await client.create_task(payload)

                done_resp = await client.poll_until_done(
                    task_id,
                    interval_sec=interval_sec,
                    timeout_sec=timeout_sec,
                )

                status = _extract_status(done_resp)
                video_url = _extract_video_url(done_resp)
                last_frame_url = _extract_last_frame_url(done_resp)

                rr = RenderResult(
                    idx=idx,
                    task_id=task_id,
                    status=status,
                    video_url=video_url,
                    raw=done_resp,
                )

                if not _is_success(status):
                    state.renders.append(rr)

                    # cache current on-screen roles for next segment chaining
                    if cur_on_screen:
                        _prev_on_screen = cur_on_screen

                    raise RuntimeError(f"Seedance task failed: idx={idx}, status={status}, raw={done_resp}")

                if not video_url:
                    state.renders.append(rr)

                    # cache current on-screen roles for next segment chaining
                    if cur_on_screen:
                        _prev_on_screen = cur_on_screen

                    raise RuntimeError(f"Seedance success but no video_url: idx={idx}, raw={done_resp}")

                # download video
                local_path = out_dir / f"seg_{idx:02d}.mp4"
                await download_file(session, video_url, local_path)
                rr.local_video_path = str(local_path)

                # ✅ 更新续帧用的 last_frame_url
                if last_frame_url:
                    prev_last_frame_url = last_frame_url
                    # 可选：保存尾帧到本地（调试用）
                    save_tail = os.getenv("SAVE_LAST_FRAME", "").strip().lower() in {"1", "true", "yes", "y", "on"}
                    if save_tail:
                        tail_path = out_dir / f"seg_{idx:02d}_tail.png"
                        try:
                            await download_file(session, last_frame_url, tail_path)
                            rr.tail_frame_path = str(tail_path)
                            prev_tail_frame_path = tail_path
                        except Exception as e:
                            logger.warning(f"Download last_frame_url failed for seg {idx}: {e}")
                            prev_tail_frame_path = None
                    else:
                        prev_tail_frame_path = None
                else:
                    # 没有 last_frame_url：兜底走 ffmpeg 抽帧（需要本机 ffmpeg）
                    prev_last_frame_url = None
                    tail_path = out_dir / f"seg_{idx:02d}_tail.png"
                    try:
                        extract_tail_frame(local_path, tail_path)
                        rr.tail_frame_path = str(tail_path)
                        prev_tail_frame_path = tail_path
                    except Exception as e:
                        logger.warning(f"Tail frame extract failed for seg {idx}: {e}")
                        prev_tail_frame_path = None

                state.renders.append(rr)


                # cache current on-screen roles for next segment chaining

                if cur_on_screen:

                    _prev_on_screen = cur_on_screen

    async def _apply_edit_plan(self, state: ProjectState, settings: ProjectSettings) -> None:
        out_dir = settings.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        if not state.edit_plan:
            raise RuntimeError("No edit_plan")

        # subtitles
        srt_path = out_dir / "subtitles.srt"
        write_text(srt_path, state.edit_plan.subtitles_srt)
        state.subtitles_path = str(srt_path)

        # concat
        path_by_idx = {r.idx: Path(r.local_video_path) for r in state.renders if r.local_video_path}
        ordered_paths = [path_by_idx[i] for i in state.edit_plan.segment_order if i in path_by_idx]
        if len(ordered_paths) != len(state.edit_plan.segment_order):
            missing = [i for i in state.edit_plan.segment_order if i not in path_by_idx]
            raise RuntimeError(f"Missing rendered videos for segments: {missing}")

        final_path = out_dir / "final.mp4"
        concat_videos(ordered_paths, final_path)
        state.final_video_path = str(final_path)


# -----------------------------
# Group wrapper
# -----------------------------

from openjiuwen.core.agent_group.config import AgentGroupConfig
from openjiuwen.core.agent_group.agent_group import ControllerGroup


class ShortDramaGroup(ControllerGroup):
    def __init__(self, group_id: str = "short_drama_group"):
        cfg = AgentGroupConfig(group_id=group_id, max_agents=10)
        super().__init__(config=cfg, group_controller=ShortDramaGroupController())
