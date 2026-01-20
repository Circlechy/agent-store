# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import re
from typing import Optional

from doc_process.context.doc_schema import Document, DocNode, TextContent
from doc_process.processors.document.parsers.doc_default_parser import DocumentDefaultParser
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import LabelDict, TableSep
from doc_process.processors.document.parsers.doctree_build.utils.node_util import group_nodes_by_pageid
from doc_process.processors.document.parsers.doctree_build.utils.pdf_utils.layout_label import LayoutLabelPipeline
from doc_process.processors.document.parsers.doctree_build.utils.pdf_utils.pdfplumber_parser import PdfplumberParser
from doc_process.processors.document.parsers.doctree_build.utils.util import check_zh
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_DEGRADE_ENABLE
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class PDFParser(DocumentDefaultParser):
    """ PDFParser """
    parser: Optional[PdfplumberParser] = Field(
        None,
        description="parser"
    )
    label_pipeline: Optional[LayoutLabelPipeline] = Field(
        None,
        description="label_pipeline"
    )

    def __init__(self, **kwargs):
        super(PDFParser, self).__init__(**kwargs)
        PdfplumberParser.set_class_variable(self.cfg.parser)
        self.parser = PdfplumberParser(self.cfg)
        layout_cfg = self.cfg.layout_label
        if layout_cfg.enable_mode not in ["all", "sci_paper", "close"]:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "Wrong pdf.layout_label.enable_mode '{}' "
                                     "(Should be sci_paper/all/close)".format(layout_cfg.enable_mode))
        if layout_cfg.enable_mode == "close":
            self.label_pipeline = None
            return
        if not kwargs.get("layout_recognizer"):
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Missing arg layout_recognizer. "
                                                            "If you don't need to recognizer the layout, "
                                                            "set layout_label.enable_mode to be 'close'.")
        layout_recognizer = kwargs.get("layout_recognizer")
        self.label_pipeline = LayoutLabelPipeline(layout_cfg, layout_recognizer)

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        return ".pdf"

    def read_from_path(self, path):
        """ read from file """
        context = {}
        kwargs = {"is_degrade": self.degrade}
        nodes, page_info = self.parser.parse_pdf(path, **kwargs)

        if is_pdf_ppt(page_info):
            doc_nodes = self.ppt_nodes_to_page(nodes, path.stem)
            doc_nodes = Document.tree_from_nodes(doc_nodes)
            return doc_nodes, {"p_type": "ppt"}

        # 根据processor.pdf.layout_label.enable_mode判断是否使用layout模型进行版面分析、文本过滤、文档树结构解析
        if self.check_need_label(nodes):
            doc_nodes = self.label_pipeline.run(nodes, path)
            doc_nodes = Document.tree_from_nodes(doc_nodes)
        else:
            file_content = "\n".join([node.text for node in nodes])
            text_content = TextContent(content=file_content)
            doc_nodes = [
                DocNode(id="0", chapter=[path.stem], title_level=0,
                        content=[text_content], parent=None, children=[])
            ]
            doc_nodes = Document.tree_from_nodes(doc_nodes)
        return doc_nodes, context

    def check_need_label(self, nodes):
        """ check if the file need label """
        if not self.label_pipeline:
            return False
        if self.cfg.layout_label.enable_mode == "all":
            return True
        return self.cfg.layout_label.enable_mode == "sci_paper" and is_pdf_scientific_paper(nodes)

    def ppt_nodes_to_page(self, nodes, file_name):
        """ get node label by ppt title recognizer """
        doc_nodes = [DocNode(id="0", chapter=[file_name], title_level=0, content=[], parent=None, children=[])]
        page_nodes_list = group_nodes_by_pageid(nodes)
        for i, page_nodes in enumerate(page_nodes_list):
            w_y, w_x = self.cfg.ppt_page_title_score_weight[0], self.cfg.ppt_page_title_score_weight[1]
            content_nodes = [node for node in page_nodes if node.layout_model_label != LabelDict.TABLE]
            if len(content_nodes) == 0:
                page_title = ""
            else:
                title_node = min(content_nodes, key=lambda x: w_y * x.loc[1] + w_x * x.loc[0])
                page_nodes.remove(title_node)
                page_title = title_node.text
            page_text = ""
            for node in page_nodes:
                if TableSep.CELL in node.text or TableSep.LINE in node.text:
                    page_text += "\n" + node.text.replace(TableSep.LINE, "\n").replace(TableSep.CELL, " ")
                else:
                    page_text += node.text
            doc_node = DocNode(id=str(i + 1), parent=None, children=[], title_level=1,
                               content=[TextContent(content=page_text)], chapter=[file_name, page_title])
            doc_nodes.append(doc_node)
        return doc_nodes

    def _check_cfg(self, cfg):
        """ check config """
        CheckUtils.check_iter(cfg.ppt_page_title_score_weight, length=2, name_="parser.pdf.file_size_limit")
        for weight in cfg.ppt_page_title_score_weight:
            CheckUtils.check_types(weight, [int, float], "parser.pdf.ppt_page_title_score_weight")
            CheckUtils.check_range(weight, min_close=0.0, max_close=1.0)
        CheckUtils.check_type(cfg.parser, dict, "parser.pdf.parser")
        CheckUtils.check_type(cfg.layout_label, dict, "parser.pdf.layout_label")
        CheckUtils.check_type(cfg.max_page_limit, int, "parser.pdf.max_page_limit")
        CheckUtils.check_type(cfg.max_token_limit, int, "parser.pdf.max_token_limit")
        CheckUtils.check_type(cfg.max_worker, int, "parser.pdf.max_worker")
        CheckUtils.check_range(cfg.max_worker, min_open=0)
        CheckUtils.check_types(cfg.file_size_limit, [int, float], "parser.pdf.file_size_limit")

    def _parse_config(self, **kwargs):
        self.degrade = self.config.get("degrade", {}).get("enable", DEFAULT_DEGRADE_ENABLE)
        self.config = self.config.get("parser", {}).get("pdf", {})


def is_pdf_scientific_paper(nodes):
    """ check if file is scientific paper """
    first_page_texts = "".join([node.text for node in nodes if node.page_id == 0])
    first_page_texts = re.sub(r"\s+", "", first_page_texts)

    if check_zh(first_page_texts):
        # 中文文档：首页文本包含 ZH_SCIENTIFIC_WORDS 中的单词 2个或更多，则认为是论文
        first_page_texts = first_page_texts.lower()
        cnt = 0
        for word in ["摘要", "关键词", "abstract", "keyword", "中图分类号", "DOI"]:
            if word in first_page_texts:
                cnt += 1
            if cnt >= 2:
                return True
        return False
    # 英文文档：首页文本 1. 包含"arxiv:"(水印) 或 2. 包含abstract 和 introduction 则认为是论文
    if "arxiv:" in first_page_texts.lower():
        return True
    if "Abstract" not in first_page_texts and "ABSTRACT" not in first_page_texts:
        return False
    if "Introduction" not in first_page_texts and "INTRODUCTION" not in first_page_texts:
        return False
    return True


def is_pdf_ppt(page_info):
    """ check if file is ppt slides """
    if not page_info:
        return False
    wh_ration = page_info[0].get("width", 0) / (page_info[0].get("height", 0) + 1e-10)
    for target_wh_ratio in [4 / 3, 16 / 9]:
        if abs(wh_ration - target_wh_ratio) < 1e-02:
            return True
    return False
