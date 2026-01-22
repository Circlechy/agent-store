from abc import ABC
from typing import Any, List, Dict, Tuple

import jieba

from service.process.common.client.es_client import ESClient
from service.process.common.utils.log import request_logger
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.processors.base.adapter.bm25_adapter import Bm25Adapter
from doc_process.processors.base.adapter.delete_adapter import DeleteAdapter
from doc_process.processors.base.adapter.export_adapter import ExportAdapter
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode
from service.process.common.utils.jieba_utils import jieba_bm25_texts
from service.process.common.utils.request_utils import (RequestUtils)

logger = logging.get_logger()

class EsAdapter(Bm25Adapter, ExportAdapter, DeleteAdapter, ABC):
    """EsAdapter"""
    ...
class EsAdapterImpl(EsAdapter):
    def __init__(self, config: Dict, mapping: BaseMappingField):
        self.config = config
        self.mapping = mapping
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.mapping, BaseMappingField, "mapping")
        CheckUtils.check_type(self.config.get("es"), dict, "es")

        es_url = self.config.get("es", {}).get("url")  # 必填
        CheckUtils.check_type(es_url, str, "es.url")
        self.analyzer = self.config.get("es", {}).get("analyzer", "")
        self.client = ESClient(es_url)
        self.index = self.config.get("es", {}).get("index")  # 必填
        self.chunk_info_id = self.config.get("index", {}).get("chunk_info_id", "")
        self.tk_url = "/".join([es_url, self.index, "_analyze"])

        self.degrade_enable = self.config.get("degrade", {}).get("enable", True)
        self.truncate_num = self.config.get("es", {}).get("bm25", {}).get("truncate_num", 100)
        self.max_retry = self.config.get("es", {}).get("bm25", {}).get("max_retry", 3)
        self.bm25_timeout = self.config.get("es", {}).get("bm25", {}).get("timeout", 3)
        self.export_timeout = self.config.get("es", {}).get("export", {}).get("timeout", 3)

        CheckUtils.check_type(self.analyzer, str, "es.analyzer")
        CheckUtils.check_type(self.index, str, "es.index")
        CheckUtils.check_type(self.chunk_info_id, str, "index.chunk_info_id")
        CheckUtils.check_type(self.degrade_enable, bool, "degrade.enable")
        CheckUtils.check_type(self.truncate_num, int, "es.bm25.truncate_num")
        CheckUtils.check_type(self.max_retry, int, "es.bm25.max_retry")
        CheckUtils.check_types(self.bm25_timeout, [int, float], "es.bm25.timeout")
        CheckUtils.check_types(self.export_timeout, [int, float], "es.export.timeout")

        jieba.initialize()

    def _export(self, chunks: List[Dict], **kwargs: Any) -> bool:
        """export2es"""
        store_res = True
        if not chunks:
            return store_res
        request_logger.info(chunks)
        ids = []
        for chunk_obj in chunks:
            if self.chunk_info_id not in chunk_obj:
                raise ProcessorException(ErrorCode.CONFIG_INVALID,
                                         "chunk_info_id={} not in keys of chunk={}".format(self.chunk_info_id,
                                                                                           chunk_obj.keys()))
            ids.append(chunk_obj[self.chunk_info_id])
        logger.debug("es to be export chunks num={}".format(len(chunks)))
        return self.client.bulk_insert(self.index, chunks, ids, self.export_timeout)

    def _extract_bm25(self, texts: List[str], **kwargs: Any) -> (bool, List[List[Dict]]):
        """extract bm25 from text"""
        truncate_num = self.truncate_num if self.degrade_enable else len(texts)
        pre_texts = texts[:truncate_num]
        post_texts = texts[truncate_num:]
        bm25s: List[List[Dict]] = []
        bm25s_flag = True
        for text in pre_texts:
            flag, es_bm25 = self._extract_text_bm25(text)
            if not flag:
                logger.error("es extract bm25 failed,text={}".format(text))
                es_bm25 = []
                bm25s_flag = False
            bm25s.append(es_bm25)

        jieba_flag, jieba_bm25 = jieba_bm25_texts(post_texts)
        bm25s.extend(jieba_bm25)
        return bm25s_flag and jieba_flag, bm25s

    def _extract_text_bm25(self, text: str, **kwargs: Any) -> (bool, List[Dict]):
        body = {
            "analyzer": self.analyzer,
            "text": text
        }
        is_ok = False
        result = {}
        for _ in range(self.max_retry):
            status_code, result = RequestUtils.common_sever(self.tk_url, body, "post", self.bm25_timeout)
            if RequestUtils.RE_SUCCESS_CODE.match(str(status_code)) is None:
                logger.error(
                    "Fail to get term info! Status Code:%s, Response:%s. Retry again ...",
                    status_code, result)
                continue
            is_ok = True
            break

        if result:
            # 服务访问成功
            if result.get("tokens"):
                # 内容成功
                result = result.get("tokens")
            else:
                result = [{
                    "token": text,
                    "start_offset": 0,
                    "end_offset": len(text),
                    "type": "word",
                    "position": 0
                }]
        else:
            result = []
        if not is_ok:
            return is_ok, result
        return True, result

    def _delete_data(self, data_dict: Dict, **kwargs: Any) -> bool:
        result = True
        user_id = data_dict.get("user_id", "")
        session_id = data_dict.get("session_id", "")
        doc_ids = data_dict.get("doc_ids", [])
        if user_id and session_id and doc_ids:
            result = self.delete_by_filter([("user_id", [user_id]), ("session_id", [session_id]), ("doc_id", doc_ids)])
        elif user_id and session_id:
            result = self.delete_by_filter([("user_id", [user_id]), ("session_id", [session_id])])
        elif user_id and doc_ids:
            result = self.delete_by_filter([("user_id", [user_id]), ("doc_id", doc_ids)])
        elif user_id:
            result = self.delete_by_filter([("user_id", [user_id])])
        else:
            raise ProcessorException(ErrorCode.PARAM_INVALID, "user_id and session_id and doc_ids is None.")
        return result

    def delete_by_filter(self, pair_list: List[Tuple[str, List[str]]]) -> bool:
        query_body = self.build_multi_dsl(pair_list)
        results = self.client.search_by_key(self.index, query_body)
        chunk_ids: List[str] = [result.get("_source", {}).get(self.mapping.get_bus_name(self.mapping.CHUNK_ID), "") for
                                result in results]
        logger.debug("ES chunk_ids to be deleted. {}".format(chunk_ids))
        return self.client.delete_by_query([self.index], query_body)

    @staticmethod
    def build_multi_dsl(pair_list: List[Tuple[str, List[str]]]):
        dsl = {
            "query": {
                "bool": {
                    "must": [
                    ]
                }
            }
        }
        for pair in pair_list:
            key, values = pair
            dsl["query"]["bool"]["must"].append({"terms": {key: values}})
        return dsl
