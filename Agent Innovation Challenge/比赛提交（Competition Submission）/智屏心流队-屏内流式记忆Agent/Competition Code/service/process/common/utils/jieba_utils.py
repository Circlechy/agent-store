#   Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

"""jieba 分词工具"""
from typing import List, Any, Dict

import jieba


def jieba_to_es_format(text, cut_all=False) -> List[Dict]:  # 默认是精确模式，不是全模式
    """jieba 分词"""
    words = jieba.cut(text, cut_all=cut_all)
    result = []

    position = 0  # 记录当前词的位置
    start_offset = 0  # 记录当前词的起始位置

    for word in words:
        if word.strip():  # 忽略空白字符
            end_offset = start_offset + len(word)  # 计算结束位置

            token_data = {
                "token": word,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "type": "word",  # Elasticsearch 默认是 word 类型
                "position": position
            }
            result.append(token_data)

            # 更新 position 和 start_offset
            position += 1
            start_offset = end_offset  # 更新下一个词的起始位置

    return result


def jieba_bm25_texts(texts: List[str], **kwargs: Any) -> (bool, List[List[Dict]]):
    bm25s = []
    for text in texts:
        bm25 = jieba_to_es_format(text)
        bm25s.append(bm25)
    return True, bm25s
