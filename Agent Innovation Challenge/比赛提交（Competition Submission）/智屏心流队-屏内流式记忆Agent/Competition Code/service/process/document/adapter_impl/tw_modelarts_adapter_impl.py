import json
import traceback
from json import JSONDecodeError
from typing import Any, List, Dict

from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from service.process.document.adapter_impl.tw_bm25_adapter_impl import TwBm25AdapterImpl
from service.process.common.utils.request_utils import (RequestUtils)

logger = logging.get_logger()


class TwModelArtsAdapterImpl(TwBm25AdapterImpl):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.config = config
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.config.get("tw-modelarts"), dict, "tw-modelarts")
        CheckUtils.check_type(self.config.get("tw-modelarts").get("url"), str, "tw-modelarts.url")  # 必填
        CheckUtils.check_type(self.config.get("tw-modelarts").get("token"), str, "tw-modelarts.token")  # 必填
        self.tw_url = self.config.get("tw-modelarts", {}).get("url", "")
        self.headers = {
            'Content-Type': 'application/json',
            'csb-token': self.config.get("tw-modelarts", {}).get("token", "")
        }

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
            status_code, result = RequestUtils.common_sever(self.tw_url, body, "post", self.timeout, self.headers)
            if RequestUtils.RE_SUCCESS_CODE.match(str(status_code)) is None:
                logger.error(
                    "Fail to get term info! Status Code:%s, Response:%s. Retry again ...",
                    status_code, result)
                continue
            is_ok = True
            break
        # 将字符串的output字段解析为json
        try:
            output_data = json.loads(result.get("output", ""))
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
