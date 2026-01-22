#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""CheckUtils"""
import re
from collections.abc import Iterable
from typing import Dict

from doc_process.utils.error_code import ProcessorException, ErrorCode


class CheckUtils:
    """CheckUtils"""

    @classmethod
    def check_dict(cls, input_: Dict, key_type: type, value_type: type, name_="") -> None:
        """Check that every key and value in the dictionary match the specified types."""
        if not isinstance(input_, dict):
            raise ProcessorException(ErrorCode.TYPE_ERROR, f"{name_} Expected a dictionary, but got {type(input_)}.")

        for key, value in input_.items():
            if not isinstance(key, key_type):
                raise ProcessorException(ErrorCode.TYPE_ERROR, f"{name_} Key '{key}' is not of type {key_type}.")
            if not isinstance(value, value_type):
                raise ProcessorException(ErrorCode.TYPE_ERROR,
                                         f"{name_} Value for key '{key}' is not of type {value_type}.")

    @classmethod
    def is_all_type(cls, _iter, _type, name_=""):
        """is all type in iters"""
        if not _iter:
            raise ProcessorException(ErrorCode.TYPE_ERROR, "{} _iter is None or Empty.".format(name_))
        CheckUtils.check_iter(_iter, name_=name_)
        for data in _iter:
            CheckUtils.check_type(data, _type, "iter in {}".format(name_))

    @classmethod
    def check_key(cls, input_, key, name_=""):
        """ check dict key """
        if key not in input_:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "{} Key {} miss.".format(name_, key))

    @classmethod
    def check_iter(cls, input_, length=None, name_=""):
        """ check list """
        if not isinstance(input_, Iterable):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "{} Type is not iterable, is {} type now.".format(name_, type(input_)))
        if length is not None:
            if not len(input_) == length:
                raise ProcessorException(
                    ErrorCode.VALUE_ERROR, "{} Length should be {}, is {} now".format(name_, length, len(input_)))

    @classmethod
    def check_type(cls, input_, type_, name_=""):
        """ check data type """
        if not isinstance(input_, type_):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "{} Type should be {}, is {} now.".format(name_, type_, type(input_)))

    @classmethod
    def check_types(cls, input_, types, name_=""):
        """ check if data type in types """
        for type_ in types:
            if isinstance(input_, type_):
                return
        raise ProcessorException(ErrorCode.TYPE_ERROR,
                                 "{} Type should be in {}, is {} now.".format(name_, types, type(input_)))

    @classmethod
    def check_range(cls, input_, min_open=None, min_close=None, max_open=None, max_close=None):
        """ check number range """
        if min_open is not None and input_ <= min_open:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Wrong value {}, (<= {}).".format(input_, min_open))
        if min_close is not None and input_ < min_close:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Wrong value {}, (< {}).".format(input_, min_close))
        if max_open is not None and input_ >= max_open:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Wrong value {}, (>= {}).".format(input_, max_open))
        if max_close is not None and input_ > max_close:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Wrong value {}, (> {}).".format(input_, max_close))

    @classmethod
    def check_regex(cls, input_, name_=""):
        """ check regular expression """
        if not isinstance(input_, str):
            raise ProcessorException(
                ErrorCode.TYPE_ERROR,
                "{} Pattern config should be str type, is {} now.".format(name_, type(input_)))
        try:
            re.match(input_, "")
        except Exception as e:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "{} Pattern {} invalid.".format(name_, input_)) from e
