#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Any

from doc_process.context.multimodal_schema import MultimodalContext
from doc_process.processors.multimodal.base.loaders.base import BaseLoader


class TextLoader(BaseLoader):
    """Interface for Loader."""

    def _load(self, context: MultimodalContext, **kwargs: Any) -> None:
        """Load data"""
        ...
