#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for recognizer."""
import traceback
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

class LongTermRecognizer(BaseRecognize):
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
        try:
            stream: MultimodalStream = kwargs.get("stream")
            frame_queue: List[Any] = stream.frame_queue
            if not frame_queue:
                logger.warning("LongTermRecognizer: empty frame_queue, skipping.")
                return

            embeddings: Dict = stream.embeddings
            video_embeddings = embeddings.get(EmbeddingName.VIDEO_EMBEDDINGS)

            # 调用 scene_detector.detect，直接返回 index_datas
            index_datas = self.scene_detector.detect(frame_queue, video_embeddings)

            if not index_datas:
                logger.warning("LongTermRecognizer: no index data returned from scene_detector.")
                return

            # 写入 textuals，供后续 ES 或 summary 用
            stream.textuals[TextualName.VIDEO_LONG_TERM_TEXTUAL] = index_datas

        except Exception as e:
            logger.error(f"LongTermRecognizer: exception occurred during recognition - {str(e)}", exc_info=True)
