# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import json
import traceback
from abc import ABC
from typing import Dict

from doc_process.config_repository.config import Config
from doc_process.context.base_schema import StreamType
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_KNOWLEDGE_BASE_NAME
from doc_process.utils.error_code import ErrorCode, ProcessorException
from scene.document.pipeline.orkestractor_kernel import UpdateStreamDocsOrchestrator, UpdateLocalDocsOrchestrator, \
    DeleteDocsOrchestrator, \
    DocumentProcessOrchestrator
from scene.document.utils.constant import Scene, DEFAULT_SCENE


logger = logging.get_logger()

class Service(ABC):
    """Service"""


class DocumentProcessService:
    """DocumentProcessService"""

    def __init__(self, yaml_config_path:str):
        yaml_config = Config(config_file_path=yaml_config_path)
        config_dict = yaml_config.get_final_config()

        self.scene_pool = {
            Scene.RAG_DELETE.value: DeleteDocsOrchestrator(config_dict),
            Scene.RAG_LOCAL.value: UpdateLocalDocsOrchestrator(config_dict),
            Scene.RAG.value: UpdateStreamDocsOrchestrator(config_dict),
            Scene.FAQ.value: UpdateStreamDocsOrchestrator(config_dict),
            Scene.T2I.value: UpdateStreamDocsOrchestrator(config_dict),
            Scene.GUOZIWEI.value: UpdateStreamDocsOrchestrator(config_dict),
        }

    @staticmethod
    def validate_server_input(input_dict: Dict) -> dict:
        """
        input_dict 所有key的value都有值
        """
        # step1: 使得 input_dict[key] !=None
        # 不包含key or value 为None
        if "scene" not in input_dict or input_dict.get("scene") is None:
            input_dict["scene"] = {}

        # step2: check type
        CheckUtils.check_type(input_dict["scene"], dict, "scene")

        # step3: check sub type
        scene_dict = input_dict["scene"]
        if "name" not in scene_dict or scene_dict["name"] is None:
            scene_dict["name"] = DEFAULT_SCENE
        CheckUtils.check_type(scene_dict["name"], str, "scene_dict['name']")

        # step4: check value is valid
        # 获取所有属性的 value 值，存为字典
        scene_value_set = {scene.value for scene in Scene}
        scene_name = scene_dict["name"]
        if scene_name not in scene_value_set:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "unknown scene={}.".format(scene_name))
        return input_dict

    @staticmethod
    def validate_sdk_input(input_dict: Dict) -> dict:
        """
        input_dict 所有key的value都有值
        """
        # step1: 使得 input_dict[key] !=None
        # 不包含key or value 为None
        #
        if "input_dir" not in input_dict or input_dict.get("input_dir") is None:
            input_dict["input_dir"] = ""
        if "input_files" not in input_dict or input_dict.get("input_files") is None:
            input_dict["input_files"] = []
        if "exclude_hidden" not in input_dict or input_dict.get("exclude_hidden") is None:
            input_dict["exclude_hidden"] = True
        if "recursive" not in input_dict or input_dict.get("recursive") is None:
            input_dict["recursive"] = False
        if "user_id" not in input_dict or input_dict.get("user_id") is None:
            input_dict["user_id"] = DEFAULT_KNOWLEDGE_BASE_NAME
        if "stream_type" not in input_dict or input_dict.get("stream_type") is None:
            input_dict["stream_type"] = StreamType.REAL.value
        if "debug" not in input_dict or input_dict.get("debug") is None:
            input_dict["debug"] = False
        if "session_id" not in input_dict or input_dict.get("session_id") is None:
            input_dict["session_id"] = ""
        if "doc_id" not in input_dict or input_dict.get("doc_id") is None:
            input_dict["doc_id"] = []

        # step2: check type
        CheckUtils.check_type(input_dict["input_dir"], str, "input_dir")
        CheckUtils.check_type(input_dict["input_files"], list, "input_files")
        CheckUtils.check_type(input_dict["exclude_hidden"], bool, "exclude_hidden")
        CheckUtils.check_type(input_dict["recursive"], bool, "recursive")
        CheckUtils.check_type(input_dict["user_id"], str, "user_id")
        CheckUtils.check_type(input_dict["stream_type"], int, "stream_type")
        CheckUtils.check_type(input_dict["debug"], bool, "debug")
        CheckUtils.check_type(input_dict["session_id"], str, "session_id")
        CheckUtils.check_types(input_dict["doc_id"], [str, list], "doc_id")
        return input_dict

    def process(self, input_dict: Dict):
        input_dict = self.validate_server_input(input_dict)
        input_dict = self.validate_sdk_input(input_dict)
        scene_name = input_dict.get("scene", {}).get("name")
        orchestrator: DocumentProcessOrchestrator = self.scene_pool[scene_name]

        try:
            response = orchestrator.forward(input_dict)
        except ProcessorException as e:
            response = {"code": e.error_code.code(), "msg": str(e)}
            logger.error(traceback.format_exc())

        except Exception as e:
            response = {"code": ErrorCode.FAILURE.code(), "msg": str(e)}
            logger.error(traceback.format_exc())
        logger.info("response={}".format(json.dumps(response, ensure_ascii=False)))
        return response
