import os
import asyncio

from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig
from openjiuwen.core.runner.runner import Runner, resource_mgr

AUTO_BROWSER_SSE_URL = os.getenv("AUTO_BROWSER_SSE_URL", "http://127.0.0.1:8930/sse")

async def main():
    await Runner.start()

    tool_mgr = resource_mgr.tool()
    ok_list = await tool_mgr.add_tool_servers([
        ToolServerConfig(
            server_name="browser-use-server",
            client_type="sse",
            params=AUTO_BROWSER_SSE_URL,
        )
    ])
    if not ok_list or not ok_list[0]:
        raise RuntimeError("Failed to add MCP server")

    # Direct tool call (no agent)
    q = "Go to https://example.com and tell me the page title."
    out = await Runner.run_tool("browser-use-server.auto_browser_use", {"task": q})
    print("TOOL OUTPUT:\n", out)

    await Runner.stop()

if __name__ == "__main__":
    asyncio.run(main())
