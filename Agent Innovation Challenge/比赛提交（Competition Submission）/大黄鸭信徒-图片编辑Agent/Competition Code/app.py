#!/usr/bin/env python
# coding: utf-8

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
from werkzeug.utils import secure_filename

import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from openjiuwen.agent.react_agent.react_agent import ReActAgent, create_react_agent_config
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.common.logging import logger

# 从当前目录导入image_editor_mcp模块
sys.path.insert(0, str(Path(__file__).parent))
from image_editor_mcp.tool_wrapper import create_image_editor_tools

from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param

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
api_key = ""
# 全局变量与配置
conversations: Dict[str, Dict] = {}
AGENT_ID = "image_editor_agent"

# --- 异步后台线程支持 (核心：彻底解决 MCP 跨 Loop 卡死问题) ---
# 原因深度分析：
# 1. MCP 客户端 (Stdio/SSE) 是资源管理器的单例，它在首次连接时与当前的 asyncio.loop 强绑定。
# 2. Flask 在处理异步请求时，每个请求都会创建一个全新的 event loop。
# 3. 如果不使用后台线程，第二个请求将尝试在 Loop-2 中调用绑定在 Loop-1 的 MCP 进程，导致死循环或静默卡死。
# 4. 因此，必须有一个持久存在的专用线程来“供养”这些 MCP 长连接。
_loop = asyncio.new_event_loop()


def _run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# 启动一个后台线程运行 asyncio 事件循环，确保 Agent 单例在同一个 loop 中运行
threading.Thread(target=_run_event_loop, args=(_loop,), daemon=True).start()


def run_async(coro):
    """在后台 loop 中同步运行协程并返回结果"""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


# --- 创建模型配置 ---
def create_model_config():
    """创建模型配置"""
    model_info = BaseModelInfo(
        api_key=api_key,
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1/",
        model="qwen3-vl-plus-2025-12-19",
        timeout=300,
    )

    return ModelConfig(
        model_provider="siliconflow",
        model_info=model_info
    )


# 从image_tools模块导入生成式图片编辑功能
from image_tools import generative_image_edit, set_api_key

# 设置image_tools模块的API密钥
set_api_key(api_key)


async def setup_agent():
    """初始化并注册 Agent 到全局 Runner"""
    try:
        await Runner.start()

        # 使用自定义的 StreamingReActAgent
        agent_config = create_react_agent_config(
            agent_id=AGENT_ID,
            agent_version="1.0",
            description="智能图片编辑Agent",
            model=create_model_config(),
            prompt_template=[
                {
                    "role": "system",
                    "content": """请以专业摄影师+后期修图师的双重身份，对这张图片进行深度诊断：
1. 光影：光源方向、强度、软硬质感，对立体感与氛围的影响；
2. 景深：虚化程度是否合理？主体与背景分离度如何？
3. 色彩：主色调、色温（偏冷/暖）、饱和度是否协调？有无色偏？
4. 白平衡：是否准确还原真实场景？或有意为之的艺术偏移？
5. 构图：是否运用经典法则？视觉焦点是否明确？有无干扰元素？
6. 技术质量：锐度、动态范围、噪点、镜头畸变/暗角问题；
7. 氛围情绪：传递何种情绪？时间感（晨/午/暮）是否明确？
8. 编辑建议：指出3个最值得优化的区域，并给出具体操作方向（如：局部压暗背景、提升青橙对比、模拟f/1.4浅景深）。

从以上角度分析这个图片的编辑步骤，
重要！！不要重复调用工具
重要！！只调用最多9次工具，只调用最多9次工具，首先预计需要调用的所有工具，如果工具比较多(4个以上)说明应该优先使用generative_image_edit工具生成后再微调
重要，不要重复调用generative_image_edit，调用generative_image_edit一定要保持原图片的主题不变
重要！！生成步骤之后直接开始工具调用，连续工具调用直到你觉得这张图已经完美，如果你不返回function call就表示直接结束

每次调用工具完成后重新审视编辑后的图片思考是否需要添加或修改之后的修改步骤，如果使用工具后效果不理想可以尝试使用上一步的图片重新规划。

图片生成要求：
   - 重要！！保持原图片的主题和结构不变
   - 提升图片的视觉吸引力和艺术效果
   - 确保输出图片清晰、高质量
   - 保存到指定的output_path

3. 可选工具：
   - 如果你选择使用工具，可以使用以下工具：
     - get_image_info：了解图片信息
     - adjust_brightness：调整亮度
     - adjust_contrast：调整对比度
     - adjust_saturation：调整饱和度
     - adjust_sharpness：调整锐度
     - resize_image：调整尺寸
     - crop_image：裁剪图片
     - rotate_image：旋转图片
     - convert_format：转换格式
     - generative_image_edit：生成式图片编辑，用于添加新元素（灯笼、气泡等）或大幅改变结构

4. 工具使用规则：
   - 工具调用必须包含output_path参数
   - factor参数范围：0.0-2.0（1.0为原始值，<1.0减弱，>1.0增强）
   - generative_image_edit 工具特别说明：当用户明确要求添加原图中不存在的物体（如：灯笼、气泡等）或需要进行大幅度的创意重构时，**必须**优先使用此工具。
     - 限制条件：图片宽度和高度必须在 512-2048 像素范围内
     - 预处理要求：如果图片尺寸超过限制，请先使用 resize_image 工具调整尺寸后再调用此工具
     - 参数要求：prompt 参数应包含具体描述，size 参数必须指定且符合尺寸限制
     - 格式要求：size 参数格式为 "width*height"，例如 "1024*1024"
   - 可以链式调用多个工具
   - 链式编辑：如果你需要分多步优化，请务必使用前一个工具返回的 'saved_path' 作为下一个工具的 'image_path'，确保每次迭代都使用最新修改后的图片。

最终目标：充分发挥 generative_image_edit 的创意能力与常规工具的精确控制能力，生成最符合用户需求的高质量图片。"""
                }
            ]
        )
        agent_config.constrain.max_iteration = 10
        agent_instance = ReActAgent(agent_config)

        # 核心：由 Runner 统一管理 Agent
        Runner.add_agent(AGENT_ID, agent_instance)

        # 注册工具服务器
        env = os.environ.copy()
        params = {
            "command": sys.executable,
            "args": ["-m", "image_editor_mcp.server"],
            "env": env
        }
        image_tools = await create_image_editor_tools(
            server_name="image-editor-mcp-server",
            client_type="stdio",
            params={
                "command": sys.executable,
                "args": ["-m", "image_editor_mcp.server"],
                "env": env,
            }
        )


        # 注册生成式编辑 LocalFunction 工具
        generative_tool = LocalFunction(
            name="generative_image_edit",
            description="对图片进行生成式编辑。可以添加新元素（如在场景中添加灯笼、节日装饰、气泡等）、改变图片结构或进行风格转变。这是唯一能往图中添加实物的工具。",
            params=[
                Param(name="image_path", description="输入图片的路径", param_type="string", required=True),
                Param(name="prompt", description="描述你想要进行的修改或添加的元素，例如：'在背景中添加红红火火的灯笼' 或 '给主体加上梦幻的气泡效果'", param_type="string", required=True),
                Param(name="output_path", description="保存输出图片的路径", param_type="string", required=True),
                Param(name="size", description="输出图片尺寸，格式为 'width*height'，例如 '1024*1024'", param_type="string", required=True),
            ],
            func=generative_image_edit
        )
        agent_instance.add_tools([*image_tools, generative_tool])

        logger.info(f"Agent {AGENT_ID} and MCP/Local tools registered successfully.")
    except Exception as e:
        import traceback
        logger.error(f"Failed to setup agent: {e}\n{traceback.format_exc()}")
        raise


# 在程序启动时就完成 Agent 注册，确保其在持久后台 loop 中运行
run_async(setup_agent())


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


def _extract_stream_text(chunk):
    """从流块中提取可显示的文本内容，处理嵌套字典"""
    if not hasattr(chunk, 'payload') or not isinstance(chunk.payload, dict):
        return ""

    val = chunk.payload.get("output")
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        # 兼容框架在结束时将 {"output": "...", "result_type": "answer"} 整体包裹的情况
        return val.get("output", "")
    return ""


def _create_stream_response(message, image_path, conversation_id):
    """创建流式响应的内部函数，供chat_stream和quick-action调用"""
    from flask import Response

    def generate():
        q = asyncio.Queue()

        async def _stream_to_queue():
            try:
                unique_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"./static/outputs/{timestamp}_{unique_id}_result.png"

                query = build_query(message, image_path, output_path)
                print(f"xjtest query {query}")

                # 核心：使用 Runner 托管的方法来运行流
                async for chunk in Runner.run_agent_streaming(AGENT_ID, {
                    "conversation_id": conversation_id,
                    "query": query,
                    "image_path": image_path,  # 传入当前图片路径供 Agent 初始化状态
                    "output_path": output_path
                }):
                    print(f"xjtest chunk{chunk}")
                    await q.put(chunk)
                await q.put(None)
            except Exception as e:
                import traceback
                await q.put({"error": str(e), "detail": traceback.format_exc()})
                await q.put(None)

        asyncio.run_coroutine_threadsafe(_stream_to_queue(), _loop)

        while True:
            chunk = run_async(q.get())
            if chunk is None:
                break

            if isinstance(chunk, dict) and "error" in chunk:
                yield f"data: {json.dumps({'success': False, 'error': chunk['error']})}\n\n"
                break

            payload = None

            # --- 解析 Chunk ---
            c_type = None
            c_payload = None

            # 情况 1: 带有 payload 属性的 Object (框架常用)
            if hasattr(chunk, 'payload'):
                c_payload = chunk.payload
                c_type = getattr(chunk, 'type', getattr(chunk, 'chunk_type', None))
            # 情况 2: 字典 (手动解析或某些流返回)
            elif isinstance(chunk, dict) and 'payload' in chunk:
                c_payload = chunk['payload']
                c_type = chunk.get('type') or chunk.get('chunk_type')

            if not c_type or not c_payload:
                # 兜底处理：如果 chunk 本身就是我们想要的 payload (某些简化情况)
                if isinstance(chunk, dict) and ('output' in chunk or 'result_type' in chunk):
                    c_type = 'answer'
                    c_payload = chunk
                else:
                    continue

            # --- 提取并分发 SSE 数据 ---
            if c_type == 'tracer_agent':
                tool_name = c_payload.get('name', 'unknown_tool')
                outputs = c_payload.get('outputs')
                
                if outputs is None:
                    # 工具调用发起 (Request)
                    payload = {"content": f"🛠️ 正在调用工具: {tool_name}", "type": "tool_request"}
                else:
                    # 工具调用完成 (Response)
                    saved_path = ""
                    # 1. 优先从 outputs.outputs (JSON string) 中找
                    try:
                        if isinstance(outputs, dict):
                            inner_val = outputs.get('outputs')
                            if isinstance(inner_val, str):
                                try:
                                    import json as json_lib
                                    inner_data = json_lib.loads(inner_val)
                                    saved_path = inner_data.get('saved_path', '')
                                except: pass
                            elif isinstance(inner_val, dict):
                                saved_path = inner_val.get('saved_path', '')
                    except: pass
                    
                    # 2. 如果没有，从 inputs.inputs.output_path 中找 (用户需求)
                    if not saved_path:
                        try:
                            inputs_group = c_payload.get('inputs', {}).get('inputs', {})
                            if isinstance(inputs_group, dict):
                                saved_path = inputs_group.get('output_path', '')
                        except: pass
                    
                    if saved_path:
                        payload = {
                            "content": f"✅ {tool_name} 执行完成", 
                            "type": "tool_response", 
                            "output_path": saved_path
                        }
                    else:
                        payload = {"content": f"✅ {tool_name} 执行完成", "type": "tool_response"}

            elif c_type == 'answer':
                # 处理最终回答或中间文本
                output_data = c_payload.get('output', {})
                if isinstance(output_data, dict):
                    content = output_data.get('output', '')
                    result_type = output_data.get('result_type', '')
                    
                    if result_type == 'answer':
                        # 最终答案
                        output_files = get_latest_outputs()
                        payload = {"content": content, "type": "final", "output_files": output_files}
                    else:
                        payload = {"content": content, "type": "answer"}
                elif isinstance(output_data, str):
                    payload = {"content": output_data, "type": "answer"}
            
            if payload:
                yield f"data: {json.dumps(payload)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/chat_stream', methods=['POST'])
def chat_stream():
    """流式聊天接口 (SSE)"""
    data = request.json
    message = data.get('message', '').strip()
    image_path = data.get('image_path', '')
    conversation_id = data.get('conversation_id', '')

    if not message:
        return jsonify({"success": False, "error": "消息不能为空"}), 400

    if not image_path or not Path(image_path).exists():
        return jsonify({"success": False, "error": "图片路径无效"}), 400

    # 以前端传入的图片地址为准，而不是通过系统去查session关联的图片
    return _create_stream_response(message, image_path, conversation_id)


def build_query(message, image_path, output_path):
    """构建查询 Prompt"""
    return f"""图片优化任务开始：

[当前工作流状态]
- 初始图片: {image_path}
- 最终目标路径: {output_path}
- 待处理需求: {message}

[执行准则]
1. 链式编辑：如果你需要分多步优化，请务必使用前一个工具返回的 'saved_path' 作为下一个工具的 'image_path'。
2. 最终输出：最后一个工具的 'output_path' 必须指向上面的最终目标路径。
3. 高效处理：避免重复调用功能相同的工具，每一步都应有明确的质量提升。
4. VL协同：你可以先用 VL 能力分析，再决定调用哪些工具。

请开始你的诊断与编辑流程。"""


def get_latest_outputs():
    """获取最近生成的输出文件"""
    output_files = []
    output_folder = Path("static/outputs")
    if output_folder.exists():
        files = sorted(
            output_folder.glob("*"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        for f in files[:5]:
            output_files.append({
                "filename": f.name,
                "url": f"/static/outputs/{f.name}",
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    return output_files


@app.route('/api/quick-action', methods=['POST'])
def quick_action():
    """快速操作 (流式) - 调用_create_stream_response函数"""
    data = request.json
    action_type = data.get('action_type', '')
    image_path = data.get('image_path', '')
    conversation_id = data.get('conversation_id', f"quick_{uuid.uuid4().hex[:8]}")

    # 优化后的快速操作指令 - 更具体的参数
    action_map = {
        "beautify": "按系统提示词优化这张图,保持原图尺寸",
        "crop_wallpaper": "将图片处理为iPhone全面屏壁纸。【核心约束：绝不能拉伸或变形图片】。必须使用resize_image工具将图片调整为纵向的iPhone 15 Pro Max分辨率（1002x2048），保持原图比例，采用智能填充或居中裁切方式适配，确保画面主体完整且位于视觉中心。",
        "dark_mode": "创建深色模式效果：比例 1:1，将图片改成深色模式，整体色调变暗，天空呈现深蓝色或藏青色，云朵颜色加深，山脉阴影更浓重，湖面颜色转为深墨绿色，树木颜色加深呈深绿色。",
        "festive_mode": "创建喜庆节日模式效果：营造极致温暖的节日氛围。请自然融入灯笼、彩灯串或节日装饰元素，使画面光彩照人。注意色彩平衡，色彩鲜艳高清，不要太红。",
        "resize_social": "调整为正方形尺寸（1:1），用于社交媒体发布。【严格要求：保持原图比例，不要拉伸】，请进行完美的居中裁剪适配。"
    }

    if action_type not in action_map:
        return jsonify({"success": False, "error": "未知的操作类型"}), 400

    message = action_map[action_type]

    if not image_path or not Path(image_path).exists():
        return jsonify({"success": False, "error": "图片路径无效"}), 400

    # 调用_create_stream_response函数，使用前端传入的图片地址
    return _create_stream_response(message, image_path, conversation_id)


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
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=False)
