#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.

import time
from abc import ABC, abstractmethod
from typing import Any, List

from doc_process.context.base_schema import (
    ProcessComponent,
    Context,
)
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class BaseSerial(ProcessComponent, ABC):
    """Interface for Serial."""
    processors: List[ProcessComponent] = Field(
        default_factory=list,
        description="processors",
    )

    def __call__(self, context: Context, **kwargs: Any):
        self._parse_input(context, **kwargs)
        processors_name = [processor.__class__.__name__ for processor in self.processors]
        logger.info("Start serial:{}.".format(processors_name))
        start_time = time.time()
        self._serial(context, **kwargs)
        end_time = time.time()
        context.update_cost_time(self.__class__.__name__, "{:.2f}s".format(end_time - start_time))
        logger.info("Finish serial:{}.".format(processors_name))

    def _serial(self, context: Context, **kwargs: Any) -> None:
        """serial run model."""
        for processor in self.processors:
            processor(context, **kwargs)

    def _parse_input(self, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            CheckUtils.check_type(context, Context, "context")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.EXPORT_PARAM_INVALID, str(ex)) from ex
