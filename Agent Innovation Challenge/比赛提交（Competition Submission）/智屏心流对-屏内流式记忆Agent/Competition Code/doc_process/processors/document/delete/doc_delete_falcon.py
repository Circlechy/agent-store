#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
'''
@Department ：2012/Poisson Lab
@Author     ：wushangquan
@Since      ：2024/04/26
Copyright (c) huawei, Inc. and its affiliates.
'''

from typing import Any

from doc_process.context.base_schema import Context
from doc_process.processors.base.delete.base import BaseDelete
from doc_process.processors.base.adapter.delete_adapter import DeleteAdapter
from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentDeleteFalcon(BaseDelete):
    """implement for delete models."""
    falcon_adapter: DeleteAdapter

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def _delete(self, context: Context, **kwargs: Any) -> None:
        """delete data from document"""
        data_dict = self.build_delete_data(context)
        result = self.falcon_adapter.delete_data(data_dict)
        if result is not True:
            raise ProcessorException(ErrorCode.DELETE_FALCON_ERROR,
                                     "delete falcon failed or result incorrect.result={}".format(result))
