"""Star-Commander 使用示例.

演示如何使用NovaStar的主控Agent进行意图识别与任务路由。
"""

import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novastar.agents import StarCommander
from novastar.agents.commander import IntentType, AgentType
from novastar.utils.config import get_config, load_config


# 全局配置
_config = None
_llm_config = None


def get_llm_config() -> dict:
    """从配置文件和环境变量获取LLM配置.

    Returns:
        LLM配置字典
    """
    global _llm_config
    if _llm_config is not None:
        return _llm_config

    config = get_config()

    # 从环境变量获取API密钥
    api_key = config.get_env("openai_api_key")
    api_base = config.get_env("openai_api_base")

    # 模型配置
    model_type = config.get_env("llm_model_type") or "openai"
    model_name = config.get_env("llm_model_name") or "gpt-4o-mini"

    _llm_config = {
        "model_type": model_type,
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "timeout": 60,
    }
    return _llm_config


def create_commander_with_config(**kwargs) -> StarCommander:
    """创建带配置的StarCommander实例.

    Args:
        **kwargs: 额外的配置参数

    Returns:
        StarCommander实例
    """
    llm_config = get_llm_config()
    return StarCommander(
        name=kwargs.pop("name", "Star-Commander"),
        llm_config=llm_config if llm_config.get("api_key") else None,
        **kwargs,
    )


async def example_basic_process():
    """基础消息处理示例."""
    print("=" * 60)
    print("示例1: 基础消息处理")
    print("=" * 60)

    commander = create_commander_with_config()

    # 测试内容
    result = await commander.process(
        user_id="child_001",
        message="为什么天空是蓝色的？",
        context={"age": 6},
    )

    print(f"\n用户消息: 为什么天空是蓝色的？")
    print(f"用户ID: child_001")
    print(f"意图: {result.get('intent', 'N/A')}")
    print(f"路由到: {result.get('routed_to', 'N/A')}")
    print(f"处理者: {result.get('handled_by', 'N/A')}")
    response = result.get("response", "")
    if response:
        print(f"响应: {response[:200]}..." if len(response) > 200 else f"响应: {response}")


async def example_intent_identification():
    """意图识别示例."""
    print("\n" + "=" * 60)
    print("示例2: 意图识别")
    print("=" * 60)

    commander = create_commander_with_config()

    test_messages = [
        ("为什么月亮会变圆？", IntentType.LEARNING),
        ("给我讲一个故事", IntentType.STORY),
        ("我们来玩个游戏吧", IntentType.GAME),
        ("我今天有点难过", IntentType.EMOTION),
        ("帮我画一只小猫", IntentType.CREATIVE),
        ("我要养成早睡的习惯", IntentType.HABIT),
        ("你好", IntentType.UNKNOWN),
    ]

    for message, _ in test_messages:
        intent = await commander.identify_intent(message)
        print(f"\n消息: {message}")
        print(f"识别的意图: {intent.value}")


async def example_task_routing():
    """任务路由示例."""
    print("\n" + "=" * 60)
    print("示例3: 任务路由")
    print("=" * 60)

    commander = create_commander_with_config()

    routing_tests = [
        (IntentType.LEARNING, AgentType.MENTOR),
        (IntentType.STORY, AgentType.ARTIST),
        (IntentType.GAME, AgentType.ARTIST),
        (IntentType.CREATIVE, AgentType.ARTIST),
        (IntentType.EMOTION, AgentType.COMMANDER),
        (IntentType.HABIT, AgentType.COMMANDER),
        (IntentType.UNKNOWN, AgentType.COMMANDER),
    ]

    for intent, expected_agent in routing_tests:
        agent = await commander.route_task(intent)
        print(f"\n意图: {intent.value} -> 路由到: {agent.value}")
        assert agent == expected_agent, f"路由错误: {intent} 应该路由到 {expected_agent}"


async def example_multiple_intents():
    """多种意图处理示例."""
    print("\n" + "=" * 60)
    print("示例8: 多种意图处理")
    print("=" * 60)

    commander = create_commander_with_config()

    queries = [
        ("为什么月亮会变圆变扁？", IntentType.LEARNING),
        ("给我讲一个冒险故事", IntentType.STORY),
        ("我们来玩个游戏吧", IntentType.GAME),
        ("我今天有点难过", IntentType.EMOTION),
        ("帮我画一只小猫", IntentType.CREATIVE),
        ("我要养成早睡的习惯", IntentType.HABIT),
    ]

    for query, expected_intent in queries:
        result = await commander.process(
            user_id="child_003",
            message=query,
            context={"age": 7},
        )
        print(f"\n查询: {query}")
        print(f"预期意图: {expected_intent.value}")
        print(f"实际意图: {result.get('intent', 'N/A')}")
        print(f"路由到: {result.get('routed_to', 'N/A')}")
        print(f"处理者: {result.get('handled_by', 'N/A')}")


async def example_with_llm_config():
    """配置LLM的Commander示例."""
    print("\n" + "=" * 60)
    print("示例9: 配置LLM的Commander")
    print("=" * 60)

    llm_config = get_llm_config()

    if not llm_config.get("api_key"):
        print("⚠️  未设置OPENAI_API_KEY环境变量，将使用模拟响应")
        print("设置方法：export OPENAI_API_KEY=your-api-key")
        print("或设置环境变量：OPENAI_API_KEY=your-api-key\n")

    commander = create_commander_with_config()

    result = await commander.process(
        user_id="child_004",
        message="什么是光合作用？用简单的话解释给我听",
        context={"age": 8},
    )

    print(f"查询: 什么是光合作用？")
    print(f"意图: {result.get('intent', 'N/A')}")
    response = result.get("response", "")
    if response:
        print(f"响应:\n{response[:300]}..." if len(response) > 300 else f"响应:\n{response}")


async def example_context_handling():
    """上下文处理示例."""
    print("\n" + "=" * 60)
    print("示例10: 上下文处理")
    print("=" * 60)

    commander = create_commander_with_config()

    # 不同年龄的上下文
    contexts = [
        {"age": 5, "interests": ["动物", "故事"]},
        {"age": 8, "interests": ["科学", "太空"]},
        {"age": 10, "interests": ["编程", "数学"]},
    ]

    for context in contexts:
        result = await commander.process(
            user_id="child_005",
            message="给我讲个故事",
            context=context,
        )
        print(f"\n年龄: {context['age']}, 兴趣: {context['interests']}")
        print(f"意图: {result.get('intent', 'N/A')}")
        print(f"路由到: {result.get('routed_to', 'N/A')}")


async def main():
    """运行所有示例."""
    # 加载配置
    load_config()

    # 检查LLM配置
    llm_config = get_llm_config()
    if not llm_config.get("api_key"):
        print("\n" + "=" * 60)
        print("⚠️  注意: 未配置OPENAI_API_KEY环境变量")
        print("系统将使用模拟响应模式")
        print("请设置环境变量 OPENAI_API_KEY 以启用完整的LLM功能")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("✅ LLM配置已加载")
        print(f"模型类型: {llm_config.get('model_type')}")
        print(f"模型名称: {llm_config.get('model_name')}")
        print("=" * 60 + "\n")

    print("\n" + "=" * 60)
    print("Star-Commander 使用示例")
    print("主控Agent功能测试")
    print("=" * 60 + "\n")

    await example_basic_process()
    await example_intent_identification()
    await example_task_routing()
    await example_multiple_intents()
    await example_with_llm_config()
    await example_context_handling()

    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())