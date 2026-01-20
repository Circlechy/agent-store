#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Dict, Optional, Any

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.base.parsers.base import BaseParser
from doc_process.processors.multimodal.parsers.builder.speech_builder import SpeechBuilder
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class SpeechParser(BaseParser):
    """Interface for Parser."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    speech_builder: SpeechBuilder = Field(
        default_factory=SpeechBuilder,
        description="speech builder",
    )

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize with parameters."""
        super().__init__(config=config)
        logger.info("parser init start.")
        logger.info("parser init done.")

    def _parse(self, context: MultimodalContext, **kwargs: Any) -> None:
        """parse data"""
        ...
