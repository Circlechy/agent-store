#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
import traceback
from typing import List, Any, Dict, Optional

from doc_process.processors.adapter.abs_adapter import FalconAdapter
from doc_process.processors.export.base import BaseExport

from doc_process.processors.base.adapter.export_adapter import ExportAdapter
from doc_process.utils import logging
from doc_process.utils.base_schema import (
    Document, Field, Context, ProcessorName)
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentExportFalcon(BaseExport):
    """Export to Index Engine."""
    falcon_adapter: Optional[ExportAdapter] = Field(
        default=None,
        description="fusion_adapter",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        logger.info("export init start.")
        logger.info("export init done.")

    def _export(self, context: Context, **kwargs: Any) -> None:
        """export data to index engine"""
        documents: List[Document] = context.get_documents()
        if not documents:
            return
        for document in documents:
            try:
                self.export_document(document)
            except Exception as e:
                logger.error(traceback.format_exc())
                context.add_info_to_component(
                    ProcessorName.EXPORT_FALCON, document.get_doc_md5(),
                    e if isinstance(e, ProcessorException) else ProcessorException(ErrorCode.EXPORT_FALCON_ERROR, e))

    def export_document(self, document: Document):
        """export document"""
        if not document or not document.chunks:
            return
        store_res = self.falcon_adapter.export([], **{"document": document})
        if store_res is not True:
            raise ProcessorException(ErrorCode.EXPORT_FALCON_ERROR, "export to falcon failed")
