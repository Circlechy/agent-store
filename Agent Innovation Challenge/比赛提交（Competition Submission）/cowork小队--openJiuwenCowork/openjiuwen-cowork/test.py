import os
import asyncio
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.messages import SystemMessage, HumanMessage

os.environ["LLM_SSL_VERIFY"] = "false"

async def astream():
    try:
        # 获取ModelFactory实例
        factory = ModelFactory()

        # 获取模型
        model = factory.get_model(
            model_provider="OpenAI",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="sk-"
        )

        # 准备模型输入数据，定义system提示词和用户输入，咨询与天气无关问题，预期不调用工具，直接回答用户问题
        messages = [
            SystemMessage(content="你是一个AI助手").model_dump(exclude_none=True),
            HumanMessage(content="你好").model_dump(exclude_none=True)
        ]

        # 天气工具schema定义
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City and country e.g. Paris, France"
                        },
                        "units": {
                            "type": "string",
                            "enum": ["metric", "imperial"],
                            "description": "Temperature unit"
                        }
                    },
                    "required": ["location"]
                }
            }
        }]

        # 使用async for遍历异步迭代器
        async for chunk in model.astream(model_name="qwen2.5-72b-instruct", messages=messages, tools=tools, temperature=0.7, top_p=0.95):
            print(chunk)

    except Exception as e:
        print(f"Error in async test: {str(e)}")
        raise
    finally:
        if model:
            await model.close()

# 定义一个异步函数main
async def main():
    # 调用异步函数test_async_astream()，并使用await等待其执行完成
    await astream()

if __name__ == "__main__":
    asyncio.run(main())
