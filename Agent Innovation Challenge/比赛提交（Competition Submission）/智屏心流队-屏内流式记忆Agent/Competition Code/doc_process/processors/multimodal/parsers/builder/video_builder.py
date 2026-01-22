#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from doc_process.processors.multimodal.parsers.builder.base_builder import BaseBuilder
from doc_process.utils import logging

logger = logging.get_logger()


class VideoBuilder(BaseBuilder):
    """VideoBuilder"""

    def build(self):
        """build"""
