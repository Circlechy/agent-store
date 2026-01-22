#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for recognizer."""
from typing import Any, Dict, List

from doc_process.context.mm_constants import TextualName, EmbeddingName
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream
from doc_process.processors.multimodal.recognize.base import BaseRecognize
from doc_process.processors.multimodal.recognize.detector.event_detector import EventDetector
from doc_process.processors.multimodal.recognize.detector.memory_detector import MemoryDetector
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class LongTermRecognizer(BaseRecognize):
    """implement for recognizer."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    memory_detector: MemoryDetector = Field(
        default_factory=MemoryDetector,
        description="memory detector",
    )
    event_judgment_detector: EventDetector = Field(
        default_factory=EventDetector,
        description="event detector",
    )
    event_summary_detector: EventDetector = Field(
        default_factory=EventDetector,
        description="event detector",
    )

    def _recognize(self, context: MultimodalContext, **kwargs: Any) -> None:
        """recognizer data."""
        stream: MultimodalStream = kwargs.get("stream")
        frame_queue: List[Any] = stream.frame_queue
        if not frame_queue:
            return

        self.event_judgment_detector.detect(stream)

        #
        # # 根据DINO labels 关联ug info
        # if object_detection_splitted_results:
        #     ug_cache = context.get_multimodal().ug_cache
        #     ug_info = {}
        #     for frame_clip, object_detection in zip(frame_queue, object_detection_splitted_results):
        #         labels_ = set(object_detection["labels"] + object_detection["text_labels"])
        #         for label in labels_:
        #             if label not in ug_cache:
        #                 ug_cache[label] = self.ug_client.search(label)
        #             search_result = ug_cache[label]
        #             ug_info[label] = search_result
        #         stream.ug_info = ug_info

    def detect_long_term(self, frame_queue, video_embeddings):
        # todo: @hy
        snapshot_result = ""
        return snapshot_result

    def build_index_data(self, long_term_detector_result: str) -> List[Dict]:
        # todo:@hy
        # build long_term_detector_result to long_term_index_schema
        return [{
            "id": "",
            "start_time": "",
            "end_time": "",
            "scene_id": "",
            "scene_catogery": [],
            "location": [],
            "people": [],
            "caption": "",
            "metadata": {}
        }]
