# Multi-Agent Main 生成规则

## 概述
生成 `main.py` 文件，包含 HierarchicalGroup 的主执行逻辑。

## 关键要求

### 1. 导入必要的模块

```python
import asyncio
import os
import time
import setup_path  # 必须在导入 openjiuwen 之前
from typing import Any, Optional
from openjiuwen.agent_group.hierarchical_group import HierarchicalGroup
from openjiuwen.core.agent.message.message import Message
from openjiuwen.core.runner.runner import Runner
from config import create_group_config
from leader_agent import create_leader_agent
from worker_agents import create_worker_agents
```

### 2. 创建全局 Group 实例变量（用于支持多轮交互）

```python
_group_instance: Optional[HierarchicalGroup] = None
```

### 3. 创建 `init_group()` 异步函数

```python
async def init_group() -> HierarchicalGroup:
    """初始化并返回 HierarchicalGroup 实例"""
    global _group_instance
    if _group_instance is None:
        # 启动 Runner
        await Runner.start()
        
        # 创建 Group 配置和实例
        group_config = create_group_config()
        group = HierarchicalGroup(group_config)
        
        # 创建并添加 Leader Agent
        leader_id, leader_agent = create_leader_agent(
            agent_id=group_config.leader_agent_id,
            agent_version="1.0",
            description="主控制器，识别用户意图并分发任务"
        )
        group.add_agent(leader_id, leader_agent)
        
        # 创建并添加所有 Worker Agents
        worker_agents = create_worker_agents()
        for worker_id, worker_agent in worker_agents.items():
            group.add_agent(worker_id, worker_agent)
        
        _group_instance = group
    return _group_instance
```

### 4. 创建 `extract_response()` 函数（从结果中提取响应内容）

```python
def extract_response(result: Any) -> str:
    """从结果中提取响应内容"""
    if isinstance(result, dict):
        output = result.get("output", "")
        if output:
            # 如果是 WorkflowOutput 对象，提取 result 属性
            if hasattr(output, 'result'):
                workflow_result = output.result
                if isinstance(workflow_result, dict):
                    return workflow_result.get('responseContent') or workflow_result.get('content') or str(workflow_result)
                else:
                    return str(workflow_result)
            # 如果 output 是字符串，直接返回
            elif isinstance(output, str):
                return output
            # 其他类型，转换为字符串
            else:
                return str(output)
        else:
            # 如果没有 output 字段，尝试提取其他可能的字段
            return result.get('content') or result.get('message') or str(result)
    else:
        # 非字典类型，直接转换为字符串
        return str(result)
```

### 5. 创建 `run_test()` 异步函数（API 调用方式）

```python
async def run_test(query: str, conversation_id: str = None) -> Any:
    """API 调用方式：执行一次查询（支持多轮对话）"""
    group = await init_group()
    conv_id = conversation_id or f"conv_{int(time.time())}"
    message = Message.create_user_message(
        content=query,
        conversation_id=conv_id
    )
    result = await group.invoke(message)
    return result
```

### 6. 创建 `interactive_main()` 异步函数（命令行交互方式）

```python
async def interactive_main():
    """命令行交互式主函数"""
    try:
        group = await init_group()
        conversation_id = f"interactive_{int(time.time())}"
        
        print("=== Multi-Agent 交互模式 ===")
        print("输入 'exit', 'quit' 或 'bye' 退出")
        print(f"会话ID: {conversation_id}\n")
        
        while True:
            try:
                user_input = input("您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("再见！")
                    break
                
                # 创建消息并调用
                message = Message.create_user_message(
                    content=user_input,
                    conversation_id=conversation_id
                )
                
                result = await group.invoke(message)
                
                # 提取并显示响应
                response = extract_response(result)
                print(f"Agent: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n中断退出")
                break
            except Exception as e:
                print(f"错误: {e}\n")
                
    finally:
        await Runner.stop()
```

### 7. 在 `if __name__ == "__main__":` 块中

**重要**：必须支持测试模式和交互模式两种方式。

```python
if __name__ == "__main__":
    import sys
    
    # 检查是否是测试模式（通过命令行参数或环境变量）
    is_test_mode = len(sys.argv) > 1 and sys.argv[1] == "--test"
    test_query = sys.argv[2] if is_test_mode and len(sys.argv) > 2 else None
    
    # 如果测试模式但没有提供查询，使用默认查询（避免进入交互模式）
    if is_test_mode and not test_query:
        test_query = "测试查询"
    
    if is_test_mode and test_query:
        # 测试模式：执行一次测试并退出
        async def test_main():
            try:
                result = await run_test(test_query, conversation_id="test_conv")
                response = extract_response(result)
                print(response)
                return 0
            except Exception as e:
                print(f"测试失败: {e}", file=sys.stderr)
                return 1
            finally:
                await Runner.stop()
        
        exit_code = asyncio.run(test_main())
        sys.exit(exit_code)
    else:
        # 交互模式：进入交互式循环
        asyncio.run(interactive_main())
```

## 关键注意事项

- 两种方式都使用相同的 `conversation_id` 机制保持对话状态
- 调用 `group.invoke()` 时，必须使用 `Message` 对象
- 支持多轮交互，`conversation_id` 保持不变
- 使用全局变量 `_group_instance` 缓存实例，避免重复初始化
- 在 `interactive_main()` 的 `finally` 块中停止 `Runner`
