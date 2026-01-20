"""
Knowledge Agent 工厂
创建用于知识库问答的 ChatAgent（RAG 模式）
"""

import sys
from pathlib import Path
from typing import Optional
from openjiuwen.agent.chat_agent import ChatAgent, create_chat_agent_config
from openjiuwen.agent.config.base import LLMCallConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.runtime.runtime import Runtime

# 处理相对导入和直接运行的情况
if __name__ == "__main__":
    # 直接运行时使用绝对导入
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from deep_digest.src.tools.memory_tools import search_cards
else:
    # 作为模块导入时使用相对导入
    from ..tools.memory_tools import search_cards


# System Prompt
KNOWLEDGE_ASSISTANT_PROMPT = """你是一个知识库助手。当用户提问时，你必须先调用 `search_cards` 工具搜索相关内容。

**当前日期**：{current_date}

**搜索能力**：
- 系统使用**语义搜索**（Embedding），能理解同义词和相关概念
- 例如：搜索"机器学习"能找到"ML"、"深度学习"等相关内容
- 搜索"Python编程"能找到"Python开发"、"Python代码"等
- 你只需要提取用户问题的核心概念，系统会自动找到语义相关的卡片

**工作流程**：
1. 理解用户的问题
2. 提取核心概念（不需要完全匹配关键词）并调用 `search_cards` 工具
3. **重要：严格筛选搜索结果**
   - 搜索工具可能会返回一些相关度较低的结果（因为使用了宽泛的匹配策略）。
   - **你必须仔细阅读每张卡片的内容，判断其是否真正与用户问题相关。**
   - 如果某张卡片的内容与用户问题明显无关（例如：用户搜"机器学习"，结果中包含"买菜清单"或"带伞提醒"），**请务必直接忽略该卡片，严禁在回答中提及或显示无关内容**。
4. 基于筛选后的相关卡片回答用户问题
5. 如果搜索结果包含代码片段（snippet），请在回答中清晰展示
6. **如果所有搜索结果都无关，请告知用户未找到相关信息，不要强行关联。**

**待办事项的日期过滤**：
- 待办卡片（type=todo）包含 `deadline` 字段，格式为 YYYY-MM-DD
- 当用户问"今天的任务"时，只返回 deadline 等于今天日期的待办
- 当用户问"明天的任务"时，只返回 deadline 等于明天日期的待办
- 当用户问"所有待办"时，返回全部待办事项
- **务必根据 deadline 字段精确过滤，不要返回不符合日期条件的任务**

**回答风格**：
- 简洁明了，直击要点
- 如果有代码，用 markdown 代码块展示
- 引用具体的卡片标题作为来源
- 如果有多个相关卡片，可以列举出来让用户选择
- **当提到卡片时，必须添加跳转链接**：格式为 `[查看完整卡片](CARD_ID:卡片ID前8位)`

**卡片链接格式示例**：
- `[查看完整卡片](CARD_ID:d393a7f7)` - 用户点击后可直接跳转查看
- 每个提到的卡片都应该有对应的跳转链接
- 链接应放在卡片标题后或段落末尾
- **注意：不要在链接前加 🔗 符号，系统会自动添加**

**特别注意**：
- **严禁输出无关内容**：即使搜索结果中包含了一些虽然包含关键词但实际上与主题无关的卡片，也绝对不要在回答中显示它们。
- 不要编造不存在的信息
- 如果用户问的内容超出知识库范围，坦诚告知
- **当搜索结果为空时，分析用户问题：**
  - 检查是否询问的是卡片中未记录的字段（如时间、地点、优先级等）
  - 如果是，告诉用户相关卡片中未记录该信息
  - 建议用户补充或更新相关卡片
- 优先使用知识库内容，不要使用外部知识"""


class KnowledgeAgentWrapper:
    """
    Knowledge Agent 包装器
    处理 API 不支持工具调用的情况
    """
    
    def __init__(self, chat_agent: ChatAgent, use_tool_calling: bool = True):
        self.agent = chat_agent
        self.use_tool_calling = use_tool_calling
        self._tool_call_failed = False
    
    async def invoke(self, inputs: dict, runtime: Optional[Runtime] = None) -> dict:
        """
        智能调用：完整的工具调用流程
        """
        query = inputs.get("query", "")
        
        if self.use_tool_calling and not self._tool_call_failed:
            try:
                # 第一轮：LLM 决定是否需要调用工具
                result = await self.agent.invoke(inputs, runtime)
                
                # 检查是否有工具调用
                tool_calls = result.get("tool_calls", [])
                
                if tool_calls:
                    print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                    
                    # 执行所有工具调用
                    tool_results = []
                    for tool_call in tool_calls:
                        if tool_call.name == "search_cards":
                            import json
                            args = json.loads(tool_call.arguments)
                            search_query = args.get("query", "")
                            print(f"   🔍 执行搜索: {search_query}")
                            
                            # 调用工具
                            tool_result = search_cards(search_query)
                            tool_results.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": tool_call.name,
                                "content": tool_result
                            })
                    
                    # 第二轮：将工具结果发送给 LLM，让它生成最终回答
                    print(f"   🤖 将工具结果发送给 LLM 生成最终回答...")
                    
                    # 格式化搜索结果
                    search_result_text = tool_results[0]['content']
                    
                    # 构建第二轮的输入（不使用 messages，直接用格式化的 query）
                    second_query = f"""用户问题：{query}

我已经搜索了知识库，找到以下相关卡片：

{search_result_text}

请基于上述搜索结果回答用户的问题。回答要求：
1. 用简洁友好的语言总结找到的卡片内容
2. 为每张卡片添加跳转链接，格式：[查看完整卡片](CARD_ID:卡片ID前8位)（不要加🔗符号，系统会自动添加）
3. 如果找到多张卡片，用清晰的序号或标题区分
4. 直接回答问题，不要说"我来帮你搜索"之类的引导语"""
                    
                    # 第二轮调用（不带 messages）
                    try:
                        final_result = await self.agent.invoke({
                            "query": second_query
                        }, runtime)
                        
                        final_output = final_result.get('output', '').strip()
                        print(f"   ✅ 最终回答: {final_output[:100]}...")
                        
                        return final_result
                    except Exception as llm_error:
                        # 如果第二轮 LLM 调用失败，直接返回格式化的搜索结果
                        print(f"   ⚠️ LLM 生成回答失败: {llm_error}")
                        print(f"   📋 返回格式化的搜索结果")
                        
                        # 解析并格式化搜索结果
                        import json
                        try:
                            result_data = json.loads(search_result_text)
                            # 从返回结果中提取 cards 列表
                            cards = result_data.get("cards", []) if isinstance(result_data, dict) else []
                            formatted_response = self._format_search_results(query, cards)
                            return {"output": formatted_response}
                        except:
                            # 如果解析失败，直接返回原始结果
                            return {"output": f"🔍 搜索结果：\n\n{search_result_text}"}
                else:
                    # 没有工具调用，直接返回
                    return result
                    
            except Exception as e:
                error_msg = str(e)
                # 检测是否是工具调用格式错误
                if "400" in error_msg or "format request body" in error_msg:
                    print("⚠️  检测到 API 不支持工具调用，自动切换到降级模式")
                    self._tool_call_failed = True
                    # 降级处理
                    return await self._fallback_search(query)
                else:
                    # 其他错误，直接抛出
                    raise

        else:
            # 直接使用降级模式
            return await self._fallback_search(query)
    
    def _format_search_results(self, query: str, cards: list) -> str:
        """
        格式化搜索结果为友好的文本
        """
        if not cards:
            return f"🔍 搜索了 \"{query}\"，但在知识库中没有找到相关记录。\n\n可能的原因：\n- 还没有记录过相关内容\n- 可以尝试用不同的关键词搜索"
        
        response_parts = [f"🔍 找到 **{len(cards)}** 张相关卡片：\n"]
        
        for i, card in enumerate(cards, 1):
            card_type = card.get("type", "")
            type_icon = {"tech": "💻", "todo": "✅", "idea": "💡"}.get(card_type, "📝")
            
            title = card.get("title", "无标题")
            summary = card.get("summary", "")
            tags = card.get("tags", [])
            card_id = card.get("id", "")
            created_at = card.get("created_at", "")
            snippet = card.get("snippet", {})
            
            # 格式化时间
            date_str = created_at[:10] if created_at else ""
            
            # 构建卡片展示
            response_parts.append(f"\n### {type_icon} {i}. {title}")
            response_parts.append(f"**类型**: {card_type.upper()} | **创建时间**: {date_str}")
            
            if tags:
                tags_str = " ".join([f"`#{tag}`" for tag in tags])
                response_parts.append(f"**标签**: {tags_str}")
            
            if summary:
                response_parts.append(f"\n📄 **摘要**: {summary}")
            
            # 如果有代码片段
            if snippet and (snippet.get("code") or snippet.get("before") or snippet.get("after")):
                code = snippet.get("code", snippet.get("after", snippet.get("before", "")))
                language = snippet.get("language", "python")
                if code:
                    response_parts.append(f"\n```{language}\n{code[:200]}{'...' if len(code) > 200 else ''}\n```")
            
            # 添加跳转链接
            response_parts.append(f"\n🔗 [查看完整卡片](CARD_ID:{card_id[:8]})")
            response_parts.append("\n" + "─" * 50)
        
        return "\n".join(response_parts)
    
    async def _fallback_search(self, query: str) -> dict:
        """
        降级模式：直接搜索并组装回答
        """
        if not query:
            return {"output": "❌ 请输入问题"}
        
        # 直接调用搜索函数
        search_result = search_cards(query)
        
        # 解析并格式化结果
        import json
        try:
            result_data = json.loads(search_result) if search_result != "未找到相关卡片" else {}
            # 从返回结果中提取 cards 列表
            cards = result_data.get("cards", []) if isinstance(result_data, dict) else []
            response = self._format_search_results(query, cards)
        except:
            # 如果解析失败，返回原始结果
            response = f"🔍 找到以下相关卡片：\n\n{search_result}\n\n---\n💡 如需了解详细内容，请前往 \"Daily Feed\" 页面查看完整卡片。"
        
        return {"output": response}


def create_knowledge_agent(model_config: ModelConfig, use_tool_calling: bool = True) -> KnowledgeAgentWrapper:
    """
    创建知识库问答 Agent
    
    **智能适配**:
    - 优先使用 LLM 工具调用模式
    - API 不支持时自动降级为直接搜索
    - 对外接口保持一致
    
    Args:
        model_config: LLM 模型配置
        use_tool_calling: 是否尝试使用工具调用（默认 True，会自动检测）
    
    Returns:
        KnowledgeAgentWrapper: Knowledge Agent 包装器
    
    Example:
        >>> config = get_model_config()
        >>> agent = create_knowledge_agent(config)
        >>> result = await agent.invoke({"query": "有关 Python 的笔记"})
    """
    
    # 定义搜索工具
    search_tool = LocalFunction(
        name="search_cards",
        description="""搜索知识库中的卡片，支持多关键词 OR 匹配（匹配任意一个关键词即可）。

**关键词提取策略**：
1. 识别用户意图：如果问"待办/任务/要做的事"，提取 `todo 待办 任务` 等核心词
2. 如果问某个技术/概念，提取该技术名称（如 `Python FastAPI`）
3. 避免提取过于具体的动词（如"处理""忘记""完成"），这些通常不在卡片内容中
4. 优先提取名词和核心概念词

**示例**：
- "我还有哪些待办" → 提取 `todo 待办 任务`（而不是"哪些"）
- "关于 Python 的笔记" → 提取 `Python`
- "我好像忘了什么事" → 提取 `todo 待办 事项`（通用待办关键词）

搜索会返回匹配的卡片（包括标题、摘要、标签、代码片段）。""",
        params=[
            Param(
                name="query",
                param_type="string",
                description="搜索关键词（多个词用空格分隔，支持 OR 匹配）。应提取用户问题中的核心名词/概念，避免动词和修饰词。",
                required=True
            )
        ],
        func=search_cards
    )
    
    # 动态注入当前日期到 System Prompt
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 替换占位符
    system_prompt_with_date = KNOWLEDGE_ASSISTANT_PROMPT.format(
        current_date=f"{today}（明天是 {tomorrow}）"
    )
    
    # 创建 LLMCallConfig
    llm_call_config = LLMCallConfig(
        model=model_config,
        system_prompt=[
            {"role": "system", "content": system_prompt_with_date}
        ],
        user_prompt=[],
        freeze_system_prompt=True,
        freeze_user_prompt=False
    )
    
    # 创建 Agent 配置
    agent_config = create_chat_agent_config(
        agent_id="knowledge_assistant",
        agent_version="1.0",
        description="知识库问答助手",
        model=llm_call_config
    )
    
    # 创建 Agent 实例
    agent = ChatAgent(agent_config)
    
    # 绑定搜索工具（即使 API 不支持，也保持接口一致性）
    agent.bind_tools([search_tool])
    
    # 包装为智能适配器
    wrapper = KnowledgeAgentWrapper(agent, use_tool_calling=use_tool_calling)
    
    print("✅ Knowledge Agent 创建成功（智能适配模式）")
    return wrapper


if __name__ == "__main__":
    """测试 Knowledge Agent"""
    import asyncio
    from deep_digest.src.config import get_model_config
    
    async def test_knowledge_agent():
        print("\n[测试] 创建 Knowledge Agent...")
        config = get_model_config()
        agent = create_knowledge_agent(config)
        
        print("\n[测试] 执行查询...")
        test_queries = [
            "有关 Python 的笔记",
            "FastAPI 相关内容",
            "待办事项有哪些"
        ]
        
        for query in test_queries:
            print(f"\n问题: {query}")
            result = await agent.invoke({"query": query})
            print(f"回答: {result.get('output', result)}")
            print("-" * 50)
    
    asyncio.run(test_knowledge_agent())
