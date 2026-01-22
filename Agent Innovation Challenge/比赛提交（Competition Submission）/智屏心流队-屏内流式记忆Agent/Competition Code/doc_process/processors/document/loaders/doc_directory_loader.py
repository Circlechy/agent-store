#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from doc_process.config_repository.config import merge_internal_config
from doc_process.processors.base.loaders.base import BaseLoader
from doc_process.processors.document.parsers.doc_base import DocumentBaseParser
from doc_process.utils import logging
from doc_process.context.doc_schema import (
    StreamType, Context, Document)
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName, DEFAULT_KNOWLEDGE_BASE_NAME
from doc_process.utils.data_util import generate_id, generate_id_by_path
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.file_utils import FileUtils
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


def _try_loading_included_file_formats() -> Dict[str, Type[DocumentBaseParser]]:
    try:
        from doc_process.processors.document.parsers.doctree_parse import (
            HTMLParser,
            PlainTextParser
        )
        from doc_process.processors.document.parsers.md_parser import MDParser
        from doc_process.processors.document.parsers.docx_parser import DocxParser
        from doc_process.processors.document.parsers.pptx_parser import PPTXParser
        from doc_process.processors.document.parsers.pdf_parser import PDFParser
        from doc_process.processors.document.parsers.excel_parser import ExcelParser
    except ImportError as e:
        raise ProcessorException(ErrorCode.IMPORT_ERROR, "Cannot load Parsers") from e

    default_file_reader_cls: Dict[str, Type[DocumentBaseParser]] = {
        ".pdf": PDFParser,
        ".docx": DocxParser,
        ".pptx": PPTXParser,
        ".html": HTMLParser,
        ".txt": PlainTextParser,
        ".md": MDParser,
        ".xlsx": ExcelParser
    }
    return default_file_reader_cls


class DocumentDirectoryLoader(BaseLoader):
    """Directory Loader

    Load files from file directory.
    Automatically select the best file reader given file extensions.

    Args:
        file_extractor (Optional[Dict[str, BaseReader]]): A mapping of file
            extension to a BaseReader class that specifies how to convert that file
            to text. If not specified, use default from DEFAULT_FILE_READER_CLS.

    """
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    file_extractor: Optional[Dict[str, DocumentBaseParser]] = {}

    def __init__(
            self,
            config: Optional[Dict] = None,
            file_extractor: Optional[Dict[str, DocumentBaseParser]] = None,
    ) -> None:
        """Initialize with parameters."""
        super().__init__(config=config, file_extractor=file_extractor)
        logger.info("loader init start.")
        self._parse_config(config, file_extractor)
        if file_extractor is not None:
            CheckUtils.check_type(file_extractor, dict, "file_extractor")
            for suffix, parser_cls in file_extractor.items():
                CheckUtils.check_type(suffix, str, "suffix")
                CheckUtils.check_type(parser_cls, DocumentBaseParser, "parser_cls")
                self.file_extractor[suffix] = parser_cls
        else:
            self.file_extractor = {}
        for suffix, parser_cls in _try_loading_included_file_formats().items():
            if suffix in self.file_extractor:
                continue
            self.file_extractor[suffix] = parser_cls(config=config)
        logger.info("loader init done.")

    @staticmethod
    def get_total_files(files: List[str], exclude_hidden: bool, context: Context) -> (List[Path], List[Document]):
        """get total files"""
        new_input_files: List[Path] = []
        total_documents: List[Document] = []
        doc_id_list = context.get_input_kwarg_with_key("doc_id")
        for idx, ref in enumerate(files):
            ref = Path(ref)
            skip_because_hidden = exclude_hidden and FileUtils.is_hidden(ref)
            if skip_because_hidden:
                continue

            # 从context取到doc_id
            doc_id = doc_id_list[idx] if len(doc_id_list) > idx else ""
            # 生成document、doc_md5
            document = Document(
                knowledge_base_name=context.get_knowledge_base_name(),
                session_id=context.get_session_id(),
                stream_type=context.get_stream_type(),
                doc_md5=generate_id("", "", "", str(ref) + str(idx)),
                doc_id=doc_id
            )
            new_input_files.append(ref)
            total_documents.append(document)
        if len(new_input_files) == 0:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "No files found in inputs")
        return new_input_files, total_documents

    @staticmethod
    def get_valid_files(input_files: List[Path], total_documents: List[Document], context: Context) -> (
            List[Path], List[Document]):
        """
        get valid files
        """
        valid_files: List[Path] = []
        valid_documents: List[Document] = []
        for path, document in zip(input_files, total_documents):
            try:
                FileUtils.check_file(path)
            except Exception as ex:
                context.update_id2name(document.get_doc_md5(), path.name)
                msg = "File is invalid: {}".format(str(ex))
                logger.error(msg)
                context.add_info_to_component(
                    ProcessorName.LOADER, document.get_doc_md5(), ProcessorException(ErrorCode.FILE_INVALID, msg)
                )
            else:
                # context不包含用户提供的doc_id（允许用户传入空字符串作为doc_id）,则生成document.doc_id
                if not context.get_input_kwarg_with_key("doc_id"):
                    doc_id = generate_id_by_path(
                        context.get_knowledge_base_name(), context.get_session_id(), path.name, str(path))
                    document.set_doc_id(doc_id)

                valid_files.append(path)
                valid_documents.append(document)
        return valid_files, valid_documents

    def load(self, input_dir: Optional[str] = None,
             input_files: Optional[List[str]] = None,
             exclude_hidden: bool = True,
             recursive: bool = False,
             context: Context = None,
             **load_kwargs: Any) -> None:
        """
        Load data from the input directory.
        Args:
            input_dir (str): Path to the directory.
            input_files (List): List of file paths to read
                (Optional; overrides input_dir, exclude)
            exclude_hidden (bool): Whether to exclude hidden files (dotfiles).
            recursive (bool): Whether to recursively search in subdirectories.
                False by default.
            context (Context): context
        """

        logger.info("Start loading.")

        self._parse_input(input_dir, input_files, exclude_hidden, recursive, context)

        # 1. 获取全量待处理文件，为每一个文件生成一个Document对象，计算得到context的总文档数
        total_files: List[Path]
        total_documents: List[Document]
        if input_files:
            total_files, total_documents = self.get_total_files(input_files, exclude_hidden, context)

        elif input_dir:
            FileUtils.check_dir(input_dir)
            total_file_paths: List[str] = FileUtils.list_files(input_dir, recursive)
            total_files, total_documents = self.get_total_files(total_file_paths, exclude_hidden, context)
        else:
            raise ProcessorException(ErrorCode.PARAM_INVALID, "input_files and input_dir is none.")
        context.set_file_count(len(total_files))

        # 2. 筛选有效文件，和对应的Document对象。（文件存在且可读）
        valid_files: List[Path]
        valid_documents: List[Document]
        valid_files, valid_documents = self.get_valid_files(total_files, total_documents, context)

        logger.info("{} files to be loaded.".format(len(valid_files)))
        self.parse(valid_files, valid_documents, context)

    def parse(self, valid_files: List[Path], valid_documents: List[Document], context: Context):
        """parse"""
        for document, input_file in zip(valid_documents, valid_files):
            file_suffix: str = input_file.suffix.lower()
            context.update_id2name(document.get_doc_md5(), input_file.name)
            if file_suffix in self.file_extractor:
                logger.debug("start load and parser file={}".format(input_file.name))
                parser = self.file_extractor[file_suffix]
                parser(input_file, context=context, document=document)
            else:
                # 过滤不支持的后缀文件。
                ex = ProcessorException(
                    ErrorCode.UNSUPPORTED_FILE_FORMAT, "file suffix={} is not supported".format(file_suffix))
                msg = "file={} load failed, error_msg={}".format(
                    input_file.name, str(ex)
                )
                context.add_info_to_component(
                    ProcessorName.LOADER,
                    document.get_doc_md5(),
                    ex
                )
                logger.error(msg)

        logger.info("Finish loading.Parsed file count is {}".format(context.get_documents_count()))

    def _parse_config(self,
                      config: Optional[Dict],
                      file_extractor: Optional[Dict[str, DocumentBaseParser]],
                      ):
        """
        parse config
        """
        if config is not None and not isinstance(config, dict):
            raise ProcessorException(ErrorCode.CONFIG_INVALID, "config type is incorrect.")
        if file_extractor is not None and not isinstance(file_extractor, dict):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "file_extractor type is incorrect.")
        self.config = merge_internal_config(config)

    def _parse_input(self,
                     input_dir: Optional[str],
                     input_files: Optional[List],
                     exclude_hidden: bool,
                     recursive: bool,
                     context: Context
                     ):
        """
        parse config
        """
        CheckUtils.check_type(context, Context, "context")
        CheckUtils.check_type(exclude_hidden, bool, "exclude_hidden")
        CheckUtils.check_type(recursive, bool, "recursive")
        self._parse_context_input(context)
        doc_ids = context.get_input_kwarg_with_key("doc_id")
        if input_dir is not None and not isinstance(input_dir, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "input_dir type is incorrect.")

        if not input_dir and not input_files:
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "Must provide valid value either 'input_dir' or 'input_files'.")
        if input_dir and input_files:
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "'input_dir' and 'input_files' cannot be used at the same time.")
        if input_files is not None:
            CheckUtils.check_type(input_files, list, "input_files")
            for path in input_files:
                CheckUtils.check_type(path, str, "file path")
        # doc_ids 和 input_files 配合使用
        if doc_ids and input_files:
            if len(doc_ids) != len(input_files):
                raise ProcessorException(ErrorCode.PARAM_INVALID, "len(doc_ids) != len(input_files)")
        if input_dir:
            context.update_input_kwargs("doc_id", [])

    def _parse_context_input(self, context: Context):
        """parse context"""
        knowledge_base_name: str = context.get_knowledge_base_name()
        stream_type: StreamType = context.get_stream_type()
        verbose: bool = context.get_verbose()
        session_id = context.get_session_id()
        doc_ids = context.get_input_kwarg_with_key("doc_id")
        if knowledge_base_name is not None and not isinstance(knowledge_base_name, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "knowledge_base_name type is incorrect.")
        if stream_type is not None and not isinstance(stream_type, StreamType):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "stream_type type is incorrect.")
        if verbose is not None and not isinstance(verbose, bool):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "verbose type is incorrect.")
        if session_id is not None and not isinstance(session_id, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "session_id type is incorrect.")

        if not knowledge_base_name:
            context.set_knowledge_base_name(DEFAULT_KNOWLEDGE_BASE_NAME)
        if not stream_type:
            context.set_stream_type(StreamType.REAL)
        if not session_id:
            context.set_session_id("")

        if doc_ids:
            if isinstance(doc_ids, str):
                doc_ids = [doc_ids]
                context.update_input_kwargs("doc_id", doc_ids)
            elif isinstance(doc_ids, list):
                CheckUtils.is_all_type(doc_ids, str, "doc_id")
            else:
                raise ProcessorException(ErrorCode.TYPE_ERROR, "doc_ids type is incorrect.")
        else:
            context.update_input_kwargs("doc_id", [])
