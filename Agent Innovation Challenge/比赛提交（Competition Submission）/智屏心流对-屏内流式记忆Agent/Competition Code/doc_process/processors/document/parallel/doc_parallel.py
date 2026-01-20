#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.

import copy
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

from doc_process.processors.base.parallel.base import BaseParallel
from doc_process.processors.document.bm25.doc_bm25 import DocumentBm25
from doc_process.processors.document.embedding.doc_embedding import DocumentEmbedding
from doc_process.utils import logging
from doc_process.context.doc_schema import (
    Context, IndexInfo, Document)

logger = logging.get_logger()


class DocumentParallel(BaseParallel):
    """Parallel models."""
    bm25: DocumentBm25
    embedding: DocumentEmbedding

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _parallel(self, context: Context, **kwargs: Any) -> None:
        """parallel run model."""
        documents: List[Document] = context.get_documents()
        if not documents:
            return
        context2: Context = copy.deepcopy(context)
        # 使用线程池 主线程和子线程之间可以共享context变量
        with ThreadPoolExecutor() as executor:
            future1 = executor.submit(self.bm25, context)
            future2 = executor.submit(self.embedding, context2)
            try:
                future1.result()  # 执行并获取结果
                future2.result()
            except Exception:
                logger.error(traceback.format_exc())
            finally:
                self.merge_result(context, context2)

    def merge_result(self, context1: Context, context2: Context) -> None:
        """merge semantics embedding from context2 to context1"""
        context1.update_cost_time(
            self.embedding.__class__.__name__, context2.get_cost_time().get(self.embedding.__class__.__name__, ""))
        if not context1.documents or not context2.documents:
            return
        for document1, document2 in zip(context1.documents, context2.documents):
            if not document1.chunks or not document2.chunks:
                continue
            for chunk1, chunk2 in zip(document1.chunks, document2.chunks):
                for field2, index_info2 in chunk2.index_infos.items():
                    index_info1: IndexInfo = chunk1.index_infos.get(field2, IndexInfo())
                    index_info1.semantics = index_info2.semantics
                    chunk1.index_infos[field2] = index_info1
