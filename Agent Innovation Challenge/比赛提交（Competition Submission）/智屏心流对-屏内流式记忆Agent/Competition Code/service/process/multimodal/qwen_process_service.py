# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import json
import traceback
from typing import Dict
import os

from doc_process.utils import logging
from doc_process.utils.error_code import ErrorCode, ProcessorException
from service.process.multimodal.orkestractor_kernel import UpdateLocalVideoOrchestrator, \
    MultimodalProcessOrchestrator
from service.process.multimodal.pipeline_factory import PipelineFactory
from service.process.multimodal.textual_process_service import BaseProcessService
from service.process.multimodal.utils.constant import Scene
from service.process.multimodal.utils.file_utils import FileStorageWithLock
from transformers import AutoProcessor, Qwen2_5OmniForConditionalGeneration
from cn_clip.clip import load_from_name
logger = logging.get_logger()


def init_vision_model(args):
    clip_model, preprocess = load_from_name('ViT-L-14', device=args.device_vision, download_root=os.path.dirname(args.vision_model_path))
    clip_model.eval()
    model_kwargs = {
        "model": clip_model,
        "image_processor": preprocess,
    }
    return model_kwargs


vision_model_inited_kwargs = {}
scene_pool = {}
# 不要包含锁、logger、线程、pipeline对象，否则多进程启动失败！！！

class QwenProcessService(BaseProcessService):
    """MultimodalProcessService"""

    def __init__(self, args, config_dict, **kwargs):
        self.config_dict = config_dict
        global vision_model_inited_kwargs
        if not vision_model_inited_kwargs:
            vision_model_inited_kwargs = init_vision_model(args)
        self.model_kwargs = vision_model_inited_kwargs

    def process(self, input_dict: Dict):
        input_dict.update(self.model_kwargs)
        scene_name = input_dict.get("scene", {}).get("name")
        # scene_pool 不能为对象属性，因为它是复杂对象，不能被pickle
        global scene_pool
        if not scene_pool:
            # todo: 1. @xinjiapo
            small_pipe = PipelineFactory.create_qwen_textual_pipeline(self.config_dict, **input_dict)
            big_pipe   = PipelineFactory.create_event_only_pipeline(self.config_dict, **input_dict)
            scene_pool = {
                Scene.VIDEO.value: UpdateLocalVideoOrchestrator(
                    config_dict=self.config_dict,
                    small_pipeline=small_pipe,    # ← 仅 3-帧小算子
                    big_pipeline=big_pipe         # ← 含 event_textual_recognizer
                )
            }
        orchestrator: MultimodalProcessOrchestrator = scene_pool[scene_name]

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