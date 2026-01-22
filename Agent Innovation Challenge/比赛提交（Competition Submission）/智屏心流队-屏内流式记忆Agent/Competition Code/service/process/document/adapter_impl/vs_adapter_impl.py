import hashlib
import hmac
import json
import struct
import time
from abc import ABC
from enum import Enum
from typing import Any, List, Dict, Tuple

import grpc

from service.process.common.client.es_client import ESClient
from doc_process.config_repository.document.mapping import BaseMappingField
from doc_process.processors.base.adapter.delete_adapter import DeleteAdapter
from doc_process.processors.base.adapter.export_adapter import ExportAdapter
from doc_process.processors.document.embedding.doc_embedding import gen_semantic_id
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode
from service.process.document.adapter_impl.es_adapter_impl import EsAdapterImpl
from service.process.common.proto import vector_service_pb2
from service.process.common.proto.vector_service_pb2_grpc import VectorWorkerStub
from service.process.common.utils.request_utils import RequestUtils

logger = logging.get_logger()
DSL_BODY_MAX_SIZE = 4 * 1000 * 1000  # dsl的最大字节数


def list_2_bytes(float_list):
    """float list to bytes"""
    buf = bytes()
    for val in float_list:
        buf += struct.pack("f", val)
    return buf


def get_auth_metadata(hash_code, request):
    """auth info for metadata"""
    timestamp = str(int(time.time() * 1000)).encode("utf-8")
    serial_str = b"timestamp=" + timestamp + b"&body=" + request.SerializeToString()
    hmac_str = hmac.new(hash_code.encode("utf-8"), serial_str, digestmod=hashlib.sha256)
    metadata = (("timestamp", timestamp), ("auth_code", hmac_str.hexdigest()))
    return metadata


class StatusCode(Enum):
    SUCCESS = 200


class VsAdapter(ExportAdapter, DeleteAdapter, ABC):
    """VsAdapter"""
    ...

class VsAdapterImpl(VsAdapter):
    def __init__(self, config: Dict, mapping: BaseMappingField):
        self.config: Dict = config
        self.mapping = mapping
        CheckUtils.check_type(self.config, dict, "config")
        CheckUtils.check_type(self.mapping, BaseMappingField, "mapping")
        CheckUtils.check_type(self.config.get("vs"), dict, "vs")

        self.semantic_fields = self.config.get("index", {}).get("semantic", [])
        self.scalar_filter_fields = self.config.get("index", {}).get("scalar_filter", [])
        self.index = "default"
        vs_server_url = self.config.get("vs", {}).get("url")  # 必填
        CheckUtils.check_type(vs_server_url, str, "vs.url")
        # link rpc server
        MAX_MESSAGE_LENGTH = 1024 * 1024 * 1024
        options = [
            ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
            ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH)
        ]
        self.channel = grpc.insecure_channel(vs_server_url, options=options)
        self.stub = VectorWorkerStub(self.channel)
        self.hmac_info = ""
        es_url = self.config.get("es", {}).get("url", "")
        self.es_index = self.config.get("es", {}).get("index", "")
        self.es_client = ESClient(es_url)
        self.es_dapter_impl: EsAdapterImpl = EsAdapterImpl(config, mapping)

    def _export(self, vectors: List[Dict], **kwargs: Any) -> bool:
        """
        export2vs
        Args:
            vectors:  vector schema is
            {
            "field": [{"id": "","embeddings": [],"doc_id":"","session_id":""}]
            }
        """
        result = True
        logger.debug("vs to be export vectors num={}".format(len(vectors)))
        for field in self.semantic_fields:
            for i, vector in enumerate(vectors):
                if field not in vector:
                    raise ProcessorException(ErrorCode.EXPORT_VS_ERROR,
                                             "field={} not in vector={}".format(field, vector))
                semantics: List[Dict] = vector[field]
                if not semantics:
                    raise ProcessorException(ErrorCode.EXPORT_VS_ERROR,
                                             "field={},semantics={}".format(field, semantics))
                response: vector_service_pb2.InsertOrUpdateResponse = self.insert_by_semantics(semantics)
                if RequestUtils.RE_SUCCESS_CODE.match(str(response.code)) is None:
                    raise ProcessorException(ErrorCode.EXPORT_VS_ERROR, f"insert vs error,response is {response}")
        return result

    def simple_method(self):
        request = vector_service_pb2.GetIndexInfoRequest(hmacauth="", index_name_list=[""])
        response = self.stub.GetIndexInfo(request)
        logger.info("simple method client received: ".format(response))

    def insert_by_semantics(self, semantics: List[Dict], **kwargs) -> vector_service_pb2.InsertOrUpdateResponse:
        """
        单条数据的embeddings
        split_num=len(semantics)
        """
        doc_values = []
        if semantics is None:
            return vector_service_pb2.InsertOrUpdateResponse(code=ErrorCode.FAILURE.code(), msg="semantics is None")
        for semantic in semantics:
            if not semantic.get("embeddings"):
                raise ProcessorException(ErrorCode.EXPORT_VS_ERROR,
                                         "export to vs failed because semantic embeddings is None.")
            # 获取当前时间的秒数
            current_time_seconds = time.time()

            doc_value = {"id": semantic["id"],
                         "fields": [
                             {"name": "embedding", "vectorValue": {"value": list_2_bytes(semantic["embeddings"])}},
                             {"name": "split_num", "stringValue": str(len(semantics))}
                         ],
                         "dtype": "float"}
            # 构造标量过滤dsl元素
            for field in self.scalar_filter_fields:
                doc_value["fields"].append({"name": field, "stringValue": str(semantic[field])})

            doc_values.append(doc_value)
        return self.insert_by_dsl(doc_values)

    def insert_by_dsl(self, dsl_bodys: List[dict]) -> vector_service_pb2.InsertOrUpdateResponse:
        """
        通过dsl插入
        """
        request = vector_service_pb2.InsertOrUpdateRequest(index_name=self.index, doc_list=dsl_bodys,
                                                           hmacauth="")
        metadata = get_auth_metadata(self.hmac_info, request)
        return self.stub.UpsertDocs(request, metadata=metadata)

    def inquery_by_id(self, ids, auth="Hello") -> List[vector_service_pb2.DocInfo]:
        """
        查询
        """
        request = vector_service_pb2.GetVectorDocsRequest(hmacauth=auth, ids=ids, index_name=self.index)
        response: vector_service_pb2.GetVectorDocsResponse = self.stub.GetVectorDocs(request)
        if response.code != StatusCode.SUCCESS.value:
            logger.error("GetVectorDocs response:{}".format(response))
            return []
        else:
            return response.docs

    def delete_by_id(self, data_id, auth="Hello"):
        """
        删除,vs只支持单条数据删除
        """
        request = vector_service_pb2.DeleteByIdsRequest(hmacauth=auth, ids=[data_id], index_name=self.index)
        response: vector_service_pb2.DeleteByIdsResponse = self.stub.DeleteDocsByIds(request)
        if response.code != StatusCode.SUCCESS.value:
            logger.error("DeleteDocsByIds response:{}".format(response))
            return False
        else:
            return True

    def _delete_data(self, data_dict: Dict, **kwargs: Any) -> bool:
        result = True
        user_id = data_dict.get("user_id", "")
        session_id = data_dict.get("session_id", "")
        doc_ids = data_dict.get("doc_ids", [])
        if user_id and session_id and doc_ids:
            result = self.delete_by_filter([("user_id", [user_id]), ("session_id", [session_id]), ("doc_id", doc_ids)])
        elif user_id and session_id:
            result = self.delete_by_filter([("user_id", [user_id]), ("session_id", [session_id])])
        elif user_id and doc_ids:
            result = self.delete_by_filter([("user_id", [user_id]), ("doc_id", doc_ids)])
        elif user_id:
            result = self.delete_by_filter([("user_id", [user_id])])
        else:
            raise ProcessorException(ErrorCode.PARAM_INVALID, "user_id and session_id and doc_ids is None.")
        return result

    def delete_by_filter(self, pair_list: List[Tuple[str, List[str]]]) -> bool:
        # 先查询文档，以获取其 _id
        query_body = EsAdapterImpl.build_multi_dsl(pair_list)
        results = self.es_dapter_impl.client.search_by_key(self.es_index, query_body)
        chunk_ids: List[str] = [result.get("_source", {}).get(self.mapping.get_bus_name(self.mapping.CHUNK_ID), "") for
                                result in results]
        # 基础的semantic_ids
        semantic_id0_list = []
        for field in self.semantic_fields:
            for chunk_id in chunk_ids:
                semantic_id = gen_semantic_id(self.mapping, field, chunk_id, 0)
                semantic_id0_list.append(semantic_id)

        semantic_res_list: List[vector_service_pb2.DocInfo] = self.inquery_by_id(semantic_id0_list)

        semantic_ids = []
        for semantic_res in semantic_res_list:
            semantic_id0: str = semantic_res.id
            # 数据存在ES，不存在VS的情况
            if not semantic_res.info:
                continue
            split_num = json.loads(semantic_res.info).get("split_num", "1")
            semantic_ids.append(semantic_id0)
            semantic_ids.extend([semantic_id0[:-3] + str(index).rjust(3, "0") for index in range(1, int(split_num))])

        success_semantic_ids = []
        for semantic_id in semantic_ids:
            flag = self.delete_by_id(semantic_id)
            if flag:
                success_semantic_ids.append(semantic_id)
        success_count = len(success_semantic_ids)
        logger.info("VS删除向量成功{}个,失败{}个,VS删除条件为{}".format(
            success_count, len(semantic_ids) - success_count,pair_list))
        logger.debug("VS semantic_ids to be deleted. {}".format(semantic_ids))
        logger.debug("VS删除向量成功的semantic_ids={}".format(success_semantic_ids))
        return success_count == len(semantic_ids)
