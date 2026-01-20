# -*- coding: utf-8 -*-
"""CLI entry.

Example:
  export LLM_API_BASE=... LLM_API_KEY=... LLM_MODEL_PROVIDER=openai LLM_MODEL_NAME=...
  export ARK_SEEDANCE_CREATE_URL=... ARK_SEEDANCE_QUERY_URL_TEMPLATE='...{task_id}...'
  export ARK_API_KEY=...
  python main.py --input '风格:港风悬疑\n内容:一个外卖员发现客户家...'

Dry-run (skip Seedance calls):
  DRY_RUN=true python main.py --input ...
"""

from __future__ import annotations


# Load environment variables from a local .env file so you can run directly in PyCharm.
# - Looks for .env in current working directory and its parents.
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    # python-dotenv is optional; if not installed, fall back to OS env vars.
    pass

import argparse
import asyncio
import json
from datetime import datetime

from openjiuwen.core.runner.runner import Runner

from short_drama.config import load_llm_settings, load_project_settings
from short_drama.agents.factory import (
    create_showrunner_agent,
    create_writer_agent,
    create_shot_agent,
    create_prompt_agent,
    create_editor_agent,
)
from short_drama.group.short_drama_group import ShortDramaGroup


async def run_once(user_input: str) -> dict:
    llm = load_llm_settings()
    _ = load_project_settings()  # validates defaults

    group = ShortDramaGroup()
    group.add_agent("showrunner", create_showrunner_agent(llm))
    group.add_agent("writer", create_writer_agent(llm))
    group.add_agent("shot", create_shot_agent(llm))
    group.add_agent("prompt", create_prompt_agent(llm))
    group.add_agent("editor", create_editor_agent(llm))

    conversation_id = f"shortdrama_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # Runner will pass dict to ControllerGroup.invoke; it auto-wraps into a Message
    result = await Runner.run_agent_group(
        group,
        {
            "query": user_input,
            "conversation_id": conversation_id,
            "user_id": "demo_user",
        },
    )
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        required=False,
        default="风格:动漫搞笑\n内容:我参加了一个九问 agent大赛的比赛，经过我的不断努力，最终获得冠军，结果是梦境",
        help="User brief + style (text or JSON). If omitted, uses the default string in code.",
    )
    ap.add_argument("--json", action="store_true", help="Print full JSON state")
    args = ap.parse_args()

    state = asyncio.run(run_once(args.input))

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print("==== DONE ====")
        print(f"final_video_path: {state.get('final_video_path')}")
        print(f"subtitles_path: {state.get('subtitles_path')}")

if __name__ == "__main__":
    main()
