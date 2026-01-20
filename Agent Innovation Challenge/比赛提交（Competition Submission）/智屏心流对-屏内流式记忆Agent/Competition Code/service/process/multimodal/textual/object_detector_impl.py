#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any

import numpy as np
import torch
from PIL import Image
from PIL import ImageDraw, ImageFont
from openai import OpenAI
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

from doc_process.processors.multimodal.recognize.detector.scene_detector import SceneDetector
from doc_process.utils import logging
from service.process.multimodal.textual.textual_config import FOOD_DETECT_STR, PERSONAL_DETECT_STR
from service.process.multimodal.utils.image_utils import base64_to_int64, frames_to_base64
from service.process.multimodal.utils.ug_utils import UgClient

logger = logging.get_logger()


class SceneInAndOutDetectorAdapterImpl(SceneDetector):
    def __init__(self,
                 object_str: str = PERSONAL_DETECT_STR,
                 object_detect_model_path: str = '/home/users/nus/e0970163/scratch/models/grounding-dino-base/',
                 device: str = "cuda:0", **kwargs):
        # init object detect model
        self.object_str = object_str
        self.object_detect_processor = AutoProcessor.from_pretrained(object_detect_model_path)
        self.object_detect_model = AutoModelForZeroShotObjectDetection.from_pretrained(
            object_detect_model_path).to(device=device)
        self.device = device

    def detect(self, frame_queue, video_embeddings, **kwargs) -> Any:
        results_list = []
        for frame_info in frame_queue:
            frame = frame_info.frame_np
            results = self.dino_object_detect(frame)
            # todo:@hy
            if results and results[0]["labels"]:
                logger.info("检测结果：{}".format(results))
                results_list.append(results)
                # annotated_image = draw_detections(frame, results)
                # output_path = '_detected.jpg'
                # annotated_image.save(output_path)
                # logger.info(f"检测结果已保存至: {output_path}")
                #
                # # 可选：显示图像
                # # annotated_image.show()
            else:
                logger.info("未检测到目标物体")
                results_list.append(None)

        return results_list

    def dino_object_detect(self, image: np.array):

        image = Image.fromarray(image[0], mode='RGB')
        start_time = time.time()
        inputs = self.object_detect_processor(images=image, text=self.object_str, return_tensors="pt").to(
            device=self.device)

        with torch.no_grad():
            outputs = self.object_detect_model(**inputs)

        results = self.object_detect_processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=0.4,
            text_threshold=0.3,
            target_sizes=[image.size[::-1]])

        # TODO: LOG '耗时：', str(time.time() - start_time) + 's'
        return results
