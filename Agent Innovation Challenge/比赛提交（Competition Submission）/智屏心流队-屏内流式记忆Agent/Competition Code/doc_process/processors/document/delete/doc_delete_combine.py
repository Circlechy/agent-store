#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import List, Any

from doc_process.processors.base.delete.base import BaseDelete
from doc_process.processors.document.delete.doc_delete import DocumentDelete
from doc_process.processors.document.delete.doc_delete_es import DocumentDeleteEs
from doc_process.processors.document.delete.doc_delete_vs import DocumentDeleteVs
from doc_process.utils import logging
from doc_process.context.base_schema import (
    Context)
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentDeleteCombine(DocumentDelete):
    """implement for delete models."""
    deletes: List[BaseDelete]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.validate_deletes()

    def validate_deletes(self) -> None:
        """
        校验 deletes 数组中的 DeleteVs 对象必须在 DeleteEs 对象之前
        """
        # 跟踪是否已经遇到 DeleteEs 对象
        found_delete_es = False

        for delete in self.deletes:
            if isinstance(delete, DocumentDeleteEs):
                found_delete_es = True
            elif isinstance(delete, DocumentDeleteVs):
                # 如果遇到 DeleteVs，并且已经找到了 DeleteEs，则验证失败
                if found_delete_es:
                    raise ProcessorException(ErrorCode.PARAM_INVALID,
                                             f"Invalid order: DeleteVs should be before DeleteEs.")

    def _delete(self, context: Context, **kwargs: Any) -> None:
        """delete data from document"""
        for delete_processor in self.deletes:
            delete_processor(context)
