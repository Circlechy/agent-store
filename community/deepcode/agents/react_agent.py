#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
import json
from pydantic import BaseModel, Field
from typing import Dict, AsyncIterator, Any, List, Union, Optional

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.runner.runner import Runner, resource_mgr
from openjiuwen.core.utils.llm.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig, McpToolInfo
from openjiuwen.core.utils.tool.schema import ToolInfo


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


class AgentConfig(BaseModel):
    name: str
    llm_config: dict
    system_prompt: str = "你是一个小助手。"


class BaseAgent:
    def __init__(self, agent_config: AgentConfig):
        self.agent_config = agent_config
        self.name = agent_config.name
        self.system_prompt = agent_config.system_prompt
        self.model_name = agent_config.llm_config.pop("model_name", None)

        self._mcps = []
        self._tool_infos = []
        self._tool_names = []

        self._llm = ModelFactory().get_model(**agent_config.llm_config)

    async def astream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        pass

    async def ainvoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        pass

    async def add_mcps(self, mcp_configs: list[ToolServerConfig]):
        tool_mgr = resource_mgr.tool()
        await tool_mgr.add_tool_servers(mcp_configs)
        for config in mcp_configs:
            server_tools = tool_mgr.get_tool_infos(tool_server_name=config.server_name)
            if server_tools:
                for server_tool in server_tools:
                    self._tool_infos.append(self._convert_mcp_tool_info_to_openai_schema(server_tool))
                self._tool_names.extend([tool.name for tool in server_tools])
                self._mcps.append(config.server_name)
            else:
                raise ValueError(f"No tool found for MCP server: {config.server_name}")

    async def execute_mcp_tool(self, tool_name: str, inputs: dict):
        if tool_name in self._tool_names:
            tool = resource_mgr.tool().get_tool(tool_name)
            return await tool.ainvoke(inputs=inputs)
        else:
            raise ValueError(f"{tool_name} tool not found")

    def call_llm(self, model_name: str, messages: Union[List[BaseMessage], List[Dict], str],
               tools: Union[List[ToolInfo], List[Dict]] = None, temperature: Optional[float] = None,
               top_p: Optional[float] = None, **kwargs: Any):
        return self._llm.invoke(model_name, messages, tools, temperature, top_p, **kwargs)

    @staticmethod
    def _convert_mcp_tool_info_to_openai_schema(mcp_tool_info: McpToolInfo):
        return mcp_to_openai_tool({
            "name": mcp_tool_info.name,
            "description": mcp_tool_info.description,
            "inputSchema": mcp_tool_info.schema,
        })


class ReActAgent(BaseAgent):
    async def ainvoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        messages: List[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        query = inputs.get("query", "")
        if query == "":
            raise ValueError("No query provided")

        messages.append(HumanMessage(content=query))

        response: AIMessage = self.call_llm(self.model_name, messages, self._tool_infos)
        messages.append(response)
        while response.tool_calls:
            for tool_call in response.tool_calls:
                result = await self.execute_mcp_tool(tool_call.name, json.loads(tool_call.arguments))
                messages.append(ToolMessage(tool_call_id=tool_call.id, content=str(result)))

            response: AIMessage = self.call_llm(self.model_name, messages, self._tool_infos)
            messages.append(response)

        return {
            "content": response.content,
            "history": self._format_tool_use_response(messages)
        }

    @staticmethod
    def _format_tool_use_response(messages: List[BaseMessage]):
        response = ["# 当前工具调用历史："]
        tool_call_history = {}
        for message in messages[:-1]:
            if message.role == "assistant":
                temp_tool_calls = message.tool_calls
                for tool_call in temp_tool_calls:
                    tool_call_history[tool_call.id] = {"tool_name": tool_call.name, "arguments": tool_call.arguments}
            elif message.role == "tool":
                tool_call_history[message.tool_call_id]["result"] = message.content

        idx = 1
        for tool_call_id in tool_call_history.keys():
            tool_name = tool_call_history[tool_call_id]["tool_name"]
            arguments = tool_call_history[tool_call_id]["arguments"]
            result = tool_call_history[tool_call_id].get("result", "")
            response.append(f"""{str(idx)}. 调用工具：{tool_name}， 工具参数{arguments}
工具结果：{result}""")
            idx += 1

        if messages[-1].role == "assistant":
            content = messages[-1].content
            response.append(f"\n\n# Agent最终回复\n{content}")

        return "\n".join(response)


class ChatAgent(BaseAgent):
    """
    ChatAgent类，继承BaseAgent，实现简单的聊天功能
    """

    async def ainvoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        # 构建消息列表
        messages: List[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        query = inputs.get("query", "")
        if query == "":
            raise ValueError("No query provided")
        messages.append(HumanMessage(content=query))

        # 调用大模型获取响应
        response: AIMessage = await self._llm.ainvoke(self.model_name, messages)

        # 确保返回格式为Dict
        return {
            "content": response.content
        }