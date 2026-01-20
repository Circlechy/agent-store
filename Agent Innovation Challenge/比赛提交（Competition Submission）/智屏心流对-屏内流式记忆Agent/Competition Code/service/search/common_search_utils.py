import base64
from io import BytesIO

from PIL import Image


def parse_img(text_recall_ans):
    images = []
    for recall_ans in text_recall_ans.get("data", []):
        base64_str = recall_ans.get("metadata", {}).get("base64", "")
        # 移除可能存在的data URI前缀（如果有）
        if base64_str.startswith('data:image/'):
            base64_str = base64_str.split(',', 1)[1]

        # 解码 base64 字符串为字节数据
        image_data = base64.b64decode(base64_str)

        # 将字节数据放入BytesIO对象中
        image_io = BytesIO(image_data)

        # 使用PIL打开图像
        image = Image.open(image_io)
        images.append(image)
    return images


def parse_vector_img(vector_results):
    return [Image.open(vector_result) for vector_result in vector_results]
