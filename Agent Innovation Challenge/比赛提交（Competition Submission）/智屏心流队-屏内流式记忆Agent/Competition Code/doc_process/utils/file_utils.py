#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""File Utils"""
import os
from pathlib import Path
from typing import List

from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class FileUtils:
    """File Utils"""

    @staticmethod
    def get_base_name(path: str):
        """ get path basename """
        if isinstance(path, str):
            path: Path = Path(path)
        if not isinstance(path, Path):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "Path should be str or Path type, is {} now.".format(type(path)))
        file_name = path.name
        return file_name

    @staticmethod
    def check_path(input_):
        """ check path """
        file_name = FileUtils.get_base_name(input_)
        if not os.path.exists(input_):
            raise ProcessorException(ErrorCode.FILE_INVALID, "Path of {} does not exist.".format(file_name))
        if not os.access(input_, os.R_OK):
            raise ProcessorException(ErrorCode.FILE_INVALID, "Path of {} is not readable.".format(file_name))

    @staticmethod
    def check_dir(path):
        """
        is valid dir
        """
        FileUtils.check_path(path)
        if not os.path.isdir(path):
            file_name = FileUtils.get_base_name(path)
            raise ProcessorException(ErrorCode.FILE_INVALID, "Path of {} is not directory.".format(file_name))

    @staticmethod
    def check_file(file_path, size_limit: float = None):
        """
        is valid file
        """
        FileUtils.check_path(file_path)
        file_name = FileUtils.get_base_name(file_path)
        if not os.path.isfile(file_path):
            raise ProcessorException(ErrorCode.FILE_INVALID, "Path of {} is not a file.".format(file_name))
        if size_limit is not None:
            file_size = os.path.getsize(file_path) / 1024 / 1024
            if file_size > size_limit:
                raise ProcessorException(
                    ErrorCode.FILE_TOO_LARGE,
                    "File {} is too big(size={:.2f}MB). Size limit: {:.2f}MB.".format(
                        file_name, file_size, size_limit
                    )
                )

    @staticmethod
    def is_hidden(path: Path) -> bool:
        """where is hidden"""
        return any(
            part.startswith(".") and part not in [".", ".."] for part in path.parts
        )

    @staticmethod
    def list_files(directory: str, recursive: bool) -> List[str]:
        """
        返回指定文件夹下文件路径
        :param directory: 待处理目录
        :param recursive: 是否递归搜索文件路径
        """

        file_paths: List[str] = []
        FileUtils.check_dir(directory)
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_paths.append(os.path.join(root, file))
        else:
            for entry in os.scandir(directory):
                if entry.is_file():
                    file_paths.append(entry.path)
        return file_paths
