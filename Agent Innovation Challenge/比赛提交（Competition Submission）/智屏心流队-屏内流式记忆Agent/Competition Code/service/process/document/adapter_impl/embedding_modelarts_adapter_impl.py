import copy
from typing import Any, List, Dict

from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from service.process.document.adapter_impl.embedding_adapter_impl import TextEmbeddingAdapterImpl
from service.process.common.utils.request_utils import RequestUtils

logger = logging.get_logger()


class EmbeddingModelArtsAdapterImpl(TextEmbeddingAdapterImpl):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.config = config
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.config.get("embedding-modelarts"), dict, "embedding-modelarts")
        CheckUtils.check_type(self.config.get("embedding-modelarts").get("url"), str, "embedding-modelarts.url")  # 必填
        CheckUtils.check_type(self.config.get("embedding-modelarts").get("token"), str,
                              "embedding-modelarts.token")  # 必填
        self.emb_url = self.config.get("embedding-modelarts", {}).get("url", "")
        self.headers = {
            'Content-Type': 'application/json',
            'csb-token': self.config.get("embedding-modelarts", {}).get("token", "")
        }

    def batch_embedding(self, text_list: List[str], **kwargs: Any) -> (bool, List[List[List[float]]]):
        """embedding"""
        if text_list is None or len(text_list) == 0:
            return (False, [])
        body = copy.deepcopy(self.body_shema)

        body["data"]["data_list"] = text_list

        is_ok = False
        embs_list = []
        for _ in range(self.max_retry):
            status_code, result = RequestUtils.common_sever(self.emb_url, body, "post", self.timeout, self.headers)
            if RequestUtils.RE_SUCCESS_CODE.match(str(status_code)) is None:
                logger.error(
                    "Fail to get embeddings! Status Code:%s, Response:%s. Retry again ...",
                    status_code, result)
                continue
            is_ok: bool = result.get("status", "success") == "success"
            embs_list = result.get("embeddings_list", [[]])[0]
            if not is_ok:
                logger.error(
                    "Fail to get embeddings! text_list: %s,result: %s", text_list, result
                )
                break
            is_ok = True
            break
        if not is_ok:
            return False, []

        return is_ok, embs_list
