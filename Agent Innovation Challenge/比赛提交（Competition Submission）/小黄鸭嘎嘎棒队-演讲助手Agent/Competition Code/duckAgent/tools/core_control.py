#!/usr/bin/env python3
import re


class CoreControl:
    """核心控制类（支持multimodal_matcher为None的兼容模式）"""

    def __init__(self, renderer, data_parser, multimodal_matcher=None):
        self.renderer = renderer
        self.data_parser = data_parser
        self.multimodal_matcher = multimodal_matcher
        self.elem_texts = data_parser.get_elem_texts()
        self.match_threshold = 0.2
        # 兼容multimodal_matcher为None的场景，默认空字典
        self.image_elems = (
            multimodal_matcher.image_elems
            if (multimodal_matcher and hasattr(multimodal_matcher, "image_elems"))
            else {}
        )

    def _text_similarity(self, input_text, elem_text):
        """精准文本相似度计算（无兜底）"""

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

    def process_multimodal_text(self, input_text):
        """兼容multimodal_matcher为None的处理逻辑"""
        self.renderer.clear_all()

        # 1. 当multimodal_matcher为None时，降级为本地文本匹配
        if not self.multimodal_matcher:
            return self._local_text_match(input_text)

        # 2. 有multimodal_matcher时，优先使用模型匹配
        try:
            match_res = self.multimodal_matcher.match(input_text)
            # 模型匹配无结果时，降级为本地文本匹配
            if not match_res.get("text_idx"):
                return self._local_text_match(input_text)

            # 高亮文本（仅模型匹配结果）
            self.renderer.show_highlight(match_res["text_idx"], "text")

            # 高亮图片（兼容图片索引不存在的场景）
            match_img_count = 0
            for img_idx in match_res["img_indices"]:
                if img_idx in self.image_elems:
                    img_coords = self.image_elems[img_idx]["coords"]
                    self.renderer.show_highlight(img_idx, "image", img_coords)
                    match_img_count += 1
                else:
                    # 仅警告，不抛出异常
                    print(f"警告：图片索引{img_idx}不存在，跳过该图片高亮")

            return (
                f"模型匹配结果 | 匹配文本[{match_res['text_idx']}]：{self.elem_texts[match_res['text_idx']]} | "
                f"匹配图片数量：{match_img_count} | "
                f"相似度：{match_res['similarity']:.3f}"
            )
        except Exception as e:
            # 模型匹配出错时，降级为本地文本匹配
            print(f"模型匹配出错：{str(e)}，降级为本地文本匹配")
            return self._local_text_match(input_text)

    def _local_text_match(self, input_text):
        """本地文本匹配兜底逻辑（无multimodal_matcher时使用）"""
        max_similarity = 0.0
        match_text_idx = None

        # 遍历所有文本元素计算相似度
        for idx, elem_text in self.elem_texts.items():
            similarity = self._text_similarity(input_text, elem_text)
            if similarity > max_similarity and similarity >= self.match_threshold:
                max_similarity = similarity
                match_text_idx = idx

        # 无匹配文本时返回提示
        if match_text_idx is None:
            return "无匹配内容（本地文本匹配未找到符合阈值的内容）"

        # 高亮匹配的文本
        self.renderer.show_highlight(match_text_idx, "text")

        return (
            f"本地匹配结果 | 匹配文本[{match_text_idx}]：{self.elem_texts[match_text_idx]} | "
            f"相似度：{max_similarity:.3f} | 无图片匹配（未启用多模态匹配器）"
        )

    # 兼容原有调用
    def process_text(self, input_text):
        return self.process_multimodal_text(input_text)
