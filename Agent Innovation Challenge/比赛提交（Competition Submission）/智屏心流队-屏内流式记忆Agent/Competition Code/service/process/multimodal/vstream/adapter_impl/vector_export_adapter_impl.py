from typing import List, Dict, Any

import torch

from doc_process.processors.multimodal.base.adapter.export_adapter import ExportAdapter
from doc_process.utils import logging
from service.process.multimodal.vstream.model.vstream_arch import VStreamMetaForCausalLM

logger = logging.get_logger()


class VstreamVectorExportAdapterImpl(ExportAdapter):
    def __init__(self, config: Dict, **kwargs):
        self._parse_input(config)
        self.init_kwargs = kwargs

    def _parse_input(self, config: Dict):
        """_parse_input"""
        self.config = config

    def _export(self, datas: List[Dict], **kwargs: Any) -> bool:
        model: VStreamMetaForCausalLM = self.init_kwargs.get("model")
        for image_features in datas:
            with torch.inference_mode():
                model.stored_video_streaming(image_features)
        return True
