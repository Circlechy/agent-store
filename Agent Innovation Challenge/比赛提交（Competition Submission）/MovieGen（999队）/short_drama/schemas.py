# -*- coding: utf-8 -*-
"""Structured schemas for blackboard state and agent outputs.

Agents are instructed to output JSON only. We validate and normalize here.

The core idea:
- 60s short drama = 10 segments x 6 seconds (default)
- Each segment has: summary, dialogue, shot plan, generation task, render result
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CharacterCard(BaseModel):
    name: str
    role: str = Field(description="角色身份/关系")
    appearance: str = Field(description="外观要点，尽量短且可复用")
    outfit: str = Field(description="服装要点")
    voice: str = Field(description="声音/口癖/语气")


class StyleBible(BaseModel):
    style: str = Field(description="用户指定风格，比如 写实/二次元/港风/悬疑/搞笑")
    aspect_ratio: str = Field(default="9:16")
    lighting_tone: str = Field(default="cinematic")
    camera_language: str = Field(default="handheld mild, shallow depth of field")
    characters: List[CharacterCard]


class OutlineBeat(BaseModel):
    idx: int
    seconds: int
    beat: str = Field(description="这一段发生了什么（1-2句）")
    emotion_goal: str = Field(description="情绪目标，比如 紧张/甜/尴尬/爆点")


class Outline10(BaseModel):
    beats: List[OutlineBeat]


class DialogueLine(BaseModel):
    speaker: str
    text: str
    emotion: str = "neutral"
    pace: str = Field(default="normal", description="slow/normal/fast")
    pause_ms: int = Field(default=0, description="句后停顿，毫秒")


class SegmentScript(BaseModel):
    idx: int
    seconds: int
    narration: Optional[str] = None
    dialogues: List[DialogueLine] = Field(default_factory=list)
    sfx: List[str] = Field(default_factory=list)
    ambience: List[str] = Field(default_factory=list)
    action: str = Field(description="画面动作/表演指令（简洁）")


class SegmentScriptPack(BaseModel):
    segments: List[SegmentScript]


class SegmentShotPlan(BaseModel):
    idx: int
    seconds: int
    shot: str = Field(description="镜头描述：景别/机位/构图/运镜")
    blocking: str = Field(description="站位与动作连续性")
    continuity_tags: List[str] = Field(default_factory=list)
    use_tail_frame_as_next_first_frame: bool = Field(default=True)


class SegmentShotPack(BaseModel):
    segments: List[SegmentShotPlan]


class GenTask(BaseModel):
    idx: int
    seconds: int
    mode: str = Field(description="t2v or i2v")
    prompt: str
    negative_prompt: Optional[str] = ""
    with_audio: bool = True
    # i2v inputs
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    # provider-specific extras
    extra: Dict[str, Any] = Field(default_factory=dict)


class GenTaskPack(BaseModel):
    tasks: List[GenTask]


class RenderResult(BaseModel):
    idx: int
    task_id: str
    status: str
    video_url: Optional[str] = None
    local_video_path: Optional[str] = None
    tail_frame_path: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class EditPlan(BaseModel):
    # order of segments
    segment_order: List[int]
    # subtitle lines with absolute time
    subtitles_srt: str
    notes: Optional[str] = None


class ProjectState(BaseModel):
    brief: str
    style: str
    segments: int
    segment_duration_sec: int

    style_bible: Optional[StyleBible] = None
    outline: Optional[Outline10] = None
    scripts: Optional[SegmentScriptPack] = None
    shots: Optional[SegmentShotPack] = None
    gen_tasks: Optional[GenTaskPack] = None

    renders: List[RenderResult] = Field(default_factory=list)
    edit_plan: Optional[EditPlan] = None

    final_video_path: Optional[str] = None
    subtitles_path: Optional[str] = None


