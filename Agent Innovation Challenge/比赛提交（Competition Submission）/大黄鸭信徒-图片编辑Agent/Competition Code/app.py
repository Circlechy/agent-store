#!/usr/bin/env python
# coding: utf-8
"""
Intelligent Image Studio - 优化版后端API
改进点：
1. 优化提示词，提高工具调用成功率
2. 支持单张图片的多次连续编辑
3. 改进错误处理和日志记录
4. 优化对话状态管理
"""
import logging
import httpx


import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import threading
import json

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openjiuwen.agent.chat_agent import ChatAgent
from openjiuwen.agent.config.react_config import ConstrainConfig
from werkzeug.utils import secure_filename

import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from openjiuwen.agent.react_agent.react_agent import ReActAgent, create_react_agent_config
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

# 从当前目录导入image_editor_mcp模块
sys.path.insert(0, str(Path(__file__).parent))
from image_editor_mcp.tool_wrapper import create_image_editor_tools

# Flask应用初始化
app = Flask(__name__)
CORS(app)
os.environ["LLM_SSL_VERIFY"] = "false"

# 配置
UPLOAD_FOLDER = Path("static/uploads")
OUTPUT_FOLDER = Path("static/outputs")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 全局变量
agent_instance: Optional[ChatAgent] = None
agent_lock = threading.Lock()
conversations: Dict[str, Dict] = {}


def create_model_config():
    """创建模型配置"""
    model_info = BaseModelInfo(
        api_key="",
        api_base="",
        model="",
        timeout=300
    )

    return ModelConfig(
        model_provider="siliconflow",
        model_info=model_info
    )


async def get_agent():
    """获取或创建Agent实例（单例模式）"""
    global agent_instance

    if agent_instance is None:
        await Runner.start()

        # 优化后的系统提示词 - 支持VL模型直接生成图片
        agent_config = create_react_agent_config(
            agent_id="image_editor_agent",
            agent_version="1.0",
            description="智能图片编辑Agent",
            model=create_model_config(),
            prompt_template=[
                {
                    "role": "system",
                    "content": """你是一个专业的图片美化助手，拥有强大的视觉语言（VL）能力。
你的目标是为用户生成高质量的优化图片，重点关注喜庆模式和深色模式这两个核心场景。

核心工作方式：
1. 你可以选择两种方式完成任务：
   a) 直接使用你的VL能力生成优化图片（推荐用于艺术效果和风格转换）优先！
   b) 调用工具进行精确调整（适合参数化调整）优先使用滤镜，如果使用了滤镜，就不需要再调整亮度、对比度、饱和度、锐度了

2. 对于核心场景的详细要求：
   - 喜庆模式：增强暖色调（红色、金色为主），提高饱和度，增加亮度，营造节日氛围
   - 深色模式：降低亮度，增强对比度，调整色调为冷色调，营造深邃、专业的氛围
   - 智能美化：平衡亮度、对比度和饱和度，提升整体视觉效果
   - 提高亮度：适度增加亮度，同时保持细节和对比度

3. 图片生成要求：
   - 保持原图片的主题和结构不变
   - 提升图片的视觉吸引力和艺术效果
   - 确保输出图片清晰、高质量
   - 保存到指定的output_path

4. 可选工具：
   - 如果你选择使用工具，可以使用以下工具：
     - get_image_info：了解图片信息
     - adjust_brightness：调整亮度
     - adjust_contrast：调整对比度
     - adjust_saturation：调整饱和度
     - adjust_sharpness：调整锐度
     - resize_image：调整尺寸
     - crop_image：裁剪图片
     - rotate_image：旋转图片
     - apply_filter：应用滤镜
     - convert_format：转换格式

5. 工具使用规则（如果选择使用）：
   - 工具调用必须包含output_path参数
   - factor参数范围：0.0-2.0（1.0为原始值，<1.0减弱，>1.0增强）
   - 可以链式调用多个工具

最终目标：生成最符合用户需求的高质量图片，重点优化视觉效果和艺术表现力。"""
                }
            ]
        )
        agent_config.constrain.max_iteration = 10
        agent_instance = ReActAgent(agent_config)

        # 注册工具
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root) + os.pathsep + env.get('PYTHONPATH', '')

        image_tools = await create_image_editor_tools(
            server_name="image-editor-mcp-server",
            client_type="stdio",
            params={
                "command": sys.executable,
                "args": ["-m", "image_editor_mcp.server"],
                "env": env,
            }
        )

        agent_instance.add_tools(image_tools)

    return agent_instance


# ============ API 路由 ============

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """上传图片"""
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "没有上传文件"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"}), 400

    filename = secure_filename(file.filename)
    unique_id = uuid.uuid4().hex[:8]
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
    new_filename = f"{unique_id}_{filename}"

    filepath = UPLOAD_FOLDER / new_filename
    file.save(str(filepath))

    from PIL import Image
    img = Image.open(str(filepath))

    return jsonify({
        "success": True,
        "data": {
            "image_id": unique_id,
            "filename": new_filename,
            "path": str(filepath),
            "url": f"/static/uploads/{new_filename}",
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "size_bytes": filepath.stat().st_size
        }
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求，支持多次编辑"""
    data = request.json
    message = data.get('message', '').strip()
    image_path = data.get('image_path', '')
    conversation_id = data.get('conversation_id', '')

    if not message:
        return jsonify({"success": False, "error": "消息不能为空"}), 400

    if not image_path or not Path(image_path).exists():
        return jsonify({"success": False, "error": "图片路径无效"}), 400

    # 初始化或获取对话
    if conversation_id not in conversations:
        conversations[conversation_id] = {
            "id": conversation_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "operations": [],
            "original_image_path": image_path,  # 保存原始图片路径
            "current_image_path": image_path,  # 当前工作图片路径
            "edit_history": []  # 编辑历史
        }

    # 获取当前对话的工作图片
    current_image_path = conversations[conversation_id]["current_image_path"]

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            process_message(message, current_image_path, conversation_id)
        )

    result = run_async_task()
    return jsonify(result)


async def process_message(message: str, image_path: str, conversation_id: str):
    """处理消息并执行图片编辑"""
    try:
        agent = await get_agent()

        # 生成唯一的输出路径
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"./static/outputs/{timestamp}_{unique_id}_result.png"

        # 中间步骤的临时路径
        temp_path = f"./static/outputs/{timestamp}_{unique_id}_temp.png"

        # 构建优化后的查询 - 支持VL模型直接生成图片
        query = f"""图片优化任务：

输入图片: {image_path}
优化需求: {message}
输出路径: {output_path}

核心优化要求：
1. 保持原图片的主题和结构不变
2. 根据需求生成高质量的优化图片：
   - 喜庆模式：增强暖色调（红、金为主），提高饱和度，增加亮度，营造节日氛围
   - 深色模式：降低亮度，增强对比度，调整为冷色调，营造深邃专业氛围
   - 智能美化：平衡亮度、对比度和饱和度，提升整体视觉效果
   - 提高亮度：适度增加亮度，保持细节和对比度
3. 可以选择直接生成图片或使用工具辅助

可选工具（如需使用）：
- get_image_info: 获取图片信息
- adjust_brightness: 调整亮度
- adjust_contrast: 调整对比度
- adjust_saturation: 调整饱和度
- adjust_sharpness: 调整锐度
- resize_image: 调整尺寸
- crop_image: 裁剪图片
- rotate_image: 旋转图片
- apply_filter: 应用滤镜
- convert_format: 转换格式

请直接生成优化后的高质量图片，或使用工具完成任务。"""

        print(f"\n{'=' * 60}")
        print(f"开始处理消息: {message}")
        print(f"输入图片: {image_path}")
        print(f"输出路径: {output_path}")
        print(f"{'=' * 60}\n")

        # 调用Agent执行任务
        result = await Runner.run_agent(agent, {
            "conversation_id": conversation_id,
            "query": query
        })

        output = result.get('output', '')

        print(f"\n{'=' * 60}")
        print(f"Agent输出: {output}")
        print(f"{'=' * 60}\n")

        # 查找生成的输出文件
        output_files = []
        output_folder = Path("static/outputs")
        if output_folder.exists():
            # 获取最近生成的文件
            files = sorted(
                output_folder.glob("*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            for f in files[:5]:  # 返回最近5个文件
                output_files.append({
                    "filename": f.name,
                    "url": f"/static/outputs/{f.name}",
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })

        # 生成友好的响应消息
        if not output and output_files:
            output = "✅ 图片处理完成！请查看结果。"
        elif not output:
            output = "✅ 操作已执行。"

        # 更新对话历史
        conversations[conversation_id]["messages"].extend([
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
                "image_path": image_path
            },
            {
                "role": "assistant",
                "content": output,
                "timestamp": datetime.now().isoformat(),
                "output_files": output_files
            }
        ])

        # 更新当前工作图片路径（使用最新生成的文件）
        if output_files:
            latest_file_url = output_files[0]["url"]
            latest_file_path = f".{latest_file_url}"
            conversations[conversation_id]["current_image_path"] = latest_file_path
            conversations[conversation_id]["edit_history"].append({
                "operation": message,
                "input_path": image_path,
                "output_path": latest_file_path,
                "timestamp": datetime.now().isoformat()
            })

            print(f"✅ 更新工作图片: {latest_file_path}")

        return {
            "success": True,
            "response": output,
            "output_files": output_files,
            "conversation_id": conversation_id,
            "current_image": conversations[conversation_id]["current_image_path"],
            "edit_count": len(conversations[conversation_id]["edit_history"])
        }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"\n{'=' * 60}")
        print(f"❌ 处理错误:")
        print(error_detail)
        print(f"{'=' * 60}\n")

        return {
            "success": False,
            "error": str(e),
            "detail": error_detail
        }


@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    """分析图片"""
    data = request.json
    image_path = data.get('image_path', '')

    if not image_path or not Path(image_path).exists():
        return jsonify({"success": False, "error": "图片路径无效"}), 400

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(analyze_image_with_agent(image_path))

    result = run_async_task()
    return jsonify(result)


async def analyze_image_with_agent(image_path: str):
    """使用Agent分析图片"""
    try:
        agent = await get_agent()

        query = f"""请分析这张图片: {image_path}

步骤：
1. 调用 get_image_info(image_path='{image_path}') 获取详细信息
2. 基于获取的信息，分析并给出：
   - 图片基本情况（尺寸、格式、文件大小）
   - 质量评估（建议从亮度、对比度、清晰度等角度）
   - 具体改进建议
   - 推荐的编辑操作

要求：用简洁友好的语言，分点说明。立即调用工具！"""

        result = await Runner.run_agent(agent, {"query": query})

        return {
            "success": True,
            "analysis": result.get('output', ''),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc()
        }


@app.route('/api/quick-action', methods=['POST'])
def quick_action():
    """快速操作"""
    data = request.json
    action_type = data.get('action_type', '')
    image_path = data.get('image_path', '')

    # 优化后的快速操作指令 - 更具体的参数
    action_map = {
        "beautify": "智能美化这张图片：提升亮度(factor=1.2)、增强对比度(factor=1.3)、提高饱和度(factor=1.2)",
        "brighten": "提升亮度30%，使用factor=1.3",
        "dark_mode": "创建深色模式效果：降低亮度(factor=0.8)、增强对比度(factor=1.4)、提高锐度(factor=1.2)",
        "festive_mode": "创建喜庆模式效果：提高饱和度(factor=1.5)、提升对比度(factor=1.3)、增加亮度(factor=1.1)",
        "resize_social": "调整为1080x1080正方形尺寸"
    }

    if action_type not in action_map:
        return jsonify({"success": False, "error": "未知的操作类型"}), 400

    message = action_map[action_type]
    conversation_id = f"quick_{uuid.uuid4().hex[:8]}"

    # 初始化快速操作的对话
    conversations[conversation_id] = {
        "id": conversation_id,
        "created_at": datetime.now().isoformat(),
        "messages": [],
        "operations": [],
        "original_image_path": image_path,
        "current_image_path": image_path,
        "edit_history": []
    }

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            process_message(message, image_path, conversation_id)
        )

    result = run_async_task()
    return jsonify(result)


@app.route('/api/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """获取对话详情"""
    if conversation_id not in conversations:
        return jsonify({"success": False, "error": "对话不存在"}), 404

    return jsonify({
        "success": True,
        "conversation": conversations[conversation_id]
    })


@app.route('/api/conversation/<conversation_id>/reset', methods=['POST'])
def reset_conversation(conversation_id):
    """重置对话到原始图片"""
    if conversation_id not in conversations:
        return jsonify({"success": False, "error": "对话不存在"}), 404

    conv = conversations[conversation_id]
    conv["current_image_path"] = conv["original_image_path"]
    conv["messages"] = []
    conv["edit_history"] = []

    return jsonify({
        "success": True,
        "message": "已重置到原始图片",
        "current_image": conv["current_image_path"]
    })


@app.route('/static/<path:folder>/<path:filename>')
def serve_static(folder, filename):
    """提供静态文件服务"""
    static_dir = Path("static") / folder
    return send_from_directory(str(static_dir), filename)


@app.route('/')
def index():
    """首页"""
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Intelligent Image Studio 启动中...")
    print("=" * 60)
    print(f"📁 上传目录: {UPLOAD_FOLDER.absolute()}")
    print(f"📁 输出目录: {OUTPUT_FOLDER.absolute()}")
    print(f"🌐 访问地址: http://localhost:5000")
    print("=" * 60)
    print("\n优化说明:")
    print("✅ 改进了提示词，提高工具调用成功率")
    print("✅ 支持单张图片的多次连续编辑")
    print("✅ 增强了错误处理和日志记录")
    print("✅ 优化了对话状态管理")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=False)