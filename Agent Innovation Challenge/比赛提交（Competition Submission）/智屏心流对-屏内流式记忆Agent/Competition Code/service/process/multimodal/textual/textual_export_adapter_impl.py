import json
from typing import List, Dict, Any

from doc_process.processors.multimodal.base.adapter.export_adapter import ExportAdapter
from doc_process.utils import logging
from service.process.common.client.es_client import ESClient
from service.process.common.client.es_request import bulk_insert_documents
from service.process.common.utils.log import request_logger

logger = logging.get_logger()


class TextualExportAdapterImpl(ExportAdapter):
    def __init__(self, config: Dict):
        self.config = config

        self.es_url = self.config.get("url")  # 必填
        self.analyzer = self.config.get("analyzer", "")
        # self.client = ESClient(es_url)
        self.index = self.config.get("index")  # 必填

    def _export(self, datas: List[Dict], **kwargs: Any) -> bool:
        """export2es"""
        store_res = True
        if not datas:
            return store_res
        request_logger.info(datas)
        ids = [data["id"] for data in datas]
        logger.debug("es to be export chunks num={}".format(len(datas)))
        # 执行批量插入
        result = bulk_insert_documents(
            host_url=self.es_url,
            index_name=self.index,
            documents=datas,
        )

        # 处理结果
        if result is not None:
            logger.info(f"成功插入文档到 {self.index} 索引:成功插入文档数量: {result.get('items', []) and len(result['items'])}")
        else:
            logger.error(f"未能插入文档到 {self.index} 索引")
        return True