#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


import hashlib
import io
import base64
import numpy as np
from PIL import Image

from doc_process.context.doc_constants import DEFAULT_INVALID_CONTENT
from doc_process.utils.file_utils import FileUtils


def generate_id_by_path(knowledge_base_name: str, session_id: str, title: str, file_path: str):
    """Generate id for document/chunk."""
    FileUtils.check_path(file_path)
    # get document id
    with open(file_path, "rb") as f_in:
        file_content_bin = f_in.read()
    doc_id = generate_id(knowledge_base_name, session_id, title, str(file_content_bin))
    del file_content_bin
    return doc_id


def generate_id(knowledge_base_name: str, session_id: str, title: str, content: str):
    """Generate id for document/chunk."""
    content_md5 = hashlib.md5(content.encode()).hexdigest()
    res = hashlib.md5((knowledge_base_name + session_id + title + content_md5).encode()).hexdigest()
    return res


def is_valid_generated_content(content: str):
    """Check whether is valid generated content"""
    if content.startswith(DEFAULT_INVALID_CONTENT):
        return False
    return True


def check_xlsx_document(doc_name: str):
    """Check whether the document is an xlsx format file."""
    if isinstance(doc_name, str) and doc_name.endswith("xlsx"):
        return True
    return False
