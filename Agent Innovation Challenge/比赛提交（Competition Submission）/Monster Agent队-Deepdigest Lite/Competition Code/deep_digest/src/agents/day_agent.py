"""
Day Agent 工厂
创建用于极速录入的 ChatAgent

支持两种模式：
1. 标准模式：使用 LLM 工具调用（需要 API 支持 Function Calling）
2. 降级模式：API 不支持时自动降级为直接保存
"""

from typing import Optional
from openjiuwen.agent.chat_agent import ChatAgent, create_chat_agent_config
from openjiuwen.agent.config.base import LLMCallConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.runtime.runtime import Runtime

from ..prompts.day_prompts import RECORDER_SYSTEM_PROMPT
from ..tools.inbox_tools import add_fragment


class DayAgentWrapper:
    """
    Day Agent 包装器
    自动处理 API 兼容性问题
    """
    
    def __init__(self, chat_agent: ChatAgent, use_tool_calling: bool = True):
        self.agent = chat_agent
        self.use_tool_calling = use_tool_calling
        self._tool_call_failed = False
    
    async def invoke(self, inputs: dict, runtime: Optional[Runtime] = None) -> dict:
        """
        智能调用：两轮工具调用流程
        Round 1: LLM 决定调用工具 → 执行工具 → Round 2: LLM 生成响应
        """
        if self.use_tool_calling and not self._tool_call_failed:
            try:
                # Round 1: 获取工具调用决策
                result = await self.agent.invoke(inputs, runtime)
                tool_calls = result.get("tool_calls", [])
                
                if not tool_calls:
                    # 没有工具调用，直接返回
                    return result
                
                # 执行所有工具调用
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.arguments
                    
                    print(f"🔧 [Day Agent] 执行工具: {tool_name}, 参数: {tool_args}")
                    
                    # 执行工具
                    if tool_name == "save_fragment":
                        import json
                        args = json.loads(tool_args)
                        content = args.get("content", "")
                        fragment_id = add_fragment(content)
                        
                        if fragment_id:
                            tool_result = f"✅ 已保存碎片到 Inbox (ID: {fragment_id})"
                        else:
                            tool_result = "❌ 保存失败"
                    else:
                        tool_result = f"⚠️ 未知工具: {tool_name}"
                    
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_result
                    })
                    
                    print(f"✅ [Day Agent] 工具执行结果: {tool_result}")
                
                # Round 2: 将工具结果反馈给 LLM 生成最终响应
                # 构建包含工具结果的新输入
                messages = [
                    {"role": "user", "content": inputs.get("query", "")},
                    {"role": "assistant", "content": result.get("output", ""), "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                        for tc in tool_calls
                    ]},
                ]
                messages.extend(tool_results)
                
                # 使用工具结果作为新输入调用 agent
                second_result = await self.agent.invoke({
                    "query": inputs.get("query", ""),
                    "messages": messages
                }, runtime)
                
                return second_result
                
            except Exception as e:
                error_msg = str(e)
                # 检测是否是工具调用格式错误
                if "400" in error_msg or "format request body" in error_msg:
                    print("⚠️  检测到 API 不支持工具调用，自动切换到降级模式")
                    self._tool_call_failed = True
                    # 降级处理
                    return await self._fallback_save(inputs)
                else:
                    # 其他错误，直接抛出
                    raise
        else:
            # 直接使用降级模式
            return await self._fallback_save(inputs)
    
    async def _fallback_save(self, inputs: dict) -> dict:
        """
        降级模式：直接保存，不经过 LLM
        """
        query = inputs.get("query", "")
        
        if not query:
            return {"output": "❌ 输入为空"}
        
        # 直接保存到 Inbox
        fragment_id = add_fragment(query)
        
        if fragment_id:
            return {"output": "✅ [已记录]"}
        else:
            return {"output": "❌ 保存失败"}


def _create_save_fragment_tool() -> LocalFunction:
    """
    创建 save_fragment 工具
    
    这是 Day Agent 唯一需要的工具，用于保存用户输入的碎片
    
    Returns:
        LocalFunction: save_fragment 工具实例
    """
    def save_fragment_func(content: str) -> str:
        """
        保存碎片到 Inbox
        
        Args:
            content: 用户输入的内容
        
        Returns:
            str: 保存结果
        """
        fragment_id = add_fragment(content)
        if fragment_id:
            return f"✅ 碎片已保存 (ID: {fragment_id})"
        else:
            return "❌ 保存失败"
    
    # 定义工具参数
    params = [
        Param(
            name="content",
            description="用户输入的内容，完整保存，不要修改",
            param_type="string",
            required=True
        )
    ]
    
    tool = LocalFunction(
        name="save_fragment",
        description="保存用户输入的碎片到短期记忆池。无论用户输入什么，都必须调用此工具。",
        params=params,
        func=save_fragment_func
    )
    
    return tool


def create_day_agent(model_config: ModelConfig, use_tool_calling: bool = True) -> DayAgentWrapper:
    """
    创建 Day Agent（速记员）
    
    **智能适配**:
    - 优先使用 LLM 工具调用模式
    - API 不支持时自动降级为直接保存
    - 对外接口保持一致
    
    Args:
        model_config: LLM 模型配置
        use_tool_calling: 是否尝试使用工具调用（默认 True，会自动检测）
    
    Returns:
        DayAgentWrapper: Day Agent 包装器，自动处理兼容性
    
    Example:
        >>> from src.config import get_model_config
        >>> from src.agents import create_day_agent
        >>> 
        >>> model_config = get_model_config()
        >>> day_agent = create_day_agent(model_config)
        >>> 
        >>> # 自动适配 API，统一接口
        >>> result = await day_agent.invoke({
        ...     "query": "Bug: Docker 容器无法连接 Redis",
        ...     "conversation_id": "session_1"
        ... })
        >>> print(result)
        {'output': '✅ [已记录]'}
    """
    
    # 1. 创建 LLMCallConfig（包装 ModelConfig 和 system prompt）
    llm_call_config = LLMCallConfig(
        model=model_config,
        system_prompt=[
            {"role": "system", "content": RECORDER_SYSTEM_PROMPT}
        ],
        user_prompt=[],
        freeze_system_prompt=True,
        freeze_user_prompt=False
    )
    
    # 2. 创建 ChatAgent 配置
    config = create_chat_agent_config(
        agent_id="day_recorder",
        agent_version="1.0",
        description="DeepDigest Day Agent - 静默速记员（智能适配）",
        model=llm_call_config
    )
    
    # 3. 创建 Agent 实例
    agent = ChatAgent(config)
    
    # 4. 绑定工具（即使 API 不支持，也保持接口一致性）
    save_fragment_tool = _create_save_fragment_tool()
    agent.bind_tools([save_fragment_tool])
    
    # 5. 包装为智能适配器
    wrapper = DayAgentWrapper(agent, use_tool_calling=use_tool_calling)
    
    print("✅ Day Agent 创建成功（智能适配模式）")
    print(f"   - Agent ID: day_recorder")
    print(f"   - 工具调用: {'启用（自动降级）' if use_tool_calling else '禁用'}")
    
    return wrapper


# ===================== 测试代码 =====================
if __name__ == "__main__":
    import asyncio
    from ..config import get_model_config
    from ..tools import init_inbox_db, count_pending_fragments
    
    async def test_day_agent():
        print("=" * 50)
        print("Day Agent 测试")
        print("=" * 50)
        
        # 1. 初始化
        print("\n[步骤 1] 初始化环境...")
        init_inbox_db()
        model_config = get_model_config()
        
        # 2. 创建 Agent
        print("\n[步骤 2] 创建 Day Agent...")
        agent = create_day_agent(model_config)
        
        # 3. 测试录入
        print("\n[步骤 3] 测试用户输入...")
        test_inputs = [
            "Bug: Docker 容器无法连接 Redis",
            "明天下午3点技术评审会",
            "想法：用 AI 做代码审查工具"
        ]
        
        for i, user_input in enumerate(test_inputs, 1):
            print(f"\n--- 测试 {i} ---")
            print(f"用户输入: {user_input}")
            
            result = await agent.invoke({
                "query": user_input,
                "conversation_id": "test_session"
            })
            
            print(f"Agent 回复: {result}")
        
        # 4. 验证结果
        print("\n[步骤 4] 验证数据库...")
        count = count_pending_fragments()
        print(f"待处理碎片数: {count} 条")
        
        if count >= len(test_inputs):
            print("✅ 测试通过！碎片已成功保存")
        else:
            print("⚠️ 测试异常！碎片数量不匹配")
    
    asyncio.run(test_day_agent())
