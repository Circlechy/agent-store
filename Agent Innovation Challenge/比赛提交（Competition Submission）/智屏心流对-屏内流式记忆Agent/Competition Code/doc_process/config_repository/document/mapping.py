from abc import ABC, abstractmethod
from typing import Dict, Optional

from doc_process.context.doc_schema import Chunk, Document
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode


class BaseMappingField(ABC):
    """MappingField"""
    # context 各字段
    DOC_ID = "DOC_ID"
    CHUNK_ID = "CHUNK_ID"
    CONTENT = "CONTENT"
    TITLE = "TITLE"
    CHAPTER_SUMMARY = "CHAPTER_SUMMARY"
    CHUNK = "CHUNK"
    KNOWLEDGE_BASE_NAME = "KNOWLEDGE_BASE_NAME"
    SESSION_ID = "SESSION_ID"

    # base field to business field
    config: Dict[str, str]
    # business field to base field
    bus2base_dict: Optional[Dict[str, str]]

    def __init__(self, **kwargs):
        config = kwargs.get("config", {})
        CheckUtils.check_type(config.get("index"), dict, "index")
        CheckUtils.check_type(config.get("index").get("mapping"), dict, "index.mapping")
        self.config = config.get("index").get("mapping")
        self.bus2base_dict = {value: key for key, value in self.config.items()}

    def get_base2bus_dict(self) -> Dict:
        """get base2bus config dict, mapping"""
        return self.config

    def get_bus_name(self, base_field: str) -> str:
        """
        获得基础字段对应的业务字段
        """
        return self.config[base_field]

    def get_bus2base_dict(self) -> Dict:
        """get bus2base config dict"""
        return self.bus2base_dict

    def get_base_name(self, bus_field: str) -> str:
        """
        获得业务字段对应的基础字段
        """
        return self.bus2base_dict[bus_field]

    def is_mapping(self, bus_field: str, base_field: str) -> bool:
        """
        判断业务字段和基础字段是否为对应的映射关系
        """
        return self.bus2base_dict[bus_field] == base_field

    def get_mapping_field(self, obj, bus_field: str) -> str:
        """
        根据业务字段获得obj对象中对应的属性
        """
        field = self.bus2base_dict[bus_field]
        if isinstance(obj, Chunk):
            return self.get_chunk_field(obj, field)
        elif isinstance(obj, Document):
            return self.get_document_field(obj, field)
        else:
            raise ProcessorException(ErrorCode.TYPE_ERROR, "obj={} is unknown".format(obj))

    @abstractmethod
    def get_chunk_field(self, chunk: Chunk, field: str) -> str:
        """
        根据field字段返回chunk 属性
        """
        ...

    @abstractmethod
    def get_document_field(self, document: Document, field: str) -> str:
        """
        根据field字段返回document 属性
        """
        ...

    def get_chunk_field_keys(self):
        return {self.CHUNK_ID, self.CONTENT, self.TITLE, self.CHAPTER_SUMMARY, self.CHUNK}

    def get_document_field_keys(self):
        return {self.KNOWLEDGE_BASE_NAME, self.DOC_ID, self.SESSION_ID}


class MappingField(BaseMappingField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_chunk_field(self, chunk: Chunk, field: str) -> str:
        field_mapping = {
            self.CHUNK_ID: chunk.get_chunk_id,
            self.CONTENT: chunk.get_content,
            self.TITLE: chunk.get_title,
            self.CHAPTER_SUMMARY: chunk.get_chapter_summary,
            self.CHUNK: chunk.get_content
        }
        if field in field_mapping:
            return field_mapping[field]()  # 在这里调用方法

        raise ProcessorException(ErrorCode.TYPE_ERROR, "field={} is unknown".format(field))

    def get_document_field(self, document: Document, field: str) -> str:
        if field == self.KNOWLEDGE_BASE_NAME:
            return document.get_knowledge_base_name()
        elif field == self.DOC_ID:
            return document.get_doc_id()
        elif field == self.SESSION_ID:
            return document.get_session_id()
        else:
            raise ProcessorException(ErrorCode.TYPE_ERROR, "field={} is unknown".format(field))
