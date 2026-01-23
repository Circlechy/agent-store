from __future__ import annotations
import abc
import asyncio
import json
import httpx
import traceback
from typing import Any, Optional, Literal, List, Dict
from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


class McpServerConfig(BaseModel):
    type: Optional[Literal["stdio", "sse", "ws", "http"]] = None
    tools: List[str] = Field(default_factory=lambda: ["*"])
    timeout: Optional[int] = None
    env: Dict[str, str] = Field(default_factory=dict)
    envFile: Optional[str] = None
    displayName: Optional[str] = None
    description: Optional[str] = None

    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)

    url: Optional[str] = None

    @field_validator("command")
    @classmethod
    def check_stdio_command(cls, v: Optional[str], info: FieldValidationInfo) -> Optional[str]:
        if info.data.get("type") == "stdio" and not v:
            raise ValueError("stdio command requires a value")
        return v

    @field_validator("url")
    @classmethod
    def check_remote_url(cls, v: Optional[str], info: FieldValidationInfo) -> Optional[str]:
        t = info.data.get("type")
        if t in {"sse", "ws", "http"} and not v:
            raise ValueError(f"remote {t} requires a value")
        return v

    @classmethod
    def from_file(cls, path: str) -> McpServerConfig:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, raw: str) -> McpServerConfig:
        return cls.model_validate_json(raw)


class McpConfig(BaseModel):
    class McpServerConfigDict(BaseModel):
        mcp_server_id: str
        mcp_server_name: str
        configs: McpServerConfig
    servers: list[McpServerConfigDict]
    enable_agent_ids: list[str]

    @classmethod
    def from_file(cls, path: str) -> "McpConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, raw: str) -> "McpConfig":
        return cls.model_validate_json(raw)


def create_mcp_http_client(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    if headers is not None:
        headers.update({"Accept": "text/event-stream"})

    kwargs: dict[str, Any] = {
        "follow_redirects": True
    }
    kwargs["timeout"] = timeout if timeout is not None else httpx.Timeout(30.0)
    if headers is not None:
        kwargs["headers"] = headers

    if auth is not None:
        kwargs["auth"] = auth

    kwargs['verify'] = False
    kwargs['proxy'] = None

    return httpx.AsyncClient(**kwargs)


class McpClientBase(metaclass=abc.ABCMeta):
    def __init__(self, server_id, name, config: McpServerConfig):
        self.server_id = server_id
        self.name = name
        self.config = config
        self.tools = self.get_tools()
        self.tool_schemas = self.get_tool_schemas()

    def get_tools(self):
        try:
            if self.config.type == "sse":
                return asyncio.run(self.async_sse_get_tools())
            elif self.config.type == "stdio":
                return asyncio.run(self.async_stdio_get_tools())
            else:
                raise NotImplementedError(f"get_tools not implemented for {self.config.type}")
        except Exception as e:
            print("Failed to get tools:", e)
            traceback.print_exc()
            return None

    async def async_stdio_get_tools(self):
        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
        )
        async with stdio_client(server_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.list_tools()
                return result

    async def async_sse_get_tools(self):
        try:
            async with sse_client(self.config.url, headers={"Accept": "text/event-stream"},
                                  httpx_client_factory=create_mcp_http_client) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    return await session.list_tools()
        except ExceptionGroup as e:
            for ex in e.exceptions:
                print(f"sub-exception: {type(ex).__name__}: {ex}")
            print(f"Failed to get tools via SSE: {self.config.url}")
        except Exception as e:
            print(f"SSE connect failed: {e}")
        return None

    def call_tool(self, name, arguments):
        if self.config.type == "sse":
            result = asyncio.run(self.async_sse_call_tool(name, arguments))
            return result
        if self.config.type == "stdio":
            result = asyncio.run(self.async_stdio_call_tools(name, arguments))
            return result
        else:
            raise NotImplementedError(f"call_tool not implemented for {self.config.type}")

    async def async_stdio_call_tools(self, name, arguments):
        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env
        )
        async with stdio_client(server_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return result.content

    async def async_sse_call_tool(self, name, arguments):
        async with sse_client(url=self.config.url, httpx_client_factory=create_mcp_http_client) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return result.content

    def get_tool_schemas(self, model: str | None = None):
        schemas = []
        model = model or "deepseek"
        for tool in self.tools.tools:
            properties = self.get_input_schema(tool.inputSchema)
            if model == "openai":
                properties = {**properties, "additionalProperties": False}
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "strict": False,
                        "parameters": properties,
                    }
                })
            elif model in ["deepseek", "qwen"]:
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": properties,
                    }
                })
            elif model == "claude":
                schemas.append({
                    "name": "claude",
                    "description": tool.description,
                    "parameters": properties,
                })
            else:
                raise NotImplementedError(f"model {model} is not supported")
        return schemas

    @staticmethod
    def get_input_schema(mcp_input_schema):
        properties = mcp_input_schema["properties"]
        for item in properties:
            if "title" in properties[item]:
                properties[item]["description"] = properties[item].pop("title")
        return {
            "type": "object",
            "properties": properties,
            "required": mcp_input_schema.get("required", []),
        }


if __name__ == "__main__":
    config = McpServerConfig(
        type="sse",
        url="http://127.0.0.1:8000/sse"
    )
    client = McpClientBase("code-implementation-server", "github-downloader", config)
    print(client.tools)
    print(client.tools.tools)
    print([t.name for t in client.tools.tools])
    # result = client.call_tool("bocha_ai_search", {"query": "空客软件问题", "count": 1})
    # result = client.call_tool("get_document_overview", {"paper_dir": r"D:\project\jiuwen\Agent\test-agentcore\examples\deepcode_agent\tools\generate_code"})
    # result = client.call_tool("parse_download_urls", {"text": r"Download https://ee.hnu.edu.cn/__local/9/55/4C/E95E5B74293CC59A70897CD17B9_9E097C46_E2F3F.pdf to documents folder"})
    result = client.call_tool("download_github_repo", {"instruction": "Get https://github.com/facebook/react"})
    print("RESULT:", result)
