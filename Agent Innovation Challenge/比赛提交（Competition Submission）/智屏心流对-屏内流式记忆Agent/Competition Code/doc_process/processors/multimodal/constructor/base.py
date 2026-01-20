#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


import time
from abc import ABC, abstractmethod
from typing import Any

from doc_process.utils import logging
from doc_process.context.base_schema import (
    ProcessComponent,
    Context,
)
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class BaseConstructor(ProcessComponent, ABC):
    """Interface for Constructor."""

    def __call__(self, context: Context, **kwargs: Any):
        self._parse_input(context, **kwargs)
        logger.info("Start {}.".format(self.__class__.__name__))
        start_time = time.time()
        self._construct(context, **kwargs)
        end_time = time.time()
        context.update_cost_time(self.__class__.__name__, "{:.2f}s".format(end_time - start_time))
        logger.info("Finish {}.".format(self.__class__.__name__))

    @abstractmethod
    def _construct(self, context: Context, **kwargs: Any) -> None:
        """construct data before export."""
        ...

    def _parse_input(self, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            CheckUtils.check_type(context, Context, "context")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.BM25_PARAM_INVALID, str(ex)) from ex
