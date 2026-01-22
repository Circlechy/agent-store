import copy
from typing import Any, List, Dict

from doc_process.processors.base.adapter.embedding_adapter import TextEmbeddingAdapter
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from service.process.common.utils.request_utils import RequestUtils

logger = logging.get_logger()


class TextEmbeddingAdapterImpl(TextEmbeddingAdapter):

    def __init__(self, config: Dict):
        self._parse_input(config)

    def _parse_input(self, config: Dict):
        """_parse_input"""
        self.config = config
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.config.get("embedding"), dict, "embedding")
        CheckUtils.check_type(self.config.get("degrade"), dict, "degrade")

        self.emb_url = self.config.get("embedding", {}).get("url")  # 必填
        self.batch_size = self.config.get("embedding", {}).get("batch_size", 16)
        self.max_retry = self.config.get("embedding", {}).get("max_retry", 3)
        self.timeout = self.config.get("embedding", {}).get("timeout", 3)
        CheckUtils.check_type(self.emb_url, str, "embedding.url")
        CheckUtils.check_type(self.batch_size, int, "embedding.batch_size")
        CheckUtils.check_type(self.max_retry, int, "embedding.max_retry")
        CheckUtils.check_types(self.timeout, [int, float], "embedding.timeout")
        CheckUtils.check_range(self.batch_size, min_open=0)
        CheckUtils.check_range(self.max_retry, min_open=0)
        CheckUtils.check_range(self.timeout, min_close=0)
        self.body_shema = {
            "data": {
                "service_mode": "auto_embedding",
                "operator": "add",
                "data_list": []
            }
        }

    def _text_embedding(self, text_list: List[str], **kwargs: Any) -> (bool, List[List[List[float]]]):
        embeddings: List[List[List[float]]] = []
        embeddings_flag = True
        n_text_list = len(text_list)
        for beg in range(0, n_text_list, self.batch_size):
            end = min(n_text_list, beg + self.batch_size)
            batch_text_list: List[str] = text_list[beg: end]
            flag, batch_embeddings = self.batch_embedding(batch_text_list, **kwargs)
            if not flag:
                logger.error("embeddings result flag is false.")
                batch_embeddings = [[[]]] * (end - beg)
                embeddings_flag = False
            embeddings.extend(batch_embeddings)
        return embeddings_flag, embeddings

    def batch_embedding(self, text_list: List[str], **kwargs: Any) -> (bool, List[List[List[float]]]):
        """embedding"""
        if text_list is None or len(text_list) == 0:
            return (False, [])
        body = copy.deepcopy(self.body_shema)

        body["data"]["data_list"] = text_list

        is_ok = False
        embs_list = []
        for _ in range(self.max_retry):
            status_code, result = RequestUtils.common_sever(self.emb_url, body, "post", self.timeout)
            if RequestUtils.RE_SUCCESS_CODE.match(str(status_code)) is None:
                logger.error(
                    "Fail to get embeddings! Status Code:%s, Response:%s. Retry again ...",
                    status_code, result)
                continue
            result = result.get("result", {})
            code = result.get("code")
            content = result.get("content", [])
            embs_list = content[0].get(
                "embeddings_list", []) if len(content) == 1 else []
            if code != "0" or len(embs_list) == 0:
                logger.error(
                    "Fail to get embeddings! text_list: %s,result: %s", text_list, result
                )
                break
            is_ok = True
            break
        if not is_ok:
            return False, []

        return is_ok, embs_list
