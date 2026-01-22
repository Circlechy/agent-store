# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import json
import traceback
from typing import Dict

from doc_process.utils import logging
from doc_process.utils.error_code import ErrorCode, ProcessorException
from service.process.multimodal.orkestractor_kernel import UpdateLocalVideoOrchestrator, \
    MultimodalProcessOrchestrator
from service.process.multimodal.pipeline_factory import PipelineFactory
from service.process.multimodal.utils.constant import Scene
from doc_process.utils import logging
from service.process.multimodal.orkestractor_kernel import UpdateLocalVideoOrchestrator
from service.process.multimodal.pipeline_factory import PipelineFactory
from service.process.multimodal.textual_process_service import BaseProcessService
from service.process.multimodal.utils.constant import Scene
from service.process.multimodal.utils.file_utils import FileStorageWithLock
from service.process.multimodal.vstream.mm_utils import get_model_name_from_path
from service.process.multimodal.vstream.model.builder import load_pretrained_model

logger = logging.get_logger()


def init_vision_model(args):
    # model_path = "/data/yjx/code/Flash-VStream/model/vision_model"
    model_name = get_model_name_from_path(args.model_path)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        args.vision_model_path, args.model_base,
        model_name, args.load_8bit,
        args.load_4bit, device=args.device_vision)

    #
    # model.save_pretrained("/data/yjx/code/Flash-VStream/model/vision_model") # 保存模型
    # # 清空文件
    # model.storage.clear()

    model.use_video_streaming_mode = True
    # model.video_embedding_memory = Manager().list()

    if args.video_max_frames is not None:
        model.config.video_max_frames = args.video_max_frames
        logger.info(f'Important: set model.config.video_max_frames = {model.config.video_max_frames}')

    logger.info("process model.device is {}".format(model.device))
    model_kwargs = {
        "model_name": model_name,
        "model": model,
        "image_processor": image_processor,
    }
    return model_kwargs


vision_model_inited_kwargs = {}
scene_pool = {}
# 不要包含锁、logger、线程、pipeline对象，否则多进程启动失败！！！

class VstreamProcessService(BaseProcessService):
    """MultimodalProcessService"""

    def __init__(self, config_dict, args, **kwargs):
        self.config_dict = config_dict
        global vision_model_inited_kwargs
        if not vision_model_inited_kwargs:
            vision_model_inited_kwargs = init_vision_model(args)
        self.model_kwargs = vision_model_inited_kwargs
        self.model_kwargs.get("model").storage = FileStorageWithLock(kwargs.get("embedding_file"))


    def process(self, input_dict: Dict):
        input_dict.update(self.model_kwargs)
        scene_name = input_dict.get("scene", {}).get("name")
        # scene_pool 不能为对象属性，因为它是复杂对象，不能被pickle
        global scene_pool
        if not scene_pool:
            pipeline = PipelineFactory.create_vstream_textual_pipeline(self.config_dict, **self.model_kwargs)
            scene_pool = {
                Scene.VIDEO.value: UpdateLocalVideoOrchestrator(self.config_dict, pipeline=pipeline),
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
