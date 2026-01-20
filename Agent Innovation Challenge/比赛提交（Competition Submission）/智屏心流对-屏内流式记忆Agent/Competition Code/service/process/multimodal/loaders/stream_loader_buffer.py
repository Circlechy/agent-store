#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from typing import Any

import cv2

from doc_process.context.multimodal_schema import FrameInfo
from doc_process.processors.multimodal.base.loaders.base import BaseLoader
from doc_process.utils import logging
from service.process.multimodal.loaders.frame_sampling import ndarray_image_resolution_resize, \
    pixel_differential_keyframe_sampling, optical_flow_keyframe_sampling
from service.process.multimodal.utils.image_utils import img_np2base64, save_base64_as_image

logger = logging.get_logger()

import time
import traceback
from queue import Empty  # 用于捕获队列为空的异常


class StreamLoaderBuffer(BaseLoader):
    """Interface for Loader."""

    def load(self, video_frame_global, frame_queue, llm_frame_queue, data_buffer, video_fps=1.0, play_speed=1.0,
             frame_selection='uniform', **kwargs: Any) -> None:
        """
        主要加载函数，从视频帧队列中读取帧并进行处理。
        """
        logger.info(f"[生产者] 进程启动:StreamLoader")
        logger.info(f'Important: set video_fps = {video_fps}')

        interval = 1.0 / video_fps  # 目标处理间隔时间（秒）
        last_processed_time = time.time()  # 上一次处理的时间点
        count = 0  # 帧计数器


        while True:
            try:
                # 从全局队列中获取帧
                frame = video_frame_global.get()
                timestamp = time.time()

                # 判断是否达到目标处理时间间隔
                if timestamp >= last_processed_time + interval:
                    last_processed_time = timestamp

                    if frame_selection == 'pixelDiff':
                        frame = pixel_differential_keyframe_sampling(frame)
                    elif frame_selection == 'opticalFlow':
                        frame = optical_flow_keyframe_sampling(frame)
                    if frame is None or frame.size == 0:
                        continue

                    # RGB 格式
                    frame_base64 = img_np2base64(frame[0])
                    # 对图片进行降分辨率缩放。
                    frame = ndarray_image_resolution_resize(frame.squeeze())[None, ...]
                    # 构造帧信息对象
                    frame_info = FrameInfo(
                        index=count,
                        frame_np=frame,
                        frame_base64=frame_base64
                    )

                    # 将帧信息放入处理队列和缓冲区
                    frame_queue.put(frame_info)
                    llm_frame_queue.append(frame)
                    data_buffer.append(frame_info)

                    # 每10帧打印一次日志
                    if count % 5 == 0:
                        logger.info(f"stream loader receive {count}")
                        # # ----------delete debug-----------
                        # out_path = rf"./loader_output_{count}.jpg"
                        # save_base64_as_image(frame_base64, out_path)
                        # # ----------delete debug-----------
                    count += 1

            except Empty:
                # 队列为空，跳过当前循环继续等待
                continue
            except Exception as e:
                # 记录错误日志，并抛出异常避免隐藏问题
                logger.error(traceback.format_exc())

        logger.info("stream loader buffer end.")


if __name__ == "__main__":
    stream_loader = StreamLoader()
    frame_queue = Queue()
    stream_loader.load(frame_queue)
