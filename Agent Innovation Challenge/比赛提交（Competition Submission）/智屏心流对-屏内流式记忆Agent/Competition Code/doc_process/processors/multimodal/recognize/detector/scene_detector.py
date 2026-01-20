#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from doc_process.processors.multimodal.recognize.detector.base_detector import BaseDetector
from doc_process.utils import logging

logger = logging.get_logger()


class SceneDetector(BaseDetector):
    """SceneDetector"""
    def detect(self,frame_queue, video_embeddings,**kwargs):
        """detect"""
