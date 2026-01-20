"""Star-Mentor 使用示例.

演示如何使用NovaStar的智教Agent进行汉字学习与问答。
支持两种使用方式：
1. 简化API（novastar.agents.StarMentor）
2. 底层节点（novastar.nodes.MentorNode）
"""

import asyncio
import os
import sys
import io

# 设置输出编码为UTF-8（Windows系统需要）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novastar.agents import StarMentor
from novastar.nodes import MentorNode
from novastar.utils.config import get_config


def get_llm_config_from_env() -> dict:
    """从环境变量和配置文件获取LLM配置."""
    config = get_config()
    api_key = config.get_env("openai_api_key")
    api_base = config.get_env("openai_api_base")
    model_type = config.get_env("llm_model_type") or "openai"
    model_name = config.get_env("llm_model_name") or "qwen-plus"
    
    if not api_key:
        return None
    
    return {
        "model_type": model_type,
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "timeout": 60,
    }


def create_mentor_with_llm():
    """创建带LLM配置的StarMentor实例."""
    llm_config = get_llm_config_from_env()
    if llm_config:
        return StarMentor(name="Star-Mentor", llm_config=llm_config)
    else:
        return StarMentor(name="Star-Mentor")


def print_images(result: dict) -> None:
    """打印配图信息."""
    images = result.get("images") or []
    if not images:
        return
    print("配图：")
    for idx, (image_url, doc) in enumerate(images, 1):
        print(f"- {idx}. {doc} -> {image_url}")


async def example_basic_question():
    """基础语言学习示例（使用简化API）."""
    print("=" * 60)
    print("示例1: 基础问题处理（简化API）")
    print("=" * 60)

    mentor = create_mentor_with_llm()

    result = await mentor.process(
        user_id="child_001",
        message="教我学英文单词 cat",
        context={"age": 6},
    )

    print("问题：教我学英文单词 cat")
    print(f"回答：\n{result['response']}\n")
    print(f"课程类型：{result.get('lesson_type')}")
    print_images(result)


async def example_character_learning():
    """汉字立体学习示例."""
    print("\n" + "=" * 60)
    print("示例2: 汉字立体学习")
    print("=" * 60)

    mentor = create_mentor_with_llm()

    result = await mentor.teach_character(
        user_id="child_001",
        character="山",
        context={"age": 6},
    )

    print(f"汉字学习：{result['character']}")
    print(f"教学内容：\n{result['teaching_content']}\n")
    print(f"学习维度：{', '.join(result['dimensions'])}")
    print_images(result)


async def example_using_node_directly():
    """直接使用底层节点示例（更多控制）."""
    print("\n" + "=" * 60)
    print("示例4: 直接使用底层MentorNode")
    print("=" * 60)

    # 创建节点
    mentor_node = MentorNode(config={})

    # 模拟输入
    inputs = {
        "query": "学习汉字“水”",
        "user_id": "child_002",
        "context": {"age": 7},
    }

    # 调用节点
    result = await mentor_node._do_invoke(inputs, None, None)

    print(f"问题：{inputs['query']}")
    print(f"课程类型：{result.get('lesson_type', 'unknown')}")
    print(f"回答：\n{result.get('response', '')[:200]}")
    print_images(result)


async def example_with_llm_config():
    """配置LLM的示例."""
    print("\n" + "=" * 60)
    print("示例4: 配置LLM（需要API Key）")
    print("=" * 60)

    # 从环境变量和配置文件获取LLM配置
    llm_config = get_llm_config_from_env()

    if not llm_config:
        print("未设置OPENAI_API_KEY，跳过此示例")
        print("请在 .env 文件中设置 OPENAI_API_KEY 和 OPENAI_API_BASE")
        return

    mentor = StarMentor(
        name="Star-Mentor",
        llm_config=llm_config,
    )

    result = await mentor.process(
        user_id="child_003",
        message="什么是光合作用？",
        context={"age": 9},
    )

    print(f"问题：什么是光合作用？")
    print(f"回答：\n{result['response']}")
    print_images(result)


async def main():
    """运行所有示例."""
    print("\n" + "=" * 60)
    print("Star-Mentor 使用示例")
    print("基于openjiuwen框架构建")
    print("=" * 60 + "\n")

    await example_basic_question()
    await example_character_learning()
    await example_using_node_directly()
    await example_with_llm_config()

    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
