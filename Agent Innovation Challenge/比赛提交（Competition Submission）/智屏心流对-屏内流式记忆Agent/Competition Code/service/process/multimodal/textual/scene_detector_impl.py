#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any

import numpy as np
import torch
import requests
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

logger = logging.get_logger()


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




def load_cache(ug_info):
    cache = {}
    filename = f"llms_cache{ug_info}"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line.strip())
                    cache.update(item)
                except Exception:
                    continue
    return cache


def append_cache(ug_info, base64_image, result):
    filename = f"llms_cache{ug_info}"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps({base64_image: result}, ensure_ascii=False) + "\n")


class FusionSceneDetectorAdapterImpl(SceneDetector):
    """SceneDetector"""

    def __init__(self, **kwargs):

        #self.model = 'qwen-vl-max-latest'
        # self.model = 'qwen3-vl-plus'
        # api_key = 'sk-857eab32bd8d4a069142b41b4a473786'
        # base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        # self.client = OpenAI(api_key=mlops_api_key, base_url=mlops_base_url)
        
        self.model = 'qwen3-vl-32b-instruct-npu'
        self.api_headers = {
            "Authorization": "Bearer sk-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50TmFtZSI6InVua25vd24iLCJhY2NvdW50SWQiOiJkNTk5MDA0NTQiLCJrZXlWZXJzaW9uIjoiMi4wIiwiYWNjb3VudE5hbWUiOiJkb25neXVrdW4iLCJ0ZW5hbnRJZCI6IjM3ZmI2OTU5NWVlMjYxOGM2ZTI5ODY2NzAyMWQyNmExIn0.cqH9PEeAza20JbyXGxlkTd6aoSPBXXjGtVkuw56YCsI",
            "Content-Type": "application/json",
        }
        self.api_url = 'http://mlops.huawei.com/mlops-service/api/v2/agentService/v1/chat/completions'

        self.img_ids = set()
        self.ug_client = UgClient()
        self.nearline_ug_info_queue = kwargs.get("nearline_ug_info_queue")
        self.nearline_es_queue = kwargs.get("nearline_es_queue")
        self.ug_write_dict = kwargs.get("ug_write_dict")

    def detect(self, frame_queue, video_embeddings, **kwargs) -> List[Dict]:
        """detect"""
        results_list = self.detect_short_term(frame_queue, video_embeddings)
        logger.info(results_list)
        return results_list

    def detect_short_term(self, frame_queue, video_embeddings):
        frames_np = [frame_info.frame_np for frame_info in frame_queue]
        frames_base64 = [frame_info.frame_base64 for frame_info in frame_queue]

        # 往UG中写入mock信息
        if self.ug_write_dict:
            for base64 in frames_base64:
                if base64 in self.ug_write_dict and self.nearline_ug_info_queue:
                    self.nearline_ug_info_queue.append("往UG写入：{}".format(self.ug_write_dict[base64]))

        # 生成caption
        ug_infos = self.ug_client.search("")
        ug_info = "\n".join(ug_infos)

        start_time = time.time()
        result_list = []
        result = self.image_parsing(ug_info, frames_base64)
        result_list.append(result)

        logger.info("gen caption cost time={}".format(time.time() - start_time))

        # 塞入到队列中
        if self.nearline_ug_info_queue:
            self.nearline_ug_info_queue.append("从UG读取：{}".format(ug_info))
        if self.nearline_es_queue:
            self.nearline_es_queue.append("\n".join(result_list))

        return result_list

    def image_parsing(self, ug_info: str, frames_base64):
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
        # text_prompt = {
        #     "type": "text",
        #     "text": (
        #         "请根据图片中的内容完成回答以下问题：\n"
        #         f"1. 图中是否存在车牌包含{self.ug_client.search('车牌')}的车，"
        #         "如果存在请回复车牌的请车位，如果不存在请直接回答“未找到车辆”，禁止做任何解释性描述\n"
        #         "2. 请找到图中存在哪些个人物品并说明所有个人物品的位置"
        #     )
        # }
        text_prompt = {
            "type": "text",
            "text": (
                "请根据图片中的内容完成回答以下问题：\n"
                "1. 请找到图中存在哪些个人物品并说明所有个人物品的位置。"
                "2. 请从这些图像中识别和提取到主要的文字内容，提取文字的要求包括:"
                "  1) 如果某段文字在不同帧中逐渐出现或被遮挡后逐渐完整，请将这些零散的部分合并为一段完整的文字"
                "  2) 这些帧是连续的，很多文字会在多帧中重复出现，请只保留一次"
                "  3) 在输出时，尽量保留视频中出现的有效、重要文字（如标题、字幕、标识、提示信息等），避免输出过于零散、无意义的碎片"
                "  4) 输出结果时，请以自然、连贯的方式呈现，确保文字完整、可读"
            )
        }
        message_content.append(text_prompt)

        # 4. 创建ChatCompletion请求
        # completion = self.client.chat.completions.create(
        #     model=self.model,
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": message_content
        #         }
        #     ],
        # )

        messages = [
            {
                "role": "user",
                "content": message_content
            }
        ]

        json_data = {
            "model": self.model,
            "messages": messages
        }

        print(f"========================================={os.environ['http_proxy']}, {os.environ['https_proxy']}")
        start_time = time.perf_counter()
        response = requests.post(
            url=self.api_url,
            json=json_data,
            headers=self.api_headers
        )
        logger.info(f"FusionSceneDetectorAdapterImpl api response time: {time.perf_counter() - start_time}")
        
        print(f"=====================================")
        print(extract_generated_text(response))
        print(f"=====================================end===========================")

        return extract_generated_text(response=response)


class ParkingSceneDetectorAdapterImpl(SceneDetector):
    """SceneDetector"""

    def __init__(self):

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

        self.img_ids = set()
        self.ug_client = UgClient()

    def detect(self, frame_queue, video_embeddings, **kwargs) -> List[Dict]:
        """detect"""
        results_list = self.detect_short_term(frame_queue, video_embeddings)
        short_term_index = self.build_index_data(results_list)
        return short_term_index

    def load_cache(self, ug_info):
        cache = {}
        filename = f"llms_cache{ug_info}"
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line.strip())
                        cache.update(item)
                    except Exception:
                        continue
        return cache

    def append_cache(self, ug_info, base64_image, result):
        filename = f"llms_cache{ug_info}"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps({base64_image: result}, ensure_ascii=False) + "\n")

    def detect_short_term(self, frame_queue, video_embeddings):
        base64_image_list = frames_to_base64(frame_queue)
        cur_img_ids = set(base64_to_int64(base64_image) for base64_image in base64_image_list)
        self.img_ids = self.img_ids.union(cur_img_ids)
        logger.info("num={},img_ids={}".format(len(self.img_ids), self.img_ids))
        ug_infos = self.ug_client.search("")
        ug_info = "\n".join(ug_infos)
        cache = self.load_cache(ug_info)
        parking_spot_list = []
        for base64_image in base64_image_list:
            if base64_image in cache:
                result = cache[base64_image]
            else:
                result = self.image_parsing(ug_info, base64_image)
                self.append_cache(ug_info, base64_image, result)
            parking_spot_list.append(result)
        parking_spot_list = [parking_spot for parking_spot in parking_spot_list if '无' not in parking_spot]
        # todo:@hy
        return parking_spot_list

    def image_parsing(self, ug_info: str, base64_image):
        messages = [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/jpg;base64,{base64_image}'},
                    },
                    {'type': 'text',
                        'text': f'请直接回答车牌号包含{ug_info}的车的停车位是多少，不要做任何解释。如果图片中没有上述信息，请直接回答：无'},
                ],
            }
        ]

        # completion = self.client.chat.completions.create(
        #     model=self.model,
        #     messages=messages
        # )

        json_data = {
            "model": self.model,
            "messages": messages
        }

        response = requests.post(
            url=self.api_url,
            json=json_data,
            headers=self.api_headers
        )

        # return completion.choices[0].message.content
        return extract_generated_text(response=response)

    def build_index_data(self, results_list) -> List[Dict]:
        # todo:@hy
        # build short_term_detector_result to short_term_index_schema
        # todo: 使用图片base64转为int64作为es id。
        ug_infos = self.ug_client.search("")
        ug_info = "\n".join(ug_infos)
        index_datas = []
        for result in results_list:
            index_datas.append({
                "id": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scene_id": "",
                "scene_catogery": [
                    "car",
                    "card",
                    "meeting"
                ],
                "caption": f" My car with license plate {ug_info} is parked in parking lot {result}",
                "metadata": {
                },
                "detail": [
                    {
                        "category": "",
                        "ocr": "",
                        "location": "",
                        "caption": "",
                        "metadata": {
                        }
                    }
                ]
            })
        return index_datas


class SeekingSceneDetectorAdapterImpl(SceneDetector):
    """SceneDetector"""

    def __init__(self):

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


        self.img_ids = set()
        self.ug_client = UgClient()

    def detect(self, frame_queue, video_embeddings, **kwargs) -> List[Dict]:
        """detect"""
        results_list = self.detect_short_term(frame_queue, video_embeddings)
        logger.info(results_list)
        short_term_index = self.build_index_data(results_list)
        return short_term_index

    def load_cache(self, ug_info):
        cache = {}
        filename = f"llms_cache{ug_info}"
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line.strip())
                        cache.update(item)
                    except Exception:
                        continue
        return cache

    def append_cache(self, ug_info, base64_image, result):
        filename = f"llms_cache{ug_info}"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps({base64_image: result}, ensure_ascii=False) + "\n")

    def detect_short_term(self, frame_queue, video_embeddings):
        base64_image_list = frames_to_base64(frame_queue)
        cur_img_ids = set(base64_to_int64(base64_image) for base64_image in base64_image_list)
        self.img_ids = self.img_ids.union(cur_img_ids)
        logger.info("num={},img_ids={}".format(len(self.img_ids), self.img_ids))
        ug_infos = self.ug_client.search("")
        ug_info = "\n".join(ug_infos)
        cache = self.load_cache(ug_info)

        parking_spot_list = []
        for base64_image in base64_image_list:
            if base64_image in cache:
                result = cache[base64_image]
            else:

                result = self.image_parsing(ug_info, base64_image)
                self.append_cache(ug_info, base64_image, result)
            parking_spot_list.append(result)
        parking_spot_list = [parking_spot for parking_spot in parking_spot_list if '无' not in parking_spot]
        # todo:@hy
        return parking_spot_list

    def image_parsing(self, ug_info: str, base64_image):
        messages = [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/jpg;base64,{base64_image}'},
                    },
                    {'type': 'text',
                        'text': f'Please indicate the locations of all personal items in the image (e.g., ID cards, keys, glasses, wallet, mobile phone, earphones, watch, lipstick, water bottle, etc.).'},
                ],
            }
        ]

        # completion = self.client.chat.completions.create(
        #     model=self.model,
        #     messages=messages
        # )

        json_data = {
            "model": self.model,
            "messages": messages
        }

        response = requests.post(
            url=self.api_url,
            json=json_data,
            headers=self.api_headers
        )

        # return completion.choices[0].message.content
        return extract_generated_text(response=response)

    def build_index_data(self, results_list) -> List[Dict]:
        # todo:@hy
        # build short_term_detector_result to short_term_index_schema
        # todo: 使用图片base64转为int64作为es id。
        index_datas = []
        for result in results_list:
            index_datas.append({
                "id": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scene_id": "",
                "scene_catogery": [
                    "car",
                    "card",
                    "meeting"
                ],
                "caption": result,
                "metadata": {
                },
                "detail": [
                    {
                        "category": "",
                        "ocr": "",
                        "location": "",
                        "caption": "",
                        "metadata": {
                            "coordinate": ""
                        }
                    }
                ]
            })
        return index_datas
