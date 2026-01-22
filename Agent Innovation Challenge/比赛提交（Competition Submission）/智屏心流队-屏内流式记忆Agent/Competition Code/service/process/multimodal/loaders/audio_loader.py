#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Dict, Optional, Any

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.base.loaders.base import BaseLoader
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class AudioLoader(BaseLoader):
    """Interface for Loader."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize with parameters."""
        super().__init__(config=config)
        logger.info("loader init start.")
        logger.info("loader init done.")

    def _load(self, context: MultimodalContext, **kwargs: Any) -> None:
        """Load data"""
        ...
