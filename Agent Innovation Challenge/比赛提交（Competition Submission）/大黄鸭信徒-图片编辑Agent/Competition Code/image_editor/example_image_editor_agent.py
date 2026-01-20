#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""
Example: Image Editor Agent using MCP Protocol
Demonstrates how to create an agent with image editing capabilities.
"""

import asyncio
import os
import sys
from pathlib import Path

# Set SSL verification to false (required for some API providers)
os.environ.setdefault("LLM_SSL_VERIFY", "false")

# Add parent directory to path to import openjiuwen modules and image_editor_mcp
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from openjiuwen.agent.react_agent.react_agent import ReActAgent, create_react_agent_config
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from image_editor_mcp.tool_wrapper import create_image_editor_tools


def create_model_config(
    model_name: str = "",
    api_key: str = "",
    api_base: str = "",
):
    """Create model configuration for ReActAgent"""
    from openjiuwen.core.utils.llm.base import BaseModelInfo

    model_info = BaseModelInfo(
        api_key=api_key,
        api_base=api_base,
        model=model_name,
        timeout=300  # 5 minutes timeout (reduced from 20 minutes to avoid hanging)
    )

    return ModelConfig(
        model_provider="siliconflow",  # 使用 siliconflow 作为模型提供商
        model_info=model_info
    )


async def create_image_editor_agent():
    """Create an agent with image editing capabilities."""

    # Start Runner
    await Runner.start()

    # Create agent configuration
    agent_config = create_react_agent_config(
        agent_id="image_editor_agent",
        agent_version="1.0",
        description="An agent specialized in image editing tasks",
        model=create_model_config(
            model_name="Qwen/Qwen3-VL-32B-Instruct",  # 使用 SiliconFlow 上的正确模型名称
            api_key="sk-iimeqzridkmqtnoggoinouysymkkgwttphygwapjjtxcaitp",
            api_base="https://api.siliconflow.cn/v1",
        ),
        prompt_template=[
            {
                "role": "system",
                "content": (
                    "You are an expert image editing assistant. "
                    "You have access to various image editing tools including:\n"
                    "- adjust_brightness: Adjust image brightness\n"
                    "- adjust_contrast: Adjust image contrast\n"
                    "- adjust_saturation: Adjust color saturation\n"
                    "- adjust_sharpness: Adjust image sharpness\n"
                    "- resize_image: Resize images\n"
                    "- crop_image: Crop images to specific regions\n"
                    "- rotate_image: Rotate images by angle\n"
                    "- apply_filter: Apply filters (blur, sharpen, etc.)\n"
                    "- convert_format: Convert image formats\n"
                    "- get_image_info: Get image information\n\n"
                    "When users request image editing, use the appropriate tools. "
                    "Always provide clear feedback about what operations you're performing."
                ),
            }
        ]
    )
    
    # Create agent with token limit (SiliconFlow max_prompt_tokens is 163840, 
    # set to 150000 to leave room for response)
    agent = ReActAgent(agent_config)
    
    # Register image editor tools from MCP server
    # Using stdio client (runs the MCP server as a subprocess)
    # Set PYTHONPATH to include project root so image_editor_mcp can be imported
    import os
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
    
    # Add tools to agent
    agent.add_tools(image_tools)
    
    return agent


async def run_image_editing():
    """具体测试案例：完整的图片编辑流程"""
    import os

    try:
        # 创建 Agent
        agent = await create_image_editor_agent()
        
        # 使用指定的测试图片（相对于脚本文件的路径）
        script_dir = Path(__file__).parent
        test_image = str(script_dir / "1.png")
        
        if not os.path.exists(test_image):
            print(f"错误: 图片文件不存在: {test_image}")
            print(f"请确保图片文件存在于: {script_dir}")
            return
        
        print(f"使用图片: {test_image}")
        
        # 测试1: 获取图片信息
        result = await Runner.run_agent(agent, {
            "query": f"获取图片 '{test_image}' 的详细信息"
        })
        print(f"图片信息: {result.get('output', '')}")
        
        # 准备输出文件路径（与输入图片同一目录）
        script_dir = Path(__file__).parent
        output_bright = str(script_dir / "1_bright.png")
        output_enhanced = str(script_dir / "1_enhanced.png")
        output_resized = str(script_dir / "1_resized.png")
        
        # 测试2: 调整亮度
        result = await Runner.run_agent(agent, {
            "query": f"将图片 '{test_image}' 的亮度提高30%，保存为 '{output_bright}'"
        })
        print(f"亮度调整: {result.get('output', '')}")
        
        # 测试3: 调整对比度和饱和度
        result = await Runner.run_agent(agent, {
            "query": f"对图片 '{test_image}' 进行以下处理：1) 对比度提高20% 2) 饱和度提高15% 3) 保存为 '{output_enhanced}'"
        })
        print(f"图片增强: {result.get('output', '')}")
        
        # 测试4: 调整大小
        result = await Runner.run_agent(agent, {
            "query": f"将图片 '{test_image}' 调整为宽度400像素（保持宽高比），保存为 '{output_resized}'"
        })
        print(f"尺寸调整: {result.get('output', '')}")
        
        # 显示生成的文件
        output_files = [output_bright, output_enhanced, output_resized]
        existing_files = [f for f in output_files if os.path.exists(f)]
        if existing_files:
            print(f"\n生成的文件: {', '.join(existing_files)}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await Runner.stop()


if __name__ == "__main__":
    # 运行测试案例
    asyncio.run(run_image_editing())

