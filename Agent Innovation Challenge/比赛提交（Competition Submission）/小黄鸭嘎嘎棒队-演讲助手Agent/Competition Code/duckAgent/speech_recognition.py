#!/usr/bin/env python
# coding: utf-8
"""
语音识别工具 - 终极异步解耦版
核心改进：独立线程运行识别逻辑，彻底解决首句阻塞问题
"""

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.context_engine.base import Context
import asyncio
import dashscope
import threading
import queue as sync_queue
from datetime import datetime
from dashscope.audio.asr import *
from typing import AsyncIterator, Dict, Any, Optional
import os

# 全局控制变量
g_core_control = None


# 配置API Key
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


# 加载API Key
load_api_key()


def get_timestamp():
    """获取格式化时间戳"""
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")


# 常量定义
DEFAULT_AUDIO_PATH = "./samples/harmonyOS.mp3"
LARGE_FILE_THRESHOLD = 700000  # 700KB

# Mock 语音识别文本 - 用于无音频文件时的模拟
MOCK_SPEECH_TEXT = """
Machine Learning Kit提供了场景化能力,包括通用卡证识别、实时语音识别等,提供AI控件能力，使系统控件融合文字识别等AI能力。CoreAI API提供了图像语义、语言语音解析、OCR文字识别等能力。Core DeepLearning APl提供了高性能低功耗的端侧推理和端侧学习环境。意图框架提供了HARMLESS系统级的意图标准体系，通过多维系统感知大模型等能力，构建全局意图范式，实现对用户显性与潜在意图的理解，并及时准确的将用户需求传递给生态伙伴，匹配合时宜的服务，为用户提供多模态、场景化进阶体验。
"""


# 解析Mock文本为句子列表
def _parse_mock_sentences():
    """解析Mock文本为句子列表"""
    mock_text = MOCK_SPEECH_TEXT.strip()
    # 分割句子（支持多种句号格式）
    sentences = []
    for sentence in mock_text.split("。"):
        sentence = sentence.strip()
        if sentence:
            sentences.append(sentence)
    return sentences


MOCK_SENTENCES = _parse_mock_sentences()


# ====================== 1. 独立线程的识别引擎 ======================
class ThreadedASREngine:
    """独立线程运行的ASR引擎，与主事件循环完全解耦"""

    def __init__(self, result_queue: sync_queue.Queue):
        self.result_queue = result_queue
        self.recognition: Optional[Recognition] = None
        self.callback: Optional[RecognitionCallback] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.audio_path = ""
        self.sample_rate = 24000
        self.audio_format = "mp3"

    def _asr_callback(self, result: RecognitionResult):
        """内部回调函数：识别到完整句子立即入队"""
        try:
            sentence = result.get_sentence()
            if (
                sentence
                and "text" in sentence
                and RecognitionResult.is_sentence_end(sentence)
            ):
                text = sentence["text"].strip()
                if text:
                    self.result_queue.put_nowait(
                        {
                            "type": "sentence",
                            "status": "success",
                            "recog_sentence": text,
                            "timestamp": get_timestamp(),
                            "confidence": sentence.get("confidence", 0.95),
                        }
                    )
                    print(get_timestamp() + f" [识别线程] 识别到完整句子：{text}")
        except Exception as e:
            print(f"[识别线程] 回调处理异常: {e}")

    def _run_asr(self):
        """独立线程中运行的ASR主逻辑"""
        # 初始化识别器
        self.callback = RecognitionCallback()
        self.callback.on_event = self._asr_callback  # 重写回调

        try:
            # 检查是否需要使用mock文本
            if not self.audio_path or not os.path.exists(self.audio_path):
                print(
                    f"[识别线程] 未提供音频路径或文件不存在，使用mock文本模拟语音识别"
                )
                self._use_mock_text()
                return

            # 获取文件大小
            file_size = os.path.getsize(self.audio_path)
            print(f"[识别线程] 文件大小: {file_size / 1024:.2f} KB")

            # 对于大文件，使用不同的策略
            if file_size > LARGE_FILE_THRESHOLD:
                # 大文件处理策略
                print(f"[识别线程] 检测到大文件，使用特殊处理策略")
                self._process_large_file(file_size)
            else:
                # 正常文件处理策略
                self._process_normal_file()

        except Exception as e:
            error_msg = f"音频处理错误: {str(e)}"
            print(f"[识别线程] 错误: {error_msg}")
            self.result_queue.put_nowait(
                {"type": "error", "status": "error", "error": error_msg}
            )
        finally:
            # 停止识别器并发送结束信号
            self.is_running = False
            if hasattr(self, "recognition") and self.recognition:
                try:
                    self.recognition.stop()
                except:
                    pass
            self.result_queue.put_nowait({"type": "end"})
            print(get_timestamp() + " [识别线程] 识别结束")

    def _process_normal_file(self):
        """处理正常大小的文件"""
        try:
            self.recognition = Recognition(
                model="fun-asr-realtime",
                format=self.audio_format,
                sample_rate=self.sample_rate,
                callback=self.callback,
            )

            # 启动识别器
            self.is_running = True
            self.recognition.start()

            with open(self.audio_path, "rb") as f:
                while self.is_running:
                    frame = f.read(3200)
                    if not frame:
                        break

                    try:
                        if not self.recognition or not self.is_running:
                            break

                        self.recognition.send_audio_frame(frame)
                        threading.Event().wait(0.05)
                    except Exception as e:
                        print(f"[识别线程] 发送音频帧失败: {e}")
                        self.is_running = False
                        break

            # 等待最后2秒，确保收尾句子不丢失
            threading.Event().wait(2.0)

        except Exception as e:
            print(f"[识别线程] 处理正常文件失败: {e}")
            raise

    def _process_large_file(self, file_size):
        """处理大文件的特殊策略 - 实现流式分片发送 + 心跳保活"""
        try:
            # 使用更保守的参数和超时设置
            self.recognition = Recognition(
                model="fun-asr-realtime",
                format=self.audio_format,
                sample_rate=self.sample_rate,
                callback=self.callback,
                timeout=600,  # 10分钟超时
            )

            # 启动识别器
            self.is_running = True
            self.recognition.start()

            # 存储识别结果
            recognized_sentences = []

            # 流式分片发送
            with open(self.audio_path, "rb") as f:
                processed_size = 0
                total_size = file_size
                frame_size = 512  # 更小的帧，提高实时性
                chunk_size = 4096  # 分片大小
                keep_alive_interval = 5  # 心跳间隔（秒）
                last_keep_alive = datetime.now()

                while self.is_running:
                    # 读取当前分片
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    processed_size += len(chunk)

                    # 逐帧发送
                    for i in range(0, len(chunk), frame_size):
                        if not self.is_running:
                            break

                        frame = chunk[i : i + frame_size]
                        if not frame:
                            break

                        try:
                            if not self.recognition or not self.is_running:
                                break

                            # 检查连接状态
                            if (
                                hasattr(self.recognition, "_websocket")
                                and not self.recognition._websocket.open
                            ):
                                print(f"[识别线程] 连接已关闭，停止发送")
                                self.is_running = False
                                break

                            self.recognition.send_audio_frame(frame)

                            # 心跳保活
                            current_time = datetime.now()
                            if (
                                current_time - last_keep_alive
                            ).total_seconds() > keep_alive_interval:
                                try:
                                    # 发送空帧作为心跳
                                    self.recognition.send_audio_frame(b"")
                                    last_keep_alive = current_time
                                except:
                                    pass

                            # 适当的等待时间，平衡实时性和稳定性
                            threading.Event().wait(0.005)

                        except Exception as e:
                            # 规避向关闭的连接写入数据
                            if "Cannot write to closing transport" in str(e):
                                print(f"[识别线程] 连接已关闭，停止发送")
                                self.is_running = False
                                break
                            else:
                                print(f"[识别线程] 发送音频帧失败: {e}")
                                # 继续处理下一个帧，不停止整个过程
                                continue

                    # 显示进度
                    progress = processed_size / total_size * 100
                    if int(progress) % 5 == 0:
                        print(f"[识别线程] 处理进度: {progress:.1f}%")

                    # 处理分片后稍作休息
                    if self.is_running:
                        threading.Event().wait(0.01)

            # 等待最后5秒，确保收尾句子不丢失
            print(f"[识别线程] 发送完成，等待结果...")
            threading.Event().wait(5.0)

            # 合并结果并保存
            # 结果已经通过回调实时存储，这里可以添加额外的保存逻辑

        except Exception as e:
            print(f"[识别线程] 处理大文件失败: {e}")
            # 对于大文件错误，尝试使用默认音频作为fallback
            self._use_fallback_audio()

    def _use_fallback_audio(self):
        """使用默认音频作为fallback"""
        print(f"[识别线程] 使用默认音频作为fallback")
        fallback_path = DEFAULT_AUDIO_PATH

        if os.path.exists(fallback_path):
            self.result_queue.put_nowait(
                {
                    "type": "warning",
                    "status": "warning",
                    "message": f"大文件处理失败，使用默认音频",
                    "fallback_audio": fallback_path,
                }
            )

            # 切换到默认音频
            self.audio_path = fallback_path
            self._process_normal_file()
        else:
            # 如果默认音频也不存在，使用mock文本
            self._use_mock_text()

    def _use_mock_text(self):
        """使用mock文本模拟语音识别"""
        print(f"[识别线程] 使用mock文本模拟语音识别")
        self.result_queue.put_nowait(
            {
                "type": "info",
                "status": "info",
                "message": "使用mock文本模拟语音识别",
            }
        )

        # 计算总句子数和目标总时间
        total_sentences = len(MOCK_SENTENCES)
        target_total_time = 50.0  # 目标总时间60秒

        # 每句话的平均等待时间（包括句子间的自然停顿）
        # 预留10秒作为基础延迟，剩余50秒平均分配给所有句子
        base_delay = 0
        sentence_wait_time = (target_total_time - base_delay) / total_sentences

        print(
            f"[识别线程] 模拟语音识别：共 {total_sentences} 句，目标总时长 {target_total_time:.1f} 秒"
        )
        print(f"[识别线程] 每句平均等待时间: {sentence_wait_time:.1f} 秒")

        total_text_len = 0
        for s in MOCK_SENTENCES:
            total_text_len += len(s)
        # 模拟语音识别过程，按照正常语速发送句子
        for i, sentence in enumerate(MOCK_SENTENCES, 1):
            try:
                # 使用计算出的等待时间
                wait_time = len(sentence) / total_text_len * target_total_time

                print(
                    f"[识别线程] 模拟识别句子 {i}: {sentence} (发送后等待 {wait_time:.1f} 秒)"
                )

                # 先发送mock句子到队列，让text_match节点立即开始渲染
                self.result_queue.put_nowait(
                    {
                        "type": "sentence",
                        "status": "success",
                        "recog_sentence": sentence,
                        "timestamp": get_timestamp(),
                        "confidence": 0.95,
                    }
                )

                # 然后等待模拟正常说话时间
                threading.Event().wait(wait_time)
            except Exception as e:
                print(f"[识别线程] 模拟识别失败: {e}")
                break

    def start(self, audio_path: str, sample_rate: int, audio_format: str):
        """启动独立识别线程"""
        self.audio_path = audio_path
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.thread = threading.Thread(target=self._run_asr, daemon=True)
        self.thread.start()

    def stop(self):
        """停止识别线程"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)


# ====================== 2. 核心组件（异步解耦版） ======================
class SpeechRecognitionComponent(WorkflowComponent, ComponentExecutable):
    """
    语音识别组件 - 终极异步解耦版
    核心特性：
    1. 识别逻辑在独立线程运行，与主事件循环解耦
    2. 下游处理首句时，不阻塞后续句子的识别和入队
    3. 保证所有句子都能实时推送给下游
    """

    def __init__(self):
        super().__init__()
        # 关键：使用线程安全队列，连接识别线程和异步迭代器
        self.result_queue = sync_queue.Queue(maxsize=100)
        self.asr_engine = ThreadedASREngine(self.result_queue)
        self.is_streaming = False

    def _preprocess_audio(self, audio_path):
        """预处理大音频文件 - 转换为16kHz单声道MP3格式"""
        import tempfile
        import subprocess

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
                # 尝试其他方法 - 直接使用原始文件的前半部分
                print(f"[语音识别] 尝试使用文件截取")

                # 直接截取原始文件的前半部分
                with open(audio_path, "rb") as f:
                    audio_data = f.read()

                # 只取前400KB
                processed_data = audio_data[: 400 * 1024]

                # 保存为原始格式
                with open(temp_file, "wb") as f:
                    f.write(processed_data)

                print(f"[语音识别] 文件截取完成")
                print(
                    f"[语音识别] 截取后文件大小: {os.path.getsize(temp_file) / 1024:.2f} KB"
                )
                return temp_file

        except Exception as e:
            print(f"[语音识别] 预处理失败: {e}")
            return None

    def to_executable(self) -> ComponentExecutable:
        return self

    async def stream(
        self, inputs, runtime, context: Context
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        核心流式接口 - 异步迭代器
        逻辑：异步轮询队列，有数据就yield，不阻塞识别线程
        """
        print("🎤 [语音识别] 启动异步流式识别（独立线程模式）")
        self.is_streaming = True

        # 解析输入参数
        input_data = (
            inputs.data
            if hasattr(inputs, "data")
            else (inputs if isinstance(inputs, dict) else {})
        )
        # 获取音频路径（优先使用外部传入的路径）
        audio_path = input_data.get("audio_path")
        if audio_path is None:
            print("🎤 [语音识别] 未提供音频路径，使用mock文本模拟语音识别")
            # 显式设置为None，触发mock文本逻辑
        elif not audio_path:
            print("🎤 [语音识别] 使用默认音频文件")
            # 使用默认路径作为 fallback
            audio_path = DEFAULT_AUDIO_PATH

        # 检查文件大小，对于大文件进行预处理
        use_preprocessing = input_data.get("use_preprocessing", True)
        is_large_file = False

        # 只有当audio_path不为None时才检查文件大小
        if audio_path is not None:
            try:
                file_size = os.path.getsize(audio_path)
                print(f"🎤 [语音识别] 文件大小: {file_size / 1024:.2f} KB")

                # 对于超过阈值的文件，根据用户选择决定处理方式
                if (
                    file_size > LARGE_FILE_THRESHOLD
                    and audio_path != DEFAULT_AUDIO_PATH
                ):
                    if use_preprocessing:
                        print(f"🎤 [语音识别] 检测到大文件，将进行音频预处理")
                        # 尝试音频预处理
                        processed_audio = self._preprocess_audio(audio_path)
                        if processed_audio:
                            audio_path = processed_audio
                            print(f"🎤 [语音识别] 使用预处理后的音频: {audio_path}")
                            print(
                                f"🎤 [语音识别] 预处理后文件大小: {os.path.getsize(audio_path) / 1024:.2f} KB"
                            )
                        else:
                            print(f"🎤 [语音识别] 预处理失败，将尝试直接处理")
                            is_large_file = True
                    else:
                        print(f"🎤 [语音识别] 检测到大文件，将尝试直接处理（无预处理）")
                        is_large_file = True
            except Exception as e:
                print(f"🎤 [语音识别] 文件大小检查失败: {e}")

        sample_rate = input_data.get("sample_rate", 24000)
        audio_format = input_data.get("format", "mp3")

        # 只有当audio_path不为None时才检查文件存在性
        if audio_path is not None:
            print(f"🎤 [语音识别] 使用音频文件: {audio_path}")
            try:
                print(f"🎤 [语音识别] 文件存在: {os.path.exists(audio_path)}")
            except Exception as e:
                print(f"🎤 [语音识别] 文件存在性检查失败: {e}")
        else:
            print(f"🎤 [语音识别] 使用mock文本模拟语音识别")

        # 启动独立识别线程（立即返回，不阻塞）
        self.asr_engine.start(audio_path, sample_rate, audio_format)

        # ====================== 核心：异步轮询队列 ======================
        sentence_index = 0
        while self.is_streaming:
            try:
                # 非阻塞获取队列数据，无数据则短暂休眠
                item = self.result_queue.get(timeout=0.01)

                # 处理结束信号
                if item.get("type") == "end":
                    break

                # 处理错误
                if item.get("type") == "error":
                    yield {
                        "status": "error",
                        "error": item.get("error", "未知错误"),
                        "timestamp": get_timestamp(),
                        "node": "speech_recognition",
                        "component": "speech_recognition",
                    }
                    continue

                # 处理句子数据 - 核心：每句都立即yield
                if item.get("type") == "sentence" and item.get("status") == "success":
                    sentence_index += 1
                    yield {
                        "status": "success",
                        "recog_sentence": item["recog_sentence"],
                        "sentence_index": sentence_index,
                        "confidence": item["confidence"],
                        "timestamp": item["timestamp"],
                        "node": "speech_recognition",
                        "component": "speech_recognition",
                    }
                    # 释放CPU，给下游组件处理时间，但不阻塞识别线程
                    await asyncio.sleep(0.001)

            except sync_queue.Empty:
                # 队列为空时休眠，降低CPU占用
                await asyncio.sleep(0.005)
                continue
            except Exception as e:
                yield {
                    "status": "error",
                    "error": f"队列处理异常: {str(e)}",
                    "timestamp": get_timestamp(),
                    "node": "speech_recognition",
                }
                await asyncio.sleep(0.001)

        # ====================== 资源清理 ======================
        self.asr_engine.stop()
        self.is_streaming = False
        print(get_timestamp() + " [语音识别] 流式输出结束")

        # 输出完成标记
        yield {
            "status": "completed",
            "message": f"共识别{sentence_index}个句子，全部推送完成",
            "total_sentences": sentence_index,
            "timestamp": get_timestamp(),
            "node": "speech_recognition",
        }

    async def invoke(self, inputs, runtime, context: Context) -> Dict[str, Any]:
        """同步调用接口"""
        all_sentences = []
        async for item in self.stream(inputs, runtime, context):
            if item.get("status") == "success":
                all_sentences.append(item)
        return {
            "status": "completed",
            "total_sentences": len(all_sentences),
            "sentences": all_sentences,
            "full_text": "\n".join([s["recog_sentence"] for s in all_sentences]),
        }


# ====================== 3. 组件导出 ======================
__all__ = ["SpeechRecognitionComponent"]


# ====================== 4. 测试代码 ======================
async def test_full_stream():
    """测试：验证所有句子都能实时推送，无阻塞"""
    # 配置API Key
    # dashscope.api_key = "your-api-key"

    component = SpeechRecognitionComponent()
    test_input = {
        "audio_path": DEFAULT_AUDIO_PATH,
        "sample_rate": 24000,
        "format": "mp3",
    }

    print("\n=== 开始测试异步流式识别 ===")
    async for result in component.stream(test_input, None, Context()):
        if result.get("status") == "success":
            print(
                f"✅ 下游接收句子{result['sentence_index']}：{result['recog_sentence']}"
            )
            # 模拟下游组件处理延迟（验证不阻塞后续句子）
            await asyncio.sleep(0.5)
        elif result.get("status") == "completed":
            print(f"\n🏁 {result['message']}")


if __name__ == "__main__":
    asyncio.run(test_full_stream())
