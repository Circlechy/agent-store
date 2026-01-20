"""NovaStar工作流使用示例.

演示如何使用基于openjiuwen框架构建的完整NovaStar工作流。
"""

import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novastar.workflow import NovaStarWorkflow, create_novastar_workflow
from novastar.utils.config import get_config


async def example_basic_workflow():
    """基础工作流使用示例."""
    print("=" * 60)
    print("示例1: 基础工作流使用")
    print("=" * 60)

    # 创建工作流（无LLM配置，使用模拟响应）
    workflow = create_novastar_workflow()

    # 运行查询
    query = "为什么天空是蓝色的？"
    user_id = "child_001"

    print(f"查询：{query}")
    print(f"用户：{user_id}")
    print("-" * 40)

    async for chunk in workflow.run(
        query=query,
        user_id=user_id,
        context={"age": 6},
    ):
        if "response" in chunk and chunk["response"]:
            print(f"响应：{chunk['response']}")
            break


async def example_process_message():
    """使用process_message方法（非流式）."""
    print("\n" + "=" * 60)
    print("示例2: 非流式处理（process_message）")
    print("=" * 60)

    workflow = create_novastar_workflow()

    result = await workflow.process_message(
        query="给我讲个恐龙的故事",
        user_id="child_002",
        context={"age": 5},
    )

    print(f"查询：{result['query']}")
    print(f"意图：{result.get('intent', 'N/A')}")
    print(f"处理者：{result.get('handled_by', 'N/A')}")
    response = result.get("response", "")
    print(f"响应：{response[:200]}..." if len(response) > 200 else f"响应：{response}")


async def example_multiple_intents():
    """多种意图处理示例."""
    print("\n" + "=" * 60)
    print("示例3: 多种意图处理")
    print("=" * 60)

    workflow = create_novastar_workflow()

    queries = [
        ("为什么月亮会变圆变扁？", "learning"),
        ("给我讲一个冒险故事", "story"),
        ("我们来玩个游戏吧", "game"),
        ("我今天有点难过", "emotion"),
        ("帮我画一只小猫", "creative"),
    ]

    for query, expected_intent in queries:
        result = await workflow.process_message(
            query=query,
            user_id="child_003",
            context={"age": 7},
        )
        print(f"\n查询：{query}")
        print(f"预期意图：{expected_intent}")
        print(f"实际意图：{result.get('intent', 'N/A')}")
        print(f"处理者：{result.get('handled_by', 'N/A')}")


async def example_with_llm_config():
    """配置LLM的工作流示例."""
    print("\n" + "=" * 60)
    print("示例4: 配置LLM的工作流")
    print("=" * 60)

    config = get_config()
    api_key = config.get_env("openai_api_key")

    if not api_key:
        print("未设置OPENAI_API_KEY环境变量，跳过此示例")
        print("设置方法：export OPENAI_API_KEY=your-api-key")
        return

    llm_config = {
        "model_type": "openai",
        "model_name": "gpt-4o-mini",
        "api_key": api_key,
    }

    workflow = create_novastar_workflow(llm_config=llm_config)

    result = await workflow.process_message(
        query="什么是光合作用？用简单的话解释给我听",
        user_id="child_004",
        context={"age": 8},
    )

    print(f"查询：什么是光合作用？")
    print(f"响应：\n{result.get('response', 'N/A')}")


async def example_streaming_output():
    """流式输出示例."""
    print("\n" + "=" * 60)
    print("示例5: 流式输出")
    print("=" * 60)

    workflow = create_novastar_workflow()

    print("流式输出内容：")
    print("-" * 40)

    async for chunk in workflow.run(
        query="讲一个简短的睡前故事",
        user_id="child_005",
        context={"age": 5},
    ):
        # 输出每个chunk的内容
        if "content" in chunk and chunk["content"]:
            print(f"[内容] {chunk['content'][:50]}...")
        if "response" in chunk and chunk["response"]:
            print(f"[响应] {chunk['response'][:100]}...")
        if "agent" in chunk:
            print(f"[Agent] {chunk['agent']}")


async def example_custom_workflow():
    """自定义工作流配置示例."""
    print("\n" + "=" * 60)
    print("示例6: 自定义工作流配置")
    print("=" * 60)

    # 自定义Agent配置
    agent_config = {}

    workflow = NovaStarWorkflow(
        workflow_name="custom_workflow",
        version="2.0",
        agent_config=agent_config,
    )
    workflow.initialize()

    result = await workflow.process_message(
        query="为什么小狗会摇尾巴？",
        user_id="child_006",
        context={"age": 6, "interests": ["动物"]},
    )

    print(f"工作流名称：custom_workflow v2.0")
    print(f"查询：为什么小狗会摇尾巴？")
    print(f"处理者：{result.get('handled_by', 'N/A')}")


async def main():
    """运行所有示例."""
    print("\n" + "=" * 60)
    print("NovaStar 工作流使用示例")
    print("基于openjiuwen框架构建")
    print("=" * 60 + "\n")

    await example_basic_workflow()
    await example_process_message()
    await example_multiple_intents()
    await example_with_llm_config()
    await example_streaming_output()
    await example_custom_workflow()

    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
