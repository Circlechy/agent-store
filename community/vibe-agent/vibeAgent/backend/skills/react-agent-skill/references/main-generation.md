# ReAct Agent Main 生成规则

## 概述
生成 `main.py` 文件，包含 ReActAgent 的主执行逻辑。

## 重要说明

**这是 Agent 模式（ReActAgent），不是 Workflow 模式**

**严格禁止使用 Workflow 相关的内容：**
- ❌ 禁止导入 `workflow_builder`
- ❌ 禁止使用 `build_workflow_agent()`
- ❌ 禁止使用 `WorkflowAgent`
- ❌ 禁止使用任何 Workflow 相关的函数或类

**必须使用的内容（Agent 模式）：**
- ✅ 必须导入 `from local_agent import create_agent`
- ✅ 必须使用 `agent = create_agent()` 创建 Agent
- ✅ 必须使用 `agent.invoke()` 调用 Agent
- ✅ 必须包含 `run_test()` 函数（供测试代码调用）

## 代码结构

### 1. 导入模块（严格按照以下顺序和内容）

```python
import asyncio
import os
import sys
from pathlib import Path

import setup_path  # 必须在导入 openjiuwen 之前

# 重要：在 setup_path 之后，确保优先导入本地的模块文件，而不是 openjiuwen 包中的同名模块
# 将当前文件所在目录添加到 sys.path 的最前面
current_dir = Path(__file__).parent.resolve()
current_dir_str = str(current_dir)
if current_dir_str in sys.path:
    sys.path.remove(current_dir_str)
sys.path.insert(0, current_dir_str)

from local_agent import create_agent  # 从 local_agent.py 导入 create_agent 函数
```

### 2. 创建 `run_test()` 异步函数（必须包含）

该函数供测试代码调用：

```python
async def run_test(query: str, conversation_id: str = "test_123"):
    """
    运行单个测试用例
    
    Args:
        query: 用户输入的查询内容
        conversation_id: 对话ID，用于标识会话
        
    Returns:
        执行结果字典
    """
    try:
        print(f"开始执行测试用例: {query}")
        print(f"对话ID: {conversation_id}")
        
        # 创建 Agent
        agent = create_agent()
        
        # 调用 invoke
        inputs = {
            "query": query,
            "conversation_id": conversation_id
        }
        result = await agent.invoke(inputs)
        
        print(f"执行结果: {result}")
        print("=" * 50)
        return result
        
    except Exception as e:
        print(f"执行测试用例时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
```

### 3. 创建 `main()` 异步函数

```python
async def main():
    """
    主函数，运行所有测试用例
    """
    print("开始运行 {agent_name} 测试...")
    print("=" * 50)
    
    # 测试用例1：基本测试
    await run_test("与用户需求相关的测试查询1", "test_001")
    
    # 测试用例2：扩展测试
    await run_test("与用户需求相关的测试查询2", "test_002")
    
    print("所有测试用例执行完成")
```

**重要**：测试查询应该与用户需求相关。

### 4. 添加 `if __name__ == "__main__":` 块

```python
if __name__ == "__main__":
    asyncio.run(main())
```

## 关键注意事项

- 这是 ReActAgent 模式，不是 WorkflowAgent 模式
- 必须使用 `create_agent()` 函数（在 `local_agent.py` 中定义）
- 必须使用 `agent.invoke({"query": "...", "conversation_id": "..."})` 调用 Agent
- **必须包含 `run_test()` 函数**，该函数接受 `query` 和 `conversation_id` 参数，供测试代码调用
- 测试查询应该与用户需求相关

## 完整示例

```python
"""
ReAct Agent 主程序
"""
import asyncio
import os
import sys
from pathlib import Path

import setup_path  # 必须在导入 openjiuwen 之前

# 重要：在 setup_path 之后，确保优先导入本地的模块文件
current_dir = Path(__file__).parent.resolve()
current_dir_str = str(current_dir)
if current_dir_str in sys.path:
    sys.path.remove(current_dir_str)
sys.path.insert(0, current_dir_str)

from local_agent import create_agent

async def run_test(query: str, conversation_id: str = "test_123"):
    """
    运行单个测试用例
    
    Args:
        query: 用户输入的查询内容
        conversation_id: 对话ID，用于标识会话
        
    Returns:
        执行结果字典
    """
    try:
        print(f"开始执行测试用例: {query}")
        print(f"对话ID: {conversation_id}")
        
        # 创建 Agent
        agent = create_agent()
        
        # 调用 invoke
        inputs = {
            "query": query,
            "conversation_id": conversation_id
        }
        result = await agent.invoke(inputs)
        
        print(f"执行结果: {result}")
        print("=" * 50)
        return result
        
    except Exception as e:
        print(f"执行测试用例时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """主函数，运行所有测试用例"""
    print("开始运行情绪咨询助手测试...")
    print("=" * 50)
    
    # 测试用例1：基本测试
    await run_test("我今天心情很糟糕", "test_001")
    
    # 测试用例2：扩展测试
    await run_test("如何缓解焦虑情绪？", "test_002")
    
    print("所有测试用例执行完成")

if __name__ == "__main__":
    asyncio.run(main())
```
