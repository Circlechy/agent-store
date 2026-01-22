#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.

"""Set of constants."""
from enum import Enum

# constants
FILE_COUNT_ONE = 1
LIST_LENGTH_TWO = 2

# truncate
DEFAULT_DEGRADE_ENABLE = True

# pipeline
DEFAULT_PIPELINE_NAME = "default_pipeline"
FILES_TOTAL_COUNT = "total_count"
DEFAULT_KNOWLEDGE_BASE_NAME = "default_knowledge_base_name"


class ProcessorName(Enum):
    LOADER = "loader"
    PARSER = "parser"
    SPLITTER = "splitter"
    SUMMARY = "summary"
    BM25 = "bm25"
    EMBEDDING = "embedding"
    EXPORT = "export"
    EXPORT_ES = "export_es"
    EXPORT_VS = "export_vs"
    EXPORT_FALCON = "export_falcon"
    DELETE = "delete"
    DELETE_ES = "delete_es"
    DELETE_VS = "delete_vs"
    DELETE_FALCON = "delete_falcon"
    CONSTRUCT = "construct"
    RECOGNIZE = "recognizer"


# loader

# parser
PARA_TYPE = 1
COMB_TYPE = 2
TABLE_TYPE = 3

INF = float('inf')
NINF = float('-inf')

TREE_KEY = "tree"

FILE_NAME_KEY = "file_name"

OUTLINE_MIN_TH = 1

MAX_CONTINUOUS_TITLE = 7

TITLE_APPEAR_PATTERN = (r'(^\(?[\d+MDCLXVI]+(\.[\d+MDCLXVI]+)*\)?$)'
                        r'|(^\(?[〇零一二三四五六七八九十]+\)?([\.\、\:\：])*$)'
                        r'|(^\(?[a-zA-Z]?(\.[a-zA-Z])*\)?$)')

# splitter

# bm25

# embedding


# chapter summary
DEFAULT_INVALID_CONTENT = "抱歉"
# 定义常量
IS_GENERATED_SUMMARY_CHUNK = "is_generated_summary_chunk"
IS_EXTRACTED_SUMMARY_CHUNK = "is_extracted_summary_chunk"
IS_ADD_METADATA = "is_add_metadata"
SUMMARY_TARGET_LENGTH = "target_length"
DEFAULT_SUMMARY_TARGET_LENGTH = 4000

# export


# delete
