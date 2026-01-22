import os
import time
from abc import ABC
from typing import Dict, List

from doc_process.context.base_schema import Context, StreamType
from doc_process.context.doc_schema import DocContext
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ErrorCode, ProcessorException
from service.process.document.pipeline.loader_factory import LoaderFactory
from service.process.document.pipeline.pipeline_factory import PipelineFactory
from service.process.common.utils.common_utils import base64_2_file, detect_dir

logger = logging.get_logger()


class BaseOrchestrator(ABC):
    """OrchestratorKernel"""

    def parse_input(self, input_dict: Dict) -> Dict:
        """
        对input预处理
        """

    def transform_input(self, input_dict: Dict, context: Context):
        """
        从input构造context
        """

    def forward(self, input_dict: Dict):
        """
        Orchestrator执行入口
        """
    def call_pipeline(self, context: Context):
        """
        执行pipeline
        """

    def transform_output(self, context: Context) -> dict:
        """
        从context构造output
        """


class DocumentProcessOrchestrator(BaseOrchestrator):
    """DocumentOrchestrator"""

    def parse_input(self, input_dict: Dict) -> Dict:
        """
        对input预处理
        """
        return input_dict

    def transform_input(self, input_dict: Dict, context: Context):
        """
        从input构造context
        """
        user_id: str = input_dict.get("user_id", None)
        doc_id = input_dict.get("doc_id", "")
        session_id: str = input_dict.get("session_id", "")
        stream_type_int: int = input_dict.get("stream_type", None)
        debug: bool = input_dict.get("debug", None)

        context: Context = DocContext()
        if debug is not None:
            context.set_verbose(debug)
        if user_id:
            context.set_knowledge_base_name(user_id)
        context.set_session_id(session_id)
        if doc_id:
            if isinstance(doc_id, str):
                context.update_input_kwargs("doc_id", [doc_id])
            elif isinstance(doc_id, list):
                context.update_input_kwargs("doc_id", doc_id)

        if stream_type_int is not None and stream_type_int in {0, 1}:
            stream_type: StreamType = StreamType.REAL if stream_type_int == 0 else StreamType.STATIC
            context.set_stream_type(stream_type)

        if context.get_verbose():
            logging.set_level_debug()
        else:
            logging.set_level_info()

    def transform_output(self, context: Context) -> dict:
        """
        从context 构造response
        """
        if not context.get_verbose():
            fail_documents = context.get_fail_documents()
            fail_documents = {key: value[0] for key, value in fail_documents.items()}
            context.set_fail_documents(fail_documents)
            context.get_pipeline_response().pop("cost_time")
        return context.get_pipeline_response()


class UpdateLocalDocsOrchestrator(DocumentProcessOrchestrator):
    """UpdateLocalDocsOrchestrator"""

    def __init__(self, config_dict: Dict):
        super().__init__()
        self.directory_loader = LoaderFactory.create_directory_loader(config_dict)
        self.pipeline = PipelineFactory.create_default_pipeline(config_dict)

    def forward(self, input_dict: Dict) -> dict:
        logger.debug("doc process start run")
        start_time = time.time()

        context = DocContext()
        input_dict = self.parse_input(input_dict)
        self.transform_input(input_dict, context)

        self.call_loader(context, input_dict)
        context.update_cost_time("Loader&Parser", "{:.2f}s".format(time.time() - start_time))

        pipeline_response = self.call_pipeline(context)
        context.update_cost_time("total", "{:.2f}s".format(time.time() - start_time))

        logger.info("component_info={}".format(context.get_component_info()))
        logger.info("pipeline_response={}".format(context.get_pipeline_response()))
        response = self.transform_output(context)
        del context
        return response

    def call_loader(self, context: Context, input_dict: Dict):
        input_dir: str = input_dict.get("input_dir", None)
        input_files: List[str] = input_dict.get("input_files", None)
        exclude_hidden: bool = input_dict.get("exclude_hidden", True)
        recursive: bool = input_dict.get("recursive", False)
        self.directory_loader.load(input_dir=input_dir,
                                   input_files=input_files,
                                   exclude_hidden=exclude_hidden,
                                   recursive=recursive,
                                   context=context)

    def call_pipeline(self, context: Context) -> dict:
        return self.pipeline.run(context)


class UpdateStreamDocsOrchestrator(UpdateLocalDocsOrchestrator):
    """UpdateStreamDocsOrchestrator"""

    def __init__(self, config_dict: Dict):
        super().__init__(config_dict=config_dict)
        self.local_data_dir = "data"
        detect_dir(self.local_data_dir)

    def parse_input(self, input_dict: Dict) -> Dict:
        """
        将file_stream内容保存为本地文件，并将文件路径赋值给input_files
        """
        if "file_stream" not in input_dict or input_dict.get("file_stream") is None:
            input_dict["file_stream"] = ""
        if "file_name" not in input_dict or input_dict.get("file_name") is None:
            input_dict["file_name"] = ""

        CheckUtils.check_type(input_dict["file_stream"], str, "file_stream")
        CheckUtils.check_type(input_dict["file_name"], str, "file_name")

        file_stream = input_dict.get("file_stream", "")
        session_id = input_dict.get("session_id", "")
        file_name = input_dict.get("file_name", "")
        scene_name = input_dict.get("scene", "").get("name")
        if not file_stream or not file_name:
            raise ProcessorException(ErrorCode.PARAM_INVALID, "file_stream or file_name is invalid.")

        base64_str = file_stream
        # save to temp path
        save_path = os.path.join(self.local_data_dir, file_name)
        base64_2_file(base64_str, save_path)

        # run pipeline
        input_files = [
            save_path
        ]
        input_dict["input_files"] = input_files
        return input_dict


class DeleteDocsOrchestrator(DocumentProcessOrchestrator):
    """DeleteDocsOrchestrator"""

    def __init__(self, config_dict: Dict):
        super().__init__()
        self.pipeline = PipelineFactory.create_rag_delete_pipeline(config_dict)

    def forward(self, input_dict: Dict) -> dict:
        logger.debug("doc process start run")
        start_time = time.time()

        context = Context()
        self.transform_input(input_dict, context)

        pipeline_response = self.call_pipeline(context)
        context.update_cost_time("total", "{:.2f}s".format(time.time() - start_time))

        logger.info("component_info={}".format(context.get_component_info()))
        logger.info("pipeline_response={}".format(context.get_pipeline_response()))

        response = self.transform_output(context)
        del context
        return response

    def call_pipeline(self, context: Context) -> dict:
        return self.pipeline.run(context)
