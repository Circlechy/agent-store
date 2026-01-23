import asyncio
import unittest

from mcp import StdioServerParameters

from examples.deepcode_agent.agents import ReActAgent, AgentConfig
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig


class ReactAgentTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.agent = ReActAgent(
            AgentConfig(
                name="default_agent",
                llm_config={
                    "model_provider": "openai",
                    "api_key": "please provide your api_key",
                    "api_base": "please provide your api_base",
                    "model_name": "please provide your model_name",
                }
            )
        )

    def tearDown(self):
        """每个测试后关闭事件循环"""
        self.loop.close()
        asyncio.set_event_loop(None)

    @unittest.skip("require llm config")
    def test_call_model(self):
        response = self.agent.call_llm(model_name="deepseek-chat", messages=[dict(role="user", content="你好")])
        assert len(response.content) != 0

    @unittest.skip("require stdio mcp server path")
    async def test_mcp_tool(self):
        mcp_config = ToolServerConfig(
            server_name="command_executor",
            params=StdioServerParameters(command="python", args=["provide your mcp server path"]),
            client_type="stdio"
        )

        await self.agent.add_mcps([mcp_config])
        result = await self.agent.execute_mcp_tool('replace with tool name', {})
        print(result)

    @unittest.skip("require llm config")
    async def test_react_loop(self):
        mcp_config = ToolServerConfig(
            server_name="command_executor",
            params=StdioServerParameters(command="python", args=["provide your mcp server path"]),
            client_type="stdio"
        )

        await self.agent.add_mcps([mcp_config])

        result = await self.agent.ainvoke({"query": "帮我查一下当前工作路径是什么，里面都有哪些文件？"})

        print(result)