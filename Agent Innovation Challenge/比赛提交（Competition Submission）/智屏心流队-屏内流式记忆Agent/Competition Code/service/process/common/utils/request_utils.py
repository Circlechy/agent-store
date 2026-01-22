import re
from typing import (Tuple, Dict, Any)

import requests

from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

LOGGER = logging.get_logger()


class RequestUtils:
    RE_SUCCESS_CODE = re.compile("^20[0-6]$")

    @classmethod
    def common_sever(cls, url, data=None, method="get", timeout=30, headers=None) -> Tuple[int, Dict[str, Any]]:
        if headers is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        result: dict = {}
        status_code = 0
        response = None
        try:
            if method == "put":
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == "post":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == "delete":
                response = requests.delete(url, json=data, headers=headers, timeout=timeout)
            elif method == "get":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                raise ProcessorException(ErrorCode.VALUE_ERROR, f"Unsupported method: {method}")

            status_code = response.status_code
            if cls.RE_SUCCESS_CODE.match(str(status_code)) is None:
                LOGGER.error("request fail! code=%s,response=%s", status_code, response.text)
            else:
                result = response.json()
        except Exception as e:
            LOGGER.error("Exception to request %s, error details: %s", url, e)
            # 部分异常是没有响应，则包装返回一个默认错误。部分异常情况有响应体，
            # 只是响应体内容不是json导致上面解析异常，则直接包装返回响应体
            except_msg = "Exception to request"
            if response is not None:
                status_code = response.status_code
                except_msg = response.text
            result["exception_msg"] = except_msg
        return status_code, result
