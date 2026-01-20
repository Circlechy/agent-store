from typing import Any, List, Dict
from PIL import Image

import torch
import os
import faiss

from doc_process.processors.multimodal.base.adapter.embedding_adapter import ImageEmbeddingAdapter
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from service.process.multimodal.vstream.model.vstream_arch import VStreamMetaForCausalLM

logger = logging.get_logger()


class QwenImageEmbeddingAdapterImpl(ImageEmbeddingAdapter):

    def __init__(self, config: Dict,**kwargs):
        self._parse_input(config)
        self.model = kwargs.get("model")
        self.image_processor = kwargs.get("image_processor")
        self.device = kwargs.get("args").device_vision
        self.vision_cache_folder = os.path.join(config['faiss_engine']['vision_cache'], str(config['event_id']))
        if not os.path.exists(self.vision_cache_folder):
            os.makedirs(self.vision_cache_folder)
        self.index_path = os.path.join(self.vision_cache_folder, config['faiss_engine']['index'])

    def _parse_input(self, config: Dict):
        """_parse_input"""
        self.config = config
        CheckUtils.check_type(self.config, dict, "config")

    def _image_embedding(self, bytes_list: List[Any], **kwargs: Any) -> List:
        results = []
        logger.info("QwenImageEmbeddingAdapterImpl _image_embedding()")
        if os.path.exists(self.index_path):
            self.vector_faiss = faiss.read_index(self.index_path)
            cur_index = self.vector_faiss.ntotal
        else:
            cur_index = 0
        for i, video_clip in enumerate(bytes_list):
            pil_image = Image.fromarray(video_clip.frame_np.squeeze())
            image = self.image_processor(pil_image) # 将其转换为 PyTorch 张量
            image = image.unsqueeze(0)  # 在张量的第 0 维添加一个维度，以满足模型输入的要求。
            image_tensor = image.to(self.device, dtype=torch.float16)
            with torch.inference_mode():
                image_features = self.model.encode_image(image_tensor)
                image_features /= image_features.norm(dim=-1, keepdim=True)
                results.append(image_features)
            pil_image.save(os.path.join(self.vision_cache_folder, f'{cur_index + i}.png'), 'png')
        return results
