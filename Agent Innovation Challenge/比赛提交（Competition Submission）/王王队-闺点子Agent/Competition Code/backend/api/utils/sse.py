import json
from datetime import datetime
from typing import Any


def _format_event(payload: str) -> str:
    return f"data: {payload}\n\n"


def sse_message(payload: Any) -> str:
    """将任意数据序列化为 SSE chunk."""
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        text = json.dumps(str(payload), ensure_ascii=False)
    return _format_event(text)


def sse_done() -> str:
    """完成标记."""
    return _format_event("[DONE]")


def sse_error(error_code: str, message: str) -> str:
    """返回 SSE 错误事件."""
    payload = {
        "type": "error",
        "error": error_code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    return _format_event(json.dumps(payload, ensure_ascii=False))
