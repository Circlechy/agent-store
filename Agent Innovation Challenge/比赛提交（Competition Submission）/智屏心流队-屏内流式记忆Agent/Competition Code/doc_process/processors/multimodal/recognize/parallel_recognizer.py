#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import concurrent
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from doc_process.context.base_schema import (
    Context,
)
from doc_process.context.multimodal_schema import MultimodalStream
from doc_process.processors.multimodal.base.parallel.base import BaseParallel
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class ParallelRecognizer(BaseParallel):
    """Interface for Parallel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _parallel(self, context: Context, **kwargs: Any) -> None:
        """parallel run model."""
        # 使用线程池 主线程和子线程之间可以共享context变量
        # 使用线程池并发执行所有处理器
        with ThreadPoolExecutor() as executor:
            # 提交所有任务到线程池
            futures = [executor.submit(processor, context, **kwargs) for processor in self.processors]

            try:
                # 按完成顺序处理结果和异常
                for future in concurrent.futures.as_completed(futures):
                    future.result()  # 获取任务结果（若无返回值则仅检查异常）
            except Exception as e:
                # 异常处理（例如记录日志或收集错误）
                logger.error(f"Processor failed: {e}")
                logger.error(traceback.format_exc())
            finally:
                # stream: MultimodalStream = kwargs.get("stream")
                # _merge_frames_detection_results(stream, "food", stream.food_detection_filtered_frames,
                #                                 stream.food_detection_filtered_frames)
                # _merge_frames_detection_results(stream, "personal", stream.personal_detection_filtered_frames,
                #                                 stream.personal_detection_filtered_frames)
                self._merge1(context, **kwargs)

    def _merge1(self, context: Context, **kwargs: Any):
        """
        merge frame_queue 只要food或者personal命中，都会留下来。
        """
        stream: MultimodalStream = kwargs.get("stream")
        new_frames = []
        for index, (food_frame, personal_frame) in enumerate(
                zip(stream.food_detection_filtered_frames, stream.personal_detection_filtered_frames)):
            if food_frame and personal_frame:
                new_frames.append(food_frame)
            elif food_frame:
                new_frames.append(food_frame)
            elif personal_frame:
                new_frames.append(personal_frame)
            else:
                pass

        # 全为None
        if not new_frames:
            stream.set_frame_queue(new_frames)
        else:
            pass
        new_metadatas = []
        for index, (food_metadata, personal_metadata) in enumerate(
                zip(stream.food_detection_results, stream.personal_detection_results)):
            metadata = food_metadata if food_metadata else personal_metadata
            new_metadatas.append(metadata)

        # 全为None
        if not new_frames:
            pass
        else:
            stream.stream_metadata = new_metadatas
        logger.info(
            "merged result:len(frames)={}".format(len(new_frames)))

    def _parse_input(self, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            CheckUtils.check_type(context, Context, "context")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.EXPORT_PARAM_INVALID, str(ex)) from ex
