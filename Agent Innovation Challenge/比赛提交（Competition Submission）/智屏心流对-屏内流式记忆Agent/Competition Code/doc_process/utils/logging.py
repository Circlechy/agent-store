#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
'''
@Department ：2012/Poisson Lab
@Author     ：yangjianxin
'''

import logging
import sys
import threading
from typing import Optional

_lock = threading.Lock()
_default_handler: Optional[logging.Handler] = None

log_levels = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_default_log_level = logging.INFO


def _get_default_logging_level():
    """Get default logging level"""
    return _default_log_level


def _get_library_name() -> str:
    """Get library name"""
    return __name__.split(".")[0]


def _get_library_root_logger() -> logging.Logger:
    """Get library root logger"""
    return logging.getLogger(_get_library_name())


def _configure_library_root_logger() -> None:
    """Configure library root logger"""
    global _default_handler

    with _lock:
        if _default_handler:
            return
        _default_handler = logging.StreamHandler()
        _default_handler.flush = sys.stderr.flush

        library_root_logger = _get_library_root_logger()
        library_root_logger.addHandler(_default_handler)
        library_root_logger.setLevel(_get_default_logging_level())
        library_root_logger.propagate = False


def _reset_library_root_logger() -> None:
    """Reset library root logger"""
    global _default_handler

    with _lock:
        if not _default_handler:
            return

        library_root_logger = _get_library_root_logger()
        library_root_logger.removeHandler(_default_handler)
        library_root_logger.setLevel(logging.NOTSET)
        _default_handler = None


def get_log_levels_dict():
    """Get log level"""
    return log_levels


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get logger"""
    if name is None or isinstance(name, str) and name.strip() == "":
        name = _get_library_name()

    _configure_library_root_logger()
    logger = logging.getLogger(name)
    enable_explicit_format()
    return logger


def add_handler(handler: logging.Handler) -> None:
    """Add handler"""
    _configure_library_root_logger()

    if handler is None:
        return
    _get_library_root_logger().addHandler(handler)


def remove_handler(handler: logging.Handler) -> None:
    """Remove handler"""
    _configure_library_root_logger()

    if handler is not None and handler in _get_library_root_logger().handlers:
        _get_library_root_logger().removeHandler(handler)


def enable_explicit_format() -> None:
    """Enable explicit format"""
    handlers = _get_library_root_logger().handlers

    for handler in handlers:
        formatter = logging.Formatter("[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s >> %(message)s")
        handler.setFormatter(formatter)


def get_level(name: Optional[str] = None) -> str:
    """
    Args:
        name: name of logger
    Return the current level of logger
    """
    if name is None or isinstance(name, str) and name.strip() == "":
        name = _get_library_name()
    _configure_library_root_logger()
    logger = logging.getLogger(name)
    return logging.getLevelName(logger.getEffectiveLevel())


def _set_level(verbosity: int, name: Optional[str] = None) -> None:
    """
    Args:
        verbosity (`int`): logging level
        name: name of logger
    """
    if name is None or isinstance(name, str) and name.strip() == "":
        name = _get_library_name()

    _configure_library_root_logger()
    logger = logging.getLogger(name)

    logger.setLevel(verbosity)


def set_level_debug(name: Optional[str] = None):
    """Set the verbosity to the `DEBUG` level."""
    return _set_level(logging.DEBUG, name)


def set_level_info(name: Optional[str] = None):
    """Set the verbosity to the `INFO` level."""
    return _set_level(logging.INFO, name)


def set_level_warning(name: Optional[str] = None):
    """Set the verbosity to the `WARNING` level."""
    return _set_level(logging.WARNING, name)


def set_level_error(name: Optional[str] = None):
    """Set the verbosity to the `ERROR` level."""
    return _set_level(logging.ERROR, name)


def warning_advice(self, *args, **kwargs):
    """Warning advice"""
    self.warning(*args, **kwargs)


logging.Logger.warning_advice = warning_advice
