#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


from typing import Any, List, Optional, Sequence

from doc_process.context.base_schema import Context, StreamType, ProcessComponent
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_PIPELINE_NAME, ProcessorName
from doc_process.utils.error_code import ErrorCode, ProcessorException
from doc_process.utils.pydantic import BaseModel, Field

logger = logging.get_logger()


def run_processors(
        context: Context = None,
        processors: Sequence[ProcessComponent] = None,
        **kwargs: Any,
) -> None:
    """
    Run a series of processors

    Args:
        context: The context of pipeline.
        processors: The processors to apply to the documents.
    """
    for processor in processors:
        processor(context, **kwargs)


class BasePipeline(BaseModel):
    """A pipeline that can allow arbitrary chaining of different component.

    Args:
        name (str, optional):
            Unique name of the document process pipeline. Defaults to DEFAULT_PIPELINE_NAME.
        processors (List[ProcessComponent], optional):
            processors to apply to the data. Defaults to None.
    """

    name: str = Field(
        default=DEFAULT_PIPELINE_NAME,
        description="Unique name of the  pipeline",
    )
    processors: List[ProcessComponent] = Field(
        description="Processors to apply to the data"
    )

    def __init__(
            self,
            name: str,
            processors: Optional[List[ProcessComponent]] = None
    ):
        if processors is None:
            logger.info("processors not set.")
        super().__init__(
            name=name,
            processors=processors
        )
        CheckUtils.check_type(name, str, "pipeline.name")
        CheckUtils.is_all_type(processors, ProcessComponent, "pipeline.processors")

    @staticmethod
    def _generate_response(context) -> None:
        """Generate response from context"""
        pass

    def run(
            self,
            context: Optional[Context] = None,
            **kwargs,
    ) -> dict:
        """
        Run pipeline.

        Args:
            context (Optional[Context]], optional): context of pipeline, include documents、response. Defaults to None.
        """
        CheckUtils.check_type(context, Context, "context")
        CheckUtils.check_type(context.get_verbose(), bool, "context.verbose")
        CheckUtils.check_type(context.get_knowledge_base_name(), str, "context.knowledge_base_name")
        CheckUtils.check_type(context.get_stream_type(), StreamType, "context.stream_type")

        run_processors(context, self.processors, **kwargs, )

        # generate response from context
        self._generate_response(context)

        return context.get_pipeline_response()


class DocumentProcessPipeline(BasePipeline):
    """A pipeline that can allow arbitrary chaining of different component.

    Args:
        name (str, optional):
            Unique name of the document process pipeline. Defaults to DEFAULT_PIPELINE_NAME.
        processors (List[ProcessComponent], optional):
            processors to apply to the data. Defaults to None.
    """

    def __init__(
            self,
            name: str,
            processors: Optional[List[ProcessComponent]] = None
    ):
        super().__init__(
            name=name,
            processors=processors
        )

    @staticmethod
    def _generate_response(context) -> None:
        """Generate response from context"""
        fail_documents = {}
        # 关键模块
        critical_processors = set()

        for processor in ProcessorName:
            # 排除 BM25、EMBEDDING 和 SUMMARY
            if processor not in {ProcessorName.BM25, ProcessorName.EMBEDDING, ProcessorName.SUMMARY}:
                critical_processors.add(processor)
        component_info = context.get_component_info()
        id2name = context.get_id2name()
        # 获取第一个键值对
        first_resp: Optional[ProcessorException] = None
        for component in component_info.keys():
            if component not in critical_processors:
                continue
            for doc_md5, resp in component_info[component].items():
                if not resp or resp.get_error_code() is ErrorCode.SUCCESS:
                    continue
                if not first_resp:
                    first_resp = resp
                # 拼接错误信息
                message = fail_documents.get(doc_md5)[-1] if doc_md5 in fail_documents else ""
                message = message + "{}:{}.".format(component.value, str(resp))
                fail_info = (id2name.get(doc_md5, ""), message)
                fail_documents[doc_md5] = fail_info

        success_count = context.get_file_count() - len(fail_documents)
        context.set_fail_documents(fail_documents)
        context.set_success_count(success_count)
        # set context response
        if success_count != context.get_file_count():
            # 取第一个文档的失败信息
            context.set_msg(first_resp.get_error_code().message())
            context.set_code(first_resp.get_error_code().code())
        else:
            context.set_msg(ErrorCode.SUCCESS.message())
            context.set_code(ErrorCode.SUCCESS.code())


class StreamProcessPipeline(BasePipeline):
    """Stream Process Pipeline"""

    def __init__(
            self,
            name: str,
            processors: Optional[List[ProcessComponent]] = None
    ):
        super().__init__(
            name=name,
            processors=processors
        )
    def run(
            self,
            context: Optional[Context] = None,
            **kwargs,
    ) -> dict:
        """
        Run pipeline.

        Args:
            context (Optional[Context]], optional): context of pipeline, include documents、response. Defaults to None.
        """
        CheckUtils.check_type(context, Context, "context")
        CheckUtils.check_type(context.get_verbose(), bool, "context.verbose")
        CheckUtils.check_type(context.get_knowledge_base_name(), str, "context.knowledge_base_name")
        CheckUtils.check_type(context.get_stream_type(), StreamType, "context.stream_type")

        for processor in self.processors:
            processor(context, **kwargs)

        # generate response from context
        self._generate_response(context)

        return context.get_pipeline_response()