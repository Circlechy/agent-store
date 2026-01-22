# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a base class to build doctree for file."""
from abc import ABC

from doc_process.processors.document.parsers.doctree_build.utils.util import ConfigItem
from doc_process.processors.document.parsers.doctree_build.utils.consts import DEFAULT_USER_CONFIG, INTERNAL_CONFIG
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_DEGRADE_ENABLE
from doc_process.utils.error_code import ProcessorException, ErrorCode


class ABSBuilder(ABC):
    """ Abstract doctree builder  """

    def __init__(self, cfg, **kwargs):
        default_user_cfg = self._get_default_user_cfg()
        internal_cfg = self._get_internal_cfg()
        CheckUtils.check_type(cfg, dict, "cfg")
        final_cfg = default_user_cfg
        final_cfg = ConfigItem.merge_dict_cfg(final_cfg, cfg)
        final_cfg = ConfigItem.merge_dict_cfg(final_cfg, internal_cfg)
        self.degrade = kwargs.get("degrade", {}).get("enable", DEFAULT_DEGRADE_ENABLE)
        cfg_item = ConfigItem.from_dict(final_cfg)
        self._check_cfg(cfg_item)
        self.cfg = cfg_item

    @classmethod
    def decide(cls, f_path):
        """ match builder and file by file suffix """
        return f_path.endswith(cls.file_suffix())

    @classmethod
    def file_suffix(cls) -> str:
        """file suffix"""
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    def build(self, path):
        """ build doctree from file """
        doc, context = self.read_from_path(path)
        return doc, context

    def read_from_path(self, path):
        """ read from file """
        raise ProcessorException(ErrorCode.NOT_IMPLEMENTED_ERROR)

    def _check_cfg(self, cfg):
        """ check config """
        ...

    def _get_default_user_cfg(self):
        """ get default cfg """
        return DEFAULT_USER_CONFIG.get(self.file_suffix().strip("."), {})

    def _get_internal_cfg(self):
        """ get internal cfg """
        return INTERNAL_CONFIG.get(self.file_suffix().strip("."), {})
