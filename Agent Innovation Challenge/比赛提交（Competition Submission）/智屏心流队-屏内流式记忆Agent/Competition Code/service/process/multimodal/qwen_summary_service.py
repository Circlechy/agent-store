# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
import json
import traceback
from typing import Dict
import os
import difflib
import requests

from doc_process.utils import logging
from openai import OpenAI
from cn_clip.clip import load_from_name
from service.process.common.utils.common_utils import extract_generated_text
logger = logging.get_logger()


def init_vision_model(args):
    clip_model, preprocess = load_from_name('ViT-L-14', device=args.device_vision, download_root=os.path.dirname(args.vision_model_path))
    clip_model.eval()
    model_kwargs = {
        "model": clip_model,
        "image_processor": preprocess,
    }
    return model_kwargs


vision_model_inited_kwargs = {}
scene_pool = {}
# 预定义的合法分类标签
EVENT_CATEGORIES = [
    "travel_events", "catering_events", "social_events", "entertainment_events",
    "shop_events", "work_events", "incident_events", "meeting_events",
    "medicine_events", "not_related_events"
]

# 不要包含锁、logger、线程、pipeline对象，否则多进程启动失败！！！

class QwenSummaryService():
    """MultimodalProcessService"""

    def __init__(self, args, config_dict, **kwargs):
        #self.model = 'qwen-max-latest'
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
        self.api_url = 'https://openrouter.ai/api/v1/chat/completions'

        self.config_dict = config_dict
        global vision_model_inited_kwargs
        if not vision_model_inited_kwargs:
            vision_model_inited_kwargs = init_vision_model(args)
        self.model_kwargs = vision_model_inited_kwargs

    def process(self, input_dict: Dict) -> Dict:
        input_dict.update(self.model_kwargs)

        events = input_dict.get("inter_captions", [])
        if not isinstance(events, list):
            logger.warning("inter_captions is not a list. Fallback to empty.")
            events = []

        # 提取 caption 列表
        event_captions = [e.get("caption", "") for e in events if isinstance(e, dict) and "caption" in e]

        # 若无 caption，则直接返回 fallback
        if not event_captions:
            return {
                "type": "not_related_events",
                "总结描述": "暂无有效事件可供分析。"
            }

        # 提取所有参与人并去重（参与人是列表）
        raw_participants = []
        for e in events:
            if isinstance(e, dict):
                metadata = e.get("metadata", {})
                persons = metadata.get("参与人", [])
                if isinstance(persons, list):
                    raw_participants.extend(persons)
        unique_participants = list(set(p for p in raw_participants if isinstance(p, str) and p.strip()))

        # 构造编号提示
        caption_block = "\n".join([f"{i + 1}. {cap}" for i, cap in enumerate(event_captions)])
        participant_block = "，".join(unique_participants) if unique_participants else "无可识别的参与人"

        # 构造 Prompt
        prompt = (
            "你将接收到一个按时间顺序排列的事件列表，每条仅包含一段自然语言的事件描述：\n\n"
            f"{caption_block}\n\n"
            f"此外，这些事件中出现过以下参与人：{participant_block}\n\n"
            "请完成以下两个任务：\n\n"
            "---\n"
            "## 一、总结整组事件的一句话描述\n"
            "请从整组事件中提取主要情节，生成一句自然流畅的中文句子，概括：\n"
            "- 发生了什么（事件核心）\n"
            "- 谁参与了（参与人特征）\n"
            "- 在哪里发生（具体场景）\n\n"
            "请同时输出以下四个字段：\n"
            "- **事件描述**（一整句自然语言，总结事件主线）\n"
            "- **参与人**（人物特征描述，列表）\n"
            "- **地点**（事件发生地点，字符串）\n"
            "- **type**（事件类型，参考下方分类）\n\n"
            "---\n"
            "## 二、事件分类\n"
            "请根据你总结出的事件内容，将其归入以下十类中的一个：\n\n"
            "- **travel_events**：与出行、旅游、探访、差旅相关的事件\n"
            "- **catering_events**：与吃饭、点餐、做饭、用餐相关的事件\n"
            "- **social_events**：与朋友见面、交往、聚会、社交互动相关\n"
            "- **entertainment_events**：与看剧、玩游戏、观影、听音乐等娱乐活动相关\n"
            "- **shop_events**：与线下购物、电商购买、支付、试穿等相关\n"
            "- **work_events**：与办公、任务处理、文档撰写、工作沟通等相关\n"
            "- **incident_events**：突发、异常、事故类事件（如争执、摔倒、交通事故等）\n"
            "- **meeting_events**：正式或非正式会议、讨论、汇报、线上线下参与的活动\n"
            "- **medicine_events**：与医疗、服药、体检、挂号、诊疗等相关\n"
            "- **not_related_events**：与上述类别都不相关的事件\n\n"
            "> 请仔细判断整组事件的行为线索，仅选择最贴近的一类，不可多选。\n\n"
            "---\n"
            "## 输出格式:\n"
            "请以如下 JSON 格式输出：\n"
            "{\n"
            "  \"事件描述\": \"一句话概括这组事件的主要内容\",\n"
            "  \"参与人\": [\"参与人1\", \"参与人2\"],\n"
            "  \"地点\": \"事件发生的地点\",\n"
            "  \"type\": \"事件分类标签（如 travel_events）\"\n"
            "}"
        )

        messages = [{"role": "user", "content": prompt}]
        logger.info("summary request sending")

        try:
            # completion = self.client.chat.completions.create(
            #     model=self.model,
            #     messages=messages,
            #     response_format={"type": "json_object"}
            # )
            # content = completion.choices[0].message.content

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

            content = extract_generated_text(response=response)

            logger.info(f"summary response: {content}")

            result = json.loads(content)

            # 模糊归一化 type 字段
            raw_type = result.get("type", "")
            best_match = difflib.get_close_matches(raw_type, EVENT_CATEGORIES, n=1, cutoff=0.6)
            result["type"] = best_match[0] if best_match else "not_related_events"

            return result

        except Exception as e:
            logger.warning(f"Summary response parse failed: {e}")
            return {
                "type": "not_related_events",
                "总结描述": "模型响应无法解析，已回退默认输出。"
            }
