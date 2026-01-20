"""多模态工具函数模块.

提供图像生成和文本转语音的便捷接口，方便各个节点调用。
"""

import base64
import logging
from typing import Any, Dict, Optional

try:
    import httpx
except ImportError:
    httpx = None

from novastar.core.llm_wrapper import LLMWrapper

logger = logging.getLogger(__name__)


async def generate_image(
    llm: Optional[LLMWrapper],
    prompt: str,
    style: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    fallback_url: Optional[str] = None,
) -> str:
    """生成图像.

    Args:
        llm: LLMWrapper 实例（如果为 None，返回模拟 URL）
        prompt: 图像生成提示词
        style: 图像风格（可选）
        width: 图像宽度（默认 1024）
        height: 图像高度（默认 1024）
        fallback_url: 失败时的备用 URL（默认为模拟 URL）

    Returns:
        图片 URL 或 base64 数据 URL
    """
    if llm is None:
        mock_url = fallback_url or f"[模拟图片URL] prompt={prompt[:50]}..."
        logger.warning(f"[MultimodalUtils] LLM 未配置，返回模拟图片 URL: {mock_url}")
        return mock_url

    try:
        result = await llm.generate_image(
            prompt=prompt,
            style=style,
            width=width,
            height=height,
        )
        
        if result.get("url"):
            return result["url"]
        elif result.get("base64"):
            return f"data:image/png;base64,{result['base64']}"
        else:
            mock_url = fallback_url or f"[模拟图片URL] prompt={prompt[:50]}..."
            logger.warning(f"[MultimodalUtils] 图像生成结果为空，返回模拟 URL")
            return mock_url
    except Exception as e:
        logger.error(f"[MultimodalUtils] 图像生成失败: {e}", exc_info=True)
        mock_url = fallback_url or f"[模拟图片URL] prompt={prompt[:50]}..."
        return mock_url


async def text_to_speech(
    llm: Optional[LLMWrapper],
    text: str,
    voice: str = "Cherry",
    speed: str = "normal",
    age: Optional[int] = None,
    fallback_url: Optional[str] = None,
) -> str:
    """文本转语音.

    Args:
        llm: LLMWrapper 实例（如果为 None，返回模拟 URL）
        text: 要转换的文本
        voice: 声音名称（默认 "Cherry"，DashScope 支持）
        speed: 语速（slow/normal/fast，默认 "normal"）
        age: 用户年龄（如果提供且 <= 6，自动使用 "slow" 语速）
        fallback_url: 失败时的备用 URL（默认为模拟 URL）

    Returns:
        音频 URL 或 base64 数据 URL
    """
    if llm is None:
        mock_url = fallback_url or f"[模拟音频URL] text={text[:50]}..."
        logger.warning(f"[MultimodalUtils] LLM 未配置，返回模拟音频 URL: {mock_url}")
        return mock_url

    # 根据年龄自动调整语速
    if age is not None and age <= 6:
        speed = "slow"

    try:
        result = await llm.text_to_speech(
            text=text,
            voice=voice,
            speed=speed,
        )
        
        # 如果已经有 base64 数据，直接返回 data URI
        if result.get("base64"):
            return f"data:audio/mp3;base64,{result['base64']}"
        
        # 如果有 URL，下载音频并转换为 base64
        if result.get("url"):
            audio_url = result["url"]
            try:
                # 下载音频文件
                if not httpx:
                    logger.warning("[MultimodalUtils] httpx 未安装，无法下载音频，返回 URL")
                    return audio_url
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()
                    
                    # 将音频数据转换为 base64
                    audio_data = response.content
                    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                    
                    # 返回 data URI 格式
                    return f"data:audio/mp3;base64,{audio_base64}"
            except Exception as download_error:
                logger.warning(f"[MultimodalUtils] 音频下载失败，返回原始 URL: {download_error}")
                return audio_url
        
        # 如果没有 URL 和 base64，返回模拟 URL
        mock_url = fallback_url or f"[模拟音频URL] text={text[:50]}..."
        logger.warning(f"[MultimodalUtils] 音频生成结果为空，返回模拟 URL")
        return mock_url
    except Exception as e:
        logger.error(f"[MultimodalUtils] 音频生成失败: {e}", exc_info=True)
        mock_url = fallback_url or f"[模拟音频URL] text={text[:50]}..."
        return mock_url


async def speech_to_text(
    llm: Optional[LLMWrapper],
    audio: str,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
    fallback_text: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """语音转文本.

    Args:
        llm: LLMWrapper 实例（如果为 None，返回模拟文本）
        audio: 音频文件路径、URL 或 base64 编码的音频数据
        model_name: 模型名称（可选，默认使用 LLMWrapper 的 asr_model_name）
        language: 语言代码（如 "zh", "en" 等，可选）
        fallback_text: 失败时的备用文本（默认为模拟文本）
        **kwargs: 其他参数（传递给 llm.speech_to_text）

    Returns:
        转录的文本字符串
    """
    if llm is None:
        mock_text = fallback_text or "[模拟转录文本] 音频已接收"
        logger.warning(f"[MultimodalUtils] LLM 未配置，返回模拟转录文本: {mock_text}")
        return mock_text

    try:
        result = await llm.speech_to_text(
            audio=audio,
            model_name=model_name,
            language=language,
            **kwargs,
        )
        
        # 提取转录文本
        text = result.get("text", "")
        if text:
            return text
        else:
            mock_text = fallback_text or "[模拟转录文本] 音频已接收"
            logger.warning(f"[MultimodalUtils] 语音转文本结果为空，返回模拟文本")
            return mock_text
    except Exception as e:
        logger.error(f"[MultimodalUtils] 语音转文本失败: {e}", exc_info=True)
        mock_text = fallback_text or "[模拟转录文本] 音频已接收"
        return mock_text
