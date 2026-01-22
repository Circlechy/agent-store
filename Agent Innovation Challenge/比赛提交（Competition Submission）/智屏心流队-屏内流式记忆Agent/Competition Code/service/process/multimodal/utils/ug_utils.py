from doc_process.utils import logging
from service.process.common.client.es_request import bulk_insert_documents, delete_all_documents_in_index, \
    elasticsearch_query, get_all_documents
from service.process.multimodal.textual.textual_config import UG_DOCUMENTS
from typing import List, Dict
import json
import os
from pathlib import Path

logger = logging.get_logger()


def bulk_insert(es_url, index_name, documents):
    # 执行批量插入
    result = bulk_insert_documents(
        host_url=es_url,
        index_name=index_name,
        documents=documents,
    )
    # 处理结果
    if result is not None:
        logger.info(f"成功插入到{index_name} 索引，成功插入文档数量: {result.get('items', []) and len(result['items'])}")
    else:
        logger.error(f"未能插入文档到 {index_name} 索引")


def delete_all_documents(host, index_name):
    result = delete_all_documents_in_index(
        host_url=host,
        index_name=index_name,
    )
    # 处理结果
    if result is not None:
        logger.info(f"成功删除 {index_name} 索引中的所有文档:已删除文档数量: {result.get('deleted', 0)}")
    else:
        logger.error(f"未能清空 {index_name} 索引")


def search_documents(ES_URL, index_name, query):
    # 构建查询请求体
    QUERY_BODY = {
        "query": {
            "match": {
                "caption": query
            }
        }
    }

    # 执行查询
    result = elasticsearch_query(ES_URL, index_name, QUERY_BODY)

    # 处理查询结果
    if result:
        return [hit['_source'] for hit in result['hits']['hits']]

    return []

# ------------------- 把小艺简报UG数据转成caption -------------------

def events_json_to_documents(json_path: str) -> List[Dict]:
    """
    将 indexed_events.json 中所有事件转成
    [{"caption": "..."} , ...] 以便写入 ES。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    # 顶层每个 key 都是一类 events
    for event_list in data.values():          
        if not isinstance(event_list, list):
            continue
        for evt in event_list:
            # 直接把整条事件 dump 成 JSON 字符串写进 caption
            # documents.append({
            #     "caption": json.dumps(evt, ensure_ascii=False, separators=(",", ":"))
            # })
            documents.append({
                "caption": "```json\n" +
                           json.dumps(evt, ensure_ascii=False, indent=2) +
                           "\n```"
            })
    logger.info(f"共转换 {len(documents)} 条事件为 ES 文档")
    return documents

class UgClient:
    def __init__(self):
        self.es_url = "https://10.168.12.121:9200"  # 替换为你的 ES 地址
        self.index_name = "ug_mock"  # 替换为你的目标索引

    def search(self, query=None):
        result = search_documents(self.es_url, self.index_name, query)
        result = list(set(data.get("caption") for data in result))
        return result

    def search_all(self):
        result = get_all_documents(self.es_url, self.index_name)
        result = list(set(data.get("caption") for data in result))
        return result


# 使用示例
if __name__ == "__main__":
    ug_client = UgClient()
    es_url = "https://10.168.12.121:9200"  # 替换为你的 ES 地址
    index_name = "ug_mock_offline"  # 替换为你的目标索引
    BASE_DIR = Path(__file__).resolve().parent
    JSON_PATH = (BASE_DIR.parent / "indexed_events0.json").as_posix()
    docs = events_json_to_documents(JSON_PATH)
    delete_all_documents(es_url, index_name)
    # documents = [
    #     {
    #         "caption": (
    #             "起点: （空）; 地点: 星巴克; 事件描述: 和穿着灰色衣服男士一起喝咖啡; "
    #             "发生日期: （空）; 持续时间: （空）; 参与人: 穿着灰色衣服的男士; "
    #             "event_id: 92; type: social_events"
    #         )
    #     }
    # ]
    # bulk_insert(es_url, index_name, UG_DOCUMENTS)
    bulk_insert(es_url, index_name, docs)
    # logger.info(ug_client.search("号码"))
    # logger.info(ug_client.search(""))
    # logger.info(ug_client.search_all())
# StreamingQA/service/process/multimodal/utils/ug_utils.py
# StreamingQA/service/process/multimodal/indexed_events0.json