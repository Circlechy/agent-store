"""Star-Companion 使用示例."""

import asyncio
import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novastar.agents import StarCompanion
from novastar.nodes import CompanionNode


async def example_basic_chat():
    print("=" * 60)
    print("示例1: 陪伴闲聊")
    print("=" * 60)

    companion = StarCompanion(name="Star-Companion")
    result = await companion.process(
        user_id="child_001",
        message="我今天有点无聊。",
        context={"age": 6},
    )
    print(f"回复：{result.get('response', '')}")


async def example_using_node_directly():
    print("\n" + "=" * 60)
    print("示例2: 直接使用底层CompanionNode")
    print("=" * 60)

    node = CompanionNode(config={})
    inputs = {
        "query": "你喜欢什么颜色？",
        "user_id": "child_002",
        "context": {"age": 7},
    }
    result = await node._do_invoke(inputs, None, None)
    print(f"回复：{result.get('response', '')}")


async def main():
    await example_basic_chat()
    await example_using_node_directly()


if __name__ == "__main__":
    asyncio.run(main())
