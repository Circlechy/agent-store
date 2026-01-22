#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Extract bm25 info."""
import traceback
from typing import List, Any, Dict

from doc_process.config_repository.config import merge_internal_config
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.context.doc_schema import DocContext
from doc_process.processors.base.adapter.bm25_adapter import Bm25Adapter
from doc_process.processors.base.bm25.base import BaseBm25
from doc_process.utils import logging
from doc_process.context.doc_schema import (
    Document, Chunk, Inverted, IndexInfo, )
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class DocumentBm25(BaseBm25):
    """Extract bm25 info."""
    mapping: BaseMappingField
    bm25_adapter: Bm25Adapter
    config: Dict[str, object] = Field(
        description="configuration, index相关参数必填",
    )
    inverted_fields: List[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        logger.info("bm25 init start.")
        self._parse_config()
        logger.info("bm25 init done.")

    def _bm25(self, context: DocContext, **kwargs: Any) -> None:
        """Extract the fields that need to be extracted bm25"""
        documents: List[Document] = context.get_documents()
        if not documents:
            return
        for document in documents:
            try:
                self._bm25_document(document)
            except Exception as e:
                logger.error(traceback.format_exc())
                context.add_info_to_component(
                    ProcessorName.BM25, document.get_doc_md5(),
                    e if isinstance(e, ProcessorException) else ProcessorException(ErrorCode.BM25_ERROR, e)
                )

    def _parse_config(self):
        """
        _parse_config
        必填项：
        index： dict。 index.inverted: list，不可以是[]。
        """
        if self.bm25_adapter is None:
            raise ProcessorException(ErrorCode.CONFIG_INVALID, "bm25_adapter is None")
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)

        CheckUtils.check_type(self.config.get("index"), dict, "index")
        CheckUtils.check_type(self.config.get("index").get("chunk_info"), list, "index.chunk_info")
        CheckUtils.check_type(self.config.get("index").get("inverted"), list, "index.inverted")

        index_: dict = self.config.get("index", {})
        self.inverted_fields: List[str] = index_.get("inverted")
        CheckUtils.is_all_type(self.inverted_fields, str, "index.inverted")

        bus_fields_set = self.mapping.get_bus2base_dict().keys()
        if not set(self.inverted_fields).issubset(bus_fields_set):
            raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                     "inverted_fields={} is not subset of bus_fields_set={}".format(
                                         self.inverted_fields, bus_fields_set))

    def _bm25_document(self, document: Document) -> None:
        """bm25_document"""
        if not document or not document.chunks:
            return
        chunks: List[Chunk] = document.chunks
        chunks_to_remove = []
        bm25s_res: (bool, List[List[Dict]])
        for field in self.inverted_fields:
            if self.mapping.get_base_name(field) in self.mapping.get_document_field_keys():
                chunk_list = chunks
                field_text = self.mapping.get_mapping_field(document, field)
                bm25s_res = (True, [[{"token": field_text, "start_offset": 0, "end_offset": len(field_text),
                                      "type": "word", "position": 0}]] * len(chunk_list)
                             )
            elif self.mapping.get_base_name(field) in self.mapping.get_chunk_field_keys():
                chunk_list, field_text_list = get_valid_field_chunks(self.mapping, chunks, field)
                bm25s_res: (bool, List[List[Dict]]) = self.bm25_adapter.extract_bm25(field_text_list)
            else:
                raise ProcessorException(ErrorCode.VALUE_ERROR,
                                         "field={} not in chunk or document.".format(
                                             self.mapping.get_base_name(field)))
            bm25s: List[List[Dict]] = bm25s_res[1]
            if bm25s and len(bm25s) != len(chunk_list):
                logger.error("len(bm25s)={} not equal to len(chunks)={}".format(len(bm25s), len(chunk_list)))
                continue
            for res, chunk in zip(bm25s, chunk_list):
                if not res:
                    chunks_to_remove.append(chunk)
                inverted = self._convert_list2inverted(res)
                index_info = chunk.index_infos.get(field, IndexInfo())
                index_info.inverted = inverted
                chunk.index_infos[field] = index_info
        if chunks_to_remove:
            logger.info(
                "bm25 result failed:num={},chunks ={}.".format(len(chunks_to_remove), chunks_to_remove))

    def _convert_list2inverted(self, bm25s: List[Dict]) -> Inverted:
        """convert_list2inverted"""
        inverted = Inverted()
        for bm25 in bm25s:
            # 跳过异常情况
            if not (bm25.get("token") and bm25.get("position")):
                continue
            inverted.tokens.append(bm25.get("token").encode("utf-8", errors="ignore").decode("utf-8"))
            inverted.pos.append(bm25.get("position"))
        return inverted


def get_valid_field_chunks(mapping: BaseMappingField, chunks: List[Chunk], field: str) -> (List[Chunk], List[str]):
    """
    get valid test_list from chunks
    遇到字段为空的情况，则从document中直接剔除掉该chunk
    """
    text_list = []
    chunk_list = []
    chunks_to_remove = []

    for chunk in chunks:
        chunk_field = mapping.get_mapping_field(chunk, field).strip()
        if chunk_field:
            text_list.append(chunk_field)
            chunk_list.append(chunk)
        else:
            chunks_to_remove.append(chunk)  # 标记需要删除的 chunk

    remove_invalid_index_info_chunks(chunks, chunks_to_remove, "get_valid_chunk")
    return chunk_list, text_list


def remove_invalid_index_info_chunks(chunks: List[Chunk], chunks_to_remove: List[Chunk], flag_name=""):
    """
    remove invalid index_info chunks
    如果单个chunk的bm25或者embedding服务返回值不合法，则从document中直接剔除掉该chunk
    """
    # 删除 chunks 中的无效元素
    for chunk in chunks_to_remove:
        if chunk in chunks:
            chunks.remove(chunk)  # 确保不会在循环中直接修改 chunks
    if chunks_to_remove:
        logger.error("{} chunks_to_remove={}".format(flag_name, chunks_to_remove))
