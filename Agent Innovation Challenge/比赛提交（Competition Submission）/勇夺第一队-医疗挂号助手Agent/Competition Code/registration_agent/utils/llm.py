import os
from typing import Any

try:
    # pip 版本 openjiuwen
    from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
except Exception:  # pragma: no cover
    # 兼容旧版本路径（如存在）
    from openjiuwen.core.foundation.llm import ModelFactory  # type: ignore


os.environ.setdefault("API_BASE", "https://api.deepseek.com/v1")
os.environ.setdefault("MODEL_PROVIDER", "openai")
os.environ.setdefault("MODEL_NAME", "deepseek-chat")
os.environ.setdefault("API_KEY", "sk-738b635f64264a62a73665a41739022b")
os.environ.setdefault("LLM_SSL_VERIFY", "false")
if os.getenv("LLM_SSL_VERIFY", "").strip().lower() in {"true", "1", "yes"} and not os.getenv("LLM_SSL_CERT"):
    os.environ["LLM_SSL_VERIFY"] = "false"


def _get_model_client():
    provider = os.getenv("MODEL_PROVIDER", "openai")
    api_key = os.getenv("API_KEY", "")
    api_base = os.getenv("API_BASE", "")
    if not api_key or not api_base:
        raise RuntimeError("Missing API_KEY env var")
    return ModelFactory().get_model(model_provider=provider, api_key=api_key, api_base=api_base)


async def llm_chat(*, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> str:
    model_name = os.getenv("MODEL_NAME", "")
    if not model_name:
        raise RuntimeError("Missing MODEL_NAME env var")

    client = _get_model_client()
    ai_msg = await client.ainvoke(model_name=model_name, messages=messages, tools=tools)
    return ai_msg.content or ""


async def llm_chat_json(*, messages: list[dict[str, Any]]) -> Any:
    import json

    content = (await llm_chat(messages=messages)).strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1].strip()
        if content.startswith("json"):
            content = content[4:].strip()
    return json.loads(content)
