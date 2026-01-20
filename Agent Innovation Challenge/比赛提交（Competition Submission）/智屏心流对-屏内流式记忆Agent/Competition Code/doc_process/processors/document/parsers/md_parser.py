# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
from typing import List
import re

from doc_process.processors.document.parsers.doc_default_parser import DocumentDefaultParser
from doc_process.context.doc_schema import TextContent, TableContent
from doc_process.context.doc_schema import DocNode, Document
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_DEGRADE_ENABLE
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class MDParser(DocumentDefaultParser):
    """ MDParser """

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        return ".md"

    @classmethod
    def build_md_nodes(cls, text, file_title):
        """build markdown nodes with multi-level chapter"""
        lines = cls.repl_code(text.split('\n'))
        nodes = [DocNode(id="", chapter=[file_title], title_level=0, content=[], parent=None, children=[])]
        txt = ""
        cell_2d_list = []
        chap_stack = [(0, file_title)]
        i = 0
        while i < len(lines):
            line = lines[i]
            # 表格
            table_line = re.match(r'^\|(.*?)\|$', re.sub(r'^\s{1,3}', '', lines[i]).rstrip())
            next_line = "" if i == len(lines) - 1 else re.match(r'^\|(.*?)\|$',
                                                                re.sub(r'^\s{1,3}', '',
                                                                       lines[i + 1]).rstrip() if i != len(
                                                                    lines) - 1 else "")
            if table_line:
                cell_2d_list.append([s.strip() for s in table_line.group(1).split('|')])
                txt = txt + line
                cell_2d_list, txt = cls.probable_table_util(cell_2d_list, next_line, nodes, txt)
                i += 1
                continue
            # 标题等级
            title_level, title = cls.get_title_level(line)
            if title_level != -1:
                while title_level <= chap_stack[-1][0]:
                    chap_stack.pop()
                chap_stack.append((title_level, title))
                node = DocNode(id='', parent=None, children=[], title_level=title_level, content=[],
                               chapter=[tup[1] for tup in chap_stack])
                nodes.append(node)
            # 正文
            elif line:
                nodes[-1].content.append(TextContent(content=line))
            i += 1
        # DocNode.id
        for i, node in enumerate(nodes):
            node.id = i
        return nodes

    @classmethod
    def probable_table_util(cls, cell_2d_list, next_line, nodes, txt):
        """表格内容添加为TableContent, 非表格内容添加为TextContent"""
        if not next_line:
            if cls.is_md_table(cell_2d_list):
                cell_2d_list.pop(1)
                nodes[-1].content.append(TableContent(table=cell_2d_list))
            else:
                nodes[-1].content.append(TextContent(content=txt))
            cell_2d_list = []
            txt = ""
        return cell_2d_list, txt

    @classmethod
    def get_title_level(cls, text):
        """ get title level by pattern match """
        match = re.match(r'^(#{1,6})\s+(.+)$', text)                    # md标题共6层级
        title_level, title = (len(match.group(1)), text.lstrip('#').lstrip()) if match else (-1, text)
        return title_level, title

    @classmethod
    def is_md_table(cls, cell_2d_list: List):
        """ check if list is md table """
        for cell in cell_2d_list[1]:
            if set(cell) == {'-'}:
                continue
            return False
        return True

    @classmethod
    def chaos_mark(cls, block_idx, lines, pre, follow):
        """ code block alternative mark with ``` and ~~~ """
        if len(pre) == 1:
            block_idx.append((pre[0], len(lines)))
        else:
            block_idx.append((pre[0], pre[1]))
            count = 0
            for mid in follow:
                if block_idx[-1][0] < mid < block_idx[-1][1]:
                    count += 1
            del follow[:count]
            del pre[:2]

            if pre and follow:
                pre_rest = pre if pre[0] < follow[0] else follow
                fol_rest = follow if follow[0] > pre[0] else pre
                block_idx = cls.chaos_mark(block_idx, lines, pre_rest, fol_rest)
            else:
                block_idx = cls.single_mark(block_idx, lines, pre) if pre else block_idx
                block_idx = cls.single_mark(block_idx, lines, follow) if follow else block_idx
        return block_idx

    @classmethod
    def single_mark(cls, block_idx, lines, codes):
        """ code block mark only with ``` or ~~~ """
        block_idx.extend(list(zip(codes[::2], codes[1::2])))
        if len(codes) % 2 != 0:
            block_idx.append((codes[-1], len(lines)))
        return block_idx

    @classmethod
    def repl_code(cls, lines):
        """ recognizer code blocks and replace # in code blocks"""
        # 1 两行```中间; 2 两行~~~中间; 3 ```bash ```shell ```toml ```python ```sh和```之间
        code_backquote = [i for i, line in enumerate(lines) if line == '```']
        code_tidle = [i for i, line in enumerate(lines) if line == '~~~']
        code_backquote_add = [i for i, line in enumerate(lines) if re.match('^```.+', line)]
        code_tidle_add = [i for i, line in enumerate(lines) if re.match('^~~~.+', line)]

        block_idx = []
        # ```bash和```之间
        for start in code_backquote_add:
            for end in code_backquote:
                if end > start:
                    block_idx.append((start, end))
                    code_backquote.remove(end)
                    break
        # ~~~bash和~~~之间
        for start in code_tidle_add:
            for end in code_tidle:
                if end > start:
                    block_idx.append((start, end))
                    code_tidle.remove(end)
                    break
        # ```之间 ~~~之间
        if code_backquote and code_tidle:
            pre = code_backquote if code_backquote[0] < code_tidle[0] else code_tidle
            follow = code_backquote if code_backquote[0] > code_tidle[0] else code_tidle
            block_idx = cls.chaos_mark(block_idx, lines, pre, follow)
        elif code_backquote:
            block_idx = cls.single_mark(block_idx, lines, code_backquote)
        elif code_tidle:
            block_idx = cls.single_mark(block_idx, lines, code_tidle)
        elif not block_idx:
            return lines

        # 代码行‘# 注释信息’替换标识符
        for (start, end) in block_idx:
            codes = lines[start + 1: end]
            for c, code_row in enumerate(codes):
                if re.match(r'^(#{1,6})\s+(.+)$', code_row):
                    lines[start + 1 + c] = "\\" + code_row
        return lines

    def decode_file(self, path):
        """ decode md file """
        for decode_type in self.cfg.decode_type:
            try:
                with open(path, "r", encoding=decode_type) as md_file:
                    text_result = md_file.read()
                    self.check_large_file(text_result)
                return text_result
            except UnicodeDecodeError:
                logger.debug("File {} parse by decode_type={} fail.".format(path.name, decode_type))
        raise ProcessorException(ErrorCode.FILE_READ_ERROR, "File {} read fail.".format(path.name))

    def check_large_file(self, text_result):
        """限制超大文件"""
        if self.degrade and len(text_result) > self.cfg.max_token_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} tokens. "
                                     "Current tokens count: {} "
                                     .format(self.cfg.max_token_limit, len(text_result)))

    def read_from_path(self, path):
        """ read from file """
        text_result = self.decode_file(path)
        doc_nodes = self.build_md_nodes(text_result, path.stem)
        doc_tree = Document.tree_from_nodes(doc_nodes)
        return doc_tree, {}

    def _parse_config(self, **kwargs):
        self.degrade = self.config.get("degrade", {}).get("enable", DEFAULT_DEGRADE_ENABLE)
        self.config = self.config.get("parser", {}).get("md", {})

    def _check_cfg(self, cfg):
        """ check config """
        CheckUtils.check_type(cfg.decode_type, list, "parser.md.decode_type")
        CheckUtils.check_type(cfg.max_token_limit, int, "parser.md.max_token_limit")
        CheckUtils.check_types(cfg.file_size_limit, [int, float], "parser.md.file_size_limit")
        if len(cfg.decode_type) <= 0:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "'decode_type' is empty.")
        for decode_type in cfg.decode_type:
            CheckUtils.check_type(decode_type, str, "parser.md.decode_type")
