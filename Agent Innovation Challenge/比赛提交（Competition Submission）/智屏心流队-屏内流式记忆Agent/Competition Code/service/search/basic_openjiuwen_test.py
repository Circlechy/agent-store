import asyncio
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.runtime.workflow import WorkflowRuntime
from openjiuwen.core.workflow.base import Workflow

# 演示Start组件的基本用法和工作流创建流程
async def demo_start_component():
    # 1. 创建工作流实例
    workflow = Workflow()
    
    # 2. 配置Start组件的输入参数
    start_config = {
        "inputs": [
            {"id": "query", "required": True},
            {"id": "dialogueHistory", "default_value": ["c", "d"], "required": False},
            {"id": "conversationHistory", "default_value": ["a", "b"], "required": False},
        ]
    }
    
    # 3. 创建并设置开始组件
    start_comp = Start(start_config)
    workflow.set_start_comp("start", start_comp,
                           inputs_schema={
                               "query": "${user_inputs.query}", 
                               "dialogueHistory": "${user_inputs.dialogueHistory}", 
                               "conversationHistory": "${user_inputs.conversationHistory}"
                           })
    
    # 4. 设置结束组件捕获输出
    workflow.set_end_comp("end", Start(),
                         inputs_schema={
                             "query": "${start.query}", 
                             "dialogueHistory": "${start.dialogueHistory}", 
                             "conversationHistory": "${start.conversationHistory}"
                         })
    
    # 5. 添加组件间连接
    workflow.add_connection("start", "end")
    
    # 6. 执行工作流
    result = await workflow.invoke(
        inputs={"user_inputs": {
            "query": "hello world",
            "conversationHistory": ["a", "b"]
        }},
        runtime=WorkflowRuntime()
    )

    print(f"{result}")

def main():
    asyncio.run(demo_start_component())

if __name__ == "__main__":
    main()