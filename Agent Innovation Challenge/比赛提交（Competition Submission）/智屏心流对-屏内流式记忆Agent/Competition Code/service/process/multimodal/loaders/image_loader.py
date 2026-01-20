#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Any, List

import numpy as np
from PIL import Image
from torch.multiprocessing import Queue

from doc_process.processors.multimodal.base.loaders.base import BaseLoader


class ImageLoader(BaseLoader):
    """Interface for Loader."""

    def load(self, file_paths: List[str], frame_queue: Queue, video_fps=1.0, play_speed=1.0, **kwargs: Any) -> None:
        for file_path in file_paths:
            # 读取本地图片
            img = Image.open(file_path).convert('RGB')
            # 转为 numpy 数组，shape 为 (720, 1280, 3)
            img_array = np.array(img)
            # 扩展 batch 维度，shape 变为 (1, 720, 1280, 3)
            img_array = np.expand_dims(img_array, axis=0)
            frame_queue.put(img_array)
        frame_queue.put(None)
