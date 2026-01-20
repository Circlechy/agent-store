import base64
import json
import logging

from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.utils.config import deepsearch_config
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream

logger = logging.getLogger(__name__)


class ImageIntentRecognition:
    def __init__(self):
        pass

    def _encode_image(self, image_path: str) -> str:
        """将图片文件编码为base64字符串"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"[ImageIntentRecognition] _encode_image error: {e}")
            return ""

    async def recognize(self, algorithm_input: dict) -> dict:
        """
        识别图像中的购物意图
        
        Args:
            algorithm_input: 包含图像路径或base64数据的字典
                - image_path: 图片本地路径 (可选)
                - base64_image: 图片base64数据 (可选)
                - query: 用户输入的补充查询文本 (可选)
                
        Returns:
            dict: 包含 scene_type, query_intent, generated_query 等信息的字典
        """
        try:
            # 1. 获取系统提示词
            llm_input = apply_system_prompt("image_intent_recognition", algorithm_input)

            # 2. 获取图片数据
            image_path = algorithm_input.get("image_path")
            base64_image = algorithm_input.get("base64_image")

            # 如果没有base64但有路径，则读取文件
            if not base64_image and image_path:
                base64_image = self._encode_image(image_path)

            if not base64_image:
                logger.error("[ImageIntentRecognition] recognize failed: No image data provided")
                return {}

            # 3. 构造多模态用户消息
            # 适配 OpenAI 兼容的多模态格式
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    },
                }
            ]

            llm_input.append({
                "role": "user",
                "content": user_content
            })

            # 4. 调用大模型 (使用支持视觉的模型)
            vision_model = deepsearch_config.get("model.vision_model_name", "qwen3-vl-flash")

            llm_output = await llm_astream(
                llm_input,
                need_stream_out=True,
                agent_name="image_intent_recognition",
                specific_model=vision_model
            )

            logger.info(f'[ImageIntentRecognition] recognize, llm_output: {llm_output}')

            content = llm_output.get("content", "{}")

            # 尝试解析 JSON
            try:
                # llm_astream 已经做了正则替换 ```json ... ```
                res = json.loads(content)
                return res
            except json.JSONDecodeError as e:
                logger.error(f"[ImageIntentRecognition] JSON decode error: {e}, content: {content}")
                # 兜底处理，尝试提取可能存在的 generated_query
                return {"generated_query": content}

        except Exception as e:
            logger.error(f'[ImageIntentRecognition] recognize error: {e}')
            return {}
