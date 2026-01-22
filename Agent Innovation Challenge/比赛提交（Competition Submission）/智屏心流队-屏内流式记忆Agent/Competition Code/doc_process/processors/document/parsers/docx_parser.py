# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import re

from doc_process.processors.document.parsers.doc_default_parser import DocumentDefaultParser
from doc_process.processors.document.parsers.doctree_build.utils.docx_util.doc2qa import Doc2QA
from doc_process.processors.document.parsers.doctree_build.utils.clean_util.base_clean_handler import BaseCleanHandler
from doc_process.processors.document.parsers.doctree_build.utils.title_util import find_title, find_sub_title, find_third_title
from doc_process.context.doc_schema import TextContent, TableContent
from doc_process.context.doc_schema import DocNode, Document
from doc_process.utils import logging
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import TableSep
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_DEGRADE_ENABLE

logger = logging.get_logger()


class DocxParser(DocumentDefaultParser):
    """ DocxParser """
    def __init__(self, **kwargs):
        super(DocxParser, self).__init__(**kwargs)

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        return ".docx"

    @classmethod
    def build_docx_nodes(cls, text, fnm):
        """ build node list from text """
        lines = text.split("\n")
        nodes = [DocNode(id="", chapter=[fnm], title_level=0, content=[], parent=None, children=[])]
        chap_stack = [(0, fnm)]
        table_starts = [i for i, line in enumerate(lines) if line == TableSep.START]
        table_ends = [i for i, line in enumerate(lines) if line == TableSep.END]
        # 表格首尾数量不一致时，不进行表格提取
        if len(table_starts) != len(table_ends):
            table_starts, table_ends = [], []
            lines = [line for line in lines if line not in TableSep.get_all_tablesep()]
        i = 0
        while i < len(lines):
            if i in table_starts:
                # table
                table_text = "\n".join(lines[i: table_ends[table_starts.index(i)] + 1])
                table_name, table_2d_list = cls.convert_2d_list(table_text)
                nodes[-1].content.append(TableContent(title=table_name if table_name else None, table=table_2d_list))
                i = table_ends[table_starts.index(i)] + 1  # skip table lines
                continue

            title_level, title = cls.get_title_level(lines[i])
            if title_level != -1:
                # title
                while title_level <= chap_stack[-1][0]:
                    chap_stack.pop()
                chap_stack.append((title_level, title))
                node = DocNode(id='', parent=None, children=[], title_level=title_level, content=[],
                               chapter=[tup[1] for tup in chap_stack])
                nodes.append(node)
            else:
                # content
                nodes[-1].content.append(TextContent(content=lines[i]))
            i += 1

        # udpate DocNode.id
        for i, node in enumerate(nodes):
            node.id = i
        return nodes

    @classmethod
    def get_title_level(cls, text):
        """ get title level by pattern match """
        titles = [find_third_title(text), find_sub_title(text), find_title(text)]
        for i, title in enumerate(titles):
            if not title:
                continue
            title_level = len(titles) - i
            return title_level, title
        return -1, text

    @classmethod
    def clean_txt(cls, tmp_text):
        """ clean text """
        tmp_text = cls.clean_blank_words(tmp_text)
        tmp_text = cls.clean_txt_before_content(tmp_text, "---Contents---")
        tmp_text = cls.delete_muti_blank(tmp_text)
        tmp_text = cls.clean_txt_by_replace(tmp_text)
        tmp_text = cls.delete_blank_line(tmp_text)
        tmp_text = cls.clean_txt_after_sentence(
            tmp_text, r"(\d(\.)?)+[ ]?参考文献$")
        return tmp_text

    @classmethod
    def clean_blank_words(cls, text):
        """ clean blank words """
        blank_list = [
            r"[\u3000]+", r"[\ufeff]+",
            r"[\uf070]+", r"[\xa0]+", r"[\u200e]+"
        ]
        new_text = text
        for blank in blank_list:
            new_text = re.sub(blank, "", new_text)
        return new_text

    @classmethod
    def clean_txt_before_content(cls, text, regex_str):
        """ clean text before content """
        if regex_str == "" or str(regex_str).strip() == "":
            return text
        lines = text.splitlines(True)
        result_index = -1
        for i, line in enumerate(lines):
            match_result = re.match(regex_str, line.strip())
            if match_result:
                result_index = i
        if result_index == -1:
            return text
        result_lines = lines[result_index + 1:]
        return "".join(result_lines)

    @classmethod
    def delete_muti_blank(cls, tmp_text):
        """ delete multi blank """
        lines = tmp_text.splitlines()
        new_lines = []
        for _, line in enumerate(lines):
            new_line = re.sub("目[ ]+录", "目录", line)
            new_line = re.sub("前[ ]+言", "前言", new_line)
            new_line = re.sub("摘[ ]+要", "摘要", new_line)
            new_line = new_line.replace(u"\xa0", "")
            if new_line != "":
                new_lines.append(new_line)
        return "\n".join(new_lines)

    @classmethod
    def clean_txt_by_replace(cls, tmp_text):
        """ clean txt by replace """
        error_infos = [
            "版权所有 © 华为技术有限公司", "华为专有和保密信息", "修订记录",
            "Copyright © Huawei Technologies Co., Ltd.", "Huawei Technologies Proprietary"
        ]
        for error_info in error_infos:
            tmp_text = str(tmp_text).replace(error_info, "")
        return tmp_text

    @classmethod
    def delete_blank_line(cls, text):
        """ delete blank line """
        # 将多个空行替换为单个空行
        new_text = re.sub("\n{2}", "\n", text)
        new_text = re.sub("\t", "", new_text)
        return new_text

    @classmethod
    def clean_txt_after_sentence(cls, text, clean_line):
        """ clean text after sentence """
        # 获取特定语句在文本中的索引位置
        lines = text.splitlines()
        result_index = cls.get_match_line_index(lines, clean_line)
        if result_index == -1:
            return text
        result_lines = lines[:result_index]
        return "\n".join(result_lines)

    @classmethod
    def get_match_line_index(cls, lines, sentence):
        """ get match line index """
        result_index = -1
        if sentence == "" or str(sentence).strip() == "":
            return result_index
        for i in range(len(lines)):
            cur_index = len(lines) - i - 1
            match_obj = re.match(sentence, lines[cur_index].strip())
            if match_obj:
                result_index = cur_index
                break
        return result_index

    @classmethod
    def convert_2d_list(cls, table_text):
        """ convert table_text to 2d list  """
        table_name = re.match(r'#TableSTART#([\s\S]*)#TableNameSEP#', table_text).group(1).strip()
        table_cnt = re.findall(r'#TableNameSEP#([\s\S]*)#TableEND#', table_text)
        table_2d_list = \
            [[cells.strip().split(TableSep.CELL) for cells in row.split(TableSep.LINE)] for row in table_cnt
             if table_cnt][0]
        return table_name, table_2d_list

    def read_from_path(self, path):
        """ read from file """
        doc_to_qa = Doc2QA(str(path))
        kwargs = {"config": self.cfg, "is_degrade": self.degrade}
        tmp_text = doc_to_qa.parse_doc(**kwargs)
        text_result = BaseCleanHandler.clean_txt_all(
            self.clean_txt(tmp_text))
        doc_nodes = self.build_docx_nodes(text_result, path.stem)
        doc_tree = Document.tree_from_nodes(doc_nodes)
        return doc_tree, {}

    def _parse_config(self, **kwargs):
        self.degrade = self.config.get("degrade", {}).get("enable", DEFAULT_DEGRADE_ENABLE)
        self.config = self.config.get("parser", {}).get("docx", {})

    def _check_cfg(self, cfg):
        """ check config """
        CheckUtils.check_type(cfg.large_table_rows, int, "parser.docx.large_table_rows")
        CheckUtils.check_type(cfg.max_large_table_limit, int, "parser.docx.max_large_table_limit")
        CheckUtils.check_type(cfg.max_table_rows_limit, int, "parser.docx.max_table_rows_limit")
        CheckUtils.check_type(cfg.max_paragraph_limit, int, "parser.docx.max_paragraph_limit")
        CheckUtils.check_type(cfg.max_token_limit, int, "parser.docx.max_token_limit")
        CheckUtils.check_types(cfg.file_size_limit, [int, float], "parser.docx.file_size_limit")
