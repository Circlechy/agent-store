"""In-memory chat history store."""

from __future__ import annotations

import time
from threading import RLock
from typing import Any, Dict, List, Optional


class InMemoryChatHistory:
    """Simple in-memory chat history store (lifecycle bound to process)."""

    def __init__(self, max_messages: int = 200):
        self._max_messages = max_messages
        self._lock = RLock()
        self._store: Dict[str, List[Dict[str, Any]]] = {}

    def append(self, user_id: str, message: Dict[str, Any]) -> None:
        if not user_id:
            return
        with self._lock:
            history = self._store.setdefault(user_id, [])
            message.setdefault("timestamp", int(time.time() * 1000))
            history.append(message)
            if self._max_messages and len(history) > self._max_messages:
                self._store[user_id] = history[-self._max_messages :]

    def extend(self, user_id: str, messages: List[Dict[str, Any]]) -> None:
        for message in messages:
            self.append(user_id, message)

    def get(self, user_id: str) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        with self._lock:
            return list(self._store.get(user_id, []))

    def clear(self, user_id: str) -> None:
        if not user_id:
            return
        with self._lock:
            self._store[user_id] = []


chat_history_store = InMemoryChatHistory()
