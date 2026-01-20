from openai import OpenAI
import numpy as np
import os

# 配置 DeepSeek
client = OpenAI(
    api_key="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", 
    base_url="https://openrouter.ai/api/v1"
)

def get_embedding(text: str):
    """
    调用 seed-1.6-flash API 将文本转化为向量
    """
    try:
        response = client.embeddings.create(
            model="BAAI/bge-m3",  # ❗注意：这是专门的模型名，不能写 deepseek-chat
            input=text
        )
        # 返回向量数据 (通常是一个长长的浮点数列表)
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding 失败: {e}")
        return []

def cosine_similarity(v1, v2):
    """计算两个向量的相似度 (余弦相似度)"""
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

# --- 测试 ---
if __name__ == "__main__":
    # 1. 把文字变数字
    vec1 = get_embedding("机器学习")
    vec2 = get_embedding("Machine Learning")
    vec3 = get_embedding("今天天气不错")

    # 2. 计算相似度
    score_1_2 = cosine_similarity(vec1, vec2) # 应该很高 (语义相同)
    score_1_3 = cosine_similarity(vec1, vec3) # 应该很低 (语义无关)

    print(f"机器学习 vs ML: {score_1_2}")  # 预期 > 0.6
    print(f"机器学习 vs 天气: {score_1_3}") # 预期 < 0.3