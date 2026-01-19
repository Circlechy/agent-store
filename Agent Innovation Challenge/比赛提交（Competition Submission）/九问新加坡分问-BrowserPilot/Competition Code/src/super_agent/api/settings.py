#!/usr/bin/env python
# coding: utf-8

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    cors_allow_origins: list[str] = None

    # OpenRouter / model
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_api_base: str = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    model_name: str = os.getenv("MODEL_NAME", "anthropic/claude-sonnet-4.5")

    # prompts（可选：不想写死在代码里就用 env）
    main_system_prompt: str = os.getenv("MAIN_SYSTEM_PROMPT", "")
    browser_system_prompt: str = os.getenv("BROWSER_SYSTEM_PROMPT", "")
    coder_system_prompt: str = os.getenv("CODER_SYSTEM_PROMPT", "")

    @staticmethod
    def build() -> "Settings":
        allow = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
        cors_allow_origins = ["*"] if allow == "*" else [x.strip() for x in allow.split(",") if x.strip()]
        return Settings(cors_allow_origins=cors_allow_origins)
