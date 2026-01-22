# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to build doctree for .txt file."""
import os
import stat

from doc_process.processors.document.parsers.doctree_build.abs_builder import ABSBuilder
from doc_process.processors.document.parsers.doctree_build.utils.data_cls import DocTree, LabelDict, Node
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class PlainBuilder(ABSBuilder):
    """ Doctree builder for .txt file """

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        return ".txt"

    def read_from_path(self, path):
        """ read from file """
        if not os.path.exists(path):
            raise ProcessorException(ErrorCode.INVALID_FILE_PATH, "txt File {} does not exist.".format(path))

        modes = stat.S_IWUSR | stat.S_IRUSR  # 用户具有读写权限
        for decode_type in self.cfg.decode_type:
            try:
                with os.fdopen(os.open(path, os.O_RDWR, modes), "r", encoding=decode_type) as f:
                    text_node = Node(text=f.read(), label=LabelDict.CONTENT)
                return DocTree.from_node_list([text_node], path.stem), {}
            except UnicodeDecodeError:
                logger.debug("File {} parse by decode_type={} fail.".format(path.name, decode_type))
        raise ProcessorException(ErrorCode.FILE_READ_ERROR, "File {} read fail.".format(path.name))

    def _check_cfg(self, cfg):
        """ check config """
        CheckUtils.check_type(cfg.decode_type, list, "parser.txt.decode_type")
        if len(cfg.decode_type) <= 0:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "'decode_type' is empty.")
        for decode_type in cfg.decode_type:
            CheckUtils.check_type(decode_type, str, "parser.txt.decode_type")
        CheckUtils.check_types(cfg.file_size_limit, [int, float], "parser.txt.file_size_limit")
