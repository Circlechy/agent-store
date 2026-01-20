"""基于openjiuwen的LLM调用封装模块.

提供统一的LLM调用接口，集成openjiuwen框架的LLM能力。
"""

import base64
import logging
import os
from typing import Any, Dict, List, Optional, Type

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from openjiuwen.core.utils.llm.base import BaseModelClient
from openjiuwen.core.utils.llm.model_library.openai import OpenAILLM
from openjiuwen.core.utils.llm.model_library.siliconflow import Siliconflow
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage, AIMessage
from novastar.utils.config import get_config

logger = logging.getLogger(__name__)


class NovaStarModelFactory(ModelFactory):
    """NovaStar模型工厂，扩展openjiuwen的ModelFactory."""

    def _initialize_models(self):
        """注册所有可用的模型类型."""
        self.model_map: Dict[str, Type[BaseModelClient]] = {
            "openai": OpenAILLM,
            "siliconflow": Siliconflow,
        }


class LLMWrapper:
    """LLM封装类，提供统一的LLM调用接口."""

    _registry: Dict[str, Any] = {}
    _default_model_name: Optional[str] = None

    def __init__(
        self,
        model_type: str = "openai",
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
        image_model_name: Optional[str] = None,
        tts_model_name: Optional[str] = None,
        asr_model_name: Optional[str] = None,
        **kwargs: Any,
    ):
        """初始化LLM封装.

        Args:
            model_type: 模型类型 (openai, siliconflow等)
            model_name: 文本模型名称
            api_key: API密钥
            api_base: API基础URL
            timeout: 超时时间(秒)
            image_model_name: 图像生成模型名称（默认从环境变量 IMAGE_MODEL_NAME 读取）
            tts_model_name: 语音合成模型名称（默认从环境变量 TTS_MODEL_NAME 读取）
            asr_model_name: 语音识别模型名称（默认从环境变量 ASR_MODEL_NAME 读取）
            **kwargs: 其他参数
        """
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout
        self.kwargs = kwargs

        # 统一从环境变量读取多模态模型名称（如果未传入）
        config = get_config()
        self.image_model_name = image_model_name or config.get_env("image_model_name") or "qwen-image-plus"
        self.tts_model_name = tts_model_name or config.get_env("tts_model_name") or "qwen3-tts-flash"
        self.asr_model_name = asr_model_name or config.get_env("asr_model_name") or "qwen3-asr-flash"

        self._model: Optional[BaseModelClient] = None
        self._init_model()

    def _init_model(self) -> None:
        """初始化模型实例."""
        if not self.api_key:
            logger.warning("API key未配置，LLM调用可能失败")
            return

        try:
            # 设置 SSL 相关环境变量（如果未设置）
            # openjiuwen 框架需要这些配置
            if "LLM_SSL_VERIFY" not in os.environ:
                config = get_config()
                os.environ["LLM_SSL_VERIFY"] = config.get_env("llm_ssl_verify") or "false"
            if "LLM_SSL_CERT" not in os.environ:
                config = get_config()
                os.environ["LLM_SSL_CERT"] = config.get_env("llm_ssl_cert") or ""
            
            factory = NovaStarModelFactory()
            self._model = factory.get_model(
                model_provider=self.model_type,
                api_key=self.api_key,
                api_base=self.api_base,
                timeout=self.timeout,
            )
            logger.info(f"成功初始化LLM模型: {self.model_type}/{self.model_name}")
        except Exception as e:
            logger.error(f"初始化LLM模型失败: {e}")
            self._model = None

    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        """与LLM对话.

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            history: 对话历史
            **kwargs: 其他参数

        Returns:
            LLM响应文本
        """
        if self._model is None:
            logger.warning("LLM模型未初始化，返回模拟响应")
            return f"[模拟响应] {message}"

        try:
            # 构建消息列表
            messages = []

            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))

            # 添加历史消息
            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))
                    elif role == "system":
                        messages.append(SystemMessage(content=content))

            # 添加当前消息
            messages.append(HumanMessage(content=message))

            # 调用模型
            response = await self._model.ainvoke(
                self.model_name,
                messages=messages,
                **kwargs,
            )

            # 提取响应内容
            if hasattr(response, "content"):
                return response.content
            elif isinstance(response, str):
                return response
            elif isinstance(response, dict) and "content" in response:
                return response["content"]
            else:
                return str(response)

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"[调用失败] {str(e)}"

    async def stream_chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ):
        """流式对话.

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            history: 对话历史
            **kwargs: 其他参数

        Yields:
            LLM响应文本片段
        """
        if self._model is None:
            yield f"[模拟响应] {message}"
            return

        try:
            # 构建消息列表
            messages = []

            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))

            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))

            messages.append(HumanMessage(content=message))

            # 流式调用模型
            async for chunk in self._model.astream(
                self.model_name,
                messages=messages,
                **kwargs,
            ):
                if hasattr(chunk, "content"):
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk

        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            yield f"[调用失败] {str(e)}"

    @classmethod
    def register(cls, name: str, llm_instance: "LLMWrapper") -> None:
        """注册LLM实例.

        Args:
            name: 实例名称
            llm_instance: LLM实例
        """
        cls._registry[name] = llm_instance
        if cls._default_model_name is None:
            cls._default_model_name = name
        logger.info(f"注册LLM实例: {name}")

    @classmethod
    def get(cls, name: Optional[str] = None) -> Optional["LLMWrapper"]:
        """获取LLM实例.

        Args:
            name: 实例名称，如果为None则返回默认实例

        Returns:
            LLM实例
        """
        if name is None:
            name = cls._default_model_name
        return cls._registry.get(name)

    @classmethod
    def set_default(cls, name: str) -> None:
        """设置默认LLM实例.

        Args:
            name: 实例名称
        """
        if name in cls._registry:
            cls._default_model_name = name
        else:
            logger.warning(f"LLM实例 {name} 未注册")

    async def generate_image(
        self,
        prompt: str,
        style: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        model_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """生成图像.

        Args:
            prompt: 图像生成提示词
            style: 图像风格
            width: 图像宽度
            height: 图像高度
            model_name: 模型名称（默认从环境变量 IMAGE_MODEL_NAME 读取）
            **kwargs: 其他参数

        Returns:
            包含图像 URL 或 base64 数据的字典
        """
        if not self.api_key:
            raise ValueError("API key 未配置")

        # 使用实例属性中的模型名称（如果未传入参数）
        if not model_name:
            model_name = self.image_model_name

        # 图像生成使用独立的 API URL（优先从环境变量 IMAGE_API_BASE 读取，否则使用 OPENAI_API_BASE）
        config = get_config()
        url = config.get_env("image_api_base") or "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 如果指定了风格，添加到提示词中
        final_prompt = prompt
        if style:
            final_prompt = f"{prompt}, style: {style}"

        # DashScope 支持的尺寸格式：width*height
        size_str = f"{width}*{height}"

        # DashScope multimodal-generation API 使用 messages 格式
        data = {
            "model": model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": final_prompt,
                                "image": None
                            }
                        ]
                    }
                ]
            },
            "parameters": {
                "size": size_str,
            },
            **kwargs,
        }

        if not httpx:
            raise RuntimeError("httpx 未安装，无法发送 HTTP 请求")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"API 调用失败 (状态码 {response.status_code}): {error_text}")
                    logger.error(f"请求 URL: {url}")
                    logger.error(f"请求数据: {data}")
                response.raise_for_status()
                result = response.json()

                # DashScope multimodal-generation API 响应格式
                # 格式: output.choices[0].message.content[0].image
                if "output" in result and "choices" in result["output"]:
                    choices = result["output"]["choices"]
                    if len(choices) > 0:
                        message = choices[0].get("message", {})
                        content = message.get("content", [])
                        if len(content) > 0:
                            image_data = content[0]
                            image_url = image_data.get("image")
                            return {
                                "url": image_url,
                                "base64": None,
                                "model": model_name,
                            }
                
                # 兼容其他格式（results 格式）
                if "output" in result and "results" in result["output"]:
                    image_result = result["output"]["results"][0]
                    image_url = image_result.get("url") or image_result.get("image")
                    image_base64 = image_result.get("base64")
                    return {
                        "url": image_url,
                        "base64": image_base64,
                        "model": model_name,
                    }
                
                # 兼容 OpenAI 格式
                if "data" in result and len(result["data"]) > 0:
                    image_url = result["data"][0].get("url")
                    image_base64 = result["data"][0].get("b64_json")
                    return {
                        "url": image_url,
                        "base64": image_base64,
                        "model": model_name,
                    }
                
                raise ValueError(f"API 返回的数据格式不正确: {result}")
        except Exception as e:
            logger.error(f"图像生成失败: {e}")
            raise

    async def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        speed: str = "normal",
        model_name: Optional[str] = None,
        max_length: int = 600,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """文本转语音.

        Args:
            text: 要转换的文本
            voice: 声音名称
            speed: 语速（slow/normal/fast）
            model_name: 模型名称（默认从环境变量 TTS_MODEL_NAME 读取）
            max_length: 最大文本长度（默认 600，DashScope 限制）
            **kwargs: 其他参数

        Returns:
            包含音频 URL 或 base64 数据的字典
        """
        if not self.api_key:
            raise ValueError("API key 未配置")

        # 检查文本长度限制（DashScope TTS API 限制为 600 字符）
        if len(text) > max_length:
            logger.warning(f"文本长度 {len(text)} 超过限制 {max_length}，将截断文本")
            text = text[:max_length]

        # 使用实例属性中的模型名称（如果未传入参数）
        if not model_name:
            model_name = self.tts_model_name

        # 语音合成使用独立的 API URL（优先从环境变量 TTS_API_BASE 读取，否则使用 OPENAI_API_BASE）
        config = get_config()
        url = (
            config.get_env("tts_api_base")
            or self.api_base
            or config.get_env("openai_api_base")
            or "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 检查是否使用 DashScope multimodal-generation API
        is_dashscope_api = "multimodal-generation" in (url or "")
        
        if is_dashscope_api:
            # DashScope TTS API 格式
            # 默认使用 Cherry 语音
            data = {
                "model": model_name,
                "input": {
                    "text": text,
                    "voice": "Cherry",
                    "language_type": kwargs.pop("language_type", "Chinese"),  # 建议与文本语种一致
                },
                "parameters": {
                    "stream": kwargs.pop("stream", False),
                },
                **kwargs,
            }
        else:
            # OpenAI 兼容格式
            valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            if voice not in valid_voices:
                voice = "nova"
            
            data = {
                "model": model_name,
                "input": text,
                "voice": voice,
                "speed": 1.0 if speed == "normal" else (0.75 if speed == "slow" else 1.25),
                **kwargs,
            }

        if not httpx:
            raise RuntimeError("httpx 未安装，无法发送 HTTP 请求")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"API 调用失败 (状态码 {response.status_code}): {error_text}")
                    logger.error(f"请求 URL: {url}")
                    logger.error(f"请求数据: {data}")
                response.raise_for_status()

                if is_dashscope_api:
                    # DashScope TTS API 返回格式
                    result = response.json()
                    
                    # 解析 DashScope 响应格式
                    # 格式: output.choices[0].message.content[0].audio
                    if "output" in result and "choices" in result["output"]:
                        choices = result["output"]["choices"]
                        if len(choices) > 0:
                            message = choices[0].get("message", {})
                            content = message.get("content", [])
                            if len(content) > 0:
                                audio_data_item = content[0]
                                audio_info = audio_data_item.get("audio") or audio_data_item.get("url")
                                # audio_info 可能是字符串 URL 或字典（包含 url 字段）
                                if isinstance(audio_info, dict):
                                    audio_url = audio_info.get("url")
                                elif isinstance(audio_info, str):
                                    audio_url = audio_info
                                else:
                                    audio_url = None
                                
                                audio_base64 = audio_data_item.get("base64")
                                return {
                                    "url": audio_url,
                                    "base64": audio_base64,
                                    "format": "mp3",
                                    "model": model_name,
                                }
                    
                    # 如果没有找到音频数据，尝试直接从 output 获取
                    if "output" in result:
                        output = result["output"]
                        audio_info = output.get("audio") or output.get("url")
                        # audio_info 可能是字符串 URL 或字典
                        if isinstance(audio_info, dict):
                            audio_url = audio_info.get("url")
                        elif isinstance(audio_info, str):
                            audio_url = audio_info
                        else:
                            audio_url = None
                        
                        audio_base64 = output.get("base64")
                        if audio_url or audio_base64:
                            return {
                                "url": audio_url,
                                "base64": audio_base64,
                                "format": "mp3",
                                "model": model_name,
                            }
                    
                    raise ValueError(f"API 返回的数据格式不正确: {result}")
                else:
                    # OpenAI 兼容格式：返回音频二进制数据
                    audio_data = response.content
                    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

                    return {
                        "url": None,
                        "base64": audio_base64,
                        "format": "mp3",
                        "model": model_name,
                    }
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            raise

    async def speech_to_text(
        self,
        audio: str,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """语音转文本.

        Args:
            audio: 音频文件路径、URL 或 base64 编码的音频数据
            model_name: 模型名称（默认从环境变量 ASR_MODEL_NAME 读取，DashScope 默认为 "paraformer-realtime-v2"）
            language: 语言代码（如 "zh", "en" 等，DashScope 默认为 "zh"）
            **kwargs: 其他参数

        Returns:
            包含转录文本的字典，格式: {"text": str, "language": str, "model": str}
        """
        if not self.api_key:
            raise ValueError("API key 未配置")

        # 使用实例属性中的模型名称（如果未传入参数）
        if not model_name:
            model_name = self.asr_model_name

        # 语音转文本使用独立的 API URL（优先从环境变量 ASR_API_BASE 读取，否则使用默认）
        url = (
            os.getenv("ASR_API_BASE")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 检查是否使用 DashScope ASR API（兼容模式）
        is_dashscope_api = "dashscope" in (url or "") and "chat/completions" in (url or "")

        if is_dashscope_api:
            # DashScope ASR API 兼容模式格式 - 使用 JSON（支持 URL / data URL / base64 / 本地路径）
            input_audio_data = None
            if isinstance(audio, str) and (
                audio.startswith("http://") or audio.startswith("https://")
            ):
                input_audio_data = audio
            elif isinstance(audio, str) and audio.startswith("data:"):
                # data URL -> 直接透传（兼容音频 data URI）
                input_audio_data = audio
            elif isinstance(audio, str):
                # 本地文件路径或 base64 文本
                from pathlib import Path
                import mimetypes

                file_path_obj = Path(audio)
                if file_path_obj.exists():
                    import base64

                    mime_type = mimetypes.guess_type(str(file_path_obj))[0] or "audio/mpeg"
                    audio_base64 = base64.b64encode(file_path_obj.read_bytes()).decode()
                    input_audio_data = f"data:{mime_type};base64,{audio_base64}"
                else:
                    # 兜底：当作 base64 音频文本处理
                    audio_base64 = audio.strip()
                    if not audio_base64:
                        raise ValueError("音频数据为空")
                    input_audio_data = f"data:audio/mpeg;base64,{audio_base64}"
            else:
                raise ValueError("无法处理音频输入，请提供音频 URL、本地文件路径或 base64 音频数据")

            # 构建请求体（兼容模式推荐使用 input_audio.data 传入 URL 或 data URI）
            input_audio = {
                "type": "input_audio",
                "input_audio": {
                    "data": input_audio_data,
                },
            }

            messages = [
                {
                    "content": [{"text": ""}],
                    "role": "system",
                },
                {
                    "content": [input_audio],
                    "role": "user",
                },
            ]

            # 构建 ASR 选项
            asr_options = kwargs.pop("asr_options", {})
            if language and "language" not in asr_options:
                asr_options["language"] = language

            data = {
                "model": model_name,
                "messages": messages,
                "stream": kwargs.pop("stream", False),
                **kwargs,
            }
            if asr_options:
                data["extra_body"] = {"asr_options": asr_options}
        else:
            # OpenAI Whisper API 格式
            from io import BytesIO
            from pathlib import Path

            # 读取音频文件
            if isinstance(audio, str) and Path(audio).exists():
                # 如果是文件路径
                with open(audio, "rb") as f:
                    audio_file = f.read()
            elif isinstance(audio, str) and audio.startswith("data:audio"):
                # 如果是 data URL，提取 base64 部分
                import base64

                _, audio_base64 = audio.split(",", 1)
                audio_file = base64.b64decode(audio_base64)
            elif isinstance(audio, str) and len(audio) > 100:
                # 假设是 base64 编码的音频数据
                import base64

                try:
                    audio_file = base64.b64decode(audio)
                except Exception:
                    raise ValueError("无法解码 base64 音频数据")
            else:
                raise ValueError("无法处理音频输入，请提供文件路径或 base64 编码的音频数据")

            files = {
                "file": ("audio.mp3", BytesIO(audio_file), "audio/mpeg")
            }
            data = {
                "model": model_name or "whisper-1",
                "language": language,
                **kwargs,
            }

        if not httpx:
            raise RuntimeError("httpx 未安装，无法发送 HTTP 请求")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if is_dashscope_api:
                    # DashScope API 使用 JSON
                    response = await client.post(url, headers=headers, json=data)
                else:
                    # OpenAI API 使用 multipart/form-data
                    response = await client.post(url, headers=headers, files=files, data=data)

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"API 调用失败 (状态码 {response.status_code}): {error_text}")
                    logger.error(f"请求 URL: {url}")
                    if is_dashscope_api:
                        logger.error(f"请求数据: {data}")
                response.raise_for_status()

                result = response.json()

                if is_dashscope_api:
                    # DashScope ASR API 返回格式（chat/completions）
                    # 格式: choices[0].message.content
                    text = ""
                    if "choices" in result and len(result["choices"]) > 0:
                        choice = result["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            content = choice["message"]["content"]
                            # content 可能是字符串或数组
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, list) and len(content) > 0:
                                # 如果是数组，提取文本内容
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        text = item["text"]
                                        break
                                    elif isinstance(item, str):
                                        text = item
                                        break

                    return {
                        "text": text,
                        "language": asr_options.get("language", language or "zh"),
                        "model": model_name,
                        "raw_response": result,
                    }
                else:
                    # OpenAI Whisper API 返回格式
                    # 格式: {"text": "转录文本", ...}
                    return {
                        "text": result.get("text", ""),
                        "language": result.get("language", language),
                        "model": result.get("model", model_name),
                        "raw_response": result,
                    }
        except Exception as e:
            logger.error(f"语音转文本失败: {e}")
            raise


def create_llm_from_config(config: Dict[str, Any]) -> LLMWrapper:
    """从配置创建LLM实例.

    Args:
        config: 配置字典，包含model_type, model_name, api_key等

    Returns:
        LLM实例
    """
    return LLMWrapper(
        model_type=config.get("model_type", "openai"),
        model_name=config.get("model_name", "gpt-4o-mini"),
        api_key=config.get("api_key"),
        api_base=config.get("api_base"),
        timeout=config.get("timeout", 60),
        image_model_name=config.get("image_model_name"),
        tts_model_name=config.get("tts_model_name"),
        asr_model_name=config.get("asr_model_name"),
    )
