from abc import ABC, abstractmethod
from typing import Any, List, Tuple

from pydantic import BaseModel

from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.utils.llm.messages import AIMessage, BaseMessage, ToolMessage


class Action(BaseModel):
    action: str
    content: Any
    id: Any = None


class ActionResult(BaseModel):
    message: BaseMessage
    is_finished: bool = False


class ActionSpace(ABC):
    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def parse_llm_response(self, message: AIMessage) -> List[Action]:
        pass

    @abstractmethod
    async def execute(self, action: Action) -> ActionResult:
        pass


class FunctionCallSpace(ActionSpace):
    def __init__(self):
        pass

    def parse_llm_response(self, message: AIMessage) -> List[Action]:
        return [
            Action(
                action=tool_call.name,
                content=tool_call.arguments,
                id=tool_call.id
            ) for tool_call in message.tool_calls
        ]

    async def execute(self, action: Action) -> ActionResult:
        result = await Runner.run_tool(action.action, action.content)
        return ActionResult(message=ToolMessage(content=str(result), tool_call_id=action.id))


async def async_run_react_loop(llm, messages: List[BaseMessage], max_iterations: int, action_space: ActionSpace = FunctionCallSpace(), tools: List = None, *args, **kwargs) -> Tuple[List[BaseMessage], bool]:
    stop = False
    curr_iteration = 0
    
    # Prepare kwargs for LLM invocation - pass tools if provided
    llm_kwargs = kwargs.copy()
    if tools is not None:
        llm_kwargs['tools'] = tools
    
    while curr_iteration < max_iterations and not stop:
        curr_iteration += 1

        response = await llm.ainvoke(messages, *args, **llm_kwargs)
        messages.append(response)

        actions = action_space.parse_llm_response(response)
        if not actions:
            return messages, False

        for action in actions:
            action_result = await action_space.execute(action)
            messages.append(action_result.message)
            stop = stop or action_result.is_finished

    return messages, curr_iteration >= max_iterations


def mcp_to_openai_tool(mcp_schema: dict) -> dict:
    """将 MCP Schema 转换为 OpenAI Tool Schema"""

    # 获取基本信息
    name = mcp_schema.get("name", "")
    description = mcp_schema.get("description", "")
    input_schema = mcp_schema.get("inputSchema", {})

    # 转换参数
    parameters = {
        "type": input_schema.get("type", "object"),
        "properties": {},
        "required": input_schema.get("required", [])
    }

    # 处理每个属性
    for prop_name, prop_schema in input_schema.get("properties", {}).items():
        openai_prop = {}

        # 1. type 字段直接复制
        if "type" in prop_schema:
            openai_prop["type"] = prop_schema["type"]

        # 2. description 字段：合并 title 和 description
        description_parts = []

        # 如果有 title，添加到描述中
        if "title" in prop_schema:
            description_parts.append(prop_schema["title"])

        # 如果有 description，添加到描述中
        if "description" in prop_schema:
            if description_parts:  # 如果已有 title
                description_parts.append("：" + prop_schema["description"])
            else:
                description_parts.append(prop_schema["description"])

        if description_parts:
            openai_prop["description"] = "".join(description_parts)

        # 3. 复制其他字段
        for key in ["enum", "default", "minimum", "maximum",
                    "minLength", "maxLength", "format", "pattern"]:
            if key in prop_schema:
                openai_prop[key] = prop_schema[key]

        # 4. 处理嵌套对象
        if prop_schema.get("type") == "object" and "properties" in prop_schema:
            openai_prop.update(mcp_to_openai_tool({
                "name": prop_name,
                "inputSchema": prop_schema
            })["function"]["parameters"])

        # 5. 处理数组
        if prop_schema.get("type") == "array" and "items" in prop_schema:
            openai_prop["items"] = {}
            items_schema = prop_schema["items"]

            # 处理数组元素的标题和描述
            if "title" in items_schema or "description" in items_schema:
                item_desc_parts = []
                if "title" in items_schema:
                    item_desc_parts.append(items_schema["title"])
                if "description" in items_schema:
                    if item_desc_parts:
                        item_desc_parts.append("：" + items_schema["description"])
                    else:
                        item_desc_parts.append(items_schema["description"])

                openai_prop["items"]["description"] = "".join(item_desc_parts)

            # 复制其他字段
            for key in ["type", "enum", "format"]:
                if key in items_schema:
                    openai_prop["items"][key] = items_schema[key]

        parameters["properties"][prop_name] = openai_prop

    # 构建完整的 OpenAI Tool Schema
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters
        }
    }
