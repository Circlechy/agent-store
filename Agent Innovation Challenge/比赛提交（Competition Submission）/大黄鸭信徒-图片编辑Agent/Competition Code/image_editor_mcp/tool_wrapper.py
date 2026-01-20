#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""
Image Editor MCP Tool Wrapper
Provides easy integration with openJiuwen Core SDK.
"""

from typing import List, Any, Dict
from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig
from openjiuwen.core.runner.runner import Runner, resource_mgr


def _remove_base64_from_result(result: Any) -> Any:
    """
    Remove Base64 image data from tool execution result to prevent token explosion.
    
    This function intercepts Base64 data before it reaches the LLM, preventing:
    1. Token explosion: Base64 images can be 100k+ characters
    2. Model confusion: Base64 strings interfere with LLM reasoning
    
    Args:
        result: Tool execution result (can be dict, list, or other types)
    
    Returns:
        Result with Base64 data removed/replaced with summary
    """
    if isinstance(result, dict):
        cleaned = {}
        for key, value in result.items():
            if key == "image_base64":
                # Replace Base64 with a summary message
                if isinstance(value, str):
                    if value.startswith("data:image"):
                        # Extract MIME type if present
                        mime_type = value.split(";")[0].split(":")[-1] if ";" in value else "image"
                        cleaned[key] = f"[Base64 image data removed: {len(value)} chars, type={mime_type}]"
                    else:
                        # Pure Base64 string
                        cleaned[key] = f"[Base64 image data removed: {len(value)} chars]"
                else:
                    cleaned[key] = value
            elif isinstance(value, (dict, list)):
                # Recursively process nested structures
                cleaned[key] = _remove_base64_from_result(value)
            else:
                cleaned[key] = value
        return cleaned
    elif isinstance(result, list):
        return [_remove_base64_from_result(item) for item in result]
    elif isinstance(result, str):
        # Check if the entire string is a Base64 image
        if result.startswith("data:image") or (len(result) > 1000 and _is_likely_base64(result)):
            return f"[Base64 image data removed: {len(result)} chars]"
        return result
    else:
        return result


def _is_likely_base64(text: str) -> bool:
    """
    Check if a string is likely Base64 encoded data.
    
    Args:
        text: String to check
    
    Returns:
        True if likely Base64
    """
    if not text or len(text) < 100:
        return False
    
    # Base64 contains only: A-Z, a-z, 0-9, +, /, = (padding)
    base64_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    text_chars = set(text)
    
    # If more than 95% of characters are Base64 valid, likely Base64
    if len(text_chars - base64_chars) / max(len(text_chars), 1) < 0.05:
        return True
    return False


async def create_image_editor_tools(
    server_name: str = "image-editor-mcp-server",
    client_type: str = "stdio",
    params: dict = None
) -> List[LocalFunction]:
    """
    Create image editor tools from MCP server and return as LocalFunction list.
    
    Args:
        server_name: Name of the MCP server
        client_type: Client type ('stdio' or 'sse')
        params: Parameters for the MCP client
            For stdio: {"command": "python", "args": ["-m", "image_editor_mcp.server"]}
            For sse: URL string like "http://127.0.0.1:8000/sse"
    
    Returns:
        List of LocalFunction tools that can be used with Agents
    """
    tool_mgr = resource_mgr.tool()
    
    # Register MCP server
    server_cfg = ToolServerConfig(
        server_name=server_name,
        server_path="",  # Not used for stdio/sse
        client_type=client_type,
        params=params or {},
    )
    ok_list = await tool_mgr.add_tool_servers([server_cfg])
    if not ok_list or not ok_list[0]:
        raise RuntimeError(f"Failed to add MCP server: {server_name}")
    
    # Get tool list from MCP server
    tool_infos = await Runner.list_tools(server_name)
    
    local_tools = []
    for info in tool_infos:
        schema = getattr(info, "input_schema", {}) or {}
        properties = schema.get("properties", {}) or {}
        required = set(schema.get("required", []) or [])
        
        params_def = []
        for pname, pinfo in properties.items():
            params_def.append(
                Param(
                    name=pname,
                    description=pinfo.get("description", ""),
                    param_type=pinfo.get("type", "string"),
                    required=pname in required,
                    default_value=pinfo.get("default"),
                )
            )
        
        # Create async function wrapper
        # Use factory function to capture tool_id correctly (fixes closure issue)
        # Note: info.name already contains server_name prefix from _normalize_mcp_tool_info
        tool_id = info.name  # Already in format: server_name.tool_name
        
        def _create_wrapper(tid):
            async def _wrapper(**kwargs):
                # Get tool directly from resource manager using the normalized tool_id
                tool = resource_mgr.tool().get_tool(tid)
                if tool is None:
                    raise RuntimeError(f"Tool not found: {tid}")
                # Call tool's ainvoke method directly
                # The MCPTool will use the original tool name from _tool_info.name
                result = await tool.ainvoke(kwargs)
                
                # Extract result if nested in "result" field
                if isinstance(result, dict) and "result" in result:
                    result = result["result"]
                
                # Remove Base64 image data before returning to LLM
                # This prevents token explosion and model confusion
                cleaned_result = _remove_base64_from_result(result)
                return cleaned_result
            return _wrapper
        
        async_func = _create_wrapper(tool_id)
        
        mcp_local_tool = LocalFunction(
            name=info.name,
            description=info.description,
            params=params_def,
            func=async_func,
        )
        
        local_tools.append(mcp_local_tool)
    
    return local_tools

