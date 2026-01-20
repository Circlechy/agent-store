#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import threading
from enum import Enum, auto
from typing import List, Any, Dict, Optional

from doc_process.context.base_schema import BaseData, Context
from doc_process.context.mm_constants import EmbeddingName, TextualName
from doc_process.utils.pydantic import BaseModel, Field


class MultimodalType(Enum):
    """MultimodalType"""
    IMAGE = auto()
    AUDIO = auto()
    VIDEO = auto()


class ExecuteType(Enum):
    """执行状态枚举"""
    RUNNING = auto()
    ERROR = auto()
    FINISH = auto()


class MultimodalInfo(BaseModel):
    """MultimodalInfo"""
    multimodal_id: str = Field(
        default="",
        description="multimodal_id."
    )
    raw_data: dict = Field(
        default=dict(),
        description="raw_data."
    )

    def get_multimodal_id(self) -> str:
        """get multimodal"""
        return self.multimodal_id

    def set_multimodal_id(self, multimodal_id: str) -> None:
        """set multimodal"""
        self.multimodal_id = multimodal_id

    def get_raw_data(self) -> dict:
        """get data"""
        return self.raw_data

    def set_raw_data(self, raw_data: dict) -> None:
        """set data"""
        self.raw_data = raw_data


class AudioInfo(MultimodalInfo):
    """音频信息类"""
    n_channels: int = Field(
        default=2,
        ge=1,
        description="声道数（>=1）"
    )
    frame_size: int = Field(
        default=0,
        ge=0,
        description="音频帧大小（字节）"
    )
    samp_width: int = Field(
        default=2,
        ge=1,
        description="采样宽度（字节）"
    )
    frame_rate: int = Field(
        default=44100,
        ge=8000,
        description="采样率（Hz）"
    )
    duration: int = Field(
        default=0,
        ge=0,
        description="持续时间（毫秒）"
    )
    multimodal_type: MultimodalType = Field(
        default=MultimodalType.AUDIO,
        description="multimodal_type."
    )

    def get_n_channels(self) -> int:
        """get channels"""
        return self.n_channels

    def set_n_channels(self, n_channels: int) -> None:
        """set channels"""
        self.n_channels = n_channels

    def get_frame_size(self) -> int:
        """get frame"""
        return self.frame_size

    def set_frame_size(self, frame_size: int) -> None:
        """set frame"""
        self.frame_size = frame_size

    def get_samp_width(self) -> int:
        """get width"""
        return self.samp_width

    def set_samp_width(self, samp_width: int) -> None:
        """set width"""
        self.samp_width = samp_width

    def get_frame_rate(self) -> int:
        """get rate"""
        return self.frame_rate

    def set_frame_rate(self, frame_rate: int) -> None:
        """set rate"""
        self.frame_rate = frame_rate

    def get_duration(self) -> int:
        """get duration"""
        return self.duration

    def set_duration(self, duration: int) -> None:
        """set duration"""
        self.duration = duration

    def get_multimodal_type(self) -> MultimodalType:
        """get type"""
        return self.multimodal_type

    def set_multimodal_type(self, multimodal_type: MultimodalType) -> None:
        """set type"""
        self.multimodal_type = multimodal_type


class FrameInfo():
    """FrameInfo"""

    def __init__(self, index=-1, frame_np=None, frame_base64=""):
        self.index = index
        self.frame_np = frame_np
        self.frame_base64 = frame_base64


class VideoInfo(MultimodalInfo):
    """视频信息类"""
    fps: int = Field(
        default=30,
        ge=1,
        description="帧率（帧/秒）"
    )
    duration: int = Field(
        default=0,
        ge=0,
        description="持续时间（毫秒）"
    )
    resolution: List[int] = Field(
        default_factory=lambda: [1920, 1080],
        min_items=2,
        max_items=2,
        description="分辨率[宽,高]"
    )
    multimodal_type: MultimodalType = Field(
        default=MultimodalType.VIDEO,
        description="multimodal_type."
    )

    def get_fps(self) -> int:
        """get fps"""
        return self.fps

    def set_fps(self, fps: int) -> None:
        """set fps"""
        self.fps = fps

    def get_duration(self) -> int:
        """get duration"""
        return self.duration

    def set_duration(self, duration: int) -> None:
        """set duration"""
        self.duration = duration

    def get_resolution(self) -> List[int]:
        """get resolution"""
        return self.resolution

    def set_resolution(self, resolution: List[int]) -> None:
        """set resolution"""
        self.resolution = resolution

    def get_multimodal_type(self) -> MultimodalType:
        """get type"""
        return self.multimodal_type

    def set_multimodal_type(self, multimodal_type: MultimodalType) -> None:
        """set type"""
        self.multimodal_type = multimodal_type


class ImageInfo(MultimodalInfo):
    """图像信息类"""
    size: List[int] = Field(
        default_factory=lambda: [0, 0],
        min_items=2,
        max_items=2,
        description="图像尺寸[宽,高]"
    )
    resolution: List[int] = Field(
        default_factory=lambda: [300, 300],
        min_items=2,
        max_items=2,
        description="分辨率[DPI宽,DPI高]"
    )
    multimodal_type: MultimodalType = Field(
        default=MultimodalType.IMAGE,
        description="multimodal_type."
    )

    def get_size(self) -> List[int]:
        """get size"""
        return self.size

    def set_size(self, size: List[int]) -> None:
        """set size"""
        self.size = size

    def get_resolution(self) -> List[int]:
        """get resolution"""
        return self.resolution

    def set_resolution(self, resolution: List[int]) -> None:
        """set resolution"""
        self.resolution = resolution

    def get_multimodal_type(self) -> MultimodalType:
        """get type"""
        return self.multimodal_type

    def set_multimodal_type(self, multimodal_type: MultimodalType) -> None:
        """set type"""
        self.multimodal_type = multimodal_type


class BatchStrategy(BaseModel):
    """流处理策略配置"""
    video_frames: int = Field(
        default=30,
        gt=0,
        description="视频帧"
    )
    audio_frames: int = Field(
        default=44100,
        gt=0,
        description="音频帧"
    )
    time_out: int = Field(
        default=5,
        gt=0,
        description="超时时间（秒）"
    )

    def get_video_frames(self) -> int:
        """get video"""
        return self.video_frames

    def set_video_frames(self, video_frames: int) -> None:
        """set video"""
        self.video_frames = video_frames

    def get_audio_frames(self) -> int:
        """get audio"""
        return self.audio_frames

    def set_audio_frames(self, audio_frames: int) -> None:
        """set audio"""
        self.audio_frames = audio_frames

    def get_time_out(self) -> int:
        """get timeout"""
        return self.time_out

    def set_time_out(self, time_out: int) -> None:
        """set timeout"""
        self.time_out = time_out


class MultimodalStream(BaseModel):
    """媒体流处理核心载体"""
    stream_index: int = Field(
        default=-1,
        description="stream_index"
    )
    stream_id: str = Field(
        default="",
        description="流唯一标识符"
    )
    frame_queue: List[Any] = Field(
        default_factory=list,
        description="视频帧队列"
    )
    audio_queue: List[Any] = Field(
        default_factory=list,
        description="音频帧队列"
    )
    speech_queue: List[Any] = Field(
        default_factory=list,
        description="语音帧队列"
    )

    embeddings: Dict[EmbeddingName, Any] = Field(
        default_factory=dict,
        description="表征向量，value和frame_queue等长"
    )
    textuals: Dict[TextualName, Any] = Field(
        default_factory=dict,
        description="文本字段，value和frame_queue等长"
    )
    stream_metadata: List[Dict] = Field(
        default_factory=list,
        description="流元数据字典,和frame_queue等长"
    )

    status: ExecuteType = Field(
        default=ExecuteType.RUNNING,
        description="处理状态"
    )

    # 多线程竞争变量,这几个变量和原始frame_queue长度一致
    food_detection_results: List[Dict] = []
    personal_detection_results: List[Dict] = []
    food_detection_filtered_frames: List[Any] = []
    personal_detection_filtered_frames: List[Any] = []

    # 类型注解（仅用于类型检查，实际初始化在__init__中完成）
    _lock: Optional[threading.RLock] = None
    _direct_access_allowed: Optional[bool] = None

    def __init__(self, **kwargs):
        # 首先调用基类初始化，创建所有定义字段
        super().__init__(**kwargs)

        # 然后添加线程安全相关的特殊属性
        # 使用绕过机制设置特殊属性（不触发__setattr__拦截）
        object.__setattr__(self, '_lock', threading.RLock())
        object.__setattr__(self, '_direct_access_allowed', True)

        # 标记完成初始化
        object.__setattr__(self, '_direct_access_allowed', False)

    # Getter and Setter 方法（带线程安全锁）
    def get_stream_index(self) -> int:
        with self._lock:
            return self.stream_index

    def set_stream_index(self, stream_index: int) -> None:
        with self._lock:
            self.stream_index = stream_index

    def get_stream_id(self) -> str:
        with self._lock:
            return self.stream_id

    def set_stream_id(self, stream_id: str) -> None:
        with self._lock:
            self.stream_id = stream_id

    def get_frame_queue(self) -> List[Any]:
        with self._lock:
            return self.frame_queue

    def set_frame_queue(self, frame_queue: List[Any]) -> None:
        with self._lock:
            self.frame_queue = frame_queue

    def get_audio_queue(self) -> List[Any]:
        with self._lock:
            return self.audio_queue

    def set_audio_queue(self, audio_queue: List[Any]) -> None:
        with self._lock:
            self.audio_queue = audio_queue

    def get_speech_queue(self) -> List[Any]:
        with self._lock:
            return self.speech_queue

    def set_speech_queue(self, speech_queue: List[Any]) -> None:
        with self._lock:
            self.speech_queue = speech_queue


    def get_embeddings(self) -> Dict[EmbeddingName, Any]:
        with self._lock:
            return self.embeddings

    def set_embeddings(self, embeddings: Dict[EmbeddingName, Any]) -> None:
        with self._lock:
            self.embeddings = embeddings

    def get_textuals(self) -> Dict[TextualName, Any]:
        with self._lock:
            return self.textuals

    def set_textuals(self, textuals: Dict[TextualName, Any]) -> None:
        with self._lock:
            self.textuals = textuals

    def get_status(self) -> ExecuteType:
        with self._lock:
            return self.status

    def set_status(self, status: ExecuteType) -> None:
        with self._lock:
            self.status = status

    def get_detection_results_by_key(self, detect_type, ) -> List[Any]:
        if detect_type == "food":
            return self.get_food_detection_results()
        elif detect_type == "personal":
            return self.get_personal_detection_results()
        else:
            raise ValueError(f"未知检测类型: {detect_type}")

    def set_detection_results_by_key(self, detect_type, results: List[Any]) -> None:
        if detect_type == "food":
            self.set_food_detection_results(results)
        elif detect_type == "personal":
            self.set_personal_detection_results(results)
        else:
            raise ValueError(f"未知检测类型: {detect_type}")

    def get_food_detection_results(self) -> List[Any]:
        with self._lock:
            return self.food_detection_results

    def set_food_detection_results(self, results: List[Any]) -> None:
        with self._lock:
            self.food_detection_results = results

    def get_personal_detection_results(self) -> List[Any]:
        with self._lock:
            return self.personal_detection_results

    def set_personal_detection_results(self, results: List[Any]) -> None:
        with self._lock:
            self.personal_detection_results = results


class Multimodal(BaseData):
    """Multimodal"""
    multimodal_info: MultimodalInfo = Field(
        default=MultimodalInfo(),
        description="媒体基本信息"
    )
    multimodal_streams: List[MultimodalStream] = Field(
        default_factory=list,
        description="媒体流集合"
    )
    stream_index: Dict[str, int] = Field(
        default_factory=dict,
        description="key:processorName,value:last index of finished stream."
    )
    stream_strategy: BatchStrategy = Field(
        default_factory=BatchStrategy,
        description="流处理策略配置"
    )
    meta_data: dict = Field(
        default_factory=dict,
        description="媒体元数据存储"
    )

    def get_multimodal_info(self) -> MultimodalInfo:
        """get info"""
        return self.multimodal_info

    def set_multimodal_info(self, multimodal_info: MultimodalInfo) -> None:
        """set info"""
        self.multimodal_info = multimodal_info

    def get_multimodal_streams(self) -> List[MultimodalStream]:
        """get streams"""
        return self.multimodal_streams

    def set_multimodal_streams(self, multimodal_streams: List[MultimodalStream]) -> None:
        """set streams"""
        self.multimodal_streams = multimodal_streams

    def get_stream_index(self) -> dict:
        """get stream_index"""
        return self.stream_index

    def get_stream_index_with_key(self, key) -> int:
        """Get stream_index"""
        return self.stream_index.get(key, -1)

    def update_stream_index(self, processor: str, value: int) -> None:
        """update stream_index value"""
        self.stream_index[processor] = value

    def get_stream_strategy(self) -> BatchStrategy:
        """get strategy"""
        return self.stream_strategy

    def set_stream_strategy(self, stream_strategy: BatchStrategy) -> None:
        """set strategy"""
        self.stream_strategy = stream_strategy

    def get_meta_data(self) -> dict:
        """get data"""
        return self.meta_data

    def set_meta_data(self, meta_data: dict) -> None:
        """set data"""
        self.meta_data = meta_data


class MultimodalContext(Context):
    """媒体处理总上下文"""
    multimodal: Multimodal = Field(
        default=Multimodal(),
        description="Multimodal"
    )

    def get_multimodal(self) -> Multimodal:
        """get multimodal"""
        return self.multimodal

    def set_multimodal(self, multimodal: Multimodal) -> None:
        """set multimodal"""
        self.multimodal = multimodal
