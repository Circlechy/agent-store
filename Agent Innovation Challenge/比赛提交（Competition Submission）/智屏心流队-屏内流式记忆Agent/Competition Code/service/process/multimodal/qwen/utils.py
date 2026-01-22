import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import cv2
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
# from transformers import AutoProcessor, Qwen2_5OmniForConditionalGeneration
#
# from qwen_omni_utils import process_mm_info

class TextSearch:
    @staticmethod
    def build_tfidf(captions: List[str]):
        vect = TfidfVectorizer().fit(captions)
        mat = vect.transform(captions)
        return vect, mat

    @staticmethod
    def most_similar(query: str, vect, mat) -> int:
        q_vec = vect.transform([query])
        sims = (mat @ q_vec.T).toarray().ravel()
        return int(sims.argmax())
class VideoUtils:
    @staticmethod
    def frames_to_tmp_mp4(frames: List[np.ndarray], fps: int) -> Path:
        h, w, _ = frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        tmp = Path(tempfile.mkstemp(suffix=".mp4")[1])
        vw = cv2.VideoWriter(str(tmp), fourcc, fps, (w, h))
        for f in frames:
            vw.write(f)
        vw.release()
        return tmp

    @staticmethod
    def build_clip_mp4(schema: dict, max_frames: int) -> Path:
        meta = schema["metadata"]
        buf_idx=meta["buf_idx"]
        #todo: use buf_idx  @xiaoneng
        cap = cv2.VideoCapture(buf_idx)
        frames = []
        for _ in range(max_frames):
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
        cap.release()
        return VideoUtils.frames_to_tmp_mp4(frames, fps)