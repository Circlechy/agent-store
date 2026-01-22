#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Adapter"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from doc_process.utils.error_code import ProcessorException, ErrorCode


class DeleteAdapter(ABC):
    """DeleteAdapter"""

    def check_delete_output(self, result: bool):
        """check adapter output"""
        if not isinstance(result, bool):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "delete adapter result type incorrect,should be bool.result={}".format(result))

    def delete_data(self, data_dict: Dict, **kwargs: Any) -> bool:
        """ export """
        result = self._delete_data(data_dict, **kwargs)
        self.check_delete_output(result)
        return result

    @abstractmethod
    def _delete_data(self, data_dict: Dict, **kwargs: Any) -> bool:
        """
        delete datas
        Args:
            datas: datas
            kwargs: 关键字参数
        Return:
            true：成功，false：失败。
        """
        ...
