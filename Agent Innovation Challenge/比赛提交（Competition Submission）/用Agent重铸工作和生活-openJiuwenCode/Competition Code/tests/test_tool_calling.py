"""
测试工具调用功能

验证：
1. 工具格式是否正确传递给 LLM
2. GLM-4 是否能正确调用工具
3. SDK 的工具格式转换是否正确
4. Agent 是否能正确调用工具
"""

import asyncio
import os
import sys
import pytest

# 清除代理环境变量
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(var, None)
os.environ.setdefault("LLM_SSL_VERIFY", "false")

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent-core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestToolFormat:
    """测试工具格式"""

    def test_tool_info_to_openai_format(self):
        """测试 ToolInfo 转换为 OpenAI 格式"""
        from packages.server.tools.openjiuwen_tools import create_all_tools
        from openjiuwen.core.utils.llm.base import BaseModelClient

        tools = create_all_tools()
        write_file_tool = [t for t in tools if t.name == "write_file"][0]
        tool_info = write_file_tool.get_tool_info()

        # 转换为 OpenAI 格式
        converted = BaseModelClient._convert_tool_info_to_dict(tool_info)

        # 验证格式
        assert converted["type"] == "function"
        assert "function" in converted
        assert converted["function"]["name"] == "write_file"
        assert "parameters" in converted["function"]
        assert converted["function"]["parameters"]["type"] == "object"


class TestGLM4FunctionCalling:
    """测试 GLM-4 的 function calling 功能"""

    @pytest.fixture
    def api_config(self):
        """获取 API 配置"""
        from packages.cli.main import get_config
        config = get_config()
        return {
            "api_key": config.get("api_key"),
            "base_url": config.get("api_base_url")
        }

    @pytest.mark.asyncio
    async def test_glm4_tool_call_direct(self, api_config):
        """测试 GLM-4 直接调用工具（使用 OpenAI 客户端）"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_config["api_key"],
            base_url=api_config["base_url"]
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "写入文件内容，用于创建新文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "文件路径"},
                            "content": {"type": "string", "description": "文件内容"}
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]

        messages = [
            {"role": "system", "content": "你是一个编程助手。当用户要求你写代码时，你必须调用 write_file 工具来创建文件。"},
            {"role": "user", "content": "帮我写一个 hello.py 文件，内容是打印 hello world"}
        ]

        response = await client.chat.completions.create(
            model="glm-4",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        # 验证返回了工具调用
        assert response.choices[0].finish_reason == "tool_calls"
        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) > 0

        tool_call = response.choices[0].message.tool_calls[0]
        assert tool_call.function.name == "write_file"


class TestAgentToolCalling:
    """测试 Agent 的工具调用"""

    @pytest.fixture
    def agent(self):
        """创建测试 Agent"""
        from packages.cli.main import get_config
        from packages.server.agents.openjiuwen_agent import JiuwenCodeAgent

        config = get_config()
        return JiuwenCodeAgent(
            model_provider=config.get("provider", "zhipu"),
            api_key=config.get("api_key"),
            api_base=config.get("api_base_url"),
            model_name=config.get("model", "glm-4"),
        )

    def test_agent_has_tools(self, agent):
        """测试 Agent 是否有工具"""
        tools = agent.get_available_tools()

        assert len(tools) > 0
        assert "write_file" in tools
        assert "read_file" in tools
        assert "bash" in tools

    @pytest.mark.asyncio
    async def test_agent_tool_call_with_explicit_instruction(self, agent):
        """测试 Agent 使用明确指令时的工具调用"""
        query = "请使用 write_file 工具创建一个 test_hello.py 文件，内容是 print('hello')"

        tool_called = False
        tool_name = None

        async for event in agent.stream(query, "test_session"):
            if event.type == "tool_call":
                tool_called = True
                if isinstance(event.data, dict):
                    tool_name = event.data.get("name")
                break

        assert tool_called, "Agent 应该调用工具"
        assert tool_name == "write_file", f"应该调用 write_file 工具，实际调用了 {tool_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

