#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Bm25Adapter"""
from abc import ABC, abstractmethod
from typing import Any, List, Dict

from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class Bm25Adapter(ABC):
    """Bm25Adapter"""

    def check_bm25_info_type(self, bm25_info: List[Dict]):
        """check bm25_info type"""
        if isinstance(bm25_info, list):
            if len(bm25_info) == 0:
                return True
            token_dict = bm25_info[0]
            if isinstance(token_dict, dict):
                if "token" not in token_dict or "position" not in token_dict:
                    logger.warning("The BM25 result dict should preferably contain key 'token' and 'position'")
                return True
        return False

    def check_bm25_output_type(self, bm25: (bool, List[List[Dict]])):
        """check bm25s type"""
        if isinstance(bm25, tuple) and len(bm25) == 2:
            flag = bm25[0]
            bm25_infos = bm25[1]

            if isinstance(flag, bool) and isinstance(bm25_infos, list):
                if len(bm25_infos) == 0:
                    return True
                bm25_info = bm25_infos[0]
                if self.check_bm25_info_type(bm25_info):
                    return True
        return False

    def check_bm25_output(self, bm25: (bool, List[List[Dict]])):
        """check adapter output"""
        if not self.check_bm25_output_type(bm25):
            raise ProcessorException(
                ErrorCode.TYPE_ERROR,
                "bm25 adapter result type incorrect,should be (bool, List[List[Dict]]).bm25={}".format(bm25))

    def extract_bm25(self, texts: List[str], **kwargs: Any) -> (bool, List[List[Dict]]):
        """extract_bm25"""
        bm25_res = self._extract_bm25(texts, **kwargs)
        self.check_bm25_output(bm25_res)
        return bm25_res

    @abstractmethod
    def _extract_bm25(self, texts: List[str], **kwargs: Any) -> (bool, List[List[Dict]]):
        """
        extract bm25 from text
        Args:
            text: 需要进行bm25的文本
            kwargs: 关键字参数
        Return:
            Tuple类型
            第一个元素：分词服务返回值状态码解析状态，true表示成功，false表示失败
            第二个元素：分词信息列表
        """
        ...
