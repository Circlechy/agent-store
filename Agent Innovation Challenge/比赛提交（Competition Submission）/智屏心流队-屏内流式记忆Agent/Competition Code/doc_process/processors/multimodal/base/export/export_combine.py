#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
from typing import List, Any

from doc_process.processors.multimodal.base.export.base import BaseExport
from doc_process.utils import logging
from doc_process.context.base_schema import (
    Context)

logger = logging.get_logger()


class ExportCombine(BaseExport):
    """Export to Index Engine."""
    exports: List[BaseExport]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def _export(self, context: Context, **kwargs: Any) -> None:
        """export data to index engine"""
        for export in self.exports:
            export(context)
