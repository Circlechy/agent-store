#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from collections import deque
from pathlib import Path

import json
from datetime import datetime
from typing import Dict, List

import numpy as np

from service.process.multimodal.qwen.prompts import PROMPT_CN
from service.process.multimodal.qwen.utils import VideoUtils
from doc_process.processors.multimodal.recognize.detector.scene_detector import SceneDetector
from doc_process.utils import logging

# from service.process.multimodal.vstream.adapter_impl.scene_detector_impl import frames_to_base64

logger = logging.get_logger()

output_dir = Path("captions")
output_dir.mkdir(exist_ok=True)

class ShortTermSceneDetectorImpl(SceneDetector):
    """SceneDetector"""
    def __init__(self,**kwargs):

        self.img_ids = set()

        self.MAX_FRAMES = kwargs.get("MAX_FRAMES")
        self.processor=kwargs.get("processor")
        self.model=kwargs.get("model")
        self.buf: deque[np.ndarray] = deque(maxlen=self.MAX_FRAMES)
        self.buf_idx = 0
        self.buf_count = 0

    def detect(self,frame_queue, video_embeddings,**kwargs)->List[Dict]:
        """detect"""
        self.buf.append(frame_queue)
        schemas = []
        if len(self.buf) == self.MAX_FRAMES:
            tmp_mp4 = VideoUtils.frames_to_tmp_mp4(self.buf)
            caption = self.generate_caption(tmp_mp4)
            tmp_mp4.unlink()

            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            schema = {
                "id": f"{self.buf_idx}",
                "start_time": now,
                "end_time": now,
                "scene_id": "",  # 空
                "scene_catogery": ["car"],
                "caption": caption,
                "metadata": {"buf_idx": self.buf_idx},
                "detail": [{"category": "", "ocr": "", "location": "", "caption": "", "metadata": {}}],
            }
            schemas.append(schema)
            Path(output_dir / f"clip_{self.buf_idx}.json").write_text(
                json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[CAP] clip_{self.buf_idx}.json saved")
            #todo: save self.buf to file @xiaoneng
            #todo: save embedding
            self.buf.clear()
            self.buf_idx += 1
        return schemas

    def generate_caption(self, tmp_mp4: Path) -> str:
        messages = [
            {"role": "system", "content": [{"type": "text", "text": "You produce Chinese video captions only."}]},
            {"role": "user", "content": [
                {"type": "video", "video": str(tmp_mp4), "max_frames": self.MAX_FRAMES},
                {"type": "text", "text": PROMPT_CN}
            ]}
        ]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        _, imgs, vids = process_mm_info(messages, use_audio_in_video=False)
        inp = self.processor(text=text, images=imgs, videos=vids, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            out = self.model.generate(**inp, max_new_tokens=128, return_audio=False)
        gen_ids = out[0][inp.input_ids.shape[1]:]
        caption = self.processor.decode(gen_ids, skip_special_tokens=True)
        return caption.strip()

