#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from doc_process.context.base_schema import (
    Context,
)
from doc_process.processors.base.delete.base import BaseDelete
from doc_process.utils import logging

logger = logging.get_logger()


class DocumentDelete(BaseDelete):
    """Interface for delete models."""

    @staticmethod
    def build_delete_data(context: Context):
        """build delete data"""
        doc_id_list = context.get_input_kwarg_with_key("doc_id")
        if not doc_id_list or not isinstance(doc_id_list, list):
            doc_id_list = []
        data_dict = {
            "user_id": context.get_knowledge_base_name(),
            "session_id": context.get_session_id(),
            "doc_ids": doc_id_list,
        }
        return data_dict
