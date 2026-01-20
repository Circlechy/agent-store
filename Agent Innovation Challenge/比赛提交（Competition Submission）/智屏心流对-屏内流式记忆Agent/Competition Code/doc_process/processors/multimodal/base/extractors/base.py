#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from abc import ABC, abstractmethod
from typing import Any

from doc_process.utils import logging
from doc_process.context.base_schema import ProcessComponent, Context
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class BaseSummaryExtractor(ProcessComponent, ABC):
    """Extract summary 

    Base generator object for summarization.
    This is an abstract class that defines the interface to the digest generator.
    It receives the Document list objects built by the pipeline's parsing module.
    The specific summary generator subclass needs to inherit this base class and
    implement the specific abstract generation method in the summary function.
    """

    def __call__(self, context: Context, **kwargs: Any) -> None:
        self._parse_input(context, **kwargs)
        self._extract(context, **kwargs)

    @abstractmethod
    def _extract(self, context: Context, **kwargs: Any) -> None:
        """Implement extract fuc"""
        ...

    def _parse_input(self, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            CheckUtils.check_type(context, Context, "context")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.EXTRACTOR_PARAM_INVALID, str(ex)) from ex
