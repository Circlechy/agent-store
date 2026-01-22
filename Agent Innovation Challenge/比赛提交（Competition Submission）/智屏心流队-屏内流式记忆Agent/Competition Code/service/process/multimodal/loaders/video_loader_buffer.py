#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import time
from typing import Any

from decord import VideoReader
from torch.multiprocessing import Queue

from doc_process.context.multimodal_schema import FrameInfo
from doc_process.processors.multimodal.base.loaders.base import BaseLoader
from service.process.multimodal.utils.image_utils import img_np2base64
from doc_process.utils import logging
from service.process.multimodal.loaders.frame_sampling import uniform_sampling, pixel_differential_keyframe_sampling, \
    ndarray_image_resolution_resize, optical_flow_keyframe_sampling

logger = logging.get_logger()


class VideoLoaderBuffer(BaseLoader):
    """Interface for Loader."""

    def load(self, file_path: str, frame_queue: Queue, llm_frame_queue, data_buffer, video_fps=1.0, play_speed=1.0,
             frame_selection='uniform', **kwargs: Any) -> None:
        """Load data"""
        logger.info(f"[生产者] 进程启动, file={file_path}")
        logger.info(f'Important: set video_fps = {video_fps}')
        logger.info(f'Important: set play_speed = {play_speed}')
        # 模拟视频流，将视频帧放入队列。
        vr = VideoReader(file_path)
        t0 = time.perf_counter()
        video = uniform_sampling(vr, video_fps)
        t_uniform = time.perf_counter() - t0
        n_uniform = len(video)
        t1 = time.perf_counter()
        if frame_selection == 'pixelDiff':
            video = pixel_differential_keyframe_sampling(video)
        elif frame_selection == 'opticalFlow':
            video = optical_flow_keyframe_sampling(video)
        t_diff = time.perf_counter() - t1
        n_diff = len(video)
        # 打印两级统计
        logger.info(
            "[LoaderTiming] uniform_sampling: %.3fs (%.3f ms/frame) | "
            "keyframe_sampling: %.3fs (%.3f ms/frame)",
            t_uniform,
            (t_uniform / max(1, n_uniform)) * 1000,
            t_diff,
            (t_diff / max(1, n_diff)) * 1000,
        )
        length = video.shape[0]
        sleep_time = 1 / video_fps / play_speed  # - 计算每帧之间的间隔时间，用于模拟视频的播放速度。
        last_start = 0
        logger.info(f'Simulator Process: start, length = {length}')
        try:
            for start in range(0, length):
                start_time = time.perf_counter()
                end = min(start + 1, length)
                video_clip = video[start:end]
                # 对图片进行降分辨率缩放。
                video_clip = ndarray_image_resolution_resize(video_clip.squeeze())[None, ...]
                frame_info = FrameInfo(index=start, frame_np=video_clip, frame_base64=img_np2base64(video_clip[0]))
                # ndarray
                frame_queue.put(frame_info)
                llm_frame_queue.append(video_clip)
                data_buffer.append(frame_info)
                if start > 0:
                    logger.info(
                        f'Simulator: write {end - start} frames,\t{start} to {end},\treal_sleep={start_time - last_start}')
                if end < length:
                    time.sleep(sleep_time)  # sleep 1s
                last_start = start_time
            frame_queue.put(None)
        except Exception as e:
            logger.error(f'Simulator Exception: {e}')
            time.sleep(0.1)
        logger.info(f'Simulator Process: end')
