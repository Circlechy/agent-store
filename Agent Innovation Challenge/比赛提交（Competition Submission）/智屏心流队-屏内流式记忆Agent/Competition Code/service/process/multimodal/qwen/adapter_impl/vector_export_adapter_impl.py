from typing import List, Dict, Any

import torch
import os
import faiss

from doc_process.processors.multimodal.base.adapter.export_adapter import ExportAdapter
from doc_process.utils import logging
from service.process.multimodal.vstream.model.vstream_arch import VStreamMetaForCausalLM

logger = logging.get_logger()

class QwenExportAdapterImpl(ExportAdapter):
        
    def __init__(self, config: Dict, **kwargs: Any):
        super().__init__()
        self.vision_cache_folder = os.path.join(config['faiss_engine']['vision_cache'], str(config['event_id']))
        if not os.path.exists(self.vision_cache_folder):
            os.makedirs(self.vision_cache_folder)        
        self.index_path = os.path.join(self.vision_cache_folder, config['faiss_engine']['index'])
        self.total_index_path = os.path.join(config['faiss_engine']['vision_cache'], config['faiss_engine']['index'])

    def _export(self, image_features: List[Dict], **kwargs: Any) -> bool:
        logger.info("QwenExportAdapterImpl _export()")        
        self.vector_faiss = faiss.read_index(self.index_path) if os.path.exists(self.index_path) else faiss.IndexFlatIP(768)
        self.total_vector_faiss = faiss.read_index(self.total_index_path) if os.path.exists(self.total_index_path) else faiss.IndexFlatIP(768)
        for image_feature in image_features:
            self.vector_faiss.add(image_feature.cpu())
            self.total_vector_faiss.add(image_feature.cpu())
        faiss.write_index(self.vector_faiss, self.index_path)
        faiss.write_index(self.total_vector_faiss, self.total_index_path)
        return True


