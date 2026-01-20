# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import os

from doc_process.utils import logging
from doc_process.utils.error_code import ErrorCode

logger = logging.get_logger()

default_env_yaml_dict = {
    "dev": "basic_config.yaml",
    "test": "basic_config.yaml",
    "release": "basic_config.yaml",
}


class ParseConfig:
    @staticmethod
    def parse_config(env: str, env_yaml_dict=None):
        if env_yaml_dict is None:
            env_yaml_dict = default_env_yaml_dict
        if env in env_yaml_dict:
            yaml_config_path = env_yaml_dict[env]
        else:
            rsp = {"code": ErrorCode.PARAM_INVALID.code(), "msg": "env={} is unknown.".format(env)}
            logger.error("response={}".format(rsp))
            return rsp

        logger.info("env={},yaml={}".format(env, yaml_config_path))
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_path = os.path.join(cur_dir, yaml_config_path)
        if not os.path.isfile(absolute_path):
            logger.error("config path={} is invalid".format(absolute_path))
            return {"code": ErrorCode.CONFIG_INVALID.code(), "msg": "config path is invalid."}

        return absolute_path
