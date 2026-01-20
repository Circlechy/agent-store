"""Global shared context manager based on openjiuwen context engine."""

from __future__ import annotations

from threading import RLock
from typing import Any, Dict, Optional

try:
    from openjiuwen.core.context_engine.base import Context as OpenJiuwenContext
except Exception:  # pragma: no cover - fallback when openjiuwen unavailable
    OpenJiuwenContext = None


class DictBackedContext:
    """Fallback context with openjiuwen-like interface."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

    def update(self, data: Dict[str, Any]) -> None:
        self._data.update(data)

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._data)

    def clear(self) -> None:
        self._data.clear()


class GlobalContextManager:
    """Global shared context storage for all agents."""

    _lock = RLock()
    _context: Optional[Any] = None
    _data: Dict[str, Any] = {}

    @classmethod
    def get_context(cls) -> Any:
        with cls._lock:
            if cls._context is None:
                cls._context = cls._create_context()
                cls._sync_to_context()
            return cls._context

    @classmethod
    def update(cls, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict) or not data:
            return
        with cls._lock:
            cls._data.update(data)
            cls._sync_to_context()

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        with cls._lock:
            cls._data[key] = value
            cls._sync_to_context(keys=[key])

    @classmethod
    def snapshot(cls) -> Dict[str, Any]:
        with cls._lock:
            return dict(cls._data)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._data.clear()
            if hasattr(cls._context, "clear"):
                cls._context.clear()

    @classmethod
    def _create_context(cls) -> Any:
        if OpenJiuwenContext is not None:
            try:
                return OpenJiuwenContext()
            except Exception:
                pass
        return DictBackedContext()

    @classmethod
    def _sync_to_context(cls, keys: Optional[list] = None) -> None:
        if cls._context is None:
            return
        payload = cls._data if keys is None else {key: cls._data.get(key) for key in keys}
        if hasattr(cls._context, "update"):
            cls._context.update(payload)
            return
        if hasattr(cls._context, "set"):
            for key, value in payload.items():
                cls._context.set(key, value)
