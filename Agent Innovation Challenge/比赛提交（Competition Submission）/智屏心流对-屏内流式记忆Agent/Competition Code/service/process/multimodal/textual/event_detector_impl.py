#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import os
import time
from typing import List, Dict

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2_5OmniForConditionalGeneration

from doc_process.context.multimodal_schema import FrameInfo
from doc_process.processors.multimodal.recognize.detector.event_detector import EventDetector
from doc_process.utils import logging
from service.process.multimodal.multiprocess_utils import BoundedFIFOQueue
from service.process.multimodal.textual.textual_config import TARGET_LABELS_EN_ZH_DICT
from service.process.multimodal.utils.ug_utils import UgClient

logger = logging.get_logger()


class ProactivecareDetectorAdapterImpl(EventDetector):
    """ProactivecareDetectorAdapterImpl"""
    MAX_FRAMES = 64
    RESIZE_SHAPE = (480, 360)
    MODEL_ID = "/home/users/nus/e0970163/scratch/models/Qwen2.5-Omni-7B"
    VIDEO_OUTPUT_FOLDER = '/data2/xiaoneng/streaming'
    COOLDOWN_PERIOD = 300  # 5分钟冷却时间（秒）

    def __init__(self, **kwargs):
        self.data_buffer: BoundedFIFOQueue = kwargs.get("data_buffer")
        self.proactive_push_queue: BoundedFIFOQueue = kwargs.get("proactive_push_queue")
        self.model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
            self.MODEL_ID,
            device_map="auto",
            torch_dtype=torch.float16,
            attn_implementation="flash_attention_2").eval()
        self.processor = AutoProcessor.from_pretrained(
            self.MODEL_ID,
            min_pixels=256 * 28 * 28,
            max_pixels=1280 * 28 * 28)
        self.en_zh_dict = TARGET_LABELS_EN_ZH_DICT
        self.target_labels = self.en_zh_dict.keys()
        self.ug_client = UgClient()
        self.video_save_count = 0
        self.last_execution_time = 0  # 初始化时间戳
        self.detect_type = kwargs.get("detect_type")

    def detect(self, frame_queue, detection_results, **kwargs) -> List[Dict]:
        """带5分钟冷却期的检测函数"""
        current_time = time.time()

        # 检查是否在冷却期内
        if current_time - self.last_execution_time < self.COOLDOWN_PERIOD:
            return []  # 直接返回空列表

        # 1.首先过滤掉没有DINO结果的帧
        # len(frame_queue)=len(detection_results)=batch_size
        # left_size
        left_frames = []
        left_detection_results = []
        for frame_info, cur_obj_detection_res in zip(frame_queue, detection_results):
            if frame_info and cur_obj_detection_res:
                left_frames.append(frame_info)
                left_detection_results.append(cur_obj_detection_res)

        frame_queue = left_frames
        detection_results = left_detection_results

        # 所有帧都没有DINO结果
        if not frame_queue:
            return

        # 2.前3帧和帧序列拼接
        first_frame_info = frame_queue[0]
        segments: List[FrameInfo] = self.data_buffer.get_segment(
            frame_base64=first_frame_info.frame_base64,
            MAX_RETRIEVAL=3)
        if len(frame_queue) > 1:
            segments.extend(frame_queue[1:])

        frame_np_segments = [frame_info.frame_np for frame_info in segments]
        frame_base64_segments = [frame_info.frame_base64 for frame_info in segments]

        # 3.merge 帧序列 labels
        merged_labels = []
        for cur_obj_detection_res in detection_results:
            merged_labels.extend(cur_obj_detection_res["merged_labels"])
        merged_labels_str = ",".join(set(merged_labels))

        # 4.  判断是否命中标签
        triggered_labels = []
        for label in self.target_labels:
            # 因为DINO检测结果可能是['mango lit', 'mango litchi']，所以使用关键词在字符串中搜索
            if label in merged_labels_str:
                triggered_labels.append(label)
        logger.info("triggered_labels={}".format(triggered_labels))

        # 5.对每个命中标签进行意图判断
        for cur_label in triggered_labels:

            cur_zh_label = self.en_zh_dict.get(cur_label)
            # 6. 根据标签从UG召回
            ug_infos = self.ug_client.search(cur_zh_label)
            if not ug_infos:
                continue

            # 7. 在UG中存在标签信息
            start_time = time.time()
            result = self.get_llms_result(cur_zh_label, frame_np_segments)
            logger.info("event judgement cost time={}".format(time.time() - start_time))

            segments_file = self.VIDEO_OUTPUT_FOLDER

            if ug_infos and self.parse_llms_result(result):
                # 8.更新执行时间并执行核心逻辑
                self.last_execution_time = current_time

                # 9. 构造推送消息，开始主动推送
                ug_info_str = "\n".join(ug_infos)
                push_info = f"温馨提醒，{ug_infos}，注意到您身边有{cur_zh_label},请注意身体健康哈"
                short_base64_segments = [base64[:5] for base64 in frame_base64_segments]
                logger.info("push_info={}, ug_info_str={}, segments_file={}, frame_base64_segments={}".format(
                    push_info, ug_info_str, segments_file, short_base64_segments))
                # self.save_video(frame_np_segments)
                if self.proactive_push_queue:
                    logger.info("已推送主动提醒")
                    self.proactive_push_queue.append((push_info, ug_info_str, segments_file, frame_base64_segments))

    @staticmethod
    def preprocess_frames(frame_np_segments, max_frames=MAX_FRAMES, resize_shape=RESIZE_SHAPE):
        """
        处理numpy数组图片列表
        返回PIL图像列表和帧信息字典
        """
        # 应用帧采样策略
        total_frames = len(frame_np_segments)
        if total_frames > max_frames:
            step = total_frames // max_frames
            indices = range(0, total_frames, step)[:max_frames]
            selected_frames = [frame_np_segments[i] for i in indices]
        else:
            selected_frames = frame_np_segments
            indices = range(total_frames)

        frames = []
        frame_info = []

        # 将numpy数组转换为PIL图像并调整大小
        for i, frame_np in zip(indices, selected_frames):
            frame_np = frame_np[0]

            # 转换为PIL.Image并调整大小
            img = Image.fromarray(np.uint8(frame_np))
            if resize_shape:
                img = img.resize(resize_shape)

            frames.append(img)
            frame_info.append({
                "type": "image",
                "image": f"frame_{i}",  # 伪文件名用于构造消息
                "frame_index": i,
                "total_frames": len(selected_frames)
            })

        return frames, frame_info

    @staticmethod
    def get_messages(food_type, frame_info):
        messages = [
            {"role": "system",
             "content": [
                 {"type": "text",
                  "text": (
                      f'你是一个视频行为分析和意图理解模型。输入是第一人称视角（主观视角）视频流。请严格按以下规则分析并输出“是”或“否”：\n'
                      f'1. **任务目标**：判断视角主角（即视频拍摄者本人）是否准备吃{food_type}定义为：主角正在执行与吃{food_type}直接相关的动作，'
                      f'例如伸手拿{food_type}、拿起{food_type}、开始剥皮或将其移向嘴边。仅当检测到此类动作序列时，输出“是”。\n'
                      f'2. **排除条件**：输出“否”的情况包括：\n'
                      f' - 主角仅看到{food_type}（如注视{food_type}但无后续动作）。\n'
                      f' - 视频中出现其他人吃{food_type}或处理{food_type}。\n'
                      f' - 主角有其他动作（如说话、行走），但未涉及吃{food_type}意图。\n'
                      f'3. **输出格式**：直接输出“是”或“否”。禁止添加任何额外文本、解释或标点。\n'
                      f'4. **分析重点**：关注主角的手部动作和意图信号（如对象交互），忽略背景、声音或其他人。视频是时序数据，需分析动作连续性。')
                  }
             ]},
            {"role": "user", "content": [
                {"type": "text", "text": "以下是按时间顺序排列的视频帧序列："}
            ]}
        ]

        for info in frame_info:
            messages[1]["content"].append(info)

        return messages

    def save_video(self, frame_np_segments, fps=3):
        # 检查输入是否为空
        if not frame_np_segments or not frame_np_segments[0].size:
            raise ValueError("输入数据为空或格式不正确")

        # 获取视频参数（假设所有帧尺寸和通道数一致）
        first_frame = frame_np_segments[0][0]  # 取第一个片段的第一帧
        height, width, channels = first_frame.shape

        # 初始化视频写入器（使用MP4V编码）
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_video_path = os.path.join(self.VIDEO_OUTPUT_FOLDER, f"{self.video_save_count}.mp4")
        video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
        self.video_save_count += 1

        # 遍历所有片段和帧
        for segment in frame_np_segments:
            for frame in segment:
                # 确保数据类型为uint8且范围0-255
                if frame.dtype != np.uint8:
                    frame = (frame * 255).astype(np.uint8)
                # 转换颜色通道（RGB转BGR，若原始为BGR则跳过）
                if channels == 3:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                else:
                    frame_bgr = frame
                video_writer.write(frame_bgr)

        video_writer.release()
        logger.info(f"视频已保存至：{output_video_path}")

    def get_llms_result(self, food_type, frame_np_segments):
        frames, frame_info = self.preprocess_frames(frame_np_segments)
        messages = self.get_messages(food_type=food_type, frame_info=frame_info)

        prompt_text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        inputs = self.processor(
            prompt_text,
            images=frames,
            return_tensors="pt",
            padding=True
        ).to(self.model.device)

        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=128, return_audio=False)

        answer_ids = output[0][inputs.input_ids.shape[1]:]
        answer = self.processor.decode(answer_ids, skip_special_tokens=True)

        print("\n" + "=" * 50)
        print(f"Final result: {answer}")
        print("=" * 50)
        return answer

    def parse_llms_result(self, result):
        return True if "是" in result else False


class EventSummaryDetectorAdapterImpl(EventDetector):
    """EventSummaryDetectorImpl"""

    def detect(self):
        """detect"""
