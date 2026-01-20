import os
from pathlib import Path
from dotenv import load_dotenv
from openjiuwen.core.runner.runner import Runner
# 复用你提供的 example_multimodal_beautify.py 中的创建逻辑
from image_editor.example_multimodal_beautify import create_multimodal_beautify_agent, encode_image_to_base64

load_dotenv()


class ImageEditingService:
    def __init__(self):
        self.agent = None

    async def initialize(self):
        if not self.agent:
            # 确保 API KEY 从环境变量读取，而不是硬编码
            if not os.getenv("SILICONFLOW_API_KEY"):
                # 兼容代码中的硬编码key，但建议用户改用环境变量
                os.environ["SILICONFLOW_API_KEY"] = "sk-iimeqzridkmqtnoggoinouysymkkgwttphygwapjjtxcaitp"

            self.agent = await create_multimodal_beautify_agent()

    async def process_image(self, image_path: str, user_instruction: str, output_path: str):
        await self.initialize()

        image_base64 = encode_image_to_base64(image_path)

        # 构造更智能的 Prompt，引导模型进行“风格迁移”或“模糊指令理解”
        multimodal_content = [
            {
                "type": "text",
                "text": (
                    f"用户需求: {user_instruction}\n\n"
                    f"任务:\n"
                    f"1. 分析图片当前存在的问题或特点。\n"
                    f"2. 将用户的自然语言需求转化为具体的图像处理参数。\n"
                    f"3. 调用工具处理图片，必须保存到: {output_path}\n"
                    f"4. 最后简要解释你做了哪些调整。"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": image_base64}
            }
        ]

        inputs = {
            "conversation_id": f"edit_{Path(image_path).stem}",
            "query": multimodal_content
        }

        try:
            result = await Runner.run_agent(self.agent, inputs)
            return {
                "success": True,
                "response": result.get('output', ''),
                "output_path": output_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# 单例模式
service = ImageEditingService()