# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing LayoutRecogAdapter."""
from abc import ABC, abstractmethod
from typing import List

from doc_process.processors.document.parsers.doctree_build.utils.pdf_utils.layout_label import LayoutLabel
from doc_process.utils.error_code import ProcessorException, ErrorCode

BBOX_LOC_LEN = 4


class LayoutRecogAdapter(ABC):
    """ Pdf layout recognizer adapter """

    def __call__(self, path):
        layouts = self.forward(path)
        if not isinstance(layouts, list):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "Output layouts should be list, is {} now.".format(type(layouts)))
        for page_layouts in layouts:
            if not isinstance(page_layouts, list):
                raise ProcessorException(ErrorCode.TYPE_ERROR,
                                         "Page layouts should be list, is {} now.".format(type(page_layouts)))
            for layout in page_layouts:
                self.check_layout(layout)
        return layouts

    def check_layout(self, layout):
        """ check layout output """
        if not isinstance(layout, dict):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "Layout should be dict, is {} now.".format(type(layout)))
        # check key
        for key in ["type", "bbox", "score"]:
            if key not in layout:
                raise ProcessorException(ErrorCode.ATTRIBUTE_ERROR, "Key {} not in layout result.".format(key))
        # check bbox
        bbox = layout.get("bbox")
        if not isinstance(bbox, list):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "Type of bbox should be list, is {} now.".format(type(bbox)))
        if len(bbox) != BBOX_LOC_LEN:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "Len of layout bbox should be {}, is {} now.".format(BBOX_LOC_LEN, len(bbox))
                                     )
        for bbox_loc in bbox:
            if not isinstance(bbox_loc, float):
                raise ProcessorException(ErrorCode.TYPE_ERROR,
                                         "Type of layout bbox loc should be float, is {} now.".format(type(bbox_loc)))
        # check type
        type_ = layout.get("type")
        if type_ not in LayoutLabel.get_all_labels():
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Layout type {} not in LayoutLabel.".format(type_))
        # check score
        score = layout.get("score")
        if not isinstance(score, int) and not isinstance(score, float):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "Layout score {} should be int or float.".format(score))

    @abstractmethod
    def forward(self, path: str = "") -> List[List[dict]]:
        """ 对输入的PDF文档，解析其版面，获取每一页的版面元素列表，表中元素为dict类型，包括"type", "bbox", "score"字段 """
        ...
