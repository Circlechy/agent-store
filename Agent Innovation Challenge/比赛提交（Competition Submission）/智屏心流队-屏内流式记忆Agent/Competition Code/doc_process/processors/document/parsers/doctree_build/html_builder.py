# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to build doctree for .html file."""
import re

from bs4 import BeautifulSoup

from doc_process.processors.document.parsers.doctree_build.abs_builder import ABSBuilder
from doc_process.processors.document.parsers.doctree_build.utils.clean_util.base_clean_handler import BaseCleanHandler
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import Node, DocTree, LabelDict
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class HTMLBuilder(ABSBuilder):
    """ Doctree builder for .html file """

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        return ".html"

    @classmethod
    def extract_ctn_from_html(cls, content):
        """ extract content from html """
        soup = BeautifulSoup(content, "html.parser")
        body = soup.find("body")
        body = soup if body is None else body
        cont_texts = []
        # 正文
        for element in body.children:
            if not element.name or element.name.lower() in ["script", "style"]:
                continue
            str_value = element.text.strip().strip("\t")
            if str_value.strip() in ["无", "N/A", ""]:
                continue
            cont_texts.extend([s.strip().strip("\t") + "\n" for s in str_value.split("\n") if s])
        cont_text = "\n".join(cont_texts)
        text_content = re.sub(" +", " ", cont_text)

        # 处理nbsp空格问题
        text_content = text_content.replace("\xa0", " ")
        text_content = BaseCleanHandler.clean_txt_all(text_content)

        # 网页标题
        title = body.find("div", attrs={"class": "title"})
        title = title or soup.find("title")
        title_content = title.get_text().strip() if title else text_content.split("\n")[0]
        title_content = title_content or " ".join(text_content.split("\n")[:3])[:200]

        context = dict(title=title_content)

        return title_content, text_content, context

    def read_from_path(self, path):
        """ read from file """
        text_result = self.decode_file(path)
        title_content, text_content, context = self.extract_ctn_from_html(text_result)
        title_content_node = Node(text=title_content, label=LabelDict.TITLE[1])
        text_content_node = Node(text=text_content, label=LabelDict.CONTENT)
        doc_tree = DocTree.from_node_list([title_content_node, text_content_node], path.stem)
        return doc_tree, context

    def decode_file(self, path):
        """ decode html file """
        for decode_type in self.cfg.decode_type:
            try:
                with open(path, "r", encoding=decode_type) as html_file:
                    text_result = html_file.read()
                    soup = BeautifulSoup(text_result, "html.parser")
                    visible_text = ''.join(soup.get_text().split())
                    self.check_large_file(visible_text)
                return text_result
            except UnicodeDecodeError:
                logger.debug("File {} parse by decode_type={} fail.".format(path.name, decode_type))
        raise ProcessorException(ErrorCode.FILE_READ_ERROR, "File {} read fail.".format(path.name))

    def check_large_file(self, visible_text):
        """限制超大文件"""
        if self.degrade and len(visible_text) > self.cfg.max_token_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} tokens. "
                                     "Current tokens count: {} "
                                     .format(self.cfg.max_token_limit, len(visible_text)))

    def _check_cfg(self, cfg):
        """ check config """
        CheckUtils.check_type(cfg.decode_type, list, "parser.html.decode_type")
        CheckUtils.check_types(cfg.file_size_limit, [int, float], "parser.html.file_size_limit")
        if len(cfg.decode_type) <= 0:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "'decode_type' is empty.")
        for decode_type in cfg.decode_type:
            CheckUtils.check_type(decode_type, str, "parser.html.decode_type")
