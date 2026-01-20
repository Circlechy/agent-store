# -*- coding: utf-8 -*-
"""Volcengine Ark (火山方舟) Seedance video generation helpers.

This repo targets Ark "Contents Generation" REST API:
- POST /api/v3/contents/generations/tasks
- GET  /api/v3/contents/generations/tasks/{id}

Seedance 1.5 pro commonly uses a `content` array payload, where the first item
is text (prompt + control flags like `--duration 5`) and the second item can be
an `image_url` for i2v.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

from examples.short_drama_multiagent.short_drama.config import ArkSeedanceSettings


def _extract_task_id(resp_json: Dict[str, Any]) -> Optional[str]:
    """Try several common shapes to find task id."""
    for key in ("task_id", "taskId", "id"):
        v = resp_json.get(key)
        if isinstance(v, str) and v:
            return v
    data = resp_json.get("data")
    if isinstance(data, dict):
        for key in ("task_id", "taskId", "id"):
            v = data.get(key)
            if isinstance(v, str) and v:
                return v
    return None


def _extract_status(resp_json: Dict[str, Any]) -> str:
    for key in ("status", "state"):
        v = resp_json.get(key)
        if isinstance(v, str) and v:
            return v
    data = resp_json.get("data")
    if isinstance(data, dict):
        for key in ("status", "state"):
            v = data.get(key)
            if isinstance(v, str) and v:
                return v
    return "unknown"


def _extract_video_url(resp_json: Dict[str, Any]) -> Optional[str]:
    """Try to find a usable video url from common response shapes."""
    content = resp_json.get("content")
    if isinstance(content, dict):
        v = content.get("video_url")
        if isinstance(v, str) and v.startswith("http"):
            return v

    for key in ("video_url", "videoUrl", "url"):
        v = resp_json.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v

    data = resp_json.get("data")
    if isinstance(data, dict):
        for key in ("video_url", "videoUrl", "url"):
            v = data.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for list_key in ("outputs", "result", "results"):
            lst = data.get(list_key)
            if isinstance(lst, list):
                for it in lst:
                    if isinstance(it, dict):
                        for k in ("url", "video_url", "videoUrl"):
                            u = it.get(k)
                            if isinstance(u, str) and u.startswith("http"):
                                return u
    return None

def _extract_last_frame_url(resp: dict):
    """Try to extract last frame image URL from various response shapes."""
    if not isinstance(resp, dict):
        return None

    # helper to safely walk nested dicts
    def g(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    # Common shapes
    candidates = [
        g(resp, "last_frame_url"),
        g(resp, "content", "last_frame_url"),
        g(resp, "data", "last_frame_url"),
        g(resp, "data", "content", "last_frame_url"),
    ]

    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()

    # Some providers put outputs array under data.outputs
    outputs = g(resp, "data", "outputs")
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, dict):
                lf = item.get("last_frame_url") or item.get("last_frame") or item.get("lastFrameUrl")
                if isinstance(lf, str) and lf.strip():
                    return lf.strip()

    # Some put it under result/outputs
    outputs2 = resp.get("outputs")
    if isinstance(outputs2, list):
        for item in outputs2:
            if isinstance(item, dict):
                lf = item.get("last_frame_url") or item.get("last_frame") or item.get("lastFrameUrl")
                if isinstance(lf, str) and lf.strip():
                    return lf.strip()

    return None

def _extract_last_frame_url(resp_json: Dict[str, Any]) -> Optional[str]:
    """Try to get the provider-returned last frame url (preferred for chaining)."""
    content = resp_json.get("content")
    if isinstance(content, dict):
        v = content.get("last_frame_url") or content.get("lastFrameUrl")
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


def _is_terminal(status: str) -> bool:
    s = status.lower().strip()
    return s in {"succeeded", "success", "completed", "failed", "error", "canceled", "cancelled"}


def _is_success(status: str) -> bool:
    s = status.lower().strip()
    return s in {"succeeded", "success", "completed"}


class ArkSeedanceClient:
    def __init__(self, settings: ArkSeedanceSettings, api_key: str, session: aiohttp.ClientSession):
        self.settings = settings
        self.api_key = api_key
        self.session = session

    async def create_task(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        headers = self.settings.build_headers(self.api_key)
        async with self.session.post(self.settings.create_url, headers=headers, json=payload) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"Ark create_task HTTP {r.status}: {text}")
            try:
                data = json.loads(text)
            except Exception as e:
                raise RuntimeError(f"Ark create_task: response not JSON: {text[:500]}") from e

        task_id = _extract_task_id(data)
        if not task_id:
            raise RuntimeError(f"Ark create_task: cannot find task_id in response: {data}")
        return task_id, data

    async def query_task(self, task_id: str) -> Dict[str, Any]:
        url = self.settings.query_url_template.format(task_id=task_id)
        headers = self.settings.build_headers(self.api_key)
        async with self.session.get(url, headers=headers) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"Ark query_task HTTP {r.status}: {text}")
            try:
                return json.loads(text)
            except Exception as e:
                raise RuntimeError(f"Ark query_task: response not JSON: {text[:500]}") from e

    async def poll_until_done(
        self,
        task_id: str,
        *,
        interval_sec: float = 2.0,
        timeout_sec: float = 600.0,
    ) -> Dict[str, Any]:
        """Poll until status is terminal or timeout."""
        start = asyncio.get_event_loop().time()
        last: Dict[str, Any] | None = None
        while True:
            last = await self.query_task(task_id)
            status = _extract_status(last)
            if _is_terminal(status):
                return last
            if asyncio.get_event_loop().time() - start > timeout_sec:
                raise TimeoutError(f"Ark task timeout ({timeout_sec}s): task_id={task_id}, last={last}")
            await asyncio.sleep(interval_sec)

    async def download_to(self, url: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        async with self.session.get(url) as r:
            if r.status >= 400:
                raise RuntimeError(f"Download HTTP {r.status}: {await r.text()}")
            with out_path.open("wb") as f:
                async for chunk in r.content.iter_chunked(1024 * 1024):
                    f.write(chunk)
        return out_path




async def download_file(session: aiohttp.ClientSession, url: str, out_path: Path) -> Path:
    """Download a remote file to local path.

    Backward-compatible helper for code that imports `download_file`
    (instead of using ArkSeedanceClient.download_to).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with session.get(url) as r:
        if r.status >= 400:
            raise RuntimeError(f"Download HTTP {r.status}: {await r.text()}")
        with out_path.open("wb") as f:
            async for chunk in r.content.iter_chunked(1024 * 1024):
                f.write(chunk)
    return out_path

def extract_tail_frame(video_path: Path, out_image_path: Path) -> Path:
    """Extract the last frame as an image using ffmpeg.

    Requires ffmpeg installed and available in PATH.
    """
    out_image_path.parent.mkdir(parents=True, exist_ok=True)
    # -sseof -0.01 seeks to near end
    cmd = [
        "ffmpeg",
        "-y",
        "-sseof",
        "-0.01",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(out_image_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg and ensure it is in PATH.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg tail-frame extract failed: {e}") from e
    return out_image_path


def build_seedance_payload(
    *,
    model: str,
    prompt: str,
    seconds: int,
    with_audio: bool,
    negative_prompt: str = "",
    mode: str = "t2v",
    first_frame_url_or_b64: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build Ark Contents Generation payload for Seedance.

    Notes:
    - 要获取尾帧，必须在创建任务时设置 return_last_frame=true（默认 false）。
    """

    # --- Build text with common control flags (but don't duplicate if user already set them)
    text = (prompt or "").strip()
    flags: list[str] = []

    if "--duration" not in text.lower():
        flags.append(f"--duration {int(seconds)}")

    import os

    def _maybe_add_flag(flag_name: str, env_key: str):
        nonlocal flags, text
        if flag_name.lower() in text.lower():
            return
        v = os.getenv(env_key)
        if v is None or v == "":
            return
        flags.append(f"{flag_name} {v}")

    _maybe_add_flag("--watermark", "ARK_DEFAULT_WATERMARK")
    _maybe_add_flag("--camerafixed", "ARK_DEFAULT_CAMERAFIXED")
    _maybe_add_flag("--fps", "ARK_DEFAULT_FPS")
    _maybe_add_flag("--ratio", "ARK_DEFAULT_RATIO")
    _maybe_add_flag("--resolution", "ARK_DEFAULT_RESOLUTION")

    # (Optional) negative prompt inclusion (provider doesn't always support a dedicated field)
    include_neg = os.getenv("ARK_INCLUDE_NEGATIVE_IN_TEXT", "").strip().lower() in {"1", "true", "yes", "y", "on"}
    if include_neg and negative_prompt:
        if "negative" not in text.lower() and "避免" not in text:
            text = f"{text}\n避免：{negative_prompt.strip()}"

    if flags:
        text = f"{text} {' '.join(flags)}".strip()

    content_items: list[dict[str, Any]] = [{"type": "text", "text": text}]
    if mode == "i2v" and first_frame_url_or_b64:
        content_items.append({"type": "image_url", "image_url": {"url": first_frame_url_or_b64}})

    payload: Dict[str, Any] = {
        "model": model,
        "content": content_items,
    }

    # 让调用方仍可通过 extra 覆盖/追加字段
    if extra:
        payload.update(extra)

    # ✅ 关键：强制开启返回尾帧（除非 extra 里显式传了 return_last_frame）
    if "return_last_frame" not in payload:
        payload["return_last_frame"] = True

    return payload



def parse_task_result(resp_json: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
    """Return (task_id, status, video_url)."""
    task_id = _extract_task_id(resp_json) or ""
    status = _extract_status(resp_json)
    video_url = _extract_video_url(resp_json)
    return task_id, status, video_url


def is_success(resp_json: Dict[str, Any]) -> bool:
    return _is_success(_extract_status(resp_json))
