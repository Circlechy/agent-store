import asyncio
import unittest

from mcp import StdioServerParameters

from examples.deepcode_agent.agent_flow import AgentAggregation
from examples.deepcode_agent.agents import ReActAgent, AgentConfig
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig


class ReactAgentTest(unittest.IsolatedAsyncioTestCase):

    @unittest.skip("require llm config")
    async def test_agent_aggregation(self):
        mcp_config = ToolServerConfig(
            server_name="command_executor",
            params=StdioServerParameters(command="python", args=["provide your mcp server path"]),
            client_type="stdio"
        )

        agent_1 = ReActAgent(
            AgentConfig(
                name="agent_1",
                llm_config={
                    "model_provider": "openai",
                    "api_key": "please provide your api_key",
                    "api_base": "please provide your api_base",
                    "model_name": "please provide your model_name",
                },
                system_prompt="你是一个小助手，可以使用windows的工具完成用户任务。"
            )
        )
        await agent_1.add_mcps([mcp_config])

        agent_2 = ReActAgent(
            AgentConfig(
                name="agent_2",
                llm_config={
                    "model_provider": "openai",
                    "api_key": "sk-66e619e5e3ca4d86919f4f33238feeae",
                    "api_base": "https://api.deepseek.com",
                    "model_name": "deepseek-chat"
                },
                system_prompt = "你是一个小助手，可以使用windows的工具完成用户任务。"
            )
        )

        agent_3 = ReActAgent(
            AgentConfig(
                name="agent_3",
                llm_config={
                    "model_provider": "openai",
                    "api_key": "sk-66e619e5e3ca4d86919f4f33238feeae",
                    "api_base": "https://api.deepseek.com",
                    "model_name": "deepseek-chat"
                },
                system_prompt="你是总结小助手，请总结其他Agent的任务。"
            )
        )

        aggregation = AgentAggregation(aggregator=agent_3, source_agents=[agent_1, agent_2])
        result = await aggregation.ainvoke({"query": "帮我查一下当前工作路径是什么，里面都有哪些文件？"})
        print(result)