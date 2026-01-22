#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""Adapter"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from doc_process.utils.error_code import ProcessorException, ErrorCode


class ExportAdapter(ABC):
    """EsAdapter"""

    def check_export_output(self, result: bool):
        """check adapter output"""
        if not isinstance(result, bool):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "export adapter result type incorrect,should be bool.result={}".format(result))

    def export(self, datas: List[Dict], **kwargs: Any) -> bool:
        """ export """
        export_result = self._export(datas, **kwargs)
        self.check_export_output(export_result)
        return export_result

    @abstractmethod
    def _export(self, datas: List[Dict], **kwargs: Any) -> bool:
        """
        export to es
        Args:
            datas: datas
            kwargs: 关键字参数
        Return:
            导出状态。true：成功，false：失败。
        """
        ...
