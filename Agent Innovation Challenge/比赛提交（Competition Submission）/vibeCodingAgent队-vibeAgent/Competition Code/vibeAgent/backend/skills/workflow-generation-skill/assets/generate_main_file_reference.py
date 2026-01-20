# ========== 参考main.py代码 ==========
# 请严格按照以下示例代码的结构和模式生成测试代码
import asyncio
import os
from typing import List
from config import create_llm_client
from workflow_builder import build_workflow_agent
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
from openjiuwen.core.stream.base import OutputSchema

os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = "300"

llm_client = create_llm_client()

# 1. 测试函数示例
async def run_test(query, conversation_id: str = "test_123"):
    """运行单个测试用例"""    
    # 构建 Agent（runtime 会由 Agent 内部自动创建）
    workflow_agent = build_workflow_agent()
    
    # 调用 invoke
    response = await workflow_agent.invoke({"query": query, "conversation_id": conversation_id})

    # 处理人机交互流程
    while isinstance(response, List):
        interactive_input = InteractiveInput()
        for item in response:
            if isinstance(item, OutputSchema) and item.type == '__interaction__':
                component_id = item.payload.id
                question = item.payload.value
                # 针对提问器组件的问题进行反馈
                reply_value = await llm_client.ainvoke(
                    model_name="qwen3-max",
                    messages=[{"role": "user", "content": f"""##人设：你是工作流用户，正在试运行工作流，需要回答工作流执行过程中的人机交互问题。 ## 要求：1.直接代替用户做所有决策 2. 直接回答问题，禁止输出任何其他内容 3. 回答简洁明了 4. 禁止回复“无”、“不知道”、“不确定”等模糊不清的词语 \n系统问题是：{question}"""}]
                )
                interactive_input.update(component_id, reply_value.content)
        response = await workflow_agent.invoke({"conversation_id": conversation_id, "query": interactive_input})

    print(f"执行结果: {response}")
    return response

# 2. 主函数示例
async def main():
    """主函数，运行所有测试用例"""
    await run_test(query="测试查询", conversation_id="test_123")

# 3. 执行入口
if __name__ == "__main__":
    asyncio.run(main())
