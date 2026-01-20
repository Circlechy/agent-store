#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for embedding models."""
from typing import Any, Dict, Optional, List

from doc_process.context.multimodal_schema import MultimodalStream, MultimodalContext
from doc_process.context.mm_constants import EmbeddingName
from doc_process.processors.multimodal.base.adapter.embedding_adapter import TextEmbeddingAdapter, \
    ImageEmbeddingAdapter, AudioEmbeddingAdapter
from doc_process.processors.multimodal.base.embedding.base import BaseEmbedding
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class MultimodalEmbedding(BaseEmbedding):
    """implement for embedding models."""
    text_embedding_adapter: Optional[TextEmbeddingAdapter]
    image_embedding_adapter: Optional[ImageEmbeddingAdapter]
    audio_embedding_adapter: Optional[AudioEmbeddingAdapter]
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("embedding init start.")
        logger.info("embedding init done.")

    def _embedding(self, context: MultimodalContext, **kwargs: Any) -> None:
        """Extract the fields that need to be embedding"""
        stream: MultimodalStream = kwargs.get("stream")
        frame_queue = stream.get_frame_queue()
        embedding_res: List[Any] = self.image_embedding_adapter.image_embedding(frame_queue, **kwargs)
        stream.embeddings[EmbeddingName.VIDEO_EMBEDDINGS] = embedding_res

