#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for SparseVector."""
from typing import Any, Dict

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.represent.base import BaseRepresent
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class SparseVector(BaseRepresent):
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("SparseVector init start.")
        logger.info("SparseVector init done.")

    def _represent(self, context: MultimodalContext, **kwargs: Any) -> None:
        """represent data"""
