# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to label and merge file Nodes."""
import re
from typing import List
import pdfplumber

from doc_process.processors.document.parsers.doctree_build.utils.node_util import get_loc_intersection, group_nodes_by_pageid
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import Node, TableSep
from doc_process.processors.document.parsers.doctree_build.utils.util import check_zh
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_schema import DocNode, TextContent, TableContent, ChunkType
from doc_process.context.doc_constants import OUTLINE_MIN_TH, MAX_CONTINUOUS_TITLE, TITLE_APPEAR_PATTERN


class LayoutLabel:
    """ layout labels mapping """
    TEXT = "text"
    TITLE = "title"
    FIGURE = "figure"
    FIGURE_CAPTION = "figure caption"
    TABLE = "table"
    TABLE_CAPTION = "table caption"
    HEADER = "header"
    FOOTER = "footer"
    REFERENCE = "reference"
    EQUATION = "equation"

    @classmethod
    def get_all_labels(cls):
        """ get all layout labels """
        return [
            cls.TEXT, cls.TITLE, cls.FIGURE, cls.FIGURE_CAPTION, cls.TABLE, cls.TABLE_CAPTION,
            cls.HEADER, cls.FOOTER, cls.REFERENCE, cls.EQUATION
        ]


def fill_nodes_by_size(nodes, fill_label=None):
    """ fill label by labels of nodes with same size """
    size_label_mapping = {}
    for node in nodes:
        if not node.label:
            continue
        size_label_mapping[node.size] = size_label_mapping.get(node.size, []) + [node.label]
    # 若某个大小的字体对应多个label，则从mapping中删除
    size_label_mapping = {size: labels[0] for size, labels in size_label_mapping.items() if len(labels) == 1}
    if fill_label is not None:
        size_label_mapping = {size: label for size, label in size_label_mapping.items() if label == fill_label}
    for _, node in enumerate(nodes):
        if node.label:
            continue
        size_label = size_label_mapping.get(node.size)
        if size_label:
            node.label = size_label


class Labeler:
    def __init__(self, config):
        self.config = config


class ModelLayoutLabeler(Labeler):
    """ layout labeler for node label based on regex match (update node.layout_label)"""
    def run(self, nodes: List[Node]):
        """  layout labeler for node label layout_model_label """
        for _, node in enumerate(nodes):
            if node.layout_model_label:
                node.label = node.layout_model_label


class RegexLayoutLabeler(Labeler):
    """ layout labeler for node label based on regex match """
    def run(self, nodes: List[Node]):
        """ label labyout by regex match """
        for _, node in enumerate(nodes):
            if node.label:
                continue
            # 根据正则规则更新label
            if re.match(self.config.table_capion_pattern, node.text):
                node.label = LayoutLabel.TABLE_CAPTION
            elif re.match(self.config.figure_caption_pattern, node.text):
                node.label = LayoutLabel.FIGURE_CAPTION
            elif re.match(self.config.page_pattern, node.text):
                node.label = LayoutLabel.FOOTER


class SizeLayoutLabeler(Labeler):
    """ layout labeler for node label based on text size """
    def run(self, nodes: List[Node]):
        """ label layout by size """
        fill_nodes_by_size(nodes)


class SimpleTitleLabeler(Labeler):
    """ title labeler for node label (update node.layout_label)"""
    def check_title_len(self, title_text):
        """ check if title len meet requirement """
        if check_zh(title_text):
            return len(re.sub("[a-zA-Z]", "", title_text)) <= self.config.title_max_len[0]
        return len(title_text) <= self.config.title_max_len[1]

    def run(self, nodes: List[Node]):
        """  """
        for _, node in enumerate(nodes):
            if node.label:
                continue
            # 若文本长度太长，则不考虑其是title的情况
            if not self.check_title_len(node.text):
                continue
            # 根据layout模型结果更新title label
            if node.layout_model_label == LayoutLabel.TITLE:
                node.label = LayoutLabel.TITLE
            # 根据正则规则更新title label
            if re.match(self.config.title_pattern, node.text) and not \
                    re.findall(self.config.title_ignore_pattern, node.text):
                node.label = LayoutLabel.TITLE

        fill_nodes_by_size(nodes, LayoutLabel.TITLE)

        title_nodes = [node for node in nodes if node.label == LayoutLabel.TITLE]

        self._filter_title_by_size_unique(title_nodes)

        self.assign_title_level(title_nodes)

    def assign_title_level(self, title_nodes):
        """ adjust title level of label """
        if len(title_nodes) == 0:
            return
        title_with_patterns = []
        for _, title_node in enumerate(title_nodes):
            title = title_node.text
            pattern_idx = self.get_title_pattern(title)
            title_with_patterns.append([title_node, pattern_idx])
        title_with_patterns.sort(key=lambda x: (-x[0].size, x[1][0], x[1][1]))
        title_groups = [[title_with_patterns[0]]]
        #
        for title_with_pattern in title_with_patterns[1:]:
            if title_groups[-1][-1][1][0] == -1 \
                    or (title_groups[-1][-1][1] == title_with_pattern[1]
                        and title_groups[-1][-1][0].size == title_with_pattern[0].size):
                title_groups[-1].append(title_with_pattern)
            else:
                title_groups.append([title_with_pattern])

        for i, group in enumerate(title_groups):
            for title_with_pattern in group:
                title_with_pattern[0].title_level = i + 1

    def get_title_pattern(self, title):
        """ match title pattern """
        m = re.search(self.config.title_pattern, title)
        pattern_idx = [-1, 0]
        if m:
            title_prefix = "".join(m.groups()[:-1])
            for i, pattern in enumerate(self.config.title_rank_pattern):
                ms = re.findall(pattern, title_prefix)
                if ms:
                    pattern_idx = [i, len(ms)]
        return pattern_idx

    def _filter_title_by_size_unique(self, title_nodes):
        """ size只出现过一次title的忽略 """
        title_sizes = {}
        for node in title_nodes:
            title_sizes[node.size] = title_sizes.get(node.size, []) + [node]
        for _, size_nodes in title_sizes.items():
            if len(size_nodes) == 1:
                size_nodes[0].label = None
                title_nodes.remove(size_nodes[0])


class OriOutlineTitleLabeler(Labeler):
    """ update node label from extracted outline """

    @classmethod
    def continuous_title_label_revert(cls, continuous_title):
        """连续多个title, label转换为text"""
        if len(continuous_title) > MAX_CONTINUOUS_TITLE:
            for n in continuous_title:
                n.label = "text"

    def run(self, nodes: List[Node], path):
        """ update node label """
        outline = self.get_outline(path)
        if outline:
            self.nodes_with_outline(nodes, outline)

    def get_outline(self, path):
        """ extract outline of a file """
        outline_res = []
        try:
            with pdfplumber.open(path) as pdf:
                for outline in pdf.doc.get_outlines():
                    outline_res.append(outline[:2])
            if len(outline_res) <= OUTLINE_MIN_TH:
                return []
        except Exception:
            return []
        return outline_res

    def is_ambiguous_title(self, content, outline):
        """ match possible title from node and outline """
        long_str = content if len(content) >= len(outline) else outline
        short_str = outline if len(content) >= len(outline) else content
        for i in range(len(long_str) - len(short_str) + 1):
            if short_str == long_str[i: i + len(short_str)]:
                # 除中间重合部分，左右多余字符需满足正则
                extra = long_str[0:i] + long_str[i + len(short_str):]
                if re.match(TITLE_APPEAR_PATTERN, extra.strip().rstrip('.')):
                    return True
        return False

    def is_continuous_title(self, content, outline):
        """ match possible title from node and outline """
        long_str = content if len(content) >= len(outline) else outline
        short_str = outline if len(content) >= len(outline) else content
        for i in range(len(long_str) - len(short_str) + 1):
            if short_str == long_str[i: i + len(short_str)]:
                # 除中间重合部分，左边多余字符需满足正则
                extra = long_str[0:i]
                if re.match(TITLE_APPEAR_PATTERN, extra.strip().rstrip('.')):
                    return True
        return False


    def nodes_with_outline(self, nodes, outline):
        """ get node label from outline title """
        for _, node in enumerate(nodes):
            for title_level, title in outline:
                node_str = self.clean_space(node.text)
                title_str = self.clean_space(title)
                if (node_str == title_str or
                        self.is_ambiguous_title(node_str, title_str)):
                    node.label = LayoutLabel.TITLE
                    node.title_level = title_level
                    break
        self.avoid_continuous_title_page(nodes, outline)

    def avoid_continuous_title_page(self, nodes, outline):
        """连续多个node匹配为outline标题, 可能是目录页, 去除"""
        continuous_title = []
        outline_titles = {self.clean_space(title) for _, title in outline}
        node_count = len(nodes)

        for i in range(node_count):
            node_str = self.clean_space(nodes[i].text)

            for outline_title in outline_titles:

                if node_str in outline_titles or self.is_continuous_title(node_str, outline_title):
                    continuous_title.append(nodes[i])

                if (i + 1 == node_count) or (
                        node_str not in outline_titles and not self.is_continuous_title(node_str, outline_title)):
                    self.continuous_title_label_revert(continuous_title)
                    continuous_title = []

    def clean_space(self, text):
        """clean spaces between text"""
        text = re.sub(r'\u0020|\s+|\u3000| |\xa0|\u00A0|\u2002|\u2003', '', text)
        return text



class RegexTitleLabeler(Labeler):
    def run(self, nodes: List[Node]):
        """ """
        ...


class RuleTitleLabeler(Labeler):
    def run(self, nodes: List[Node]):
        """ """
        ...


class LayoutLabelPipeline:
    """ layout labeler for node label and merge """
    def __init__(self, config, layout_recognizer):
        self.check_config(config)
        self.layout_recognizer = layout_recognizer
        if not config.title_senior_mode:
            self.layout_labelers = [
                ModelLayoutLabeler(config),
                SimpleTitleLabeler(config),
                RegexLayoutLabeler(config),
                SizeLayoutLabeler(config)
            ]
        else:
            self.layout_labelers = [
                ModelLayoutLabeler(config),
                OriOutlineTitleLabeler(config),
                RegexTitleLabeler(config),
                RuleTitleLabeler(config),
                RegexLayoutLabeler(config),
                SizeLayoutLabeler(config)
            ]
        self.config = config

    @classmethod
    def check_config(cls, cfg):
        """ check config """
        CheckUtils.check_type(cfg.title_senior_mode, bool)

        CheckUtils.check_type(cfg.overlap_ratio_th, float)
        CheckUtils.check_range(cfg.overlap_ratio_th, min_open=0, max_open=1)

        CheckUtils.check_iter(cfg.ignore_labels)
        for label in cfg.ignore_labels:
            CheckUtils.check_type(label, str)

        CheckUtils.check_regex(cfg.table_capion_pattern)
        CheckUtils.check_regex(cfg.figure_caption_pattern)
        CheckUtils.check_regex(cfg.title_pattern)
        CheckUtils.check_regex(cfg.title_ignore_pattern)
        CheckUtils.check_iter(cfg.title_rank_pattern)
        for pattern in cfg.title_rank_pattern:
            CheckUtils.check_regex(pattern)
        CheckUtils.check_regex(cfg.page_pattern)

        CheckUtils.check_iter(cfg.title_max_len, 2)
        for th in cfg.title_max_len:
            CheckUtils.check_type(th, int)
            CheckUtils.check_range(th, min_open=0)

        CheckUtils.check_type(cfg.min_table_cell_num, int)
        CheckUtils.check_range(cfg.min_table_cell_num, min_open=0)

    @classmethod
    def build_table_content(cls, table_nodes):
        """ """
        if len(table_nodes) == 1 and (TableSep.CELL in table_nodes[0].text or TableSep.LINE in table_nodes[0].text):
            # pdfplumber工具提取到的二维表格
            table_lines = table_nodes[0].text.split(TableSep.LINE)
            tables = [table_line.split(TableSep.CELL) for table_line in table_lines]
            return tables
        # 其他没有提取到结构的表格
        return [[node.text for node in table_nodes]]

    @classmethod
    def is_table_node(cls, node):
        """ """
        return node.label in [LayoutLabel.TABLE, LayoutLabel.TABLE_CAPTION]

    @classmethod
    def get_and_update_chap(cls, chap_stack, title_text, title_level):
        """ """
        while title_level <= chap_stack[-1][0]:
            chap_stack.pop()
        chap_stack.append((title_level, title_text))
        chap = [tup[1] for tup in chap_stack]
        return chap


    def label_one_page(self, page_nodes, page_layouts):
        """ label nodes in one page by layout """
        for node in page_nodes:
            label, max_overlap_ratio = None, 0
            for layout in page_layouts:
                inter_area, node_area, layout_area = get_loc_intersection(node.loc, layout.get("bbox"))
                overlap_ratio = max(inter_area / (node_area + 1e-10), inter_area / (layout_area + 1e-10))
                if overlap_ratio > max_overlap_ratio:
                    label, max_overlap_ratio = layout.get("type"), overlap_ratio
            if max_overlap_ratio > self.config.overlap_ratio_th:
                node.layout_model_label = label

    def run(self, nodes, file_path):
        """ label nodes and merge neighbor nodes with same labels """
        layouts = self.layout_recognizer(file_path)

        # 根据layout更新layout_model_label
        page_nodes_list = group_nodes_by_pageid(nodes)
        for page_nodes, page_layouts in zip(page_nodes_list, layouts):
            self.label_one_page(page_nodes, page_layouts)

        for layout_labeler in self.layout_labelers:
            if isinstance(layout_labeler, OriOutlineTitleLabeler):
                layout_labeler.run(nodes, file_path)
            else:
                layout_labeler.run(nodes)

        # 未贴标签的node视作text
        for node in nodes:
            if not node.label:
                node.label = LayoutLabel.TEXT

        # 根据label过滤
        informative_nodes = [node for node in nodes if node.layout_model_label not in self.config.ignore_labels]
        if not informative_nodes:
            return []

        doc_nodes = self.construct_doc_nodes(informative_nodes, file_path)

        return doc_nodes

    def construct_doc_nodes(self, nodes, file_path):
        """ """
        root_node = DocNode(id="", chapter=[file_path.stem], title_level=0, content=[], parent=None, children=[])
        chap_stack = [(0, root_node.chapter[-1])]

        # merge table nodes
        docnodes = [root_node]
        content_nodes = []
        for node in nodes:
            if node.label == LayoutLabel.TITLE:
                docnodes[-1].content = self.merge_contents(content_nodes)
                title_level = node.title_level
                chap = self.get_and_update_chap(chap_stack, node.text.replace("\n", ""), title_level)
                docnodes.append(DocNode(id='', parent=None, children=[],
                                        title_level=title_level, content=[], chapter=chap))
                content_nodes = []
            else:
                content_nodes.append(node)
        if content_nodes:
            docnodes[-1].content = self.merge_contents(content_nodes)

        for i, doc_node in enumerate(docnodes):
            doc_node.id = str(i)

        return docnodes

    def merge_contents(self, nodes):
        """ """
        if not nodes:
            return []
        # nodes to groups (table/text)
        node_groups = [[nodes[0]]]
        node_type = ChunkType.TABLECONTENT if self.is_table_node(nodes[0]) else ChunkType.TEXTCONTENT
        for node in nodes[1:]:
            if self.is_table_node(node) and node_type == ChunkType.TABLECONTENT:
                node_groups[-1].append(node)
            elif not self.is_table_node(node) and node_type == ChunkType.TEXTCONTENT:
                node_groups[-1].append(node)
            else:
                node_type = ChunkType.TABLECONTENT if self.is_table_node(node) else ChunkType.TEXTCONTENT
                node_groups.append([node])

        # merge nodes
        contents = []
        for node_group in node_groups:
            if self.is_table_node(node_group[0]):
                table_title = " ".join([node.text for node in node_group if node.label == LayoutLabel.TABLE_CAPTION])
                table_nodes = [node for node in node_group if node.label == LayoutLabel.TABLE]
                tables = self.build_table_content(table_nodes)
                contents.append(TableContent(title=table_title, table=tables))
            else:
                text = "\n".join([node.text for node in node_group])
                contents.append(TextContent(content=text))

        return contents
