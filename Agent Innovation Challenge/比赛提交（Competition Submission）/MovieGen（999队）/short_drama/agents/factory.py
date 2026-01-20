# -*- coding: utf-8 -*-
"""Agent factories.

We use openJiuwen's ChatAgent for predictable single-call structured outputs.
Each agent has a fixed system prompt and uses the incoming `query` as JSON input.
"""

from __future__ import annotations

from openjiuwen.agent.chat_agent import create_chat_agent, create_chat_agent_config
from openjiuwen.agent.config.base import LLMCallConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

from examples.short_drama_multiagent.short_drama.config import LLMSettings
from examples.short_drama_multiagent.short_drama.agents import prompts


def build_model_config(llm: LLMSettings) -> ModelConfig:
    return ModelConfig(
        model_provider=llm.model_provider,
        model_info=BaseModelInfo(
            api_key=llm.api_key,
            api_base=llm.api_base,
            model=llm.model_name,
        ),
    )


def _make_chat_agent(agent_id: str, description: str, system_prompt: str, llm: LLMSettings):
    model_cfg = build_model_config(llm)
    llm_call_cfg = LLMCallConfig(
        model=model_cfg,
        system_prompt=[{"role": "system", "content": system_prompt}],
        user_prompt=[{"role": "user", "content": "{{query}}"}],
        freeze_system_prompt=True,
        freeze_user_prompt=True,
    )
    cfg = create_chat_agent_config(
        agent_id=agent_id,
        agent_version="0.1.0",
        description=description,
        model=llm_call_cfg,
    )
    return create_chat_agent(cfg)


def create_showrunner_agent(llm: LLMSettings):
    return _make_chat_agent(
        agent_id="showrunner",
        description="ShowrunnerAgent: outline + style bible",
        system_prompt=prompts.SHOWRUNNER_SYSTEM,
        llm=llm,
    )


def create_writer_agent(llm: LLMSettings):
    return _make_chat_agent(
        agent_id="writer",
        description="WriterAgent: per-segment scripts",
        system_prompt=prompts.WRITER_SYSTEM,
        llm=llm,
    )


def create_shot_agent(llm: LLMSettings):
    return _make_chat_agent(
        agent_id="shot",
        description="ShotAgent: per-segment shot plan + continuity",
        system_prompt=prompts.SHOT_SYSTEM,
        llm=llm,
    )


def create_prompt_agent(llm: LLMSettings):
    return _make_chat_agent(
        agent_id="prompt",
        description="PromptAgent: Seedance generation tasks",
        system_prompt=prompts.PROMPT_SYSTEM,
        llm=llm,
    )


def create_editor_agent(llm: LLMSettings):
    return _make_chat_agent(
        agent_id="editor",
        description="EditorAgent: edit plan + subtitles",
        system_prompt=prompts.EDITOR_SYSTEM,
        llm=llm,
    )
