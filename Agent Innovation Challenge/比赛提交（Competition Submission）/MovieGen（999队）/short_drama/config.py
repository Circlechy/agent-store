# -*- coding: utf-8 -*-
"""Project configuration (env-driven).

This repo builds a 60s (10 x 6s) short-drama generator using:
1) A TEXT LLM for planning/prompting (Showrunner/Writer/Shot/Prompt/Editor agents)
2) Volcengine Ark / 火山方舟 Seedance 1.5 pro for video generation

Ark endpoints/auth/fields may vary across regions, accounts and versions.
To avoid baking in the wrong assumptions, Ark API wiring is configurable.

Environment variables
---------------------
LLM for agents:
- LLM_API_BASE
- LLM_API_KEY
- LLM_MODEL_PROVIDER     (ModelFactory provider name, e.g. "openai")
- LLM_MODEL_NAME         (text model name)

Ark Seedance:
- ARK_SEEDANCE_CREATE_URL
- ARK_SEEDANCE_QUERY_URL_TEMPLATE   (must include {task_id})
- ARK_SEEDANCE_MODEL                (e.g. doubao-seedance-1-5-pro-251215)

Ark auth mapping (optional):
- ARK_AUTH_HEADER_NAME             default: Authorization
- ARK_AUTH_HEADER_VALUE_TEMPLATE  default: Bearer {api_key}

Render behavior:
- SEGMENTS                 default: 10
- SEGMENT_DURATION_SEC     default: 6
- CHAIN_MODE               default: true   (tail-frame chaining for continuity)
- WITH_AUDIO               default: true

Files:
- OUTPUT_DIR               default: ./outputs

"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


def _getenv(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _getenv_bool(name: str, default: bool) -> bool:
    v = _getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _getenv_int(name: str, default: int) -> int:
    v = _getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class LLMSettings:
    api_base: str
    api_key: str
    model_provider: str
    model_name: str


@dataclass(frozen=True)
class ArkSeedanceSettings:
    create_url: str
    query_url_template: str
    model: str
    auth_header_name: str = "Authorization"
    auth_header_value_template: str = "Bearer {api_key}"

    def build_headers(self, api_key: str) -> Dict[str, str]:
        return {
            self.auth_header_name: self.auth_header_value_template.format(api_key=api_key),
            "Content-Type": "application/json",
        }


@dataclass(frozen=True)
class ProjectSettings:
    segments: int = 10
    segment_duration_sec: int = 6
    chain_mode: bool = True
    with_audio: bool = True
    output_dir: Path = Path("./outputs")


def load_llm_settings() -> LLMSettings:
    api_base = _getenv("LLM_API_BASE")
    api_key = _getenv("LLM_API_KEY")
    provider = _getenv("LLM_MODEL_PROVIDER")
    model_name = _getenv("LLM_MODEL_NAME")

    missing = [k for k, v in {
        "LLM_API_BASE": api_base,
        "LLM_API_KEY": api_key,
        "LLM_MODEL_PROVIDER": provider,
        "LLM_MODEL_NAME": model_name,
    }.items() if not v]

    if missing:
        raise RuntimeError(
            "Missing LLM env vars for agent planning: " + ", ".join(missing)
        )

    return LLMSettings(
        api_base=str(api_base),
        api_key=str(api_key),
        model_provider=str(provider),
        model_name=str(model_name),
    )


def load_ark_seedance_settings() -> ArkSeedanceSettings:
    create_url = _getenv("ARK_SEEDANCE_CREATE_URL")
    query_tpl = _getenv("ARK_SEEDANCE_QUERY_URL_TEMPLATE")
    model = _getenv("ARK_SEEDANCE_MODEL")
    if not create_url or not query_tpl or not model:
        raise RuntimeError(
            "Missing Ark Seedance env vars: ARK_SEEDANCE_CREATE_URL, "
            "ARK_SEEDANCE_QUERY_URL_TEMPLATE, ARK_SEEDANCE_MODEL"
        )

    header_name = _getenv("ARK_AUTH_HEADER_NAME", "Authorization")
    header_value_tpl = _getenv("ARK_AUTH_HEADER_VALUE_TEMPLATE", "Bearer {api_key}")

    if "{task_id}" not in str(query_tpl):
        raise RuntimeError("ARK_SEEDANCE_QUERY_URL_TEMPLATE must include '{task_id}'")

    return ArkSeedanceSettings(
        create_url=str(create_url),
        query_url_template=str(query_tpl),
        model=str(model),
        auth_header_name=str(header_name),
        auth_header_value_template=str(header_value_tpl),
    )


def load_project_settings() -> ProjectSettings:
    return ProjectSettings(
        segments=_getenv_int("SEGMENTS", 10),
        segment_duration_sec=_getenv_int("SEGMENT_DURATION_SEC", 6),
        chain_mode=_getenv_bool("CHAIN_MODE", True),
        with_audio=_getenv_bool("WITH_AUDIO", True),
        output_dir=Path(_getenv("OUTPUT_DIR", "./outputs")),
    )
