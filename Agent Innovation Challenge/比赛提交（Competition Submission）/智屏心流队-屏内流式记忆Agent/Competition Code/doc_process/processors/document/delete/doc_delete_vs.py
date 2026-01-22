#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Any

from doc_process.processors.base.adapter.delete_adapter import DeleteAdapter
from doc_process.processors.base.delete.base import BaseDelete
from doc_process.processors.document.delete.doc_delete import DocumentDelete
from doc_process.utils import logging
from doc_process.context.base_schema import (
    Context)
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentDeleteVs(DocumentDelete):
    """implement for delete models."""
    vs_adapter: DeleteAdapter

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def _delete(self, context: Context, **kwargs: Any) -> None:
        """delete data from document"""
        data_dict = self.build_delete_data(context)
        result = self.vs_adapter.delete_data(data_dict)
        if result is not True:
            raise ProcessorException(ErrorCode.DELETE_VS_ERROR,
                                     "delete vs failed or result incorrect.result={}".format(result))
