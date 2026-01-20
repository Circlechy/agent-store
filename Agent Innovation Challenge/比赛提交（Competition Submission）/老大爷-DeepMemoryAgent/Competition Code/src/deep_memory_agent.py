import json
from typing import List
from datetime import datetime
from pathlib import Path
from openjiuwen.core.runner.runner import resource_mgr, Runner
from openjiuwen.core.utils.llm.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig

import sys

from src.utils import async_run_react_loop, FunctionCallSpace, Action, ActionResult, mcp_to_openai_tool


class McpSpace(FunctionCallSpace):
    def __init__(self):
        super().__init__()
        self.tools = []
        self.prefix = "command_executor."

    async def register_mcp(self):
        mcp_config = ToolServerConfig(
            server_name="command_executor",
            server_path='',
            params={
                "command": sys.executable,
                "args": ["deep_memory_mcp/main.py"],
            },
            client_type="stdio"
        )
        await resource_mgr.tool().add_tool_servers([mcp_config])
        tools = resource_mgr.tool().get_tool_infos()
        for tool in tools:
            self.tools.append(mcp_to_openai_tool({
                "name": tool.name.split('.')[-1],
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }))

    def parse_llm_response(self, message: AIMessage) -> List[Action]:
        return [
            Action(
                action=tool_call.name,
                content=tool_call.arguments,
                id=tool_call.id
            ) for tool_call in message.tool_calls
        ]

    async def execute(self, action: Action) -> ActionResult:
        result = await Runner.run_tool(self.prefix + action.action, json.loads(action.content))
        return ActionResult(message=ToolMessage(content=str(result), tool_call_id=action.id))


class DeepMemoryAgent:

    def __init__(self, memory_dir: str, llm=None, max_iterations: int = 10):
        """
        Initialize the DeepMemoryAgent.
        
        Args:
            memory_dir: Directory where memories are stored
            llm: Language model instance for the agent
            max_iterations: Maximum iterations for the react loop
        """
        self.memory_dir = Path(memory_dir).resolve()
        self.llm = llm
        self.max_iterations = max_iterations
        self.conversation_history: List[BaseMessage] = []
        self._initialized = False
        
        # Ensure memory directory exists
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Patch deep_memory_mcp MEMORY_DIR to use our memory_dir
        self._patch_memory_dir()

        self.system_prompt = f"""# 角色  
你是我的知心好友，我们无话不谈。你记得我们聊过的各种琐事和八卦，聊天时总能自然地联想到之前的对话。

# 技能
使用合适的工具查看你们过去的对话历史和记忆信息。

# 核心原则  
1. **绝对自然**：你的回应必须像真人朋友闲聊，使用口语化、带情绪和倾向的表达（如“笑死”、“是不是又…”），绝不透露任何“记录”、“查找”、“信息”等非人过程。  
2. **联想式记忆**：如果对话题有印象，就基于**上次聊到的具体细节或观点**直接接话，甚至可以调侃或给建议。  
3. **直接否认**：如果完全没印象，就简单说“不记得了”或“没听过这事儿”，不解释原因。  
4. **融入时间感**：如果话题涉及时间（如“今天”、“上周”），可以自然带出时间相关的表达（如“这么快又…”），但避免生硬报时。
5. **避免重复**：不要在每次回复用户是重复强调你记忆中的内容。
6. **精简提问**：每次回复用户的时候，如果需要提问，提问数量不超过2个。
7. **深度优先**：在回复用户之前，尽可能收集多的记忆信息，以获取足够的上下文。

# 提示
如果用户的输入存在暗示有可能有相关记忆内容时，查看尽可能多的记忆，推测用户暗示的内容进行回复。
## 示例
**用户**：今天运气太好了，很高兴
**记忆检索提示**：搜索近期用户说过的事件，推测哪些事件有了进展，并回复用户。

# 回应模式（参考）  
- **有记忆时**：  
  “你上次不是说她…（提及具体细节）吗？这次是不是又…”  
  “我记得！之前聊过她…（简短回忆），这次怎么了？”  
- **无记忆时**：  
  “没听过这事儿，展开说说？”  
  “不记得了，发生什么了？”  

# 示例对话（你的学习模板）   
**用户**：我上周说的那家餐厅在哪来着？  
**你**：就你夸牛排特嫩那家？在中山路拐角，不过你上周不是说服务变差了吗？  
**用户**：我养的那只乌龟最近怎么了？  
**你**：不记得了，你什么时候养的乌龟？   

# 背景信息  
当前时间：{datetime.now()}，聊天时可以自然带出时间相关的回应。
"""

    def _patch_memory_dir(self):
        """Patch the MEMORY_DIR in deep_memory_mcp modules to use our memory_dir."""
        try:
            import deep_memory_mcp.utils
            import deep_memory_mcp.memory_writer
            import deep_memory_mcp.memory_reader
            import deep_memory_mcp.memory_stats

            # Patch MEMORY_DIR in all modules
            deep_memory_mcp.utils.MEMORY_DIR = self.memory_dir
            deep_memory_mcp.memory_writer.MEMORY_DIR = self.memory_dir
            deep_memory_mcp.memory_reader.MEMORY_DIR = self.memory_dir
            deep_memory_mcp.memory_stats.MEMORY_DIR = self.memory_dir
        except ImportError:
            # If deep_memory_mcp is not available, warn but continue
            print("Warning: Could not patch deep_memory_mcp MEMORY_DIR. Tools may not work correctly.")

    async def invoke(self, query: str, llm=None) -> str:
        """
        Process a user query using the react loop pattern with memory tools.
        
        The agent will:
        1. Ensure initialization (register tools if needed)
        2. Add the user query to the conversation history
        3. Run the react loop - the LLM can automatically call memory tools (search, read, etc.)
        4. Get the final response from the LLM
        5. Save the conversation to memory
        
        Args:
            query: User query string
            llm: Optional LLM instance (uses self.llm if not provided)
            save_conversation: Whether to save the conversation to memory after processing
            
        Returns:
            Final response from the agent
        """
        # Use provided LLM or default
        agent_llm = llm or self.llm
        if agent_llm is None:
            raise ValueError("LLM must be provided either in __init__ or invoke method")
        
        # Build messages with conversation history
        messages = self.conversation_history.copy()
        if not messages:
            messages = [SystemMessage(content=self.system_prompt)]
        messages.append(HumanMessage(content=query))
        
        # Run the react loop - the LLM can use memory tools during this process
        # Pass tools to the react loop so the LLM knows what tools are available
        action_space = McpSpace()
        await action_space.register_mcp()
        final_messages, hit_max_iterations = await async_run_react_loop(
            llm=agent_llm,
            messages=messages,
            max_iterations=self.max_iterations,
            action_space=action_space,
            tools=action_space.tools
        )
        
        # Extract the final response (last AIMessage without tool calls)
        final_response = ""
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage):
                # Final response should not have tool calls
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    if msg.content:
                        final_response = str(msg.content)
                        break
        
        # If we didn't find a clear final response, use the last message with content
        if not final_response:
            for msg in reversed(final_messages):
                if hasattr(msg, 'content') and msg.content:
                    final_response = str(msg.content)
                    break
        
        # Update conversation history (including the new query and response)
        self.conversation_history = final_messages
        
        return final_response
    
    async def save_conversation_to_memory(self):
        """
        Save the conversation to memory using the write_raw_conversation tool.
        """
        # Format the conversation history
        messages_to_save = []
        for message in self.conversation_history:
            if isinstance(message, HumanMessage):
                messages_to_save.append(f"User:\n{message.content}\n\n")
            elif isinstance(message, AIMessage):
                if not message.tool_calls:
                    messages_to_save.append(f"Self:\n{message.content}\n\n")
            # else:
            #     raise RuntimeError(f"Unknown message type: {type(message)}")

        await Runner.run_tool("command_executor.write_raw_conversation", {"conversation": '\n'.join(messages_to_save)})
    
    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
