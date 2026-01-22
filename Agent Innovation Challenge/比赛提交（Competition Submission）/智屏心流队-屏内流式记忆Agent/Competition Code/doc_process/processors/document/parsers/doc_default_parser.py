# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a base class to build doctree for file."""
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from zipfile import BadZipFile

from doc_process.config_repository.config import merge_internal_config
from doc_process.processors.document.parsers.doc_base import DocumentBaseParser
from doc_process.processors.document.parsers.doctree_build.utils.consts import DEFAULT_USER_CONFIG, INTERNAL_CONFIG
from doc_process.processors.document.parsers.doctree_build.utils.util import ConfigItem
from doc_process.utils import logging
from doc_process.context.doc_schema import Document, Context
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.file_utils import FileUtils
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class DocumentDefaultParser(DocumentBaseParser):
    """ Abstract file parser  """

    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    cfg: Optional[ConfigItem] = Field(
        None,
        description="merge default user configuration and internal configuration"
    )

    degrade: bool = Field(
        False,
        description="check if degrade parse",
    )

    class Config:
        """ config object """
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super(DocumentDefaultParser, self).__init__(**kwargs)
        logger.info("Parser: {} init start.".format(self.__class__.__name__))
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)
        self._parse_config(**kwargs)
        default_user_cfg = self._get_default_user_cfg()
        internal_cfg = self._get_internal_cfg()
        CheckUtils.check_type(self.config, dict, "config")
        final_cfg = default_user_cfg
        final_cfg = ConfigItem.merge_dict_cfg(final_cfg, self.config)
        final_cfg = ConfigItem.merge_dict_cfg(final_cfg, internal_cfg)
        cfg_item = ConfigItem.from_dict(final_cfg)
        self._check_cfg(cfg_item)
        self.cfg = cfg_item
        logger.info("Parser: {} init done.".format(self.__class__.__name__))

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    def build(self, path):
        """ build doctree from file """
        doc, context = self.read_from_path(path)
        return doc, context

    @abstractmethod
    def read_from_path(self, path: Path) -> Tuple[Document, Dict]:
        """ read from file """
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    @abstractmethod
    def _parse_config(self, **kwargs):
        """ 依据config进行parser初始化 """
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    def _check_cfg(self, cfg):
        """ check config """
        ...

    def _get_default_user_cfg(self):
        """ get default cfg """
        return DEFAULT_USER_CONFIG.get(self.file_suffix().strip("."), {})

    def _get_internal_cfg(self):
        """ get internal cfg """
        return INTERNAL_CONFIG.get(self.file_suffix().strip("."), {})

    def _parse(self, file_path: Path, context: Context, **kwargs: Any):
        document: Document = kwargs.get("document")
        try:
            FileUtils.check_file(file_path, self.cfg.file_size_limit)
            doc_tree, parse_context = self.read_from_path(file_path)
            metadata = kwargs.get("metadata", {})
            metadata["parse_context"] = parse_context
            document.set_doc_title(file_path.name)
            document.set_root(doc_tree[0])
            document.set_chunks([])
            document.set_metadata(metadata)
            logger.debug("Document {} constructed.".format(file_path.name))
            context.add_documents(document)
        except BadZipFile as e:
            msg = "file={} is invalid excel,please check file.exception:{}".format(file_path.name, str(e))
            pe = ProcessorException(ErrorCode.FILE_INVALID, msg)
            context.add_info_to_component(ProcessorName.PARSER, document.get_doc_md5(), pe)
            logger.error("{}. Skipping...".format(msg))
        except Exception as ex:
            msg = "File {} parse fail, error_msg={}".format(file_path.name, str(ex))
            pe = ex if isinstance(ex, ProcessorException) else ProcessorException(ErrorCode.PARSER_ERROR, msg)
            context.add_info_to_component(ProcessorName.PARSER, document.get_doc_md5(), pe)
            logger.error("{}. Skipping...".format(msg))
