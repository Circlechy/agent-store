import base64
import hashlib
import io
import logging
import mimetypes
import os
import re
import struct
import traceback
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

# 配置日志输出到控制台，设置日志级别为 INFO
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def frames_to_base64(frame_queue):
    """
    将get_batch返回的批量帧转换为base64编码列表

    参数:
        batch_frames (numpy.ndarray): 形状为(N, H, W, 3)的numpy数组

    返回:
        list: 包含N个base64编码字符串的列表
    """
    base64_list = []
    for frame in frame_queue:
        # 验证数据类型和范围
        if frame.dtype != np.uint8 or frame.min() < 0 or frame.max() > 255:
            raise ValueError("Invalid frame format: must be uint8 in [0, 255]")
        img_base64 = img_np2base64(frame[0])
        base64_list.append(img_base64)

    return base64_list


def img_np2base64(frame):
    """
    frame 应为 RGB 格式 (720, 1280, 3)
    """
    # 检查图像格式
    if frame.shape[-1] != 3:
        raise ValueError("图像必须为 3 通道 RGB")

    # 直接保存 RGB 格式
    image = Image.fromarray(frame.astype('uint8'), 'RGB')

    # 保存到内存 buffer
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    # 转为 base64
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    return img_base64


def image_to_base64(file_path, with_prefix=False):
    """
    将图片文件转换为Base64编码字符串

    参数:
        file_path: 图片文件路径
        with_prefix: 是否包含数据URI前缀（默认为True）

    返回:
        Base64编码的字符串（包含或不包含前缀）
    """
    try:
        # 自动检测图片的MIME类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            # 如果无法检测或不是图片，使用默认类型
            mime_type = 'image/png'

        # 读取图片二进制数据
        with open(file_path, "rb") as img_file:
            img_bytes = img_file.read()

        # Base64编码
        base64_bytes = base64.b64encode(img_bytes)
        base64_str = base64_bytes.decode('utf-8')

        # 根据需要添加数据URI前缀
        if with_prefix:
            return f"data:{mime_type};base64,{base64_str}"
        else:
            return base64_str

    except Exception as e:
        raise RuntimeError(f"图片转换失败: {str(e)}") from e


def display_base64_image(base64_str):
    """
    将Base64字符串显示为图片
    参数:
        base64_str: Base64编码的图片字符串，可含或不含"data:image/..."前缀
    """
    # 检测并移除数据URI前缀（如"data:image/png;base64,"）
    if base64_str.startswith("data:image"):
        base64_data = re.sub(r"^data:image/\w+;base64,", "", base64_str)
    else:
        base64_data = base64_str

    try:
        # Base64解码
        img_data = base64.b64decode(base64_data)

        # 创建内存中的二进制流
        img_buffer = io.BytesIO(img_data)

        # 使用PIL打开图片
        img = Image.open(img_buffer)

        # 显示图片
        plt.figure(figsize=(8, 6))
        plt.imshow(img)
        plt.axis('off')  # 隐藏坐标轴
        plt.show()

        return "图片显示成功！"

    except Exception as e:
        return f"处理失败: {str(e)}"


def base64_to_int64(s: str) -> int:
    """支持超长Base64字符串的转换"""
    # 补全填充符号[1,3](@ref)
    s += '=' * (4 - (len(s) % 4))
    # 解码为二进制
    decoded = base64.urlsafe_b64decode(s)
    # 哈希压缩到8字节[5,8](@ref)
    hash_bytes = hashlib.md5(decoded).digest()[:8]
    return struct.unpack('>q', hash_bytes)[0]


def int64_to_base64(i: int) -> str:
    """保持与解码函数的对称性"""
    packed = struct.pack('>q', i)
    # 生成标准Base64[6](@ref)
    return base64.urlsafe_b64encode(packed).decode().rstrip('=')


def base64_to_image(base64_list):
    images = []
    for base64_str in base64_list:
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


def save_base64_as_image(base64_str: str, output_path: str) -> None:
    """
    将 Base64 编码的图片字符串保存为本地文件。

    参数:
        base64_str (str): 包含图片数据的 Base64 字符串（如 "data:image/png;base64,iVBORw0KG..."）
        output_path (str): 保存图片的本地路径（如 "output.png"）
    """
    try:
        # 移除可能存在的data URI前缀（如果有）
        if base64_str.startswith('data:image/'):
            base64_str = base64_str.split(',', 1)[1]

        # 2. 解码 Base64 数据
        image_bytes = base64.b64decode(base64_str)

        # 3. 保存为本地文件
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        logging.info(f"图片已保存到: {os.path.abspath(output_path)}")
    except Exception as e:
        logging.error(traceback.format_exc())


def save_bytes_to_file(bytes_data, output_path):
    try:
        with open(output_path, "wb") as f:
            f.write(bytes_data)
        logging.info(f"已保存到: {os.path.abspath(output_path)}")
    except Exception as e:
        logging.error(traceback.format_exc())


# 示例用法
if __name__ == "__main__":
    # 示例图片路径
    image_path = r"C:\Users\a00575982\Desktop\202503音视频流\code\StreamingQA2\data\car\img\test1_frame_1140.jpg"  # 替换为您的图片路径
    out_path = r"C:\Users\a00575982\Desktop\202503音视频流\code\StreamingQA2\data\car\img\output1.jpg"
    # 转换为不带前缀的纯Base64
    base64_raw = image_to_base64(image_path, with_prefix=False)
    print("\n纯Base64字符串（前100个字符）:", base64_raw[:100] + "...")

    # 显示图片验证转换结果（使用之前定义的display_base64_image函数）
    # display_base64_image(base64_raw)
    save_base64_as_image(base64_raw, out_path)
