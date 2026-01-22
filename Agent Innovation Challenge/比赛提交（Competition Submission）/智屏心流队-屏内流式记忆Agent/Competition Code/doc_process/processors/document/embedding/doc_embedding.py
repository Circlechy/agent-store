#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""implement for embedding models."""
import traceback
from typing import List, Any, Dict, Optional

from doc_process.config_repository.config import merge_internal_config
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.context.doc_schema import (
    Document, Chunk, Semantic, IndexInfo, Context, )
from doc_process.processors.base.adapter.embedding_adapter import TextEmbeddingAdapter
from doc_process.processors.base.embedding.base import BaseEmbedding
from doc_process.processors.document.bm25.doc_bm25 import get_valid_field_chunks
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


def gen_semantic_id(mapping: BaseMappingField, field: str, chunk_id: str, split_index: int) -> str:
    """
    生成semantic_id
    content ： chunk_id+ 100x   （x通过split_num来确定）
    title: chunk_id + 0000
    """
    prefix_id: int
    if mapping.is_mapping(field, mapping.TITLE):
        prefix_id = 0
    elif mapping.is_mapping(field, mapping.CONTENT):
        prefix_id = 1
    elif mapping.is_mapping(field, mapping.CHAPTER_SUMMARY):
        prefix_id = 2
    else:
        logger.error(f"field={field} is unknown.")
        prefix_id = 3
    return chunk_id + str(prefix_id) + str(split_index).rjust(3, "0")


class DocumentEmbedding(BaseEmbedding):
    """implement for embedding models."""
    mapping: BaseMappingField
    embedding_adapter: TextEmbeddingAdapter
    config: Dict[str, object] = Field(
        description="configuration, index相关参数必填",
    )
    semantic_fields: List[str] = None
    truncate_num: Optional[int]
    degrade_enable: Optional[bool]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        logger.info("embedding init start.")
        self._parse_config()
        logger.info("embedding init done.")

    def _embedding(self, context: Context, **kwargs: Any) -> None:
        """Extract the fields that need to be embedding"""

        documents: List[Document] = context.get_documents()
        if not documents:
            return
        for document in documents:
            try:
                self._embedding_document(document)
            except Exception as e:
                logger.error(traceback.format_exc())
                context.add_info_to_component(
                    ProcessorName.EMBEDDING, document.get_doc_md5(),
                    e if isinstance(e, ProcessorException) else ProcessorException(ErrorCode.EMBEDDING_ERROR, e))

    def _parse_config(self):
        """
        _parse_config
        必填项：
        index： dict。 index.semantic: list，不可以是[]。
        """
        if self.embedding_adapter is None:
            raise ProcessorException(ErrorCode.TYPE_ERROR, "embedding_adapter is None")
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)

        CheckUtils.check_type(self.config.get("index"), dict, "index")
        CheckUtils.check_type(self.config.get("index").get("chunk_info"), list, "index.chunk_info")
        CheckUtils.check_type(self.config.get("index").get("semantic"), list, "index.semantic")
        index_: dict = self.config.get("index", {})
        self.semantic_fields: List[str] = index_.get("semantic")
        CheckUtils.is_all_type(self.semantic_fields, str, "index.semantic")

        CheckUtils.check_type(self.config.get("embedding"), dict, "embedding")
        self.truncate_num = self.config.get("embedding", {}).get("truncate_num")
        CheckUtils.check_type(self.truncate_num, int, "embedding.truncate_num")
        CheckUtils.check_type(self.config.get("degrade"), dict, "degrade")
        self.degrade_enable = self.config.get("degrade", {}).get("enable")
        CheckUtils.check_type(self.degrade_enable, bool, "degrade.enable")

        bus_fields_set = self.mapping.get_bus2base_dict().keys()
        if not set(self.semantic_fields).issubset(bus_fields_set):
            raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                     "semantic_fields={} is not subset of bus_fields_set={}".format(
                                         self.semantic_fields, bus_fields_set))

        logger.info(f"config_dict={index_}")

    def _embedding_document(self, document: Document):

        """embedding for document.chunks"""
        if not document or not document.chunks:
            return
        chunks: List[Chunk] = document.chunks
        chunks = chunks[:self.truncate_num] if self.degrade_enable else chunks
        for field in self.semantic_fields:
            chunk_list, field_text_list = get_valid_field_chunks(self.mapping, chunks, field)
            embeddings_res: (bool, List[List[List[float]]]) = self.embedding_adapter.text_embedding(
                field_text_list)
            self._build_chunk_semantics(embeddings_res[1], chunk_list, field)

    def _convert_list2semantic(self, embeddings: List[List[float]], field: str, chunk: Chunk) -> List[Semantic]:
        """
        convert List[List[float]] to List[semantic]
        """
        semantic_list = []
        for index, sub_list in enumerate(embeddings):
            semantic_id = gen_semantic_id(mapping=self.mapping, field=field, chunk_id=chunk.chunk_id, split_index=index)
            semantic_list.append(Semantic(id=semantic_id, embeddings=sub_list))
        return semantic_list

    def _build_chunk_semantics(self, embeddings_res: List[List[List[float]]], chunks: List[Chunk], field: str) -> None:
        """
        convert embeddings_res to chunk.index_info.semantics
        """
        if embeddings_res and len(embeddings_res) != len(chunks):
            logger.error("len(embeddings_res)={} not equal to len(chunks)={}".format(len(embeddings_res), len(chunks)))
            return
        chunks_to_remove = []
        for embeddings, chunk in zip(embeddings_res, chunks):
            if not embeddings or not embeddings[0]:
                chunks_to_remove.append(chunk)
            semantic_list = self._convert_list2semantic(embeddings, field, chunk)
            index_info = chunk.index_infos.get(field, IndexInfo())
            index_info.semantics = semantic_list
            chunk.index_infos[field] = index_info
        if chunks_to_remove:
            logger.info(
                "embedding result failed:num={},chunks ={} .".format(len(chunks_to_remove), chunks_to_remove))
