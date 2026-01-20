#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from abc import abstractmethod

from doc_process.utils import logging

logger = logging.get_logger()


class BaseDetector:
    """BaseDetector"""

    @abstractmethod
    def detect(self):
        """detect"""
