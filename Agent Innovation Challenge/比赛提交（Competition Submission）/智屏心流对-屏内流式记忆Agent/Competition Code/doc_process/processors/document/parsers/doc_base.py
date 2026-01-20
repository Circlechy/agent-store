#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from doc_process.context.base_schema import ProcessComponent
from doc_process.utils import logging
from doc_process.context.doc_schema import (
    Document,
    Context,
)
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ErrorCode, ProcessorException

logger = logging.get_logger()


class DocumentBaseParser(ProcessComponent, ABC):
    """Utilities for parsing data from a file."""

    def __call__(self, file_path: Path, context: Context, **kwargs: Any):
        self._parse_input(file_path, context, **kwargs)
        self._parse(file_path, context, **kwargs)

    @abstractmethod
    def _parse(self, file_path: Path, context: Context, **kwargs: Any) -> Optional[Document]:
        """Parse file into document."""
        ...

    def _parse_input(self, file_path: Path, context: Context, **kwargs: Any):
        """_parse_input"""
        try:
            document = kwargs.get("document")
            CheckUtils.check_type(file_path, Path, "file_path")
            CheckUtils.check_type(context, Context, "context")
            CheckUtils.check_type(document, Document, "document in kwargs")
        except ProcessorException as ex:
            raise ProcessorException(ErrorCode.PARSER_PARAM_INVALID, str(ex)) from ex
