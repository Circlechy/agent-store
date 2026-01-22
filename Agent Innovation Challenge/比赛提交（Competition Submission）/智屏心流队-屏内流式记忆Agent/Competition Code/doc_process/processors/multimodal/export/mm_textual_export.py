#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
from typing import Any, Dict, Optional

from doc_process.context.mm_constants import TextualName
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream
from doc_process.processors.multimodal.base.adapter.export_adapter import ExportAdapter
from doc_process.processors.multimodal.base.export.base import BaseExport
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


# todo: @hy
class TextualExport(BaseExport):
    """Export to Index Engine."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    snipped_textual_export_adapter: Optional[ExportAdapter]
    short_term_textual_export_adapter: Optional[ExportAdapter]
    long_term_textual_export_adapter: Optional[ExportAdapter]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("TextualExport init start.")
        logger.info("TextualExport init done.")

    def _export(self, context: MultimodalContext, **kwargs: Any) -> None:
        """export data to index engine"""

        # if self.is_need_export_snipped_textual():
        #     self.export_snipped_textual(stream, **kwargs)
        self.export_short_term_textual(**kwargs)
        # todo: 4. @xinjiapo
        # self.export_long_term_textual(**kwargs)
        # if self.is_need_export_long_term_textual():
        #

    def export_snipped_textual(self, **kwargs: Any):
        stream: MultimodalStream = kwargs.get("stream")
        video_snipped_textual = stream.textuals.get(TextualName.VIDEO_SNIPPED_TEXTUAL)
        self.snipped_textual_export_adapter.export(video_snipped_textual, **kwargs)

    def export_short_term_textual(self, **kwargs: Any):
        stream: MultimodalStream = kwargs.get("stream")
        frame_queue = stream.get_frame_queue()

        video_short_term_textuals = stream.textuals.get(TextualName.VIDEO_SHORT_TERM_TEXTUAL)
        self.short_term_textual_export_adapter.export(video_short_term_textuals, **kwargs)

    def export_long_term_textual(self, **kwargs: Any):
        stream: MultimodalStream = kwargs.get("stream")
        video_long_term_textual = stream.textuals.get(TextualName.VIDEO_LONG_TERM_TEXTUAL)
        self.long_term_textual_export_adapter.export(video_long_term_textual, **kwargs)
