from typing import Dict, List, Optional

from elasticsearch import Elasticsearch


class ESClient:
    def __init__(self, host="http://localhost:9200"):
        self.es = Elasticsearch(hosts=[host], headers={"Content-Type": "application/json"})

    def basic_match_query(
            self,
            index: str,
            field: str,
            query: str,
            size: int = 10,
            from_: int = 0
    ) -> Optional[List[Dict]]:
        """
        执行基础匹配查询（基于 match 查询语法）
        :param index: 索引名称
        :param field: 查询字段名（如 caption）
        :param query: 搜索关键词
        :param size: 返回结果数量，默认10条
        :param from_: 分页起始位置，默认0
        :return: 匹配文档的 _source 内容列表
        """
        try:
            # 构建 DSL 查询体（参考网页3的match查询结构）
            body = {
                "query": {
                    "match": {
                        field: query
                    }
                },
                "from": from_,
                "size": size
            }

            # 执行搜索（参考网页7的客户端调用方式）
            response = self.es.search(index=index, body=body)

            # 提取并返回结果（参考网页5的结果处理逻辑）
            return [hit["_source"] for hit in response["hits"]["hits"]]

        except Exception as e:
            print(f"查询失败: {str(e)}")
            return None


if __name__ == "__main__":
    # 初始化客户端（参考网页8的连接配置）
    es_client = ESClient(host="https://10.168.12.121:9200")

    # 执行基础匹配查询（搜索 caption 包含"京A12345"的文档）
    results = es_client.basic_match_query(
        index="long_term",
        field="caption",
        # query="京A12345",
        query="车位",
        size=5
    )

    # 处理结果（参考网页7的打印逻辑）
    if results:
        print(f"命中 {len(results)} 条结果:")
        for i, doc in enumerate(results, 1):
            print(doc)
            print(f"文档{i}: {doc.get('caption')}")
            print(f"关联人员: {doc.get('people')}")
            print("-" * 50)
