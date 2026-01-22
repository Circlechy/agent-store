# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module provide consts."""

DEFAULT_USER_CONFIG = {
    "pdf": {
        "file_size_limit": 100,
        "max_page_limit": 100,
        "max_token_limit": 100000,
        "max_worker": 10,
        "ppt_page_title_score_weight": [0.7, 0.3],
        "layout_label": {
            "title_senior_mode": False,
            "enable_mode": "close",
            "model_score_th": 0.9,
            "overlap_ratio_th": 0.5,
        }
    },
    "pptx": {
        "file_size_limit": 100,
        "max_page_limit": 1000,
        "max_shapes_limit": 5000,
        "ppt_page_title_score_weight": [0.7, 0.3]
    },
    "html": {
        "file_size_limit": 100,
        "max_token_limit": 200000,
        "decode_type": ["utf-8", "gbk", "big5", "gb18030"]
    },
    "txt": {
        "file_size_limit": 100,
        "decode_type": ["utf-8", "gbk", "big5", "gb18030"]
    },
    "md": {
        "file_size_limit": 100,
        "max_token_limit": 1000000,
        "decode_type": ["utf-8", "gbk", "big5", "gb18030"]
    },
    "xlsx": {
        "file_size_limit": 100,
        "max_1st_col_char": 200,
        "max_2nd_col_char": 5000,
        "max_row_limit": 50000,
        "col_limit": 2
    },
    "docx": {
        "file_size_limit": 100,
        "large_table_rows": 100,
        "max_large_table_limit": 5,
        "max_table_rows_limit": 500,
        "max_paragraph_limit": 5000,
        "max_token_limit": 100000
    }
}

INTERNAL_CONFIG = {
    "pdf": {
        "parser": {
            "extract_params": [1.5, 2.0, False, True, True, True],
            "min_table_cell_num": 4,
            "table_extract_timeout": 3,
            "token_util": {
                "space_gap_th": 0.5,
                "same_line_dist_th": [1, 4],
                "same_block_dist_th": [0.5, 1.5],
                "indent_ratio": 6,
                "new_block_prefix": [
                    r"^(表|Table |Tab\.)(\d+)( |:)(.+)",
                    r"^(图|Figure |Fig\.)(\d+)( |:)(.+)",
                    r"^(第*)([\(\（]*)([〇零一二三四五六七八九十\d\.]+)([章节条\.]*)([\)\）、 ]+)"
                ]
            }
        },
        "layout_label": {
            "ignore_labels": [
                "figure",
                "figurecaption",
                "header",
                "footer",
                "reference"
            ],
            "table_capion_pattern": r"^(表|Table |Tab\.)(\d+)( |:)(.+)",
            "figure_caption_pattern": r"^(图|Figure |Fig\.)(\d+)( |:)(.+)",
            "title_pattern": r"^(第*)([\(\（]*)([〇零一二三四五六七八九十\d\.]+)([章节条\.]*)([\)\）、 ]+)",
            "title_ignore_pattern": r"[\[\+\-\*/\=\(]",
            "title_rank_pattern": [
                r".*[〇零一二三四五六七八九十]+.*",
                r"\d+",
                r"\(\d\)+"
            ],
            "page_pattern": r"^([-\(]?)(\d+)([-\)]?)$",
            "title_max_len": [30, 60],
            "min_table_cell_num": 4
        }
    }
}
