import json
import logging
import time
import uuid

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.stream.base import CustomSchema, OutputSchema

from jiuwen_memory_deepsearch.core.algorithm.answer import Answer
from jiuwen_memory_deepsearch.core.algorithm.classify_query import classify_query
from jiuwen_memory_deepsearch.core.algorithm.image_intent_recognition import ImageIntentRecognition
from jiuwen_memory_deepsearch.core.algorithm.show_image import ShowImage
from jiuwen_memory_deepsearch.core.search_context import Message, SearchContext
from jiuwen_memory_deepsearch.core.search_team_node import build_search_team_node_sub_workflow
from jiuwen_memory_deepsearch.utils.llm_utils import runtime_var

logger = logging.getLogger(__name__)


class StartNode(Start):

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[StartNode] invoke')
        query = inputs.get("query", "")
        if not query:
            search_context = SearchContext(
                image_path=inputs.get("image_path", ""),
            )
            next_node = "image_intent_recognition"
        else:
            search_context = SearchContext(
                query=query,
                messages=[Message(role="user", content=query)]
            )
            next_node = "entry"

        runtime.update_global_state(
            {"search_context": search_context.model_dump()})
        logger.info(f'[StartNode] invoke, search_context: {search_context}')

        return {"next_node": next_node}


class ImageIntentRecognitionNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[ImageIntentRecognitionNode] invoke')

        search_context_dict = runtime.get_global_state("search_context")
        image_path = search_context_dict.get("image_path")

        algorithm_input = {
            "image_path": image_path
        }

        recognition = ImageIntentRecognition()
        res = await recognition.recognize(algorithm_input)

        logger.info(f'[ImageIntentRecognitionNode] recognition result: {res}')
        need_query = res.get("need_query", "True")
        if not need_query or need_query == "False":
            return {"next_node": "end"}

        # 更新全局状态中的 query
        generated_query = res.get("generated_query", "")
        messages = [Message(role="user", content=generated_query)]
        if generated_query:
            runtime.update_global_state({
                "search_context.query": generated_query,
                "search_context.messages": messages
            })

        return {"next_node": "entry"}


class SearchEntryNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchEntryNode] invoke')
        messages = runtime.get_global_state("search_context.messages")
        algorithm_input = {
            "messages": messages
        }
        classify_query_output = await classify_query(algorithm_input)
        logger.info(
            f'[SearchEntryNode] invoke, classify_query_output: {classify_query_output}')
        if classify_query_output.get("go_deepsearch", False):
            next_node = "team"
            runtime.update_global_state({
                "search_context.language": classify_query_output.get("language", "zh-CN"),
            })
        else:
            next_node = "end"

        logger.info(f'[SearchEntryNode] invoke, next_node: {next_node}')

        return {"next_node": next_node}


class SearchTeamNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchTeamNode] invoke')
        search_context = runtime.get_global_state("search_context")
        logger.info(
            f'[SearchTeamNode] invoke start, search_context: {search_context}')
        sub_workflow = build_search_team_node_sub_workflow()

        async for chunk in Runner.run_workflow_streaming(workflow=sub_workflow,
                                                         inputs={"search_context": search_context}):
            if isinstance(chunk, CustomSchema):
                # 尝试获取 CustomSchema 的所有属性，确保 step_title, react_index 等元数据不被丢失
                output_message = {}

                # 定义必须转发的核心字段
                fields = [
                    "message_id",
                    "agent",
                    "content",
                    "message_type",
                    "event",
                    "created_time",
                    "step_title",
                    "step_description",
                    "react_index",
                    "finish_reason"]

                for field in fields:
                    # 兼容对象属性和字典键
                    val = None
                    if hasattr(chunk, field):
                        val = getattr(chunk, field)
                    elif isinstance(chunk, dict) and field in chunk:
                        val = chunk[field]
                    elif hasattr(chunk, 'get') and callable(chunk.get):
                        val = chunk.get(field)

                    if val is not None:
                        output_message[field] = val

                # 兜底：如果有些动态属性不在 fields 列表中，这里也可以通过 vars() 尝试获取（取决于 CustomSchema 的实现）
                await runtime.write_custom_stream(output_message)
            if isinstance(chunk, OutputSchema):
                if hasattr(chunk, "type") and getattr(chunk, "type") == "workflow_final":
                    logger.info(f'[SearchTeamNode] sub workflow finished, chunk: {chunk}')
                    collected_infos = getattr(chunk, "payload", [])

        runtime.update_global_state({
            "search_context.collected_infos": collected_infos
        })
        logger.info(
            f'[SearchTeamNode] invoke end, collected_infos: {collected_infos}')


class SearchAnswerNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchAnswerNode] invoke')
        search_context = runtime.get_global_state("search_context")
        query = search_context.get("query", "")
        collected_infos = search_context.get("collected_infos", [])
        language = search_context.get("language", "zh-CN")
        algorithm_input = {
            "query": query,
            "collected_infos": collected_infos,
            "language": language
        }
        answer = Answer()
        answer_output = await answer.answer(algorithm_input)

        runtime.update_global_state({
            "search_context.answer": answer_output
        })
        logger.info(
            f'[SearchAnswerNode] invoke end, answer_output: {answer_output}')


class ShowImageNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[ShowImageNode] invoke')
        search_context = runtime.get_global_state("search_context")
        answer = search_context.get("answer", "")

        # 调用 ShowImage 算法获取图片列表
        image_list = await ShowImage().get_images({"answer": answer})

        if image_list:
            msg_id = str(uuid.uuid4())
            now = int(time.time() * 1000)

            # 1. 发送 start 事件
            await runtime.write_custom_stream({
                "message_id": msg_id,
                "agent": "show_image",
                "content": "",
                "message_type": "message_chunk",
                "event": "start",
                "created_time": now
            })

            # 2. 发送 message 事件，content 为 JSON 字符串
            await runtime.write_custom_stream({
                "message_id": msg_id,
                "agent": "show_image",
                "content": json.dumps(image_list),
                "message_type": "message_chunk",
                "event": "message",
                "created_time": now
            })

            # 3. 发送 end 事件
            await runtime.write_custom_stream({
                "message_id": msg_id,
                "agent": "show_image",
                "content": "",
                "message_type": "message_chunk",
                "event": "end",
                "finish_reason": "stop",
                "created_time": now
            })

        return {"next_node": "end"}


class SearchEndNode(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime_var.set(runtime)
        logger.info(f'[SearchEndNode] invoke')
        search_context = runtime.get_global_state("search_context")
        answer = search_context.get("answer", "")
        logger.info(f'[SearchEndNode] answer: {answer}')
        return answer
