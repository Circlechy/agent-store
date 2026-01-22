#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any

import numpy as np
import requests
import torch
from PIL import Image
from PIL import ImageDraw, ImageFont
from openai import OpenAI
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

from doc_process.processors.multimodal.recognize.detector.scene_detector import SceneDetector
from doc_process.utils import logging
from service.process.common.utils.common_utils import extract_generated_text
from service.process.multimodal.textual.textual_config import FOOD_DETECT_STR
from service.process.multimodal.utils.image_utils import base64_to_int64, frames_to_base64
from service.process.multimodal.utils.ug_utils import UgClient
from datetime import datetime, timedelta

logger = logging.get_logger()

#todo: 3. @xinjiapo
def draw_detections(image, detections):
    draw = ImageDraw.Draw(image)

    # 尝试加载字体（根据系统环境调整）
    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    for detection in detections:
        boxes = detection['boxes'].cpu().numpy()
        scores = detection['scores'].cpu().numpy()
        labels = detection['text_labels']

        for i, (box, score) in enumerate(zip(boxes, scores)):
            # 转换为整数坐标
            x_min, y_min, x_max, y_max = map(int, box)

            # 绘制边界框
            draw.rectangle([x_min, y_min, x_max, y_max], outline="red", width=3)

            # 准备标签文本
            label_text = f"{labels[i]}: {score:.2f}"

            # 计算文本大小
            text_size = draw.textbbox((0, 0), label_text, font=font)
            text_width = text_size[2] - text_size[0]
            text_height = text_size[3] - text_size[1]

            # 绘制文本背景
            draw.rectangle(
                [x_min, y_min - text_height - 5, x_min + text_width, y_min],
                fill="red"
            )

            # 绘制文本
            draw.text((x_min, y_min - text_height - 5), label_text, fill="white", font=font)

    return image


class IntermiSceneDetectorAdapterImpl(SceneDetector):
    """
    IntermiSceneDetector
    该类设计的用途是：
    1. 每 30s 从 frame_queue 中取出一段 base64 图片序列（也就是一组视频帧）
    2. 基于上下文（memory buffer）做事件 captioning
    3. 写入结果（包含事件、参与人、地点等）到本地 JSON 文件
    4. 供后续总结模块（如 summary service）使用
    """

    def __init__(self, config: Dict,**kwargs):

        #self.model = 'qwen-vl-max-latest'
        # self.model = 'qwen3-vl-plus'
        # api_key = 'sk-857eab32bd8d4a069142b41b4a473786'
        # base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        # mlops_api_key="sk-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50TmFtZSI6IuiwouWwlOW-t-WunumqjOWupCIsImFjY291bnRJZCI6ImQ1OTkwMDQ1NCIsImtleVZlcnNpb24iOiIyLjAiLCJhY2NvdW50TmFtZSI6ImRvbmd5dWt1biIsInRlbmFudElkIjoiMzdmYjY5NTk1ZWUyNjE4YzZlMjk4NjY3MDIxZDI2YTEifQ.5T-lX7g9UhsIjaKS2eY0J66ojZ2A7xsV9HPUkUqkEtY"
        # mlops_base_url="http://mlops.huawei.com/mlops-service/api/v1/agentService/v1"
        # self.client = OpenAI(api_key=api_key, base_url=base_url)

        self.model = 'qwen3-vl-32b-instruct-npu'
        self.api_headers = {
            "Authorization": "Bearer sk-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50TmFtZSI6InVua25vd24iLCJhY2NvdW50SWQiOiJkNTk5MDA0NTQiLCJrZXlWZXJzaW9uIjoiMi4wIiwiYWNjb3VudE5hbWUiOiJkb25neXVrdW4iLCJ0ZW5hbnRJZCI6IjM3ZmI2OTU5NWVlMjYxOGM2ZTI5ODY2NzAyMWQyNmExIn0.cqH9PEeAza20JbyXGxlkTd6aoSPBXXjGtVkuw56YCsI",
            "Content-Type": "application/json",
        }
        self.api_url = 'http://mlops.huawei.com/mlops-service/api/v2/agentService/v1/chat/completions'

        self.memory_buffer = []  # Keep a buffer of recent memory entries
        self.actor_buffer = []
        self.max_memory = 4
        self.frm_interval = 30
        self.img_ids = set()
        self.max_input_frames = 15 if self.model == 'qwen3-vl-plus' else -1

        # 存每30S的Caption的一个本地地址，完成后会清空的
        self.intermed_cap_cache_path = config['event_caption_engine']['index_path']
        self.index_path = self.intermed_cap_cache_path + "scene_caption_results.json"
        if not os.path.exists(self.intermed_cap_cache_path):
            os.makedirs(self.intermed_cap_cache_path)
        else:
            if os.path.exists(self.index_path):
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self.loaded_data = json.load(f)
            else:
                self.loaded_data = []


    def detect(self, frame_queue, video_embeddings, **kwargs) -> List[Dict]:
        """detect"""
        results_list = self.detect_intermidiate_term(frame_queue, video_embeddings)
        logger.info(results_list)
        inter_term_index = self.build_index_data(results_list)
        self.loaded_data.append(inter_term_index[0])

        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.loaded_data, f, ensure_ascii=False, indent=2)

        return inter_term_index

    def uniform_sample(self, lst, target_len=20):
        if len(lst) <= target_len:
            return lst
        step = len(lst) / target_len
        return [lst[int(i * step)] for i in range(target_len)]

    def detect_intermidiate_term(self, frame_queue, video_embeddings):
        # 1. 读取并解析本地 JSON（只在第一次时执行）
        if not hasattr(self, "loaded_data"):  # 避免重复读取
            if os.path.exists(self.index_path):
                try:
                    with open(self.index_path, "r", encoding="utf-8") as f:
                        self.loaded_data = json.load(f)
                        if not isinstance(self.loaded_data, list):
                            self.loaded_data = []
                except json.JSONDecodeError:
                    self.loaded_data = []
            else:
                self.loaded_data = []

        # 2. 更新 memory_buffer（只保留最近 max_memory 条 caption）
        self.memory_buffer = [
            item.get("caption", "") for item in self.loaded_data[-self.max_memory:]
            if isinstance(item, dict) and "caption" in item
        ]

        # 3. 更新 actor_buffer（只保留最近 max_memory 条的去重参与人）
        all_recent_actors = []
        for item in self.loaded_data[-self.max_memory:]:
            persons = item.get("metadata", {}).get("参与人", [])
            if isinstance(persons, list):
                all_recent_actors.extend(persons)

        self.actor_buffer = list({
            p.strip() for p in all_recent_actors if isinstance(p, str) and p.strip()
        })

        image_cache = []
        if self.max_input_frames > 0:
            frame_queue = self.uniform_sample(frame_queue, self.max_input_frames)
        for i in range(len(frame_queue)):
            frame_info = frame_queue[i].frame_base64
            image_cache.append(frame_info)

        caption_result = []
        result = self.image_captioning_with_context(image_cache)
        caption_result.append(result)

        return caption_result

    def image_captioning_with_context(self, frames_base64):
        # 1. 构造前情提要（Memory）
        memory = "\n".join([f"{i + 1}. {cap}" for i, cap in enumerate(self.memory_buffer)]) or "无"

        # 2. 构造参与人列表（Actors）
        participant_str = "，".join(self.actor_buffer) if self.actor_buffer else "无可识别的参与人"

        # 1. 准备消息内容列表
        message_content = []

        # 2. 遍历所有base64图像
        for base64_image in frames_base64:
            # 为每张图片添加image_url格式
            img_dict = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpg;base64,{base64_image}"
                }
            }
            message_content.append(img_dict)

        # 3. 添加文本提示
        text_prompt = {
            "type": "text",
            "text": (
                "请从事件视角描述当前视频片段中的主要情节。\n\n"
                "如有提供“前情提要”，请参考其中已发生的事件，合理衔接当前片段中的内容，"
                "体现人物的移动、行为延续或新人物的加入；如无前情，则仅基于当前片段进行独立描述。\n\n"
                f"【前情提要】:\n{memory}\n\n"
                f"【前情参与人】：{participant_str}\n\n"
                "每条事件必须同时包含人物行为和事件发生地点，重点体现“谁在什么地方做了什么”。\n"
                "请注意，如果当前人物特征与前情参与人中某位高度相似，应使用一致的称呼，不要重复造新描述。\n"
                "例如：若前情已有‘穿蓝色上衣的人’，则后续继续用该称呼。\n\n"
                "请输出以下三个字段：\n"
                "- 事件描述：一句完整、自然的描述性话语，包含“场所 + 人物 + 行为”。\n"
                "- 参与人：人物名称列表。如不知道具体姓名，请用外貌、身份或服饰特征进行描述，例如 '戴眼镜的年轻女子'。\n"
                "- 地点：事件发生的具体场所。\n\n"
                "输出格式为 JSON 对象：\n"
                "{\n  \"事件描述\": \"...\",\n  \"参与人\": [...],\n  \"地点\": \"...\"\n}"
            )
        }
        message_content.append(text_prompt)

        messages = [
            {
                "role": "user",
                "content": message_content
            }
        ]

        json_data = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(
            url=self.api_url,
            json=json_data,
            headers=self.api_headers
        )

        generated_text = extract_generated_text(response)

        try:
            # return json.loads(completion.choices[0].message.content)
            return json.loads(generated_text)
        except Exception:
            logger.warning("LLM response format error, fallback to text")
            # return {"事件描述": completion.choices[0].message.content, "参与人": [], "地点": "未知"}
            return {"事件描述": generated_text, "参与人": [], "地点": "未知"}

    def build_index_data(self, results_list) -> List[Dict]:
        index_datas = []
        start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for idx, result in enumerate(results_list):

            # 将字符串转回 datetime 类型，方便加 30 秒
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

            # 加 self.frm_interval seconds
            end_time_dt = start_time_dt + timedelta(seconds=self.frm_interval)

            # 转回字符串形式
            end_time_str = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

            index_datas.append({
                "id": idx,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "scene_id": "",
                "scene_catogery": ["caption"],
                "caption": result.get("事件描述", ""),
                "metadata": {
                    "参与人": result.get("参与人", []),
                    "地点": result.get("地点", "")
                },
                "detail": []
            })

            # update time
            start_time_str = end_time_str

        return index_datas