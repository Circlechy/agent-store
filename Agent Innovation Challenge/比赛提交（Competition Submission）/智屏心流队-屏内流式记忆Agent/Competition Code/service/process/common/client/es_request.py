import requests
import json
from requests.auth import HTTPBasicAuth  # 如果需要认证
from doc_process.utils import logging

logger = logging.get_logger()


def delete_all_documents_in_index(host_url, index_name, username=None, password=None):
    """
    使用 Elasticsearch REST API 删除索引中的所有文档

    参数:
    host_url: Elasticsearch 服务地址 (例如: "http://10.50.91.196:9200")
    index_name: 要清空的索引名称
    username: Elasticsearch 用户名 (可选)
    password: Elasticsearch 密码 (可选)

    返回:
    API 响应对象
    """
    # 构造 API 端点 URL
    url = f"{host_url.rstrip('/')}/{index_name}/_delete_by_query"

    # 准备请求头
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 准备查询体 (删除所有文档)
    query = {
        "query": {
            "match_all": {}
        }
    }

    # 处理认证
    auth = None
    if username and password:
        auth = HTTPBasicAuth(username, password)

    try:
        # 发送 POST 请求
        response = requests.post(
            url,
            data=json.dumps(query),
            headers=headers,
            auth=auth,
            timeout=30  # 30秒超时
        )

        # 检查响应
        response.raise_for_status()  # 对4xx或5xx状态码抛出异常

        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"API请求出错: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"错误响应: {e.response.text}")
        return None



def bulk_insert_documents(host_url, index_name, documents, username=None, password=None):
    """
    使用 Elasticsearch REST API 批量插入文档

    参数:
    host_url: Elasticsearch 服务地址 (例如: "http://10.50.91.196:9200")
    index_name: 目标索引名称
    documents: 要插入的文档列表（每个文档是一个字典）
    username: Elasticsearch 用户名 (可选)
    password: Elasticsearch 密码 (可选)

    返回:
    API 响应对象
    """
    # 构造 API 端点 URL
    url = f"{host_url.rstrip('/')}/{index_name}/_bulk"

    # 准备请求头
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 构造批量插入请求体
    bulk_data = []
    for doc in documents:
        # 每个操作块由两个 JSON 对象组成：
        # 1. 操作类型和元数据（index）
        # 2. 文档内容
        bulk_data.append(json.dumps({"index": {}}))
        bulk_data.append(json.dumps(doc))

    # 将所有操作块用换行符连接，并以换行符结尾
    payload = "\n".join(bulk_data) + "\n"

    # 处理认证
    auth = None
    if username and password:
        auth = HTTPBasicAuth(username, password)

    try:
        # 发送 POST 请求
        response = requests.post(
            url,
            data=payload,
            headers=headers,
            auth=auth,
            timeout=30  # 30秒超时
        )

        # 检查响应
        response.raise_for_status()  # 对4xx或5xx状态码抛出异常

        return response.json()

    except Exception as e:
        logger.error(f"API请求出错: {str(e)}")
        # if hasattr(e, 'response') and e.response is not None:
            # logger.error(f"错误响应: {e.response.text}")
        return None


def elasticsearch_query(es_url, index_name, query_body):
    """
    执行Elasticsearch查询

    参数:
        es_url: Elasticsearch服务地址（如：'http://10.50.91.196:9200'）
        index_name: 要查询的索引名
        query_body: 查询语句（字典格式）

    返回:
        JSON格式的查询结果
    """
    url = f"{es_url.rstrip('/')}/{index_name}/_search"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=query_body, headers=headers)
        response.raise_for_status()  # 检查HTTP错误
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"查询失败: {e}")
        return None


def get_all_documents(ES_URL, index_name, size=10000):
    """
    查询索引下的所有文档

    参数:
        ES_URL: Elasticsearch 服务地址
        index_name: 要查询的索引名称
        size: 返回的最大文档数量 (默认10000)

    返回:
        文档源数据列表
    """
    # 构建匹配所有文档的查询请求体
    QUERY_BODY = {
        "query": {
            "match_all": {}  # 匹配所有文档的特殊查询
        },
        "size": size  # 指定返回的最大文档数
    }

    # 执行查询
    result = elasticsearch_query(ES_URL, index_name, QUERY_BODY)

    # 处理查询结果
    if result:
        return [hit['_source'] for hit in result['hits']['hits']]  # 返回所有文档的源数据

    return []







# ===== 示例用法 =====
if __name__ == "__main__":
    # 使用示例
    all_docs = get_all_documents("http://10.50.91.196:9200", "short_term")
    for doc in all_docs:
        print(doc)  # 打印每个文档的内容



    # # Elasticsearch 配置
    # ELASTICSEARCH_HOST = "http://10.50.91.196:9200"  # 替换为你的 ES 地址
    # INDEX_NAME = "short_term"  # 替换为你的目标索引
    # USERNAME = None  # 如有安全设置，替换为实际用户名
    # PASSWORD = None  # 如有安全设置，替换为实际密码
    #
    # # 示例文档列表
    # documents = [
    #     {"title": "文档1", "content": "这是第一个文档"},
    #     {"title": "文档2", "content": "这是第二个文档"},
    #     {"title": "文档3", "content": "这是第三个文档"},
    # ]
    #
    # # 执行批量插入
    # result = bulk_insert_documents(
    #     host_url=ELASTICSEARCH_HOST,
    #     index_name=INDEX_NAME,
    #     documents=documents,
    # )
    #
    # # 处理结果
    # if result is not None:
    #     print(f"成功插入文档到 {INDEX_NAME} 索引:")
    #     print(f"成功插入文档数量: {result.get('items', []) and len(result['items'])}")
    # else:
    #     print(f"未能插入文档到 {INDEX_NAME} 索引")



