# -*- coding: utf-8 -*-
"""FFmpeg-based editor.

EditorQAAgent in your spec is simplified (no compliance/quality auditing).
So the actual edit step is deterministic:
- concatenate the 10 segment videos in order
- apply tiny audio crossfade (optional) to hide ambience discontinuities
- burn subtitles or output SRT

This module uses ffmpeg CLI, which you need to have installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional
import os

def _run(cmd: List[str]) -> None:
    try:
        ff = os.getenv("FFMPEG_BIN", "").strip()
        if ff:
            cmd[0] = ff  # 用 .env 里指定的 ffmpeg.exe

        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        raise RuntimeError(
            "ffmpeg not found. Set FFMPEG_BIN in .env to the full path of ffmpeg.exe "
            "or ensure ffmpeg is in PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg command failed: {e}") from e


def concat_videos(video_paths: List[Path], out_path: Path) -> None:
    """
    Concatenate videos with ffmpeg concat demuxer.
    Use ABSOLUTE paths in list file to avoid 'outputs\\outputs\\xxx' issues.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # list file lives next to output
    list_file = out_path.parent / "concat_list.txt"

    # Write absolute paths (ffmpeg wants forward slashes or escaped backslashes; forward slashes works on Windows)
    lines = []
    for p in video_paths:
        ap = Path(p).resolve()
        # ffmpeg concat list requires: file '...'
        # Use forward slashes for safety
        lines.append(f"file '{ap.as_posix()}'")

    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ff = os.getenv("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"

    cmd = [
        ff,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),     # absolute/explicit file path
        "-c", "copy",
        str(out_path),
    ]
    _run(cmd)


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def burn_subtitles(video_in: Path, srt_path: Path, video_out: Path, *, font: Optional[str] = None) -> Path:
    """Burn subtitles onto video.

    If you prefer separate subtitles, just ship the .srt file.
    """
    video_out.parent.mkdir(parents=True, exist_ok=True)
    # Optional font override: force_style is ASS only; for SRT we keep simple.
    vf = f"subtitles={srt_path.as_posix()}"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_in),
        "-vf",
        vf,
        "-c:a",
        "copy",
        str(video_out),
    ]
    _run(cmd)
    return video_out
