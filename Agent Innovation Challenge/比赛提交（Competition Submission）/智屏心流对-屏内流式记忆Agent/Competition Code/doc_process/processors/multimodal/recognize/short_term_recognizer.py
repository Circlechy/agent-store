#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for recognizer."""
from datetime import datetime
from typing import Any, Dict, List

from doc_process.context.mm_constants import TextualName, EmbeddingName
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream
from doc_process.processors.multimodal.recognize.base import BaseRecognize
from doc_process.processors.multimodal.recognize.detector.relation_detector import RelationDetector
from doc_process.processors.multimodal.recognize.detector.scene_detector import SceneDetector
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class ShortTermRecognizer(BaseRecognize):
    """implement for recognizer."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    relation_detector: RelationDetector = Field(
        default_factory=RelationDetector,
        description="relation detector",
    )
    scene_detector: SceneDetector = Field(
        default_factory=SceneDetector,
        description="scene detector",
    )
    img_ids = set()
    long_term_buffer:List = []

    def _recognize(self, context: MultimodalContext, **kwargs: Any) -> None:
        """recognizer data."""

        stream: MultimodalStream = kwargs.get("stream")
        frame_queue: List[Any] = stream.frame_queue
        if not frame_queue:
            return
        embeddings: Dict = stream.embeddings
        video_embeddings = embeddings.get(EmbeddingName.VIDEO_EMBEDDINGS)

        captions = self.scene_detector.detect(frame_queue, video_embeddings)
        caption = captions[0] if captions else ""
        short_term_index = self.build_index_data(frame_queue, caption, stream)
        stream.textuals[TextualName.VIDEO_SHORT_TERM_TEXTUAL] = short_term_index

    def build_index_data(self, frame_queue, caption, stream) -> List[Dict]:
        # todo:@hy
        # build short_term_detector_result to short_term_index_schema
        # todo: 使用图片base64转为int64作为es id。
        index_datas = []
        # food_detection_results = stream.get_food_detection_results()
        # personal_detection_results = stream.get_personal_detection_results()
        # detection_results={"food":food_detection_results,"personal":personal_detection_results}
        # metadata={"object_detection":detection_results}

        # food_detection_result = food_detection_results[index] if food_detection_results else {}
        # personal_detection_result = personal_detection_results[index] if personal_detection_results else {}
        #
        # scene_catogery = []
        # if food_detection_result.get("merged_labels"):
        #     scene_catogery.extend(food_detection_result.get("merged_labels"))
        # if personal_detection_result.get("merged_labels"):
        #     scene_catogery.extend(personal_detection_result.get("merged_labels"))

        # 过滤掉stream_metadata为空的帧，将剩下的帧序列写入caption
        stream_metadata = stream.stream_metadata
        new_frame = []
        new_metadata = {}
        first_frame = None
        for index, (frame, metadata) in enumerate(zip(frame_queue, stream_metadata)):
            if metadata:
                first_frame = frame
                break
        new_metadata = {"base64": first_frame.frame_base64, "all": stream_metadata}
        index_datas.append({
            "id": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scene_id": "",
            "scene_catogery": [],
            "caption": caption,
            "metadata": new_metadata,
            "detail": [
                {
                    "category": "",
                    "ocr": "",
                    "location": "",
                    "caption": "",
                    "metadata": {}
                }
            ]
        })

        return index_datas
