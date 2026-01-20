#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import re
from typing import Any

import yaml

from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.file_utils import FileUtils

logger = logging.get_logger()


def merge_internal_config(external_config=None):
    if external_config is None:
        external_config = {}
    config = Config(config_dict=external_config)
    config.update_internal_config()
    return config.get_final_config()


class Config:
    """Parse config yaml file into Config class"""

    def __init__(self, config_file_path=None, config_dict=None):

        if config_dict is None:
            config_dict = {}
        self.yaml_loader = self._build_yaml_loader()
        self.file_config = self._load_file_config(config_file_path)
        self.variable_config = config_dict

        self.external_config = self._merge_external_config()
        self.internal_config = {}
        self.final_config = self._merge_final_config()

    def _build_yaml_loader(self):
        loader = yaml.FullLoader
        loader.add_implicit_resolver(
            "tag:yaml.org,2002:float",
            re.compile(
                """^(?:
             [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
            |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
            |\\.[0-9_]+(?:[eE][-+][0-9]+)?
            |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*
            |[-+]?\\.(?:inf|Inf|INF)
            |\\.(?:nan|NaN|NAN))$""",
                re.X,
            ),
            list("-+0123456789."),
        )
        return loader

    def _load_file_config(self, config_file_path: str) -> dict:
        file_config = dict()
        if config_file_path is None:
            return file_config
        FileUtils.check_file(config_file_path)
        with open(config_file_path, "r", encoding="utf-8") as f:
            yaml_content = yaml.load(f.read(), Loader=self.yaml_loader)
            if yaml_content:
                file_config.update(yaml_content)

        return file_config

    @staticmethod
    def _update_dict(old_dict: dict, new_dict: dict) -> dict:
        # Update the original update method of the dictionary:
        # If there is the same key in `old_dict` and `new_dict`, and value is of type dict, update the key in dict
        same_keys = []
        for key, value in new_dict.items():
            if key in old_dict and isinstance(value, dict):
                same_keys.append(key)
        for key in same_keys:
            old_item = old_dict[key]
            new_item = new_dict[key]
            old_item.update(new_item)
            new_dict[key] = old_item

        old_dict.update(new_dict)
        return old_dict

    def _merge_external_config(self) -> dict:
        external_config = dict()
        external_config = self._update_dict(external_config, self.file_config)
        external_config = self._update_dict(external_config, self.variable_config)

        return external_config

    def _merge_final_config(self) -> dict:
        final_config = dict()
        final_config = self._update_dict(final_config, self.internal_config)
        final_config = self._update_dict(final_config, self.external_config)

        return final_config

    def update_internal_config(self):
        internal_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "document/internal_basic_config.yaml")
        self.internal_config = self._load_file_config(internal_config_path)
        self.final_config = self._merge_final_config()

    def get_final_config(self) -> dict:
        return self.final_config

    def __setitem__(self, key, value):
        if not isinstance(key, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "index must be a str.")
        self.final_config[key] = value

    def __getattr__(self, item) -> Any:
        if "final_config" not in self.__dict__:
            raise ProcessorException(ErrorCode.ATTRIBUTE_ERROR,
                                     f"'Config' object has no attribute 'final_config'"
                                     )
        if item in self.final_config:
            return self.final_config[item]
        raise ProcessorException(ErrorCode.ATTRIBUTE_ERROR, f"'Config' object has no attribute '{item}'")

    def __getitem__(self, item) -> Any:
        return self.final_config.get(item)

    def __contains__(self, key) -> bool:
        if not isinstance(key, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR, "index must be a str.")
        return key in self.final_config

    def __repr__(self) -> str:
        return self.final_config.__str__()
