from typing import Any, List, Dict

import torch

from doc_process.processors.multimodal.base.adapter.embedding_adapter import ImageEmbeddingAdapter
from doc_process.utils import logging
from service.process.multimodal.vstream.model.vstream_arch import VStreamMetaForCausalLM

logger = logging.get_logger()


class VstreamImageEmbeddingAdapterImpl(ImageEmbeddingAdapter):

    def __init__(self, config: Dict, **kwargs):
        self._parse_input(config)
        self.init_kwargs = kwargs
        self.image_processor = self.init_kwargs.get("image_processor")
        self.model: VStreamMetaForCausalLM = self.init_kwargs.get("model")

    def _parse_input(self, config: Dict):
        """_parse_input"""
        self.config = config

    def _image_embedding(self, bytes_list: List[Any], **kwargs: Any) -> List:
        results = []
        for video_clip in bytes_list:
            image = self.image_processor.preprocess(video_clip, return_tensors='pt')['pixel_values']  # 将其转换为 PyTorch 张量
            image = image.unsqueeze(0)  # 在张量的第 0 维添加一个维度，以满足模型输入的要求。
            image_tensor = image.to(self.model.device, dtype=torch.float16)
            with torch.inference_mode():
                image_features = self.model.embed_video_streaming(image_tensor)  # 更新共享內存
                results.append(image_features)
        return results
