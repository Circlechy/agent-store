import threading
from contextlib import contextmanager

_lock = threading.Lock()
_is_searching = False


def can_start_search() -> bool:
    """检查是否可以开始新的搜索（单任务限制）"""
    with _lock:
        return not _is_searching


def start_search() -> None:
    """标记搜索已经开始"""
    global _is_searching
    with _lock:
        _is_searching = True


def finish_search() -> None:
    """标记搜索已结束"""
    global _is_searching
    with _lock:
        _is_searching = False

