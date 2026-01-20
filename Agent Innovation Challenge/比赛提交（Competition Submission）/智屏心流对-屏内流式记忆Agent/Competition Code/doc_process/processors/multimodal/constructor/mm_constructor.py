#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from abc import ABC
from typing import Any, Dict

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.constructor.base import BaseConstructor
from doc_process.utils import logging
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class MultimodalConstructor(BaseConstructor, ABC):
    """Interface for Constructor."""
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    def _construct(self, context: MultimodalContext, **kwargs: Any) -> None:
        """construct data before export."""
        ...
