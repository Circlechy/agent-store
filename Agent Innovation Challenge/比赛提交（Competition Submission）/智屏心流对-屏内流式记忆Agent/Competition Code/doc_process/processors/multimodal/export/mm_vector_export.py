#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
from typing import Any, Dict

from doc_process.context.mm_constants import EmbeddingName
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream
from doc_process.processors.multimodal.base.adapter.export_adapter import ExportAdapter
from doc_process.processors.multimodal.base.export.base import BaseExport
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class VectorExport(BaseExport):
    """Export to Index Engine."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    export_adapter: ExportAdapter

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("MultimodalExport init start.")
        logger.info("MultimodalExport init done.")

    def _export(self, context: MultimodalContext, **kwargs: Any) -> None:
        """export data to index engine"""
        stream: MultimodalStream = kwargs.get("stream")
        frame_embeddings = stream.embeddings[EmbeddingName.VIDEO_EMBEDDINGS]
        self.export_adapter.export(frame_embeddings, **kwargs)
