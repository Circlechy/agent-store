#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Dict, Optional, Any

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.base.parsers.base import BaseParser
from doc_process.processors.multimodal.parsers.builder.image_builder import ImageBuilder
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class ImageParser(BaseParser):
    """Interface for Parser."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    image_builder: ImageBuilder = Field(
        default_factory=ImageBuilder,
        description="image builder",
    )

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize with parameters."""
        super().__init__(config=config)
        logger.info("parser init start.")
        logger.info("parser init done.")

    def _parse(self, context: MultimodalContext, **kwargs: Any) -> None:
        """parse data"""
        ...
