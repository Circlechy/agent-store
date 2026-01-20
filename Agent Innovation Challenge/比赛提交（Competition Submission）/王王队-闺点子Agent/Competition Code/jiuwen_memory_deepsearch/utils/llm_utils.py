import contextvars
import logging
import re
import time
import uuid

from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from pydantic import BaseModel

from jiuwen_memory_deepsearch.utils.config import deepsearch_config

logger = logging.getLogger(__name__)

runtime_var = contextvars.ContextVar("runtime", default=None)

model_provider = deepsearch_config.get("model.provider")
api_base = deepsearch_config.get("model.api_base")
api_key = deepsearch_config.get("model.api_key")
model_name = deepsearch_config.get("model.model_name")


def create_model_config() -> ModelConfig:
    return ModelConfig(
        model_provider=model_provider,
        model_info=BaseModelInfo(
            model=model_name,
            api_base=api_base,
            api_key=api_key,
            timeout=200,
        ),
    )


def get_llm_model():
    model_config = create_model_config()
    return ModelFactory().get_model(
        model_provider=model_config.model_provider,
        api_key=model_config.model_info.api_key,
        api_base=model_config.model_info.api_base
    )


llm = get_llm_model()


def transfer_to_jiuwen_messages(origin_messages: list):
    """转换消息类型"""
    output_messages = []
    for message in origin_messages:
        if isinstance(message, dict):
            role = message.get("role", "")
            content = message.get("content", "")
            name = message.get("name", "")
            if role == "system":
                output_messages.append(SystemMessage(content=content, name=name))
            elif role == "user":
                output_messages.append(HumanMessage(content=content, name=name))
            elif role == "assistant":
                output_messages.append(
                    AIMessage(
                        content=content,
                        name=name,
                        tool_calls=message.get("tool_calls", []),
                        usage_metadata=message.get("usage_metadata", None),
                        raw_content=message.get("raw_content", ""),
                        reason_content=message.get("reason_content", "")
                    )
                )
            elif role == "tool":
                output_messages.append(
                    ToolMessage(content=content, name=name,
                                tool_call_id=message.get("tool_call_id", "") or f"call_{str(uuid.uuid4().hex[:22])}")
                )
            else:
                logger.error(f"role:{role} not support")
        elif isinstance(message, BaseModel):
            output_messages.append(message)
        else:
            logger.error(f"message type:{type(message)} not support")

    return output_messages


def get_current_time():
    return int(round(time.time() * 1000))


async def llm_astream(messages: list,
                      tools=None,
                      need_stream_out=False,
                      agent_name="deepsearch",
                      extra_metadata=None,
                      specific_model=None):
    llm_messages = transfer_to_jiuwen_messages(messages)
    runtime = runtime_var.get()
    if need_stream_out and runtime:
        stream_id = str(uuid.uuid4())
        stream_data = {
            "message_id": stream_id,
            "agent": agent_name,  # agent_id
            "content": "",  # 具体内容信息
            "message_type": "message_chunk",
            "event": "start",
            "created_time": get_current_time()
        }
        # 添加额外的元数据（如 step_id, step_title）
        if extra_metadata:
            stream_data.update(extra_metadata)
        await runtime.write_custom_stream(stream_data)

    # 使用async for遍历异步迭代器
    full_chunk = None
    async for chunk in llm.astream(model_name=specific_model if specific_model else model_name, messages=llm_messages,
                                   tools=tools):
        if full_chunk is None:
            full_chunk = chunk
        else:
            full_chunk += chunk

        if need_stream_out and runtime:
            stream_data = {
                "message_id": stream_id,
                "agent": agent_name,  # agent_id
                "content": chunk.content,
                "message_type": "message_chunk",
                "event": "message",
                "created_time": get_current_time()
            }
            if extra_metadata:
                stream_data.update(extra_metadata)
            await runtime.write_custom_stream(stream_data)

    if need_stream_out and runtime:
        stream_data = {
            "message_id": stream_id,
            "agent": agent_name,  # agent_id
            "content": "",  # 具体内容信息
            "message_type": "message_chunk",
            "event": "end",
            "created_time": get_current_time()
        }
        if extra_metadata:
            stream_data.update(extra_metadata)
        await runtime.write_custom_stream(stream_data)

    full_chunk.content = re.sub(r"^```(?:json)?\n|\n```$", "", full_chunk.content.strip())
    response = full_chunk.model_dump()
    return response
