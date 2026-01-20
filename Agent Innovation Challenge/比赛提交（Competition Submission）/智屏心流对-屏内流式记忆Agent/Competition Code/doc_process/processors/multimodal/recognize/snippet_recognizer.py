#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for recognizer."""
from typing import Any, Dict, List

from doc_process.context.mm_constants import EmbeddingName
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream
from doc_process.processors.multimodal.recognize.base import BaseRecognize, _merge_frames_detection_results
from doc_process.processors.multimodal.recognize.detector.event_detector import EventDetector
from doc_process.processors.multimodal.recognize.detector.scene_detector import SceneDetector
from doc_process.utils import logging
from doc_process.utils.pydantic import Field
from service.process.multimodal.utils.ug_utils import UgClient

logger = logging.get_logger()


class SnippetRecognizer(BaseRecognize):
    """implement for recognizer."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    food_detector: SceneDetector = Field(
        default=None,
        description="",
    )
    personal_detector: SceneDetector = Field(
        default=None,
        description="",
    )
    proactive_care_detector: EventDetector = Field(
        default=None,
        description="",
    )

    detect_type: str = ""
    ug_client = UgClient()

    def _recognize(self, context: MultimodalContext, **kwargs: Any) -> None:
        """recognizer data."""

        stream: MultimodalStream = kwargs.get("stream")
        frame_queue: List[Any] = stream.get_frame_queue()
        all_frames = frame_queue
        if not frame_queue:
            return

        embeddings: Dict = stream.embeddings
        video_embeddings = embeddings.get(EmbeddingName.VIDEO_EMBEDDINGS)

        # 1.获取物品识别结果
        if self.food_detector:
            object_detection_results = self.food_detector.detect(frame_queue, video_embeddings)
        elif self.personal_detector:
            object_detection_results = self.personal_detector.detect(frame_queue, video_embeddings)
        else:
            raise ValueError(f"未知检测类型: {self.detect_type}")

        # 2.过滤没有结果的帧,len=batch_size
        new_frames = []
        # new_object_detection_results = []
        for index, detection_result in enumerate(object_detection_results):
            if detection_result:
                new_frames.append(frame_queue[index])
                # new_object_detection_results.append(detection_result)
            else:
                new_frames.append(None)

        # 3. 解析DINO结果
        object_detection_split_results = self.parse_object_detection_results(
            new_frames, object_detection_results)



        # # todo:目前仅支持该算子并行！！！
        #
        # # 4. 不支持串并行两种情况，更新context
        #
        # # 5.并行：需要在merge模块更新：new_frames 和 object_detection_results
        #
        # 4.1 更新frames
        # 1)使用new_frames
        if self.food_detector:
            stream.food_detection_filtered_frames = new_frames
        elif self.personal_detector:
            stream.personal_detection_filtered_frames = new_frames
        else:
            raise ValueError(f"未知检测类型: {self.detect_type}")

        # 4.2 更新detections
        stream.set_detection_results_by_key(self.detect_type, object_detection_split_results)

        # 5.主动关怀事件判断
        #1） 使用all_frams

        if self.proactive_care_detector:
            self.proactive_care_detector.detect(all_frames, stream.food_detection_results)


    def parse_object_detection_results(self, frame_queue, object_detection_results):
        # object_detection_results和frame_queue长度一致
        object_detection_split_results = []

        if object_detection_results and frame_queue:
            base64_image_list = [frame_info.frame_base64 if frame_info else None for frame_info in frame_queue]
            for base64, object_detection in zip(base64_image_list, object_detection_results):
                metadata_ = {}
                if base64 and object_detection:
                    # 列表长度始终为1
                    sub_object = object_detection[0]
                    frame_scores = sub_object["scores"].cpu().tolist()
                    frame_boxes = sub_object["boxes"].cpu().tolist()
                    frame_text_labels = sub_object["text_labels"]
                    frame_labels = sub_object["labels"]
                    merged_labels = list(set(sub_object["text_labels"] + sub_object["labels"]))

                    metadata_["scores"] = frame_scores
                    metadata_["boxes"] = frame_boxes
                    metadata_["text_labels"] = frame_text_labels
                    metadata_["labels"] = frame_labels
                    metadata_["merged_labels"] = merged_labels
                    metadata_["base64"] = base64

                object_detection_split_results.append(metadata_)
        return object_detection_split_results
