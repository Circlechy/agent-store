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

logger = logging.get_logger()



class BaseProcessService:
    """MultimodalProcessService"""

    def process(self, input_dict: Dict):
        input_dict.update(self.model_kwargs)
        scene_name = input_dict.get("scene", {}).get("name")
        orchestrator: MultimodalProcessOrchestrator = self.scene_pool[scene_name]

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


class TextualProcessService(BaseProcessService):
    """MultimodalProcessService"""

    def __init__(self, config_dict, args, **kwargs):
        # todo:@hy
        pipeline = PipelineFactory.create_textual_pipeline(config_dict)

        self.scene_pool = {
            Scene.VIDEO.value: UpdateLocalVideoOrchestrator(config_dict, pipeline=pipeline),
        }
        self.model_kwargs = {}
