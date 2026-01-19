"""
TTS语音输出工具
支持本地TTS和云端TTS
"""

import os
import asyncio
import base64
import logging
import tempfile
import re

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import dotenv
dotenv.load_dotenv(dotenv_path=".env")

logger = logging.getLogger(__name__)

# TTS配置 - 优先使用Edge TTS（声音更自然）
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")  # edge(推荐), pyttsx3, azure
DEFAULT_VOICE = "zh-CN-XiaoyiNeural"
TTS_VOICE = os.getenv("TTS_VOICE", DEFAULT_VOICE)  # 更自然的女声
TTS_RATE = int(os.getenv("TTS_RATE", 200))
RATE_MIN = 50
RATE_MAX = 300
MAX_TTS_CHUNK_LEN = 160

# Edge TTS 可用的中文语音（都很自然）
# zh-CN-XiaoxiaoNeural - 女声，温柔亲切
# zh-CN-XiaoyiNeural - 女声，活泼可爱（推荐车载使用）
# zh-CN-YunjianNeural - 男声，沉稳大气
# zh-CN-YunxiNeural - 男声，阳光活力

# 全局TTS引擎实例
_tts_engine = None
_tts_enabled = True


def _get_tts_engine():
    """获取TTS引擎实例"""
    global _tts_engine
    
    if _tts_engine is None:
        try:
            if TTS_ENGINE == "pyttsx3":
                import pyttsx3
                _tts_engine = pyttsx3.init()
                _tts_engine.setProperty('rate', TTS_RATE)
                
                # 尝试设置中文语音
                voices = _tts_engine.getProperty('voices')
                for voice in voices:
                    if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                        _tts_engine.setProperty('voice', voice.id)
                        break
                
                logger.info("pyttsx3 TTS引擎初始化成功")
            
            elif TTS_ENGINE == "edge":
                # Edge TTS (需要 edge-tts 库)
                try:
                    import edge_tts  # noqa: F401
                    logger.info("使用Edge TTS引擎")
                    _tts_engine = "edge"
                except ImportError as e:
                    logger.error(f"Edge TTS不可用: {e}")
                    _tts_engine = None
            
            else:
                logger.warning(f"未知TTS引擎: {TTS_ENGINE}，使用pyttsx3")
                import pyttsx3
                _tts_engine = pyttsx3.init()
        
        except ImportError as e:
            logger.error(f"TTS库导入失败: {e}")
            logger.info("提示: 请安装 pyttsx3: pip install pyttsx3")
            _tts_engine = None
        except Exception as e:
            logger.error(f"TTS引擎初始化失败: {e}")
            _tts_engine = None
    
    return _tts_engine


def _run_async(coro, timeout: int = 60):
    """在存在/不存在事件循环时安全运行协程"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=timeout)
        return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


def speak_sync(text: str) -> bool:
    """同步语音播报"""
    global _tts_enabled
    
    if not _tts_enabled:
        logger.info(f"[TTS已禁用] {text}")
        return False
    
    engine = _get_tts_engine()
    
    if engine is None:
        logger.warning(f"[TTS不可用] {text}")
        return False
    
    try:
        chunks = _split_tts_text(text)
        if not chunks:
            logger.warning("TTS播报内容为空或被清洗为空")
            return False
        if engine == "edge":
            # Edge TTS 异步方式 - 使用新的事件循环
            coro = _speak_edge_sequence(chunks) if len(chunks) > 1 else _speak_edge(text)
            # 分段播放会更久，按段数放宽超时
            timeout = max(30, len(chunks) * 20)
            return _run_async(coro, timeout=timeout)
        else:
            # pyttsx3 同步方式
            for chunk in chunks:
                engine.say(chunk)
            engine.runAndWait()
            logger.info(f"[TTS播报] {text[:50]}...")
            return True
    
    except Exception as e:
        logger.error(f"TTS播报失败: {e}")
        return False


async def synthesize_audio_base64_async(text: str) -> dict:
    """合成语音并返回base64音频（浏览器播放用）"""
    chunks = _split_tts_text(text)
    if not chunks:
        return {"success": False, "error": "播报内容为空"}

    engine = _get_tts_engine()
    if engine != "edge":
        return {"success": False, "error": "当前仅支持Edge TTS合成音频"}

    try:
        audio_bytes = await _synthesize_edge_chunks_to_bytes(chunks)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {
            "success": True,
            "audio_base64": audio_b64,
            "audio_mime": "audio/mpeg"
        }
    except Exception as e:
        logger.error(f"音频合成失败: {e}")
        return {"success": False, "error": str(e)}


def synthesize_audio_base64(text: str) -> dict:
    """同步合成语音并返回base64音频"""
    return _run_async(synthesize_audio_base64_async(text), timeout=60)


async def _speak_edge(text: str, voice: str = None):
    """使用Edge TTS播报 - 微软神经网络语音，更自然"""
    try:
        import edge_tts
        
        # 使用配置的语音或默认语音
        voice = voice or TTS_VOICE or DEFAULT_VOICE
        
        communicate = edge_tts.Communicate(text, voice)
        
        # 保存到临时文件并播放
        temp_path = _create_temp_mp3()
        
        await communicate.save(temp_path)
        
        # 播放音频
        if not _play_audio_file(temp_path):
            return False
        
        logger.info(f"[Edge TTS] 播报完成: {text[:30]}...")
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return True
    
    except ImportError:
        logger.error("需要安装 edge-tts: pip install edge-tts")
        return False
    except Exception as e:
        logger.error(f"Edge TTS失败: {e}")
        return False


async def _speak_edge_sequence(chunks, voice: str = None):
    """Edge TTS 分段顺序播报，避免长文本被截断"""
    temp_paths = []
    try:
        import edge_tts
        
        voice = voice or TTS_VOICE or DEFAULT_VOICE
        tasks = []
        for chunk in chunks:
            temp_path = _create_temp_mp3()
            temp_paths.append(temp_path)
            communicate = edge_tts.Communicate(chunk, voice)
            tasks.append(communicate.save(temp_path))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Edge TTS分段合成失败: {result}")
                return False
        
        for temp_path in temp_paths:
            if not _play_audio_file(temp_path):
                return False
        
        return True
    finally:
        try:
            for temp_path in temp_paths:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception:
            pass


async def _synthesize_edge_chunks_to_bytes(chunks, voice: str = None) -> bytes:
    """Edge TTS分段合成并返回音频字节"""
    import edge_tts

    voice = voice or TTS_VOICE or DEFAULT_VOICE
    temp_paths = []
    tasks = []
    for chunk in chunks:
        temp_path = _create_temp_mp3()
        temp_paths.append(temp_path)
        communicate = edge_tts.Communicate(chunk, voice)
        tasks.append(communicate.save(temp_path))

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result

        audio_bytes = b""
        for temp_path in temp_paths:
            with open(temp_path, "rb") as f:
                audio_bytes += f.read()
        return audio_bytes
    finally:
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except:
                pass


def _create_temp_mp3() -> str:
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    temp_path = temp_file.name
    temp_file.close()
    return temp_path


def _play_audio_file(temp_path: str) -> bool:
    try:
        import platform
        import subprocess
        
        system = platform.system()
        if system == "Darwin":
            # macOS - 使用afplay（更稳定）
            subprocess.run(["afplay", temp_path], check=True)
        elif system == "Windows":
            # Windows - 使用 Windows Media Player 播放 mp3（SoundPlayer 仅支持 wav）
            ps_script = (
                "$player = New-Object -ComObject WMPlayer.OCX.7; "
                f"$player.URL = '{temp_path}'; "
                "$player.controls.play(); "
                # 等待进入播放状态，避免过早退出导致播放中断
                "while ($player.playState -ne 3 -and $player.playState -ne 8) { Start-Sleep -Milliseconds 100 }; "
                # 播放中则等待直到媒体播放结束
                "if ($player.playState -eq 3) { "
                "while ($player.playState -ne 8) { Start-Sleep -Milliseconds 200 } }"
            )
            subprocess.run(["powershell", "-c", ps_script], check=True)
        else:
            # Linux
            subprocess.run(["mpg123", "-q", temp_path], check=True)
        return True
    except Exception as e:
        logger.error(f"音频播放失败: {e}")
        return False


def _split_tts_text(text: str, max_len: int = MAX_TTS_CHUNK_LEN):
    """按标点切分，超长再按长度切分"""
    clean = _normalize_tts_text(text)
    if not clean:
        return []
    if len(clean) <= max_len:
        return [clean]
    parts = [p.strip() for p in re.split(r"([。！？!?；;，,])", clean) if p.strip()]
    chunks = []
    buf = ""
    for part in parts:
        if len(buf) + len(part) <= max_len:
            buf += part
        else:
            if buf:
                chunks.append(buf.strip())
            buf = part
    if buf:
        chunks.append(buf.strip())
    # 兜底：仍超长则硬切
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_len:
            final_chunks.append(chunk)
        else:
            for i in range(0, len(chunk), max_len):
                final_chunks.append(chunk[i:i + max_len])
    return final_chunks


def _normalize_tts_text(text: str) -> str:
    """清理markdown与多余符号，降低TTS异常风险"""
    clean = text or ""
    clean = re.sub(r"[`*_~]", "", clean)
    clean = re.sub(r"^\s*[-*]\s+", "", clean, flags=re.M)
    clean = re.sub(r"^\s*\d+\.\s+", "", clean, flags=re.M)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

@tool(name="set_tts_enabled",
      description="开启或关闭语音播报功能",
      params=[
          Param(name="enabled",
                description="是否启用TTS：true/false",
                type="bool", required=True)
      ])
def set_tts_enabled(enabled: bool) -> dict:
    """设置TTS开关"""
    global _tts_enabled
    _tts_enabled = enabled
    
    return {
        "success": True,
        "tts_enabled": _tts_enabled,
        "message": f"语音播报已{'开启' if enabled else '关闭'}"
    }


@tool(name="get_tts_status",
      description="获取TTS语音播报状态",
      params=[])
def get_tts_status() -> dict:
    """获取TTS状态"""
    engine = _get_tts_engine()
    
    return {
        "enabled": _tts_enabled,
        "engine": TTS_ENGINE,
        "available": engine is not None,
        "voice": TTS_VOICE,
        "rate": TTS_RATE
    }


@tool(name="set_tts_rate",
      description="设置语音播报语速",
      params=[
          Param(name="rate",
                description="语速：50-300，默认150。数值越大语速越快",
                type="int", required=True)
      ])
def set_tts_rate(rate: int) -> dict:
    """设置TTS语速"""
    global TTS_RATE
    
    rate = max(RATE_MIN, min(RATE_MAX, rate))
    TTS_RATE = rate
    
    engine = _get_tts_engine()
    if engine and engine != "edge":
        try:
            engine.setProperty('rate', rate)
        except:
            pass
    
    return {
        "success": True,
        "rate": rate,
        "message": f"语速已设置为{rate}"
    }


# 便捷函数：用于Agent自动播报回复
def auto_speak_response(response: str):
    """自动播报Agent回复（截断过长内容）"""
    if not _tts_enabled:
        return

    # 异步播报（不阻塞）
    import threading
    thread = threading.Thread(target=speak_sync, args=(response,))
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    print("TTS状态:", get_tts_status())
    
    # 测试播报
    result = speak_sync("你好，我是智能车载助手小九，很高兴为您服务！")
    print("播报结果:", result)
