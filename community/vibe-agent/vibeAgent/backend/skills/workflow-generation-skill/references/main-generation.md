# Main Generation Reference

## 生成规则

main.py 文件用于执行和测试工作流。

**必须包含的内容**：
1. 环境变量设置：`os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = "300"`（必须在文件开头）
2. 创建模型Client：`llm_client = create_llm_client()`（用于人机交互处理）
3. `run_test()` 函数：运行单个测试用例，必须包含人机交互处理逻辑
4. `main()` 函数：主函数，运行所有测试用例
5. `if __name__ == "__main__":` 块：执行入口

## 必需的导入

```python
import asyncio
import os
import sys
import io
from typing import List

# 设置标准输出编码为 UTF-8（避免 Windows 控制台 GBK 编码错误）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from config import create_llm_client  # 必须导入，用于人机交互处理
from workflow_builder import build_workflow_agent
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
from openjiuwen.core.stream.base import OutputSchema
```

**说明**：
- 编码设置必须在文件开头执行，避免 Windows 控制台 GBK 编码错误（当输出包含 emoji 或特殊字符时）

## 环境变量设置

**重要**：必须在文件开头设置工作流执行超时时间：

```python
# 设置工作流执行超时时间（300秒 = 5分钟）
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = "300"
```

**说明**：
- 必须在导入语句之后，在调用任何工作流相关函数之前设置
- 确保工作流执行时有足够的超时时间

## 创建模型Client实例
```python
llm_client = create_llm_client()
```

## run_test() 函数

**重要**：`run_test()` 函数必须包含人机交互处理逻辑。当工作流中有提问器组件时，可能触发中断，进入人机交互过程。

```python
async def run_test(query: str, conversation_id: str = "test_123"):
    """运行单个测试用例"""
    # 构建 Agent（runtime 会由 Agent 内部自动创建）
    workflow_agent = build_workflow_agent()
    
    # 调用 invoke
    response = await workflow_agent.invoke({"query": query, "conversation_id": conversation_id})

    # 处理人机交互流程（必须严格遵守，不能有任何修改，不能有任何遗漏）
    while isinstance(response, List):
        interactive_input = InteractiveInput()
        for item in response:
            if isinstance(item, OutputSchema) and item.type == '__interaction__':
                component_id = item.payload.id
                question = item.payload.value
                # 针对提问器组件的问题进行反馈（使用 llm_client 模拟用户回复）
                reply_value = await llm_client.ainvoke(
                    model_name="qwen3-max",
                    messages=[{"role": "user", "content": f"""##人设：你是工作流用户，正在试运行工作流，需要回答工作流执行过程中的人机交互问题。 ## 要求：1.直接代替用户做所有决策 2. 直接回答问题，禁止输出任何其他内容 3. 回答简洁明了 4. 禁止回复"无"、"不知道"、"不确定"等模糊不清的词语 \n系统问题是：{question}"""}]
                )
                interactive_input.update(component_id, reply_value.content)
        response = await workflow_agent.invoke({"conversation_id": conversation_id, "query": interactive_input})

    print(f"执行结果: {response}")
    return response
```

**重要规则**（必须严格遵守）：
1. **调用方式**：使用 `workflow_agent.invoke(inputs)`，**不需要**传入 runtime 参数
2. **参数格式**：inputs 必须是字典，包含 `query` 和 `conversation_id` 字段
3. **人机交互处理**（必须严格遵守，不能有任何修改，不能有任何遗漏）：
   - 当工作流输出结果为列表时，说明进入人机交互过程
   - 遍历列表，如果元素为 `OutputSchema` 类型且 `type` 为 `__interaction__`，则调用 `InteractiveInput.update()` 方法更新输入
   - 使用 `llm_client.ainvoke()` 模拟用户回复，**不要使用 `input()` 函数获取用户输入**
   - 重新调用 `workflow_agent.invoke()` 执行工作流
   - 循环处理人机交互流程，直到工作流输出结果不为列表为止
4. **错误处理**：包含完善的错误处理和调试信息

## main() 函数

```python
async def main():
    """主函数，运行所有测试用例"""
    print("开始运行工作流测试...")
    
    # 测试用例1
    print("\n=== 测试用例1 ===")
    await run_test("测试查询1", "test_001")
    
    # 测试用例2
    print("\n=== 测试用例2 ===")
    await run_test("测试查询2", "test_002")
    
    print("\n所有测试用例执行完成")
```

**规则**：
- 提供 1-2 个关键测试场景
- 每个测试用例调用 run_test() 时，必须提供 conversation_id 参数
- 测试用例应该覆盖主要功能

## if __name__ == "__main__" 块

```python
if __name__ == "__main__":
    asyncio.run(main())
```

## 最佳实践

1. **提供多个测试用例**：覆盖不同的使用场景
2. **使用清晰的测试用例名称**：便于理解测试目的
3. **包含错误处理**：捕获和打印异常信息
4. **添加调试信息**：打印执行状态和结果

