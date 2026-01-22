import grpc
from google.protobuf import json_format

from service.process.common.proto import falcon_service_pb2, falcon_service_pb2_grpc, root_service_pb2
from service.process.common.utils.log import logger, request_logger
from service.process.common.utils.proto_utils import ProtoUtils


class FalconClient:
    slice_size = 1000

    def __init__(self, vector_engine_url):
        # 连接 rpc 服务器
        MAX_MESSAGE_LENGTH = 1024 * 1024 * 1024
        options = [
            ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
            ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)
        ]
        self.channel = grpc.insecure_channel(vector_engine_url, options=options)
        self.stub = falcon_service_pb2_grpc.IndexerServiceStub(self.channel)

    def create_index(self, corpus, build_schema):
        """
        create index
        """
        request = falcon_service_pb2.CreateIndexRequest(
            corpus=corpus, build_schema=build_schema, slice_size=self.slice_size
        )
        request_logger.info("create_index() request={}".format(ProtoUtils.to_dict(request)))
        response: falcon_service_pb2.CreateIndexResponse = self.stub.CreateIndex(request)
        if response.error_code not in (0, 3):
            logger.error("create_index failed,response:{}".format(ProtoUtils.to_dict(response)))
        return response

    def add_docs(self, corpus: str, docs):
        """
        add docs
        """
        request = falcon_service_pb2.AddDocsRequest(corpus=corpus, docs=docs)
        request_logger.debug("add_docs() request={}".format(ProtoUtils.to_dict(request)))
        response: falcon_service_pb2.AddDocsResponse = self.stub.AddDocs(request)
        return response

    def build_index(self, doc_path: str, schema: str, corpus: str) -> falcon_service_pb2.BuildIndexResponse:
        """
        构建索引
        构建完索引时，索引存在内存中，可以直接调用Search接口查询，或调用Persist接口将索引存放到磁盘上。
        """
        request = falcon_service_pb2.BuildIndexRequest(doc_source=0, doc_path=doc_path,
                                                       build_schema=schema, corpus=corpus)
        request_logger.info("build_index() request={}".format(ProtoUtils.to_dict(request)))
        return self.stub.BuildIndex(request)

    def persist_index(self, index_path: str, index_info: str) -> falcon_service_pb2.PersistIndexResponse:
        """
        持久化索引
        将内存中的索引存储到path指定的磁盘路径中，持久化后的索引，可以被LoadIndex接口重新加载进来用于检索
        """
        request = falcon_service_pb2.PersistIndexRequest(index_path=index_path, index_info=index_info)
        request_logger.info("persist_index() request = {}".format(ProtoUtils.to_dict(request)))
        return self.stub.PersistIndex(request)

    def load_index(self, index_path, corpus) -> falcon_service_pb2.LoadIndexResponse:
        """
        从indexPath指定的磁盘路径加载索引，加载后的索引名称命名为corpus，load后可以调用Search接口检索数据。
        成功0， 失败4
        {
            "index_path": "corpus_name"
        }
        """
        request = falcon_service_pb2.LoadIndexRequest(index_path=index_path, corpus=corpus)
        request_logger.info("load_index() request = {}".format(ProtoUtils.to_dict(request)))
        return self.stub.LoadIndex(request)

    def delete_index(self, corpus) -> falcon_service_pb2.DeleteIndexResponse:
        """
        delete index
        """
        request = falcon_service_pb2.DeleteIndexRequest(corpus=corpus)
        request_logger.info("delete_index() request = {}".format(ProtoUtils.to_dict(request)))
        return self.stub.DeleteIndex(request)

    def delete_docs(self, corpus, doc_ids):
        """
        delete docs
        """
        request = falcon_service_pb2.DeleteDocsRequest(corpus=corpus, doc_ids=doc_ids)
        request_logger.info("delete_docs() request = {}".format(ProtoUtils.to_dict(request)))
        return self.stub.DeleteDocs(request)

    def search(self, json_data):
        """
        search
        """
        request = root_service_pb2.SearchRequest()
        json_format.Parse(json_data, request)
        return self.stub.Search(request)

    def get_index_info(self, corpus):
        """
        get index info
        """
        request = falcon_service_pb2.GetIndexInfoRequest(corpus=corpus)
        return self.stub.GetIndexInfo(request)
