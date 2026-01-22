import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import Any, List, Dict

import jieba

from doc_process.processors.base.adapter import Bm25Adapter
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from service.process.common.utils.jieba_utils import jieba_bm25_texts
from service.process.common.utils.request_utils import (RequestUtils)

logger = logging.get_logger()


class TwBm25AdapterImpl(Bm25Adapter):

    def __init__(self, config: Dict):
        self._parse_input(config)
        # 初始化 jieba
        jieba.initialize()

    def _parse_input(self, config: Dict):
        """_parse_input"""
        self.config = config
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.config.get("tw"), dict, "tw")

        self.tw_url = self.config.get("tw", {}).get("url")  # 必填
        self.degrade_enable = self.config.get("degrade", {}).get("enable", True)
        self.truncate_num = self.config.get("tw", {}).get("truncate_num", 100)
        self.thread_nums = self.config.get("tw", {}).get("thread_nums", 4)
        self.max_retry = self.config.get("tw", {}).get("max_retry", 3)
        self.timeout = self.config.get("tw", {}).get("timeout", 3)
        CheckUtils.check_type(self.tw_url, str, "tw.utl")
        CheckUtils.check_type(self.degrade_enable, bool, "degrade.enable")
        CheckUtils.check_type(self.truncate_num, int, "tw.truncate_num")
        CheckUtils.check_type(self.thread_nums, int, "tw.thread_nums")
        CheckUtils.check_type(self.max_retry, int, "tw.max_retry")
        CheckUtils.check_types(self.timeout, [int, float], "tw.timeout")
        CheckUtils.check_range(self.thread_nums, min_open=0)
        CheckUtils.check_range(self.max_retry, min_open=0)
        CheckUtils.check_range(self.timeout, min_close=0)

    def _extract_bm25(self, texts: List[str], **kwargs: Any) -> (bool, List[List[Dict]]):
        """extract bm25 from text"""
        bm25s: List[List[Dict]] = []
        bm25s_flag = True
        truncate_num = self.truncate_num if self.degrade_enable else len(texts)
        pre_texts = texts[:truncate_num]
        post_texts = texts[truncate_num:]
        with ThreadPoolExecutor(max_workers=self.thread_nums) as executor:
            # 使用executor.map()使得返回结果与任务提交顺序保持一致
            results = executor.map(self._extract_text_bm25, pre_texts)
            results_list = list(results)
            for text, (flag, bm25) in zip(pre_texts, results_list):
                if not flag:
                    logger.error("tw extract bm25 failed, text={}".format(text))
                    bm25 = []
                    bm25s_flag = False
                bm25s.append(bm25)

        jieba_flag, jieba_bm25s = jieba_bm25_texts(post_texts)
        bm25s.extend(jieba_bm25s)
        return bm25s_flag and jieba_flag, bm25s

    def _extract_text_bm25(self, text: str, **kwargs: Any) -> (bool, List[Dict]):
        body = {
            "data": {
                "query": text,
                "segment_mode": "index",
                "use_freq": False
            },
            "version": "0"
        }
        is_ok = False
        result = {}
        for _ in range(self.max_retry):
            status_code, result = RequestUtils.common_sever(self.tw_url, body, "post", self.timeout)
            if RequestUtils.RE_SUCCESS_CODE.match(str(status_code)) is None:
                logger.error(
                    "Fail to get term info! Status Code:%s, Response:%s. Retry again ...",
                    status_code, result)
                continue
            is_ok = True
            break
        # 将字符串的output字段解析为json
        try:
            output_data = json.loads(result.get("result", {}).get("content", [{}])[0].get("output", ""))
        except JSONDecodeError:
            output_data = {"offset": [["", [0, 1]]]}
        except Exception as e:
            output_data = {"offset": [["", [0, 1]]]}
            logger.error("TwBm25AdapterImpl exception :{}. query: {}.".format(e, text))
            logger.error(traceback.format_exc())
        result = self._convert_result(output_data)
        if not is_ok:
            return is_ok, result
        return True, result

    def _convert_result(self, output_data) -> List[Dict]:
        # 将词权重服务的输出转换为ES分词格式
        es_tokens = []
        position_map = {}
        position = 0

        for token_info in output_data.get("offset", []):
            token = token_info[0]
            start_offset, end_offset = token_info[1]

            # 如果相同的start_offset已经有了对应的position，则复用该position
            if start_offset in position_map:
                token_position = position_map[start_offset]
            else:
                token_position = position
                position_map[start_offset] = position  # 保存新的position
                position += 1  # 只有新的start_offset时，position才增加

            es_tokens.append({
                "token": token,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "type": "word",  # 假设所有的分词类型都是word
                "position": token_position
            })
        return es_tokens
