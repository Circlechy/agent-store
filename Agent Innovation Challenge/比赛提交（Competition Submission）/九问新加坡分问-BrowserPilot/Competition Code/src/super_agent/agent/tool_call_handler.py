#!/usr/bin/env python
# coding: utf-8
"""
Tool Call Handler
Handles tool call execution, type conversion, and formatting
Also manages sub-agent tool creation and execution
"""

import json
from typing import Dict, Any, List, Optional
import asyncio
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.common.logging import logger
from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param


class ToolCallHandler:
    """
    Handles all tool call related operations:
    - Sub-agent tool creation (creates LocalFunction wrappers)
    - Type conversion for tool arguments
    - Tool execution (regular tools and sub-agents)
    - Tool call formatting for message history
    """

    def __init__(self, sub_agents: Dict[str, Any] = None, agent_tools: Dict[str, Any] = None):
        """
        Initialize ToolCallHandler

        Args:
            sub_agents: Dictionary of sub-agent instances (optional)
            agent_tools: Dictionary of agent's local tools (optional, used as fallback when runtime.get_tool fails)
        """
        # Use 'is not None' instead of 'or' to preserve empty dict references
        self._sub_agents = sub_agents if sub_agents is not None else {}
        self._agent_tools = agent_tools if agent_tools is not None else {}

    def create_sub_agent_tool(self, agent_name: str, sub_agent: Any) -> LocalFunction:
        """
        Create a LocalFunction tool wrapper for a sub-agent

        Args:
            agent_name: Name of the sub-agent (should start with 'agent-')
            sub_agent: SuperReActAgent instance

        Returns:
            LocalFunction that delegates to the sub-agent
        """
        # Get description from sub-agent config
        description = sub_agent._agent_config.description or f"Sub-agent: {agent_name}"

        # Create a placeholder function
        # Note: Actual execution is handled by execute_tool_call() → _execute_sub_agent()
        def sub_agent_placeholder(subtask: str) -> str:
            """
            Placeholder function for sub-agent tool.
            Actual execution is intercepted by ToolCallHandler.execute_tool_call()
            """
            return f"Sub-agent {agent_name} invoked with task: {subtask}"

        # Create the tool with proper parameters
        sub_agent_tool = LocalFunction(
            name=agent_name,
            description=f"{description}. Delegate a subtask to this specialized agent by providing a clear task description.",
            params=[
                Param(
                    name="subtask",
                    description="The task or question to delegate to this sub-agent. Be specific and provide all necessary context.",
                    param_type="string",
                    required=True
                )
            ],
            func=sub_agent_placeholder
        )

        logger.info(f"Created tool wrapper for sub-agent '{agent_name}'")
        return sub_agent_tool

    def convert_tool_args(self, tool_args: dict, tool) -> dict:
        """
        Convert tool arguments to correct types based on parameter definitions

        Args:
            tool_args: Raw arguments from LLM (may be strings)
            tool: Tool instance with params definition

        Returns:
            Converted arguments with correct types
        """
        if not hasattr(tool, 'params') or not tool.params:
            return tool_args

        converted = {}
        for param in tool.params:
            param_name = param.name
            if param_name not in tool_args:
                continue

            value = tool_args[param_name]
            param_type = param.type

            # Convert based on type
            try:
                if param_type == 'integer':
                    converted[param_name] = int(value)
                elif param_type == 'number':
                    converted[param_name] = float(value)
                elif param_type == 'boolean':
                    if isinstance(value, str):
                        converted[param_name] = value.lower() in ('true', '1', 'yes')
                    else:
                        converted[param_name] = bool(value)
                elif param_type == 'string':
                    converted[param_name] = str(value)
                else:
                    # Keep as-is for complex types
                    converted[param_name] = value
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert {param_name} to {param_type}: {e}, using raw value")
                converted[param_name] = value

        return converted
    
    async def execute_tool_call(
        self,
        tool_call,
        runtime: Runtime
    ) -> Any:
        """
        Execute a single tool call

        Args:
            tool_call: Tool call object from LLM
            runtime: Runtime instance

        Returns:
            Tool execution result
        """
        # ---- ToolCall schema compatibility ----
        # New openjiuwen ToolCall: tool_call.name / tool_call.arguments (arguments is usually a JSON string)
        # Old OpenAI-style: tool_call.function.name / tool_call.function.arguments
        tool_name = None
        tool_args_raw = None

        # if hasattr(tool_call, "name") and hasattr(tool_call, "arguments"):
        #     # New schema
        #     tool_name = getattr(tool_call, "name", None)
        #     tool_args_raw = getattr(tool_call, "arguments", None)
        # else:
        #     # Old schema fallback
        #     fn = getattr(tool_call, "function", None)
        #     if fn is not None:
        #         tool_name = getattr(fn, "name", None)
        #         tool_args_raw = getattr(fn, "arguments", None)
        # ---- ToolCall schema compatibility ----
        tool_name = getattr(tool_call, "name", None)
        tool_args_raw = getattr(tool_call, "arguments", None)

        if not tool_name or tool_args_raw is None:
            fn = getattr(tool_call, "function", None)
            if fn is not None:
                tool_name = tool_name or getattr(fn, "name", None)
                if tool_args_raw is None:
                    tool_args_raw = getattr(fn, "arguments", None)
                if not tool_name:
                    raise RuntimeError(f"ToolCall missing tool name: {tool_call}")

        # ---- Parse arguments robustly ----
        tool_args = {}
        if isinstance(tool_args_raw, dict):
            tool_args = tool_args_raw
        elif isinstance(tool_args_raw, str):
            s = tool_args_raw.strip()
            if s:
                try:
                    tool_args = json.loads(s)
                except json.JSONDecodeError:
                    # If arguments isn't valid JSON, keep empty dict
                    tool_args = {}
        else:
            tool_args = {}

        logger.debug(
            f"Tool {tool_name} raw args: {tool_args}, "
            f"types: {[(k, type(v).__name__) for k, v in tool_args.items()]}"
        )

        # Check if this is a sub-agent call
        if tool_name.startswith("agent-"):
            return await self._execute_sub_agent(tool_name, tool_args)
        else:
            return await self._execute_regular_tool(tool_name, tool_args, runtime)

    # async def execute_tool_call(
    #     self,
    #     tool_call,
    #     runtime: Runtime
    # ) -> Any:
    #     """
    #     Execute a single tool call

    #     Args:
    #         tool_call: Tool call object from LLM
    #         runtime: Runtime instance

    #     Returns:
    #         Tool execution result
    #     """
    #     # Parse tool call
    #     tool_name = tool_call.function.name
    #     try:
    #         tool_args = json.loads(tool_call.function.arguments) if isinstance(
    #             tool_call.function.arguments, str
    #         ) else tool_call.function.arguments
    #     except (json.JSONDecodeError, AttributeError):
    #         tool_args = {}

    #     logger.debug(f"Tool {tool_name} raw args: {tool_args}, types: {[(k, type(v).__name__) for k, v in tool_args.items()]}")

    #     # Check if this is a sub-agent call
    #     if tool_name.startswith("agent-"):
    #         return await self._execute_sub_agent(tool_name, tool_args)
    #     else:
    #         return await self._execute_regular_tool(tool_name, tool_args, runtime)

    async def _execute_sub_agent(self, tool_name: str, tool_args: dict) -> Any:
        """
        Execute a sub-agent call

        Args:
            tool_name: Sub-agent tool name
            tool_args: Tool arguments

        Returns:
            Sub-agent result
        """
        if tool_name not in self._sub_agents:
            raise ValueError(f"Sub-agent not found: {tool_name}")

        sub_agent = self._sub_agents[tool_name]
        subtask = tool_args.get("subtask", "")
        subtask += "\n\nPlease provide the answer and detailed supporting information of the subtask given to you."

        # Execute sub-agent
        result = await sub_agent.invoke(
            {"query": subtask},
            runtime=None  # Sub-agent creates its own runtime
        )

        # Return the output from sub-agent
        return result.get("output", "No result from sub-agent")

    async def _execute_regular_tool(
        self,
        tool_name: str,
        tool_args: dict,
        runtime: Runtime
    ) -> Any:
        """
        Execute a regular tool call

        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            runtime: Runtime instance

        Returns:
            Tool execution result
        """
        # Get tool from runtime, fallback to agent's local tools
        tool = runtime.get_tool(tool_name) if runtime else None
        if not tool:
            # Fallback to agent's local tools (added via add_tools)
            tool = self._agent_tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Validate required parameters before execution
        missing_params = []

        # Unwrap the tool if it's wrapped (e.g., by tracer decorator)
        actual_tool = getattr(tool, '_wrapped', tool)
        params = getattr(actual_tool, 'params', None)
        param_count = len(params) if params else 0
        logger.info(f"[ParamValidation] tool={tool_name}, type={type(actual_tool).__name__}, params_count={param_count}, tool_args={tool_args}")

        # Check for LocalFunction style (params list)
        if params:
            required_param_names = [p.name for p in params if getattr(p, 'required', False)]
            logger.debug(f"Tool {tool_name} required params: {required_param_names}, provided: {list(tool_args.keys())}")
            for param in params:
                if getattr(param, 'required', False) and param.name not in tool_args:
                    missing_params.append(param.name)
        # Check for MCP tool style (MCPTool with mcp_client)
        # elif hasattr(actual_tool, 'mcp_client') and hasattr(actual_tool, 'tool_name'):
        #     try:
        #         # Get tool info from MCP client to check required params
        #         logger.info(f"Getting MCP tool info for validation: {actual_tool.tool_name}")
        #         mcp_tool_info = await actual_tool.mcp_client.get_tool_info(actual_tool.tool_name)
        #         logger.info(f"MCP tool info: {mcp_tool_info}")
        #         if mcp_tool_info and hasattr(mcp_tool_info, 'schema') and isinstance(mcp_tool_info.schema, dict):
        #             required_params = mcp_tool_info.schema.get('required', [])
        #             logger.info(f"Required params for {actual_tool.tool_name}: {required_params}")
        #             missing_params = [p for p in required_params if p not in tool_args]
        #     except Exception as e:
        #         logger.warning(f"Could not get MCP tool info for validation: {e}")
        elif hasattr(actual_tool, 'mcp_client') and hasattr(actual_tool, 'tool_name'):
            try:
                mcp_tool_info = await actual_tool.mcp_client.get_tool_info(actual_tool.tool_name)

                schema = None
                # 兼容 dict 返回
                if isinstance(mcp_tool_info, dict):
                    schema = (
                        mcp_tool_info.get("schema")
                        or mcp_tool_info.get("inputSchema")
                        or mcp_tool_info.get("parameters")
                    )
                else:
                    # 兼容对象返回
                    schema = getattr(mcp_tool_info, "schema", None) or getattr(mcp_tool_info, "inputSchema", None)

                if isinstance(schema, dict):
                    required_params = schema.get("required", []) or []
                    missing_params = [p for p in required_params if p not in tool_args]
            except Exception as e:
                logger.warning(f"Could not get MCP tool info for validation: {e}")

        # Check for direct schema attribute (JSON Schema with 'required' array)
        elif hasattr(actual_tool, 'schema') and isinstance(actual_tool.schema, dict):
            required_params = actual_tool.schema.get('required', [])
            missing_params = [p for p in required_params if p not in tool_args]

        if missing_params:
            error_msg = (
                f"Error calling tool '{tool_name}': Missing required parameters: {missing_params}. "
                f"Please provide these parameters and retry the tool call."
            )
            logger.warning(error_msg)
            return error_msg

        # Convert arguments to correct types
        tool_args = self.convert_tool_args(tool_args, tool)
        logger.debug(f"Tool {tool_name} converted args: {tool_args}, types: {[(k, type(v).__name__) for k, v in tool_args.items()]}")

        # Execute tool
        if tool_name == "auto_browser_use":
            timeout_seconds = 30 * 60  # 30 minutes safety limit for browser tool
            try:
                result = await asyncio.wait_for(tool.ainvoke(tool_args), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"Tool {tool_name} timed out after {timeout_seconds} seconds")
                return "No results obtained due to timeout from the browser use for taking too long"
        else:
            result = await tool.ainvoke(tool_args)
        # logger.info(f"Tool {tool_name} executed with result: {result}")
        # Ensure result is string for downstream processing/logging
        if not isinstance(result, str):
            result_str = str(result)
        else:
            result_str = result

        max_len = 100_000  # 100k chars = 25k tokens
        if len(result_str) > max_len:
            result_str = result_str[:max_len] + "\n... [Result truncated]"
        elif len(result_str) == 0:
            result_str = f"Tool call to {tool_name} completed, but produced no specific output or result."
        return result_str


    @staticmethod
    def format_tool_calls_for_message(tool_calls) -> Optional[List[Dict]]:
        """
        Format tool calls for message history.
        Compatible with:
        - New ToolCall: tc.name / tc.arguments
        - Old OpenAI-style: tc.function.name / tc.function.arguments
        """
        if not tool_calls:
            return None

        formatted: List[Dict] = []
        for tc in tool_calls:
            # id
            tc_id = (
                getattr(tc, "id", None)
                or getattr(tc, "tool_call_id", None)
                or getattr(tc, "call_id", None)
            )

            # type
            tc_type = getattr(tc, "type", None) or "function"

            # name / arguments (兼容两套 schema)
            name = getattr(tc, "name", None)
            arguments = getattr(tc, "arguments", None)

            if not name or arguments is None:
                fn = getattr(tc, "function", None)
                if fn is not None:
                    name = name or getattr(fn, "name", None)
                    if arguments is None:
                        arguments = getattr(fn, "arguments", None)

            # 统一 arguments：尽量存 JSON string（和 OpenAI 格式一致）
            if isinstance(arguments, dict):
                try:
                    arguments = json.dumps(arguments, ensure_ascii=False)
                except Exception:
                    arguments = "{}"
            elif arguments is None:
                arguments = "{}"
            else:
                arguments = str(arguments)

            formatted.append({
                "id": tc_id,
                "type": tc_type,
                "function": {
                    "name": name or "",
                    "arguments": arguments
                }
            })

        return formatted

    # @staticmethod
    # def format_tool_calls_for_message(tool_calls) -> Optional[List[Dict]]:
    #     """
    #     Format tool calls for message history

    #     Args:
    #         tool_calls: Tool calls from LLM response

    #     Returns:
    #         Formatted tool calls for message history, or None if no tool calls
    #     """
    #     if not tool_calls:
    #         return None

    #     formatted = []
    #     for tc in tool_calls:
    #         formatted.append({
    #             "id": tc.id,
    #             "type": tc.type,
    #             "function": {
    #                 "name": tc.function.name,
    #                 "arguments": tc.function.arguments
    #             }
    #         })
    #     return formatted
