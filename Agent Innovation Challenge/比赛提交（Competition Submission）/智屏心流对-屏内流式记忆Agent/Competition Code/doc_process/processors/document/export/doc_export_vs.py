#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
import traceback
from typing import List, Any, Dict, Optional

from doc_process.config_repository.config import merge_internal_config
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.context.base_schema import (
    Field, Context, ProcessorName, )
from doc_process.context.doc_schema import Document, Semantic, IndexInfo, Chunk
from doc_process.processors.base.adapter.export_adapter import ExportAdapter
from doc_process.processors.base.export.base import BaseExport
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentExportVs(BaseExport):
    """Export to Index Engine."""
    config: Dict[str, object] = Field(
        description="configuration, index相关参数必填",
    )

    semantic_fields: List[str] = None
    scalar_filter_fields: List[str] = None
    vs_adapter: ExportAdapter
    mapping: BaseMappingField
    truncate_num: Optional[int]
    degrade_enable: Optional[bool]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        logger.info("ExportVs init start.")
        self._parse_config()
        logger.info("ExportVs init done.")

    def _export(self, context: Context, **kwargs: Any) -> None:
        """export data to index engine"""
        documents: List[Document] = context.get_documents()
        if not documents:
            return
        for document in documents:
            try:
                self.export_document(document)
            except Exception as e:
                logger.error(traceback.format_exc())
                context.add_info_to_component(
                    ProcessorName.EXPORT_VS, document.get_doc_md5(),
                    e if isinstance(e, ProcessorException) else ProcessorException(ErrorCode.EXPORT_VS_ERROR, e))

    def export_document(self, document: Document):
        """export document"""
        if not document or not document.chunks:
            return
        vectors = self._convert_chunk2vector(document)
        store_res = self.vs_adapter.export(vectors)
        if store_res is not True:
            raise ProcessorException(ErrorCode.EXPORT_VS_ERROR, "export to vs failed")

    def _parse_config(self):
        """
        _parse_config
        必填项：
        index： dict。 index.semantic: list，不可以是[]。
        """
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)

        CheckUtils.check_type(self.config.get("index"), dict, "index")
        CheckUtils.check_type(self.config.get("index").get("semantic"), list, "index.semantic")
        CheckUtils.check_type(self.config.get("index").get("scalar_filter", []), list, "index.scalar_filter")

        self.semantic_fields = self.config.get("index").get("semantic")
        self.scalar_filter_fields = self.config.get("index").get("scalar_filter", [])
        CheckUtils.is_all_type(self.semantic_fields, str, "index.semantic")
        if self.scalar_filter_fields:
            CheckUtils.is_all_type(self.scalar_filter_fields, str, "index.scalar_filter")

        CheckUtils.check_type(self.config.get("embedding"), dict, "embedding")
        CheckUtils.check_type(self.config.get("degrade"), dict, "degrade")
        self.degrade_enable = self.config.get("degrade", {}).get("enable")
        self.truncate_num = self.config.get("embedding", {}).get("truncate_num")
        CheckUtils.check_type(self.degrade_enable, bool, "degrade.enable")
        CheckUtils.check_type(self.truncate_num, int, "embedding.truncate_num")

        bus_fields_set = self.mapping.get_bus2base_dict().keys()
        if not set(self.semantic_fields).issubset(bus_fields_set):
            raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                     "semantic_fields={} is not subset of bus_fields_set={}".format(
                                         self.semantic_fields, bus_fields_set))
        if not set(self.scalar_filter_fields).issubset(bus_fields_set):
            raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                     "scalar_filter_fields={} is not subset of bus_fields_set={}".format(
                                         self.scalar_filter_fields, bus_fields_set))

    def _convert_chunk2vector(self, document: Document, **kwargs: Any) -> List[Dict]:
        """
        convert chunk to vector schema:
        {
        "field": [{"id": "","embeddings": [],"doc_id":"","user_id":""}]
        }
        """
        vectors_schema: List[Dict] = []
        chunks: List[Chunk] = document.chunks
        chunks = chunks[:self.truncate_num] if self.degrade_enable else chunks
        for chunk in chunks:

            vector_schema: Dict[str, List[Dict]] = {}
            for field in self.semantic_fields:
                semantic_dict_list = []
                semantics: List[Semantic] = chunk.index_infos.get(field, IndexInfo()).semantics
                for semantic in semantics:
                    semantic_dict = self._build_semantic_dict(document, chunk, field, semantic)
                    semantic_dict_list.append(semantic_dict)
                vector_schema[field] = semantic_dict_list
            vectors_schema.append(vector_schema)
        return vectors_schema

    def _build_semantic_dict(self, document: Document, chunk: Chunk, field: str, semantic: Semantic):
        """build semantic dict"""
        semantic_dict = {"id": semantic.id, "embeddings": semantic.embeddings}
        for filter_field in self.scalar_filter_fields:
            if self.mapping.get_base_name(filter_field) in self.mapping.get_document_field_keys():
                value = document
            elif self.mapping.get_base_name(filter_field) in self.mapping.get_chunk_field_keys():
                value = chunk
            else:
                raise ProcessorException(ErrorCode.VALUE_ERROR,
                                         "field={} not in chunk or document.".format(
                                             self.mapping.get_base_name(field))
                                         )
            semantic_dict[filter_field] = self.mapping.get_mapping_field(value, filter_field)
        return semantic_dict
