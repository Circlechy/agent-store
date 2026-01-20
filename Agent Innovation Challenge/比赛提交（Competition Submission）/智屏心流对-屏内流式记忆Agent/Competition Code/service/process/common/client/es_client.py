from typing import List, Dict, Union

from elasticsearch import Elasticsearch, helpers

from doc_process.utils import logging
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class ESClient:
    def __init__(self, host):
        # 添加详细的兼容性配置
        self.es = Elasticsearch(
            hosts=[host],
            # 关键兼容性配置
            compatible_mode=True,  # 启用向后兼容模式
            meta_header=False,  # 禁用元信息头
            # 显式设置请求头
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            # 连接选项
            request_timeout=30,
            max_retries=3,
            retry_on_status=(502, 503, 504),
            retry_on_timeout=True
        )

        # 检查连接
        try:
            print("Elasticsearch 服务器信息:", self.es.info())
        except Exception as e:
            print(f"连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到 Elasticsearch: {str(e)}")

    def delete_all_documents(self, index_name):
        """删除索引中的所有文档"""
        query = {"query": {"match_all": {}}}

        try:
            # 使用兼容性API选项
            response = self.es.delete_by_query(
                index=index_name,
                body=query,
                conflicts="proceed",  # 安全处理冲突
                refresh=True,  # 立即刷新索引
                # 显式设置API版本兼容性
                params={"api": "7"}  # 强制使用7.x API版本
            )
            return response
        except ElasticsearchException as e:
            print(f"删除操作失败: {str(e)}")
            # 尝试兼容性回退
            try:
                print("尝试兼容性回退方案...")
                return self._delete_by_query_fallback(index_name)
            except:
                return None

    def _delete_by_query_fallback(self, index_name):
        """替代删除方法"""
        # 直接使用requests库
        import requests

        url = f"{self.es.transport.hosts[0]['host']}/{index_name}/_delete_by_query"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        query = {"query": {"match_all": {}}}

        response = requests.post(url, json=query, headers=headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"删除失败: {response.status_code}, {response.text}")
        return response.json()

    def count_documents(self, index_name):
        """查询索引中的文档数量"""
        result = self.es.count(index=index_name)
        return result['count']

    def bulk_insert(self, index_name: str, data_list: List[Dict], id_list: List[str],
                    time_out: Union[int, float]) -> bool:
        """
        批量插入数据到指定的Elasticsearch索引。

        :param index_name: 索引名称
        :param data_list: 包含多个文档的数据列表
        :param id_list: 包含每个文档的ID的列表
        :param time_out: 超时时间
        :return: 插入是否成功
        """
        store_res = True
        if not data_list or not id_list or len(data_list) != len(id_list):
            return not store_res

        # 检查索引是否存在
        if not self.es.indices.exists(index=index_name):
            raise ProcessorException(ErrorCode.EXPORT_ES_ERROR, "Index {} does not exist.".format(index_name))

        actions = [
            {
                "_index": index_name,
                "_id": id,
                "_source": data
            }
            for data, id in zip(data_list, id_list)
        ]

        # 使用bulk API批量插入数据
        success, errors = helpers.bulk(self.es, actions, **{"request_timeout": time_out})

        # 根据结果判断是否成功
        if len(errors) > 0:
            raise ProcessorException(ErrorCode.EXPORT_ES_ERROR,
                                     "Failed to insert some documents into ES: {}".format(errors))

        return store_res

    def search_by_key(self, index_name: str, query_body: dict, scroll_time: str = '2m',
                      batch_size: int = 1000) -> \
            List[Dict]:
        """
        根据key和value查询Elasticsearch中的数据，使用scroll返回全部匹配结果。

        :param index_name: 索引名称
        :param query_body  query_body
        :param scroll_time: scroll保持的时间长度，默认是2分钟
        :param batch_size: 每次返回的结果数量
        :return: 全部匹配的数据列表
        """
        query_body["size"] = batch_size  # 每批返回的数量

        # 初始化scroll查询
        response = self.es.search(index=index_name, body=query_body, scroll=scroll_time)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        results = [hit for hit in hits]

        # 使用scroll循环获取所有结果
        while len(hits) > 0:
            response = self.es.scroll(scroll_id=scroll_id, scroll=scroll_time)
            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']
            results.extend([hit for hit in hits])

        return results

    def delete_by_query(self, index_list: List[str], query_body: dict) -> bool:
        """
        根据查询条件删除指定索引中的文档。
        """
        try:
            # 执行 delete_by_query 操作
            response = self.es.delete_by_query(index=index_list, body=query_body)

            # 解析响应结果
            deleted_docs = response.get('deleted', 0)
            total_docs = response.get('total', 0)
            if response.get('failures'):
                raise ProcessorException(ErrorCode.DELETE_ES_ERROR,
                                         f"部分文档未能删除，错误信息: {response['failures']}")

            logger.info(
                f"ES删除chunk成功 {deleted_docs} 个,失败 {total_docs - deleted_docs} 个,ES 删除条件为{query_body}")
            return True

        except Exception as e:
            # 捕获 Elasticsearch 相关的异常
            raise ProcessorException(ErrorCode.DELETE_ES_ERROR, f"删除文档时出现异常: {str(e)}")
