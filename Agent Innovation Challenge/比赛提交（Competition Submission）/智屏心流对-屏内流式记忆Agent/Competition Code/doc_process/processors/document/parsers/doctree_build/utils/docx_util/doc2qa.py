# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to parse docx file to text."""
import re
from typing import List, Union, Iterable, Tuple

import pandas as pd
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from doc_process.processors.document.parsers.doctree_build.utils.data_cls import TableSep
from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class Doc2QA:
    """从word文档中抽取出问答对

    """

    def __init__(self, doc_path: str) -> None:
        """

        Args:
            doc_path: 待进行解析的doc文档路径
            qa_save_path: 解析得到问答对的保存路径
        """
        self.doc_path = doc_path

    @staticmethod
    def get_docx_title_by_language(type_name, lang="zh"):
        """ get docx title prefix by language"""
        zh_title_dict = {
            "Table": "表",
            "Note": "说明",
            "Step": "步骤",
            "Caution": "注意"
        }
        if lang in ["zh", "ch"]:
            return zh_title_dict.get(type_name)
        return type_name

    @staticmethod
    def get_table_dataframe(table):
        """ convert table to DataFrame """
        data = []
        headers = []
        df = pd.DataFrame()
        # 读取表格内容
        try:
            for j, row in enumerate(table.rows):
                if j == 0:
                    # 读取表头
                    headers = [cell.text.strip() for cell in row.cells]
                else:
                    # 读取数据
                    data.append([cell.text.strip() for cell in row.cells])
            new_headers = []
            for _, header in enumerate(headers):
                if header not in new_headers:
                    new_headers.append(header)
                else:
                    new_headers.append(str(header) + " ")
                    # 转换为DataFrame

            df = pd.DataFrame(data, columns=new_headers)
            return df
        except Exception:
            logger.debug("Get table dataframe fail.")
        return df

    @staticmethod
    def iter_block_items(parent: Union[Document, _Cell]) -> Union[Iterable[Paragraph], Iterable[Table]]:
        """
        按文档顺序返回parent中的每个段落和表。每个返回值都是表或段落的实例。
        parent通常是对主文档对象的引用，但也适用于_Cell对象，该对象本身可以包含段落和表。

        Args:
            parent: 主文档对象或者_Cell对象，依次遍历parent的孩子节点，实现word文档的遍历

        Returns:

        Raises:
            ValueError: 当parent的类型不在["Document", "_Cell"]中时，报错
        """
        if isinstance(parent, Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent
        else:
            raise ProcessorException(ErrorCode.PARSER_ERROR, "something's not right")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    @classmethod
    def list_table2str(cls, list_table) -> str:
        """将列表形式存储的表格转成字符串"""
        if len(list_table) < 1:
            return ""
        table_lines = []
        for line in list_table:
            line = [cell or "" for cell in line]
            table_lines.append(TableSep.CELL.join(line))
        return TableSep.LINE.join(table_lines)

    @classmethod
    def check_table_name(cls, prev_block):
        """ check if prev block is talbe name """
        return prev_block and isinstance(prev_block[0], Paragraph) and prev_block[1] and not prev_block[1].startswith(
            "\001")

    @classmethod
    def check_catalogue(cls, heading_list, style):
        """ check if text is catalogue and need deletion """
        return style in ["toc 1", "目录 1"] and heading_list[-1] == 0 and heading_list[0] == 0

    @classmethod
    def process_special_texts(cls, step_number_list, style, text):
        """ process special texts """
        if style == "notes heading":
            return Doc2QA.get_docx_title_by_language("note")
        if style in ["note text list", "item list", "caution text list", "notes text list"]:
            return f"\t* {text}"
        if style in ["sub item list"]:
            return f"\t\t- {text}"
        if style == "step":
            step_number_list[0] = step_number_list[0] + 1
            step_number_list[1] = 0
            step_title = Doc2QA.get_docx_title_by_language("Step")
            return f"{step_title}{step_number_list[0]} {text}"
        if style == "item step":
            step_number_list[1] = step_number_list[1] + 1
            return f"\t{step_number_list[1]} {text}"
        if style == "End".lower():
            step_number_list[0] = 0
            step_number_list[1] = 0
            return ""
        if style == "notes heading":
            return Doc2QA.get_docx_title_by_language("Note")
        return text

    @classmethod
    def get_heading_level(cls, para, style):
        """ get heading level """
        heading_level = None
        regex = r"heading (\d?)"
        match_obj = re.match(regex, style)
        xml = para._p.xml
        if match_obj is not None:
            heading_level = int(match_obj.group(1))
        elif "<w:outlineLvl" in xml:
            beg = xml.find("<w:outlineLvl")
            end = xml.find(">", beg)
            heading_level = int(
                re.search("\\d+", xml[beg: end + 1]).group()) + 1
        return heading_level

    @classmethod
    def check_large_file(cls, config, doc):
        """限制超大文件"""
        if len(doc.paragraphs) > config.max_paragraph_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} paragraphs. "
                                     "Current paragraphs count: {} "
                                     .format(config.max_paragraph_limit, len(doc.paragraphs)))
        large_table = []
        for table in doc.tables:
            num_rows = len(table.rows)
            if num_rows > config.large_table_rows:
                large_table.append(num_rows)
            if num_rows > config.max_table_rows_limit:
                raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                         "File has exceeded the maximum limit of {} table_rows. "
                                         "Current table_rows count: {} "
                                         .format(config.max_table_rows_limit, len(table.rows)))
        if len(large_table) > config.max_large_table_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} large_table. "
                                     "Current large_table count: {} "
                                     .format(config.max_large_table_limit, len(large_table)))

    def parse_doc(self, **kwargs) -> str:
        """按序读取word文档解析生成问答对，对于文本和表格分开处理

        按序遍历word中的各个block，目前仅支持处理Paragraph(文本)和Table两种格式
        """
        config = kwargs.get("config", {})
        is_degrade = kwargs.get("is_degrade", True)
        with open(self.doc_path, "rb") as f_in:
            doc = docx.Document(f_in)
        if is_degrade:
            self.check_large_file(config, doc)

        result_text = []
        heading_list = [0] * 10
        step_number_list = [0, 0]
        prev_block = None
        num_tokens = 0
        for block in self.iter_block_items(doc):
            text = ""
            if isinstance(block, Paragraph):
                if not block.text.strip():
                    text = ""
                else:
                    text = self.parse_paragraph(block, heading_list, step_number_list)
                num_tokens += len(text)
            elif isinstance(block, Table):
                text, length_table_str = self.parse_table(block)
                num_tokens += length_table_str

            if is_degrade and num_tokens > config.max_token_limit:
                raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                         "File has exceeded the maximum limit of {} tokens. "
                                         "Current tokens count: {} "
                                         .format(config.max_token_limit, num_tokens))

            if not text.strip():
                prev_block = (block, text)
                continue
            # 对表格提取表格名称
            if isinstance(block, Table):
                text = self.get_table_name(prev_block, result_text, text)
            result_text.append(text)
            prev_block = (block, text)
        result_str = "\n".join(result_text)
        return result_str

    def get_table_name(self, prev_block, result_text, text):
        """提取表格名称"""
        table_name = ""
        if self.check_table_name(prev_block):
            table_name = prev_block[1]
        text = "\n".join([TableSep.START, table_name, TableSep.NAME_SEP, text, TableSep.END])
        if len(result_text) > 0 and table_name == result_text[-1]:
            result_text.pop()
        return text

    def parse_table(self, table: Table) -> Tuple[str, int]:
        """将word中的表格转成2维数组形式

        在转markdown的过程中，需要根据self.cur_question是否为空，决定是否保留该表格
        - 如果self.cur_question为空，表明当前问题对应的答案中包含图片等暂不支持信息，则舍弃表格信息
        - 如果self.cur_question不为空，表明该问答对可用，保留表格信息

        Args:
            table: word文档中的Table对象，保存了表格信息

        Returns:

        """
        df = self.get_table_dataframe(table)
        columns = df.columns.values.tolist()
        table_list = df.values.tolist()
        table_list.insert(0, columns)
        length_table_str = len("".join(sum(table_list, [])))
        table_text = self.list_table2str(table_list)
        black_list = [
            "修订记录",
            "修改记录",
            "华为技术有限公司为客户提供全方位的技术支持",
            "版权所有 侵权必究",
            "Copyright © Huawei Technologies Co., Ltd.",
            "HUAWEI TECHNOLOGIES CO., LTD.",
            "修订版本",
            "拟制",
            "初稿完成",
            "Revise Records",
            "对此文档的权限当前受到限制。只有使用 Microsoft Office 2003 或更高版本才能打开该文档。",
            "文档版本",
            "No part of this document may be reproduced or transmitted in any form or "
            "by any means without prior written consent of"
        ]
        for black in black_list:
            if re.search(black, table_text):
                return "", length_table_str
        return table_text, length_table_str

    def parse_paragraph(self, para: Paragraph, heading_list: List, step_number_list: List):
        """根据样式补充章节名称

        Args:
            p: docx文档中的段落对象

        Returns:
        :param step_number_list:
        :param table_number_list:
        :param heading_list:
        :param para:

        """
        text = para.text
        para_style = para.style
        if para_style is None:
            return text
        style_name = para_style.name
        if style_name is None:
            return text
        style = str(style_name).lower()
        if style == "contents":
            return "---Contents---"

        # 删除目录信息
        if str(style).lower().startswith("toc") or str(style).startswith("目录"):
            regex = r"^(\d+) "
            if self.check_catalogue(heading_list, style):
                match_obj = re.search(regex, text)
                if match_obj:
                    heading_list[-1] = int(match_obj.group())
            return ""
        for starts_with_str in ["目录", "table of figures", "封面"]:
            if style.startswith(starts_with_str):
                return ""

        # 删除摘要信息
        if style in ["摘要", "figure description", ""]:
            return ""

        # 处理表格描述文本
        if style == "table description":
            return f"{Doc2QA.get_docx_title_by_language('Table')} {text}"

        # 处理标题序号
        heading_level = self.get_heading_level(para, style)

        if heading_level is not None:
            step_number_list[0] = 0
            step_number_list[1] = 0
            if heading_level > 3:
                return text

            # 避免heading从2开始
            if heading_list[-1] != 0 and heading_list[0] == 0:
                if heading_level == 1:
                    heading_list[0] = heading_list[-1]
            else:
                heading_list[heading_level - 1] += 1

            for index in range(heading_level, len(heading_list)):
                heading_list[index] = 0

            if heading_list[0] == 0:
                return text

            tag = "\001" * heading_level
            text = tag + text + tag
            return text

        return self.process_special_texts(step_number_list, style, text)
