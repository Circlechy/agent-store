"""
多模态视觉工具
支持图像识别、视频分析、摄像头模拟等功能

所有对外暴露的@tool装饰器函数都有对应的_internal内部函数，
server.py应该调用_internal函数而不是@tool装饰的函数
"""

import os
import json
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Union, Dict
from io import BytesIO
from datetime import datetime

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from carEmu.car_state import get_car_state, save_car_state, reload_car_state

import dotenv
dotenv.load_dotenv(dotenv_path=".env")

logger = logging.getLogger(__name__)

# 模型工厂
factory = ModelFactory()

# 视觉模型配置
VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "qwen-vl-plus")


def _encode_image_to_base64(image_path: str) -> str:
    """将图片编码为base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_image_mime_type(image_path: str) -> str:
    """获取图片MIME类型"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }
    return mime_types.get(ext, "image/jpeg")


async def _call_vision_model(image_data: Union[str, bytes], prompt: str) -> str:
    """调用视觉大模型"""
    model = factory.get_model(
        model_provider=os.getenv("MODEL_PROVIDER", "openai"),
        api_base=os.getenv("API_BASE"),
        api_key=os.getenv("API_KEY"),
        max_retries=3,
        timeout=60,
    )
    
    # 处理图片数据
    if isinstance(image_data, bytes):
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{image_base64}"
    elif image_data.startswith("http"):
        image_url = image_data
    elif image_data.startswith("data:"):
        # 已经是data URI格式
        image_url = image_data
    else:
        # 文件路径格式
        image_base64 = _encode_image_to_base64(image_data)
        mime_type = _get_image_mime_type(image_data)
        image_url = f"data:{mime_type};base64,{image_base64}"
    
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": prompt}
        ]
    }]
    
    try:
        response = await model.ainvoke(
            model_name=VISION_MODEL_NAME,
            messages=messages
        )
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        logger.error(f"视觉模型调用失败: {e}")
        return f"图像分析失败: {str(e)}"


# ============ 内部函数（供server.py调用） ============

def _analyze_image_internal(image_path: str, question: str = None) -> dict:
    """分析图片（内部函数）"""
    if not question:
        question = "请详细描述这张图片的内容，包括场景、主要物体、文字信息等。"
    
    prompt = f"""你是一个智能车载助手的视觉模块。请分析这张图片并回答用户的问题。

用户问题：{question}

请用简洁自然的中文回答，像在和驾驶员对话一样。如果识别出地点、店铺等，可以主动提供导航建议。"""

    # 检查是否是特殊路径格式（应该在 Agent 层面处理）
    if isinstance(image_path, str) and (
        image_path.startswith("global_state://") or 
        image_path.startswith("global://") or
        "global_state:" in image_path  # 支持 global_state:key 格式
    ):
        return {
            "success": False,
            "error": f"图片路径格式错误: {image_path}",
            "suggestion": "此路径格式应在 Agent 层面处理，请检查工具调用参数预处理逻辑"
        }
    
    # 检查是否是文件路径
    if not image_path.startswith("http") and not image_path.startswith("data:"):
        if not Path(image_path).exists():
            return {
                "success": False,
                "error": f"图片文件不存在: {image_path}",
                "suggestion": "请确认图片路径是否正确，或使用 base64 格式的 data URI"
            }
    
    try:
        # 同步包装异步调用
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _call_vision_model(image_path, prompt))
                result = future.result(timeout=60)
        else:
            result = asyncio.run(_call_vision_model(image_path, prompt))
        
        return {
            "success": True,
            "analysis": result,
            "image_path": image_path[:100] + "..." if len(image_path) > 100 else image_path
        }
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _set_camera_image_internal(camera_type: str, image_data: str) -> Dict:
    """设置摄像头图片（内部函数）"""
    state = reload_car_state()
    
    camera_map = {
        "front": "front_camera_image",
        "rear": "rear_camera_image", 
        "interior": "interior_camera_image",
        "left": "left_camera_image",
        "right": "right_camera_image"
    }
    
    if camera_type not in camera_map:
        return {"success": False, "error": f"未知摄像头类型: {camera_type}"}
    
    setattr(state.cameras, camera_map[camera_type], image_data)
    state.cameras.last_updated = datetime.now().isoformat()
    save_car_state()
    
    return {"success": True, "camera": camera_type, "updated": True}


def _get_camera_image_internal(camera_type: str) -> Dict:
    """获取摄像头图片（内部函数）"""
    state = reload_car_state()
    
    camera_map = {
        "front": "front_camera_image",
        "rear": "rear_camera_image",
        "interior": "interior_camera_image", 
        "left": "left_camera_image",
        "right": "right_camera_image"
    }
    
    if camera_type not in camera_map:
        return {"success": False, "error": f"未知摄像头类型: {camera_type}"}
    
    image_data = getattr(state.cameras, camera_map[camera_type], "")
    
    return {
        "success": True,
        "camera": camera_type,
        "has_image": bool(image_data),
        "image_data": image_data if image_data else None
    }


def _analyze_camera_view_internal(camera_type: str, question: str) -> Dict:
    """分析摄像头画面（内部函数）"""
    camera_result = _get_camera_image_internal(camera_type)
    
    if not camera_result.get("success"):
        return camera_result
    
    if not camera_result.get("has_image"):
        return {
            "success": False,
            "error": f"{camera_type}摄像头没有图片数据",
            "suggestion": "请先上传摄像头图片"
        }
    
    image_data = camera_result["image_data"]
    
    camera_context = {
        "front": "这是车辆前方摄像头拍摄的画面",
        "rear": "这是车辆后方/倒车摄像头拍摄的画面",
        "interior": "这是车内摄像头拍摄的画面",
        "left": "这是车辆左侧摄像头拍摄的画面",
        "right": "这是车辆右侧摄像头拍摄的画面"
    }
    
    context = camera_context.get(camera_type, "这是车载摄像头拍摄的画面")
    full_question = f"{context}。用户问题：{question}"
    
    return _analyze_image_internal(image_data, full_question)


def _ask_about_image_internal(image_data: str, question: str) -> Dict:
    """通用图片问答（内部函数）"""
    prompt = f"""你是一个智能车载助手。用户向你展示了一张图片并提出问题。

用户问题：{question}

请用简洁、友好的中文回答。如果图片内容与驾驶相关，可以给出相关建议。"""

    return _analyze_image_internal(image_data, prompt)


def _identify_vehicle_internal(image_data: str = None) -> Dict:
    """识别车辆（内部函数）"""
    if not image_data:
        camera_result = _get_camera_image_internal("front")
        if not camera_result.get("has_image"):
            return {
                "success": False,
                "error": "前摄像头没有图片，请提供图片或先设置摄像头图片"
            }
        image_data = camera_result["image_data"]
    
    question = """请识别这张图片中的车辆：
1. 车辆品牌（如特斯拉、宝马、奔驰、丰田等）
2. 车型/系列（如Model 3、3系、C级等）
3. 颜色
4. 大概车型类型（轿车/SUV/MPV/卡车等）
5. 与拍摄车辆的大概距离

如果能识别出具体车型，请给出估计的市场价格区间。
用简洁的中文回答。"""

    return _analyze_image_internal(image_data, question)


# ============ @tool装饰的工具函数 ============

@tool(name="analyze_image",
      description="分析图片内容，可以识别场景、物体、文字、地点等。",
      params=[
          Param(name="image_path", description="图片路径或URL或base64", type="str", required=True),
          Param(name="question", description="关于图片的问题", type="str", required=False)
      ])
def analyze_image(image_path: str, question: str = None) -> dict:
    """分析图片"""
    return _analyze_image_internal(image_path, question)


@tool(name="set_camera_image",
      description="设置模拟摄像头的图片",
      params=[
          Param(name="camera_type", description="摄像头类型：front/rear/interior/left/right", type="str", required=True),
          Param(name="image_data", description="图片数据", type="str", required=True)
      ])
def set_camera_image(camera_type: str, image_data: str) -> Dict:
    """设置摄像头图片"""
    return _set_camera_image_internal(camera_type, image_data)


@tool(name="get_camera_image",
      description="获取指定摄像头的当前图片",
      params=[
          Param(name="camera_type", description="摄像头类型", type="str", required=True)
      ])
def get_camera_image(camera_type: str) -> Dict:
    """获取摄像头图片"""
    return _get_camera_image_internal(camera_type)


@tool(name="analyze_camera_view",
      description="分析指定摄像头的画面并回答问题",
      params=[
          Param(name="camera_type", description="摄像头类型", type="str", required=True),
          Param(name="question", description="关于画面的问题", type="str", required=True)
      ])
def analyze_camera_view(camera_type: str, question: str) -> Dict:
    """分析摄像头画面"""
    return _analyze_camera_view_internal(camera_type, question)


@tool(name="identify_vehicle_ahead",
      description="识别前方车辆的品牌、型号、颜色等信息",
      params=[
          Param(name="image_data", description="图片数据，不提供则使用前摄像头", type="str", required=False)
      ])
def identify_vehicle_ahead(image_data: str = None) -> Dict:
    """识别前方车辆"""
    return _identify_vehicle_internal(image_data)


@tool(name="ask_about_image",
      description="通用图片问答",
      params=[
          Param(name="image_data", description="图片数据", type="str", required=True),
          Param(name="question", description="关于图片的问题", type="str", required=True)
      ])
def ask_about_image(image_data: str, question: str) -> Dict:
    """通用图片问答"""
    return _ask_about_image_internal(image_data, question)


@tool(name="identify_location",
      description="识别图片中的地点/建筑/商店",
      params=[
          Param(name="image_path", description="图片路径或URL", type="str", required=True)
      ])
def identify_location(image_path: str) -> dict:
    """识别地点"""
    question = """请仔细分析这张图片，识别地点/建筑/商店：
- 地点名称（如果能识别）
- 类型：商店/餐厅/景点/建筑/道路等
- 描述：简短描述
- 建议：是否需要导航或其他操作"""
    return _analyze_image_internal(image_path, question)


@tool(name="check_parking_spot",
      description="分析停车位图片，判断是否适合停车",
      params=[
          Param(name="image_path", description="停车位图片路径", type="str", required=True),
          Param(name="car_width", description="车辆宽度(米)", type="float", required=False)
      ])
def check_parking_spot(image_path: str, car_width: float = 1.9) -> dict:
    """检查停车位"""
    question = f"""分析这个停车位：
1. 停车位大小估计
2. 是否有障碍物
3. 周围车辆距离
4. 考虑到车辆宽度约{car_width}米，给出停车建议
请给出明确建议：推荐停/不推荐停/需谨慎"""
    return _analyze_image_internal(image_path, question)


@tool(name="read_road_sign",
      description="识别路牌、指示牌、交通标志",
      params=[
          Param(name="image_path", description="路牌图片路径", type="str", required=True)
      ])
def read_road_sign(image_path: str) -> dict:
    """读取路牌"""
    question = """识别这张图片中的路牌/指示牌：
1. 标志类型
2. 文字内容
3. 指示的方向/目的地
4. 对驾驶的建议"""
    return _analyze_image_internal(image_path, question)


@tool(name="analyze_dashcam_frame",
      description="分析行车记录仪画面",
      params=[
          Param(name="image_path", description="行车记录仪截图", type="str", required=True),
          Param(name="check_type", description="检查类型：safety/violation/damage", type="str", required=False)
      ])
def analyze_dashcam_frame(image_path: str, check_type: str = "safety") -> dict:
    """分析行车记录仪画面"""
    prompts = {
        "safety": "分析画面安全状况：前方道路、周围车辆、行人/障碍物、潜在风险",
        "violation": "检查是否有交通违章：信号灯、车道使用、是否违章",
        "damage": "检查是否有碰撞/刮蹭：与周围车辆距离、是否有接触迹象"
    }
    question = prompts.get(check_type, prompts["safety"])
    return _analyze_image_internal(image_path, question)


@tool(name="scan_car_interior",
      description="扫描车内情况",
      params=[
          Param(name="image_path", description="车内图片路径", type="str", required=True),
          Param(name="query", description="具体查找内容", type="str", required=False)
      ])
def scan_car_interior(image_path: str, query: str = None) -> dict:
    """扫描车内"""
    if query:
        question = f"请查看这张车内图片，回答：{query}"
    else:
        question = "描述车内情况：可见物品、座椅状态、是否有遗落物品、整洁程度"
    return _analyze_image_internal(image_path, question)


@tool(name="check_surroundings",
      description="检查车辆周围环境",
      params=[
          Param(name="focus", description="关注点：safety/parking/traffic", type="str", required=False)
      ])
def check_surroundings(focus: str = "safety") -> Dict:
    """检查周围环境"""
    cameras = ["front", "rear", "left", "right"]
    available = []
    results = {}
    
    for cam in cameras:
        cam_result = _get_camera_image_internal(cam)
        if cam_result.get("has_image"):
            available.append(cam)
    
    if not available:
        return {"success": False, "error": "没有可用的摄像头图片"}
    
    focus_prompts = {
        "safety": "分析安全隐患，包括行人、障碍物、其他车辆",
        "parking": "评估是否适合停车/倒车",
        "traffic": "描述当前交通状况"
    }
    
    for cam in available:
        cam_result = _get_camera_image_internal(cam)
        cam_names = {"front": "前方", "rear": "后方", "left": "左侧", "right": "右侧"}
        question = f"这是车辆{cam_names[cam]}的画面。{focus_prompts.get(focus, focus_prompts['safety'])}"
        analysis = _analyze_image_internal(cam_result["image_data"], question)
        results[cam] = analysis.get("analysis", "分析失败")
    
    return {"success": True, "focus": focus, "analyzed_cameras": available, "results": results}


if __name__ == "__main__":
    print("视觉工具模块加载成功")
