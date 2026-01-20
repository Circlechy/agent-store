#!/usr/bin/env python
# coding: utf-8
"""
Script to transcribe harmonyOS.mp3 using DashScope ASR
"""

import os
import sys
import tempfile
import subprocess
import asyncio
from datetime import datetime

# Add project path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from typing import Dict, Any


def load_api_key():
    """加载API Key"""
    # 从环境变量获取
    api_key = os.environ.get("API_KEY")
    if api_key:
        dashscope.api_key = api_key
        dashscope.base_websocket_api_url = (
            "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
        )
        print(f"🎤 [语音识别] 已从环境变量加载API Key")
    else:
        # 使用默认API Key
        default_api_key = "YOUR API KEY"
        dashscope.api_key = default_api_key
        dashscope.base_websocket_api_url = (
            "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
        )
        print(f"🎤 [语音识别] 已使用默认API Key")
        print(
            f"🎤 [语音识别] 警告：使用默认API Key可能会受到限制，请考虑使用自己的API Key"
        )


def get_timestamp():
    """获取格式化时间戳"""
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")


def preprocess_audio(audio_path):
    """预处理大音频文件 - 转换为16kHz单声道MP3格式"""
    print(f"[语音识别] 开始预处理音频文件: {audio_path}")

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, "processed_audio.mp3")  # 使用MP3格式

    try:
        # 尝试使用ffmpeg进行音频压缩和格式转换
        print(f"[语音识别] 尝试使用ffmpeg压缩并转换音频为16kHz单声道MP3")

        # 构建ffmpeg命令 - 严格按照要求设置参数
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            audio_path,
            "-b:a",
            "32k",  # 低比特率，减少文件大小
            "-ar",
            "16000",  # 严格设置为16kHz采样率
            "-ac",
            "1",  # 严格设置为单声道
            "-f",
            "mp3",  # 严格使用MP3格式
            temp_file,
        ]

        # 执行命令
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60  # 增加超时时间
        )

        if result.returncode == 0:
            print(f"[语音识别] ffmpeg处理成功")
            print(
                f"[语音识别] 预处理后文件大小: {os.path.getsize(temp_file) / 1024:.2f} KB"
            )
            return temp_file
        else:
            print(f"[语音识别] ffmpeg处理失败: {result.stderr}")
            return None

    except Exception as e:
        print(f"[语音识别] 预处理失败: {e}")
        return None


class HarmonyOSASR:
    """HarmonyOS音频转文本处理器"""

    def __init__(self):
        self.recognized_sentences = []
        self.is_running = False
        self.recognition = None

    def _asr_callback(self, result):
        """回调函数：识别到完整句子立即处理"""
        try:
            sentence = result.get_sentence()
            if (
                sentence
                and "text" in sentence
                and RecognitionResult.is_sentence_end(sentence)
            ):
                text = sentence["text"].strip()
                if text:
                    self.recognized_sentences.append(text)
                    print(get_timestamp() + f" [识别线程] 识别到完整句子：{text}")
        except Exception as e:
            print(f"[识别线程] 回调处理异常: {e}")

    async def transcribe(self, audio_path):
        """转录音频文件"""
        print("=" * 80)
        print("开始转录 harmonyOS.mp3")
        print("=" * 80)

        # 检查文件
        if not os.path.exists(audio_path):
            print(f"错误: 文件不存在: {audio_path}")
            return False

        file_size = os.path.getsize(audio_path)
        print(f"[系统] 音频路径: {audio_path}")
        print(f"[系统] 文件大小: {file_size / 1024:.2f} KB")

        # 预处理大文件
        preprocessed_audio = None
        sample_rate = 24000

        if file_size > 700000:  # 700KB
            print(f"[系统] 检测到大文件，进行预处理...")
            preprocessed_audio = preprocess_audio(audio_path)
            if preprocessed_audio:
                audio_path = preprocessed_audio
                sample_rate = 16000  # 预处理后使用16kHz
                print(f"[系统] 使用预处理后的音频: {audio_path}")
            else:
                print(f"[系统] 预处理失败，尝试直接处理原始音频")

        # 创建回调
        callback = RecognitionCallback()
        callback.on_event = self._asr_callback

        try:
            # 初始化识别器
            print(f"[系统] 初始化识别器 (采样率: {sample_rate}Hz)...")
            self.recognition = Recognition(
                model="fun-asr-realtime",
                format="mp3",
                sample_rate=sample_rate,
                callback=callback,
                timeout=300,  # 5分钟超时
            )

            # 启动识别
            print(f"[系统] 启动识别...")
            self.is_running = True
            self.recognition.start()

            # 等待连接建立
            print(f"[系统] 等待WebSocket连接建立...")
            await asyncio.sleep(0.5)

            # 读取音频文件
            print(f"[系统] 读取音频文件...")
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            print(f"[系统] 音频数据大小: {len(audio_data) / 1024:.2f} KB")
            print(f"[系统] 开始流式发送...")

            # 流式发送
            frame_size = 1024
            total_frames = (len(audio_data) + frame_size - 1) // frame_size

            for i in range(0, len(audio_data), frame_size):
                if not self.is_running:
                    break

                frame = audio_data[i : i + frame_size]
                if not frame:
                    break

                try:
                    self.recognition.send_audio_frame(frame)

                    # 显示进度
                    if i % (frame_size * 20) == 0:
                        progress = (i / len(audio_data)) * 100
                        print(f"[系统] 发送进度: {progress:.1f}%")

                    # 适当等待
                    await asyncio.sleep(0.01)

                except Exception as e:
                    if "Cannot write to closing transport" in str(e):
                        print(f"[系统] 连接已关闭，停止发送")
                        self.is_running = False
                        break
                    else:
                        print(f"[系统] 发送帧失败: {e}")
                        continue

            # 等待结果
            print(f"[系统] 发送完成，等待最终结果...")
            await asyncio.sleep(5.0)

        except Exception as e:
            print(f"[系统] 转录失败: {e}")
            return False
        finally:
            # 停止识别
            if self.recognition:
                try:
                    self.recognition.stop()
                except:
                    pass
            self.is_running = False

        # 保存结果
        if self.recognized_sentences:
            output_file = os.path.join(
                os.path.dirname(audio_path), "harmonyOS_transcription.txt"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self.recognized_sentences))

            print("=" * 80)
            print("转录完成!")
            print("=" * 80)
            print(f"识别结果: {len(self.recognized_sentences)} 句")
            print(f"保存路径: {output_file}")
            print("=" * 80)

            # 显示结果
            print("转录内容:")
            print("-" * 80)
            for i, sentence in enumerate(self.recognized_sentences, 1):
                print(f"{i}. {sentence}")
            print("-" * 80)

            return True
        else:
            print("=" * 80)
            print("转录失败: 未识别到任何内容")
            print("=" * 80)
            return False


async def main():
    """主函数"""
    # 加载API Key
    load_api_key()

    # 查找harmonyOS.mp3文件
    harmonyos_path = os.path.join("./samples", "harmonyOS.mp3")
    harmonyos_path = os.path.abspath(harmonyos_path)

    # 初始化并转录
    asr = HarmonyOSASR()
    success = await asr.transcribe(harmonyos_path)

    if success:
        print("✅ 转录成功!")
    else:
        print("❌ 转录失败!")


if __name__ == "__main__":
    asyncio.run(main())
