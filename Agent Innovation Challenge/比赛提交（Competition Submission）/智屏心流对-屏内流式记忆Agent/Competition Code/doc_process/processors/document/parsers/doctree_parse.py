# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing parsers to build doctree for files."""
import copy
import re
from pathlib import Path
from typing import Any, Dict, Optional
from zipfile import BadZipFile

from doc_process.config_repository.config import merge_internal_config
from doc_process.processors.document.parsers.doc_base import DocumentBaseParser
from doc_process.processors.document.parsers.doctree_build.abs_builder import ABSBuilder
from doc_process.processors.document.parsers.doctree_build.html_builder import HTMLBuilder
from doc_process.processors.document.parsers.doctree_build.plain_builder import PlainBuilder
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import Node, LabelDict, TableSep
from doc_process.utils import logging
from doc_process.context.doc_schema import DocNode, Document, Context
from doc_process.context.doc_schema import TextContent, TableContent
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.file_utils import FileUtils
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class DoctreeBaseParser(DocumentBaseParser):
    """ Parse file to Document based on doctree_builder """
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )
    doctree_builder: Optional[ABSBuilder] = Field(
        None,
        description="builder: construct raw doctree from file path"
    )

    class Config:
        """ config object """
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super(DoctreeBaseParser, self).__init__(**kwargs)
        logger.info("Parser: {} init start.".format(self.__class__.__name__))
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)
        self._parse_config(**kwargs)
        logger.info("Parser: {} init done.".format(self.__class__.__name__))

    def _parse_config(self, **kwargs):
        """ 依据config进行parser初始化 """
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    def _parse(self, file_path: Path, context: Context, **kwargs: Any):
        document: Document = kwargs.get("document")
        try:
            FileUtils.check_file(file_path, self.doctree_builder.cfg.file_size_limit)
            doc_tree, parse_context = self.doctree_builder.build(file_path)
            root = self._convert_doc_node(doc_tree.root_node)
            for i, doc_node in enumerate(root.flat_with_children()):
                doc_node.id = str(i)
            metadata = kwargs.get("metadata", {})
            metadata["parse_context"] = parse_context
            document.set_doc_title(file_path.name)
            document.set_root(root)
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

    def _convert_doc_node(self, node: Node):
        """ convert doctree_build title node to DocNode with structure """
        if node.label not in LabelDict.TITLE:
            return self._convert_node_to_content(node)
        chain_nodes = [node]
        while chain_nodes[0].parent:
            chain_nodes.insert(0, chain_nodes[0].parent)
        chapter = [node.text for node in chain_nodes]
        children = [self._convert_doc_node(child_node) for child_node in node.children if child_node.label]
        children_nodes = [child for child in children if isinstance(child, DocNode)]
        content = [child for child in children if not isinstance(child, DocNode)]
        doc_node = DocNode(id="", chapter=chapter, content=content, parent=None, children=children_nodes)
        for child_docnode in children_nodes:
            child_docnode.parent = doc_node
        return doc_node

    def _convert_node_to_content(self, node: Node):
        """ convert doctree_build node to BaseContent"""
        if node.label == LabelDict.CONTENT:
            return TextContent(content=node.text)
        if node.label == LabelDict.TABLE:
            m = re.match(
                "({})(.*)({})(.*)({})".format(TableSep.START, TableSep.NAME_SEP, TableSep.END),
                node.text.replace("\n", "")
            )
            if not m or len(m.groups()) != 5:
                logger.warning("Table match failed, node_id={}, node_text={}".format(node.id, node.text))
                return TextContent(content="")
            table_title = m.groups()[1]
            table_lines = m.groups()[3].split(TableSep.LINE)
            cell_2d_list = []
            for table_line in table_lines:
                cell_2d_list.append(table_line.split(TableSep.CELL))
            return TableContent(title=table_title, table=cell_2d_list)
        logger.error("Node label {} not supported.".format(node.label))
        raise ProcessorException(ErrorCode.PARSER_ERROR, "Node label {} not supported.".format(node.label))


class HTMLParser(DoctreeBaseParser):
    """ HTMLParser """

    def _parse_config(self, **kwargs):
        config = copy.deepcopy(self.config)
        self.config = self.config.get("parser", {}).get("html", {})
        self.doctree_builder = HTMLBuilder(self.config, **config)


class PlainTextParser(DoctreeBaseParser):
    """ PlainTextParser """

    def _parse_config(self, **kwargs):
        self.config = self.config.get("parser", {}).get("txt", {})
        self.doctree_builder = PlainBuilder(self.config, **kwargs)
