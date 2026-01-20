#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from abc import ABC

from doc_process.context.base_schema import (
    BaseComponent,
)
from doc_process.utils import logging

logger = logging.get_logger()


class BaseLoader(BaseComponent, ABC):
    """Interface for Loader."""
