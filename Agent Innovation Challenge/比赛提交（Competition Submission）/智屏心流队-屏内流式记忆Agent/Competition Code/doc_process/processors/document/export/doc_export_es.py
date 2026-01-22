#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Export to Index Engine."""
import traceback
from typing import List, Any, Dict

from doc_process.config_repository.config import merge_internal_config
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.context.doc_schema import Document
from doc_process.processors.base.adapter.export_adapter import ExportAdapter
from doc_process.processors.base.export.base import BaseExport
from doc_process.utils import logging
from doc_process.context.base_schema import (
     Field, Context, ProcessorName)
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class DocumentExportEs(BaseExport):
    """Export to Index Engine."""
    config: Dict[str, object] = Field(
        description="configuration, index相关参数必填",
    )
    chunk_info_fields: List[str] = None
    es_adapter: ExportAdapter
    mapping: BaseMappingField

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        logger.info("ExportEs init start.")
        self._parse_config()
        logger.info("ExportEs init done.")

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
                    ProcessorName.EXPORT_ES, document.get_doc_md5(),
                    e if isinstance(e, ProcessorException) else ProcessorException(ErrorCode.EXPORT_ES_ERROR, e))

    def export_document(self, document: Document):
        """export document"""
        if not document or not document.chunks:
            return
        chunks_schema = self._convert_chunk2obj(document)
        store_res = self.es_adapter.export(chunks_schema)
        if store_res is not True:
            raise ProcessorException(ErrorCode.EXPORT_ES_ERROR, "export to es failed")

    def _parse_config(self):
        """
        _parse_config
        必填项：
        index： dict。index.chunk_info: list,不可以是[]。
        """
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)

        CheckUtils.check_type(self.config.get("index"), dict, "index")
        CheckUtils.check_type(self.config.get("index").get("chunk_info"), list, "index.chunk_info")
        self.chunk_info_fields = self.config.get("index", {}).get("chunk_info")
        CheckUtils.is_all_type(self.chunk_info_fields, str, "index.chunk_info")

        bus_fields_set = self.mapping.get_bus2base_dict().keys()
        if not set(self.chunk_info_fields).issubset(bus_fields_set):
            raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                     "chunk_infos={}  is not subset of bus_fields_set={}".format(
                                         self.chunk_info_fields, bus_fields_set))

    def _convert_chunk2obj(self, document: Document, **kwargs: Any):
        """
        convert chunk to es schema
        """
        chunks_schema: List[Dict] = []
        for chunk in document.chunks:
            schema_obj = {}
            for field in self.chunk_info_fields:
                if self.mapping.get_base_name(field) in self.mapping.get_document_field_keys():
                    value = document
                elif self.mapping.get_base_name(field) in self.mapping.get_chunk_field_keys():
                    value = chunk
                else:
                    raise ProcessorException(ErrorCode.VALUE_ERROR, "field={} not in chunk or document.".format(
                        self.mapping.get_base_name(field)))
                schema_obj[field] = self.mapping.get_mapping_field(value, field)
            chunks_schema.append(schema_obj)
        return chunks_schema
