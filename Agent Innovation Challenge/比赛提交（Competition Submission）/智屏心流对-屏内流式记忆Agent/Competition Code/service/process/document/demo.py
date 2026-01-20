# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.


import json

from doc_process.utils import logging
from scene.document.parse_config import ParseConfig
from scene.document.pipeline.process_service import DocumentProcessService

logger = logging.get_logger()

if __name__ == "__main__":
    # ---------------dev-用户库----------
    kwargs_dict = {
        "input_files": ["/data01/a00575982/code/metaengine/knowledge_retriever/doc_process_full/test/demo_service/data/data8/test.xlsx"],
        "user_id": "2024120202",
        "session_id": "session_01",
        "doc_id": ["doc_01"],
        "debug": True,
        "scene": {
            "name": "rag_local",
        }
    }
    request = json.dumps(kwargs_dict, ensure_ascii=False)
    logger.info("request={}".format(request))

    yaml_config_path = ParseConfig.parse_config("dev")
    process_service = DocumentProcessService(yaml_config_path)
    response = process_service.process(kwargs_dict)
