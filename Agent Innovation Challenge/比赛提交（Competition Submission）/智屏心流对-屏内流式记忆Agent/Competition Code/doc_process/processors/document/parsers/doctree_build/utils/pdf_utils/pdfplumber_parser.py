# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing classes to parse pdf to texts."""
import itertools
import re
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from decimal import Decimal

import pdfplumber
from pdfplumber.table import TableSettings

from doc_process.processors.document.parsers.doctree_build.utils.data_cls import Node, LabelDict, TableSep
from doc_process.processors.document.parsers.doctree_build.utils.node_util import get_loc_intersection
from doc_process.processors.document.parsers.doctree_build.utils.timeout_util import timeout
from doc_process.processors.document.parsers.doctree_build.utils.util import check_zh, remove_illegal_chars
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import LIST_LENGTH_TWO, INF, NINF
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()

TOKEN_TEXT = "text"
TOKEN_SIZE = "size"
TOKEN_FONT = "fontname"


class PdfplumberTokenUtil:
    """ Util class for tokens extracted from pdf file by pdfplumber """

    def __init__(self, config):
        self.check_cfg(config)
        self.config = config

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    @classmethod
    def get_tokens_attr(cls, tokens, attrs):
        """获取token列表中出现最多的属性"""
        res = []
        for attr in attrs:
            freqs = {}
            for token in tokens:
                attr_value = token[attr]
                if isinstance(attr_value, float):
                    attr_value = float(Decimal(attr_value).quantize(Decimal("0.000")))
                freqs[attr_value] = freqs.get(attr_value, 0) + len(token.get(TOKEN_TEXT))
            res.append(max(freqs.items(), key=lambda x: x[1])[0])
        return res

    @classmethod
    def check_cfg(cls, cfg):
        """ check config """
        CheckUtils.check_types(cfg.space_gap_th, [int, float])
        CheckUtils.check_range(cfg.space_gap_th, min_open=0)

        CheckUtils.check_iter(cfg.same_line_dist_th, LIST_LENGTH_TWO)
        for th in cfg.same_line_dist_th:
            CheckUtils.check_types(th, [int, float])
            CheckUtils.check_range(th, min_open=0)

        CheckUtils.check_iter(cfg.same_block_dist_th, LIST_LENGTH_TWO)
        for th in cfg.same_block_dist_th:
            CheckUtils.check_types(th, [int, float])
            CheckUtils.check_range(th, min_open=0)

        CheckUtils.check_types(cfg.indent_ratio, [int, float])
        CheckUtils.check_range(cfg.indent_ratio, min_open=0)

        CheckUtils.check_iter(cfg.new_block_prefix)
        for prefix in cfg.new_block_prefix:
            CheckUtils.check_regex(prefix)

    def concat_token_texts(self, tokens, block_left, block_right):
        """对block内的token进行拼接"""
        if not tokens:
            return ""
        last_token = tokens[0]
        text = last_token.get(TOKEN_TEXT)
        for token in tokens[1:]:
            if self.check_tokens_continuous(last_token, token):
                # last_token和token在同一行
                if (check_zh(last_token.get(TOKEN_TEXT)) or check_zh(token.get(TOKEN_TEXT))) and (
                    token.get("x0") - last_token.get("x1")) < self.config.space_gap_th * token.get(TOKEN_SIZE):
                    # 两个token至少有一个是中文，且距离很近（即中间无空格），则不在token间加空格
                    text += token.get(TOKEN_TEXT)
                else:
                    # 英文单词间，或带有空格的中文（例如论文中的作者名），需在token间加空格
                    text += " " + token.get(TOKEN_TEXT)
            else:
                # last_token和token不在同一行
                if block_right - last_token.get("x1") > last_token.get(TOKEN_SIZE) \
                    or token.get("x0") - block_left > token.get(TOKEN_SIZE):
                    # 结合block左右边界，判断last_token后有空白，或token前有缩进，即文本分段
                    text += "\n" + token.get(TOKEN_TEXT)
                elif check_zh(last_token.get(TOKEN_TEXT)) or check_zh(token.get(TOKEN_TEXT)) \
                    or last_token.get(TOKEN_TEXT)[-1] == "-":
                    # 中文之间不加空格，英文用-连接的换行长单词不加空格
                    text += token.get(TOKEN_TEXT)
                else:
                    # 英文单词之间加空格
                    text += " " + token.get(TOKEN_TEXT)
            last_token = token
        return text

    def check_tokens_continuous(self, token_a, token_b):
        """根据两个token是否在同一水平位置（条件1）和距离是否足够近（条件2），判断阈值根据字体大小动态调整"""
        same_line_th = self.config.same_line_dist_th[0] * max(token_a.get(TOKEN_SIZE), token_b.get(TOKEN_SIZE))
        dist_th = self.config.same_line_dist_th[1] * max(token_a.get(TOKEN_SIZE), token_b.get(TOKEN_SIZE))
        if abs(token_a.get("bottom") - token_b.get("bottom")) < same_line_th \
            and abs(token_a.get("x1") - token_b.get("x0")) < dist_th:
            return True
        return False

    def check_lines_format_same(self, line_a, line_b):
        """判断两行的格式是否相同"""
        text_a = " ".join([token.get(TOKEN_TEXT) for token in line_a])
        text_b = " ".join([token.get(TOKEN_TEXT) for token in line_b])

        # 一行有中文，一行没有，直接认为格式不相同
        if check_zh(text_a) != check_zh(text_b):
            return False

        # 获取line的font，中文取所有中文token的最高频，英文取所有token的最高频
        if check_zh(text_a) and check_zh(text_b):
            font_a = self.get_tokens_attr([token for token in line_a if check_zh(token.get(TOKEN_TEXT))], [TOKEN_FONT])
            font_b = self.get_tokens_attr([token for token in line_b if check_zh(token.get(TOKEN_TEXT))], [TOKEN_FONT])
        else:
            font_a, font_b = self.get_tokens_attr(line_a, [TOKEN_FONT]), self.get_tokens_attr(line_b, [TOKEN_FONT])

        size_a, size_b = self.get_tokens_attr(line_a, [TOKEN_SIZE]), self.get_tokens_attr(line_b, [TOKEN_SIZE])

        return size_a == size_b and font_a == font_b

    def check_line_continuous(self, line_a, line_b):
        """根据前后两行的距离判断是否在连续的文字块内"""
        a_size, a_bottom = self.get_tokens_attr(line_a, [TOKEN_SIZE, "bottom"])
        b_size, b_top = self.get_tokens_attr(line_b, [TOKEN_SIZE, "top"])
        text_b = " ".join([token.get(TOKEN_TEXT) for token in line_b])
        for prefix in self.config.new_block_prefix:
            if re.match(prefix, text_b):
                return False
        if abs(a_bottom - b_top) < self.config.same_block_dist_th[0] * min(a_size, b_size):  # 距离很近
            return True
        a_left, b_left = line_a[0].get("x0"), line_b[0].get("x0")
        if abs(a_bottom - b_top) < self.config.same_block_dist_th[1] * min(a_size, b_size) \
            and self.check_lines_format_same(line_a, line_b) \
            and abs(a_left - b_left) < self.config.indent_ratio * min(a_size, b_size):  # 距离稍近且字体相近、左侧对齐
            return True
        return False

    def merge_token_lines_to_blocks(self, lines):
        """合并距离相近的line为文字块（block）"""
        if not lines:
            return []
        blocks = [[lines[0]]]
        for line in lines[1:]:
            if not line:
                continue
            if self.check_line_continuous(blocks[-1][-1], line):
                blocks[-1].append(line)
            else:
                blocks.append([line])
        blocks = [list(itertools.chain.from_iterable(block)) for block in blocks]
        return blocks


class PdfplumberParser:
    """ Pdf file parser using pdfplumber """

    extract_params = []
    table_extract_timeout = 1
    token_util = dict()
    min_table_cell_num = 1
    parser_config = {}

    def __init__(self, config):
        self.max_page_limit = config.max_page_limit
        self.max_token_limit = config.max_token_limit
        self.max_workers = config.max_worker
        self.check_cfg(config.parser)

    @classmethod
    def set_class_variable(cls, config):
        """ set class variable """
        cls.parser_config = config
        cls.extract_params = config.extract_params
        cls.table_extract_timeout = config.table_extract_timeout
        cls.token_util = PdfplumberTokenUtil(config.token_util)
        cls.min_table_cell_num = config.min_table_cell_num

    @classmethod
    def check_cfg(cls, cfg):
        """ check config """
        CheckUtils.check_iter(cfg.extract_params, 6)
        for param in cfg.extract_params[:2]:
            CheckUtils.check_types(param, [int, float])
            CheckUtils.check_range(param, min_close=0)
        for param in cfg.extract_params[2:]:
            CheckUtils.check_type(param, bool)
        CheckUtils.check_type(cfg.min_table_cell_num, int)
        CheckUtils.check_range(cfg.min_table_cell_num, min_open=0)
        CheckUtils.check_types(cfg.table_extract_timeout, [int, float])
        CheckUtils.check_range(cfg.table_extract_timeout, min_open=0, max_close=60)
        CheckUtils.check_type(cfg.token_util, dict)

    @classmethod
    def table_rows_to_2d_list_format(cls, rows):
        """ convert table rows to 2d list """
        rows_2d_list = []
        for row in rows:
            row = [cell.replace("\n", " ") for cell in row]
            rows_2d_list.append(TableSep.CELL.join(row))
        return "\n".join([TableSep.START, "", TableSep.NAME_SEP, TableSep.LINE.join(rows_2d_list), TableSep.END])

    @classmethod
    def update_table_nodes(cls, page_nodes, table_nodes):
        """ delete nodes that have been extracted to tables """
        table_nodes_mapping = {table_node: [] for table_node in table_nodes}
        for node in page_nodes:
            for table_node in table_nodes:
                inter_area, node_area, _ = get_loc_intersection(node.loc, table_node.loc)
                if inter_area / (node_area + 1e-10) > 0.95:
                    table_nodes_mapping[table_node].append(node)
                    break
        for table_node, sub_nodes in list(table_nodes_mapping.items())[::-1]:
            if not sub_nodes:
                page_nodes.append(table_node)  # table node没有找到对应的子node，无法确定位置。一般不存在这种情况
            else:
                page_nodes.insert(page_nodes.index(sub_nodes[0]), table_node)  # table node插入首个子node之前
        all_table_nodes = list(itertools.chain.from_iterable(list(table_nodes_mapping.values())))
        page_nodes = [node for node in page_nodes if node not in all_table_nodes]  # 删除所有子node
        return page_nodes

    @classmethod
    def build_nodes_from_tokens(cls, tokens):
        """将多个pdfplumber token拼接为一个，text直接拼接，font_name和size取字符数量最多的，loc取最小包围矩形框"""
        param_dict = {}
        font_freqs = {}
        size_freqs = {}
        x0, x1 = INF, NINF
        y0, y1 = INF, NINF
        for token in tokens:
            font_freqs[token.get(TOKEN_FONT)] = font_freqs.get(token.get(TOKEN_FONT), 0) + len(token.get(TOKEN_TEXT))

            token_size = float(Decimal(token.get(TOKEN_SIZE)).quantize(Decimal("0.000")))
            size_freqs[token_size] = size_freqs.get(token_size, 0) + len(token.get(TOKEN_TEXT))

            x0 = min(x0, token.get("x0", INF))
            x1 = max(x1, token.get("x1", NINF))
            y0 = min(y0, token.get("top", INF))
            y1 = max(y1, token.get("bottom", NINF))

        param_dict["font_name"] = max(font_freqs.items(), key=lambda x: x[1])[0]
        param_dict[TOKEN_SIZE] = max(size_freqs.items(), key=lambda x: x[1])[0]
        param_dict["loc"] = [x0, y0, x1, y1]

        text = cls.token_util.concat_token_texts(tokens, x0, x1)
        param_dict[TOKEN_TEXT] = text

        return Node(**param_dict)

    @classmethod
    def get_page_nodes(cls, tokens):
        """根据页面的所有token，使用is_tokens_continuous()和merge_token_lines_to_blocks()进行token间、文字行之间的合并"""
        if not tokens:
            return []
        lines = [[tokens[0]]]
        for token in tokens[1:]:
            if not token.get(TOKEN_TEXT).strip():
                continue
            if cls.token_util.check_tokens_continuous(lines[-1][-1], token):
                lines[-1].append(token)
            else:
                lines.append([token])
        blocks = cls.token_util.merge_token_lines_to_blocks(lines)
        # 根据文字块构建node
        nodes = [cls.build_nodes_from_tokens(block) for block in blocks]
        nodes = [node for node in nodes if node.text.strip()]
        return nodes

    @classmethod
    def check_table_rows(cls, rows):
        """ check table cells """
        all_cells = list(itertools.chain.from_iterable(rows))
        if None in all_cells:
            return False
        valid_cells = [cell for cell in all_cells if cell]
        if len(valid_cells) < cls.min_table_cell_num:
            return False
        return True

    @classmethod
    @timeout()
    def get_tables_nodes(cls, page, timeout_decorator_seconds):
        """ get table nodes from pdf page """
        tset = TableSettings.resolve(None)
        tables = page.find_tables(tset)
        extract_kwargs = {k: getattr(tset, "text_" + k) for k in ["x_tolerance", "y_tolerance"]}

        table_rows_list = [table.extract(**extract_kwargs) for table in tables]

        table_nodes = []
        for table, rows in zip(tables, table_rows_list):
            if not cls.check_table_rows(rows):
                continue
            text = cls.table_rows_to_2d_list_format(rows)
            loc = list(table.bbox)
            table_node = Node(label=LabelDict.TABLE, text=text, loc=loc)
            table_nodes.append(table_node)

        return table_nodes

    @classmethod
    def parse_page(cls, page_id, path, config):
        """解析PDF单个页面"""
        cls.set_class_variable(config)
        num_tokens = 0
        with pdfplumber.open(path) as plumber_pdf_object:
            pages = plumber_pdf_object.pages
            tokens = pages[page_id].extract_words(
                x_tolerance=cls.extract_params[0],
                y_tolerance=cls.extract_params[1],
                keep_blank_chars=cls.extract_params[2],
                use_text_flow=cls.extract_params[3],
                horizontal_ltr=cls.extract_params[4],
                vertical_ttb=cls.extract_params[5],
                extra_attrs=["fontname", "size"],
                split_at_punctuation=None,
            )

            for token in tokens:
                num_tokens += len(token[TOKEN_TEXT])
                token[TOKEN_TEXT] = remove_illegal_chars(token.get(TOKEN_TEXT, ""))

            nodes = cls.get_page_nodes(tokens)

            try:
                table_nodes = cls.get_tables_nodes(pages[page_id], timeout_decorator_seconds=cls.table_extract_timeout)
            except TimeoutError:
                table_nodes = []
            nodes = cls.update_table_nodes(nodes, table_nodes)
            for node in nodes:
                node.page_id = page_id
            info = {"page_id": page_id, "width": pages[page_id].width, "height": pages[page_id].height}

        return nodes, info, num_tokens

    @classmethod
    def match_pageid_nodes(cls, nodes, pageid_nodes):
        """match nodes with page id"""
        if nodes:
            pageid_nodes[nodes[0].page_id] = nodes

    def parse_pdf(self, path, **kwargs):
        """解析PDF"""
        all_nodes = []
        page_info = []
        pageid_nodes = dict()
        is_degrade = kwargs.get("is_degrade", False)
        with pdfplumber.open(path) as plumber_pdf_object:
            pages = plumber_pdf_object.pages

        num_pages = len(pages)

        if is_degrade and num_pages > self.max_page_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} pages. Current page count: {} "
                                     .format(self.max_page_limit, num_pages))

        self.parse_pdf_process_pool(is_degrade, page_info, pageid_nodes, num_pages, path)

        # 按页面id排序
        for p_node in sorted(pageid_nodes.items(), key=lambda x: x[0]):
            all_nodes.extend(p_node[1])
        page_info = sorted(page_info, key=lambda x: x['page_id'])
        return all_nodes, page_info

    def parse_pdf_process_pool(self, is_degrade, page_info, pageid_nodes, num_pages, path):
        """多进程解析PDF页面"""
        all_num_tokens = 0
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.parse_page, pid, path, self.parser_config): pid for pid in range(num_pages)}
            for future in as_completed(futures):
                try:
                    nodes, info, num_tokens = future.result()
                    self.match_pageid_nodes(nodes, pageid_nodes)
                    page_info.append(info)
                    all_num_tokens += num_tokens
                    self.check_exceed_tokens(all_num_tokens, is_degrade)
                except ProcessorException as e:
                    raise e
                except Exception:
                    exc = future.exception()
                    logger.error(traceback.format_exc())
                    logger.error(f"Error processing page {futures[future]}: {exc}")

    def check_exceed_tokens(self, all_num_tokens, is_degrade):
        """check exceed tokens"""
        if is_degrade and all_num_tokens > self.max_token_limit:
            raise ProcessorException(ErrorCode.FILE_TOO_LARGE,
                                     "File has exceeded the maximum limit of {} tokens. "
                                     "Current tokens count: {} "
                                     .format(self.max_token_limit, all_num_tokens))
