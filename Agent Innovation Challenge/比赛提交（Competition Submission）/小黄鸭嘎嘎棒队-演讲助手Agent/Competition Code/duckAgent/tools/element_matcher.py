#!/usr/bin/env python3
import re
from typing import Dict, Optional, Tuple, List
import threading


class ElementMatcher:
    """单例版元素匹配器（支持先初始化数据，后流式匹配）"""

    # 单例核心
    _instance: Optional["ElementMatcher"] = None
    _instance_lock = threading.Lock()

    # 类级属性：存储全局数据（流式节点可访问）
    _elem_texts: Dict = {}
    _image_elems: Dict = {}
    _match_threshold: float = 0.2
    _multimodal_matcher = None

    # ====================== 单例接口 ======================
    @classmethod
    def get_instance(cls) -> "ElementMatcher":
        """获取单例实例（全局唯一）"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ====================== 数据初始化接口（window_init中调用） ======================
    @classmethod
    def init_data(
        cls, elem_texts: Dict, image_elems: Dict = None, match_threshold: float = 0.2
    ):
        """
        初始化匹配器数据（window_init中调用，只需调用一次）
        :param elem_texts: 文本元素字典 {元素ID: 文本内容, ...}
        :param image_elems: 图片元素字典 {图片ID: {"coords": (x,y,w,h), ...}, ...}
        :param match_threshold: 匹配阈值
        """
        cls._elem_texts = elem_texts or {}
        cls._image_elems = image_elems or {}
        cls._match_threshold = match_threshold
        print(
            f"[ElementMatcher] 已初始化数据：文本元素{len(cls._elem_texts)}个，图片元素{len(cls._image_elems)}个"
        )

    @classmethod
    def set_multimodal_matcher(cls, multimodal_matcher):
        """设置多模态匹配器（window_init中可选调用）"""
        cls._multimodal_matcher = multimodal_matcher
        print(
            f"[ElementMatcher] 已设置多模态匹配器：{type(multimodal_matcher).__name__}"
        )

    # ====================== 私有方法 ======================
    def __init__(self):
        """私有构造函数（禁止外部实例化）"""
        if ElementMatcher._instance is not None:
            raise RuntimeError("请通过get_instance()获取ElementMatcher实例！")

    def _text_similarity(self, input_text: str, elem_text: str) -> float:
        """精准文本相似度计算"""

        def preprocess(text):
            text = text.lower()
            text = re.sub(r"[^\u4e00-\u9fff\s]", "", text)  # 仅保留中文
            text = re.sub(r"\s+", "", text)
            return text

        input_proc = preprocess(input_text)
        elem_proc = preprocess(elem_text)

        if not input_proc or not elem_proc:
            return 0.0
        common_chars = set(input_proc) & set(elem_proc)
        return len(common_chars) / max(len(input_proc), len(elem_proc))

    # ====================== 流式匹配接口（核心） ======================
    def match(self, input_text: str) -> Dict:
        """
        流式匹配接口（只需传入输入文本，无需传elem_texts等）
        :return: 匹配结果字典
        """
        # 校验数据是否已初始化
        if not self._elem_texts:
            return {
                "text_idx": None,
                "text_content": "",
                "text_similarity": 0.0,
                "img_indices": [],
                "img_coords_map": {},
                "match_type": "error",
                "message": "错误：ElementMatcher尚未初始化数据，请先调用init_data()！",
            }

        # 1. 优先使用多模态模型匹配
        if self._multimodal_matcher:
            try:
                match_res = self._multimodal_matcher.match(input_text)
                text_idx = match_res.get("text_idx")

                # 模型匹配有结果
                if text_idx and text_idx in self._elem_texts:
                    img_indices = []
                    img_coords_map = {}
                    # 过滤有效图片
                    for img_idx in match_res.get("img_indices", []):
                        if img_idx in self._image_elems:
                            img_indices.append(img_idx)
                            img_coords_map[img_idx] = self._image_elems[img_idx][
                                "coords"
                            ]
                        else:
                            print(f"警告：图片索引{img_idx}不存在")

                    return {
                        "text_idx": text_idx,
                        "text_content": self._elem_texts[text_idx],
                        "text_similarity": match_res.get("similarity", 0.0),
                        "img_indices": img_indices,
                        "img_coords_map": img_coords_map,
                        "match_type": "model",
                        "message": (
                            f"模型匹配结果 | 匹配文本[{text_idx}]：{self._elem_texts[text_idx]} | "
                            f"匹配图片数量：{len(img_indices)} | 相似度：{match_res.get('similarity', 0.0):.3f}"
                        ),
                    }
            except Exception as e:
                print(f"模型匹配出错：{str(e)}，降级为本地文本匹配")

        # 2. 降级为本地文本匹配
        max_similarity = 0.0
        match_text_idx = None
        for idx, elem_text in self._elem_texts.items():
            similarity = self._text_similarity(input_text, elem_text)
            if similarity > max_similarity and similarity >= self._match_threshold:
                max_similarity = similarity
                match_text_idx = idx

        # 无匹配结果
        if match_text_idx is None:
            return {
                "text_idx": None,
                "text_content": "",
                "text_similarity": 0.0,
                "img_indices": [],
                "img_coords_map": {},
                "match_type": "none",
                "message": "无匹配内容（本地文本匹配未找到符合阈值的内容）",
            }

        # 本地匹配有结果
        return {
            "text_idx": match_text_idx,
            "text_content": self._elem_texts[match_text_idx],
            "text_similarity": max_similarity,
            "img_indices": [],
            "img_coords_map": {},
            "match_type": "local",
            "message": (
                f"本地匹配结果 | 匹配文本[{match_text_idx}]：{self._elem_texts[match_text_idx]} | "
                f"相似度：{max_similarity:.3f} | 无图片匹配（未启用多模态匹配器）"
            ),
        }
