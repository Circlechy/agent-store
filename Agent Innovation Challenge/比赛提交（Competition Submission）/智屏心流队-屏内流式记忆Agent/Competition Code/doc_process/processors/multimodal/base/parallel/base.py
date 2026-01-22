#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import concurrent
import time
import traceback
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List
from doc_process.utils.pydantic import Field
from doc_process.context.base_schema import (
    ProcessComponent,
    Context,
)
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class BaseParallel(ProcessComponent, ABC):
    """Interface for Parallel."""
    processors: List[ProcessComponent] = Field(
        default_factory=list,
        description="processors",
    )

    def __call__(self, context: Context, **kwargs: Any):
        self._parse_input(context, **kwargs)
        processors_name = [processor.__class__.__name__ for processor in self.processors]
        logger.info("Start parallel:{}.".format(processors_name))
        start_time = time.time()
        self._parallel(context, **kwargs)
        end_time = time.time()
        context.update_cost_time(self.__class__.__name__, "{:.2f}s".format(end_time - start_time))
        logger.info("Finish parallel:{}.".format(processors_name))

    def _parallel(self, context: Context, **kwargs: Any) -> None:
        """parallel run model."""
        # 使用线程池 主线程和子线程之间可以共享context变量
        # 使用线程池并发执行所有处理器
        with ThreadPoolExecutor() as executor:
            # 提交所有任务到线程池
            futures = [executor.submit(processor, context, **kwargs) for processor in self.processors]

            # 按完成顺序处理结果和异常
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # 获取任务结果（若无返回值则仅检查异常）
                except Exception as e:
                    # 异常处理（例如记录日志或收集错误）
                    logger.error(f"Processor failed: {e}")
                    logger.error(traceback.format_exc())

    def _parse_input(self, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            CheckUtils.check_type(context, Context, "context")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.EXPORT_PARAM_INVALID, str(ex)) from ex
