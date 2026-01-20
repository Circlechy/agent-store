#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for SparseVector."""
from typing import Any, Dict

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.aggregaion.base import BaseAggregation
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class ShortTermAggregation(BaseAggregation):
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("ShortTermAggregation init start.")
        logger.info("ShortTermAggregation init done.")

    def _aggregation(self, context: MultimodalContext, **kwargs: Any) -> None:
        """aggregation data"""
        ...
