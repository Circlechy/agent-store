#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""
Example: Multimodal Image Beautification Agent
Demonstrates how to use a multimodal LLM to analyze images and provide beautification suggestions,
then execute the beautification using image editing tools.
"""

import asyncio
import base64
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
    model_name: str = "",  # 多模态视觉模型
    api_key: str = "",
    api_base: str = "",
):
    """Create model configuration for ReActAgent with multimodal support"""
    from openjiuwen.core.utils.llm.base import BaseModelInfo

    model_info = BaseModelInfo(
        api_key=api_key,
        api_base=api_base,
        model=model_name,
        timeout=300  # 5 minutes timeout
    )

    return ModelConfig(
        model_provider="siliconflow",
        model_info=model_info
    )


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string for multimodal input"""
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
        base64_str = base64.b64encode(image_data).decode("utf-8")
        # Determine image format from file extension
        ext = Path(image_path).suffix.lower()
        if ext == ".png":
            mime_type = "image/png"
        elif ext in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif ext == ".webp":
            mime_type = "image/webp"
        else:
            mime_type = "image/png"  # default
        
        return f"data:{mime_type};base64,{base64_str}"


async def create_multimodal_beautify_agent():
    """Create an agent with multimodal image beautification capabilities."""
    
    # Start Runner
    await Runner.start()
    
    # Create agent configuration with multimodal support
    agent_config = create_react_agent_config(
        agent_id="multimodal_beautify_agent",
        agent_version="1.0",
        description="An agent that analyzes images using multimodal LLM and provides beautification suggestions",
        model=create_model_config(
            model_name="",  # 多模态视觉模型
            api_key="",
            api_base="",
        ),
        prompt_template=[
            {
                "role": "system",
                "content": (
                    "You are an expert image beautification assistant. "
                    "You MUST use the available tools to analyze and beautify images.\n\n"
                    "CRITICAL RULES:\n"
                    "- You MUST call tools to complete the task. DO NOT just describe what you would do.\n"
                    "- You MUST NOT respond with only text when asked to beautify an image.\n"
                    "- If you don't call tools, the task will fail.\n\n"
                    "Available tools:\n"
                    "- get_image_info: Get image information (width, height, format, etc.) - USE THIS FIRST\n"
                    "- adjust_brightness: Adjust brightness (factor: 0.0-2.0, e.g., 1.3 = +30%)\n"
                    "- adjust_contrast: Adjust contrast (factor: 0.0-2.0, e.g., 1.2 = +20%)\n"
                    "- adjust_saturation: Adjust color saturation (factor: 0.0-2.0, e.g., 1.15 = +15%)\n"
                    "- adjust_sharpness: Adjust sharpness (factor: 0.0-2.0)\n"
                    "- resize_image: Resize images (width/height in pixels)\n"
                    "- apply_filter: Apply filters (blur, sharpen, edge_enhance, emboss, smooth, detail)\n"
                    "- convert_format: Convert formats (PNG, JPEG, WEBP, BMP, TIFF)\n\n"
                    "WORKFLOW (MANDATORY - FOLLOW EXACTLY):\n"
                    "Step 1: Call get_image_info(image_path='<user_provided_path>') FIRST\n"
                    "Step 2: Based on image info, call editing tools:\n"
                    "   - adjust_brightness(image_path='<path>', factor=1.2-1.4, output_path='<user_specified_output>')\n"
                    "   - adjust_contrast(image_path='<path>', factor=1.1-1.3, output_path='<user_specified_output>')\n"
                    "   - adjust_saturation(image_path='<path>', factor=1.1-1.2, output_path='<user_specified_output>')\n"
                    "Step 3: ALWAYS specify output_path parameter when calling editing tools\n"
                    "Step 4: Chain tools if needed (previous output_path becomes next input_path)\n"
                    "Step 5: After tools complete, provide summary\n\n"
                    "CRITICAL RULES - FOLLOW EXACTLY:\n"
                    "1. You MUST use function calling (tool calling) to complete this task\n"
                    "2. DO NOT respond with only text - you MUST call at least one tool\n"
                    "3. When user asks to beautify an image, you MUST:\n"
                    "   a) Call get_image_info(image_path='<path>') FIRST\n"
                    "   b) Then call editing tools (adjust_brightness, adjust_contrast, etc.)\n"
                    "   c) Each editing tool MUST include output_path parameter\n"
                    "4. Text-only responses are NOT acceptable - you MUST call tools\n"
                    "5. If you don't call tools, the task will be considered FAILED\n\n"
                    "Remember: Use function calling, not text descriptions!\n"
                ),
            }
        ]
    )
    
    # Create agent with token limit
    agent = ReActAgent(agent_config)
    
    # Register image editor tools from MCP server
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


async def beautify_image_with_multimodal(
    image_path: str,
    output_path: str = None,
    conversation_id: str = None
):
    """
    Use multimodal LLM to analyze an image and beautify it.
    
    Args:
        image_path: Path to the input image
        output_path: Path to save the beautified image (optional, defaults to input_path + "_beautified.png")
        conversation_id: Optional conversation ID for session management
    
    Returns:
        Dict with beautification result
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    if output_path is None:
        input_path_obj = Path(image_path)
        output_path = str(input_path_obj.parent / f"{input_path_obj.stem}_beautified{input_path_obj.suffix}")
    
    print(f"📸 输入图片: {image_path}")
    print(f"🎨 输出路径: {output_path}")
    print(f"\n{'='*60}")
    print("开始多模态图片美化流程...")
    print(f"{'='*60}\n")
    
    # Create agent
    agent = await create_multimodal_beautify_agent()
    
    try:
        # Encode image to base64 for multimodal input
        print("1️⃣ 编码图片为 base64...")
        image_base64 = encode_image_to_base64(image_path)
        print(f"   ✓ 图片已编码 ({len(image_base64)} 字符)\n")
        
        # Try multimodal first, fallback to text-only if needed
        # Set to False to test text-only mode first
        use_multimodal = False  # Temporarily disabled to test text mode
        
        if use_multimodal:
            # Create multimodal message with image
            # Format: OpenAI-compatible multimodal message format
            multimodal_content = [
                {
                    "type": "text",
                    "text": (
                        f"请仔细分析这张图片，并提供具体的美化建议。"
                        f"然后使用图片编辑工具执行美化操作，将美化后的图片保存到: {output_path}\n\n"
                        f"请告诉我：\n"
                        f"1. 你观察到了什么（图片的当前状态）\n"
                        f"2. 你认为可以如何改进（具体的美化建议）\n"
                        f"3. 你将执行哪些操作来实现美化"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_base64
                    }
                }
            ]

            
            # Prepare inputs with multimodal content
            inputs = {
                "conversation_id": conversation_id or f"beautify_{Path(image_path).stem}",
                "query": multimodal_content  # Pass multimodal content list directly
            }
        else:

            text_query = (
                f"请对图片 '{image_path}' 进行美化操作，将美化后的图片保存到: {output_path}\n\n"
                f"重要：你必须使用工具来完成这个任务，不能只描述操作。\n"
                f"工作流程：\n"
                f"1. 首先调用 get_image_info(image_path='{image_path}') 获取图片信息\n"
                f"2. 然后调用编辑工具（如 adjust_brightness, adjust_contrast 等）进行美化\n"
                f"3. 每个编辑工具调用时必须指定 output_path='{output_path}'\n"
                f"4. 可以链式调用多个工具，使用前一个工具的输出作为下一个工具的输入\n\n"
                f"请立即开始调用工具，不要只描述你会做什么。"
            )
            inputs = {
                "conversation_id": conversation_id or f"beautify_{Path(image_path).stem}",
                "query": text_query
            }

        try:
            result = await Runner.run_agent(agent, inputs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

        output_text = result.get('output', '')
        result_type = result.get('result_type', 'unknown')

        
        # Debug: Print full result if output is empty
        if not output_text:
            if 'result' in result:
                print(f"   嵌套结果: {result.get('result')}")
            print()
        
        # Check if output file was created
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
        else:
            print(f"  警告: 未找到输出文件 {output_path}")
            print("   可能的原因:")
            print("   1. 工具调用未成功保存图片")
            print("   2. 模型没有调用保存工具")
            print("   3. 输出路径不正确")
            print(f"\n   请检查日志中的工具调用信息")
        
        return {
            "success": os.path.exists(output_path),
            "output_path": output_path if os.path.exists(output_path) else None,
            "model_response": output_text,
            "result": result
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        await Runner.stop()


async def main():
    """Main function to run the multimodal beautification example"""
    import argparse
    
    parser = argparse.ArgumentParser(description="多模态图片美化示例")
    parser.add_argument(
        "image_path",
        type=str,
        help="输入图片路径"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出图片路径（可选，默认为输入文件名_beautified.png）"
    )
    parser.add_argument(
        "-c", "--conversation-id",
        type=str,
        default=None,
        help="会话ID（可选，用于会话管理）"
    )
    
    args = parser.parse_args()
    
    result = await beautify_image_with_multimodal(
        image_path=args.image_path,
        output_path=args.output,
        conversation_id=args.conversation_id
    )
    
    if result.get("success"):
        print(f"\n 美化成功！输出文件: {result['output_path']}")
    else:
        print(f"\n 美化失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    # If run without arguments, use default test image
    if len(sys.argv) == 1:
        script_dir = Path(__file__).parent
        test_image = script_dir / "1.png"
        
        if test_image.exists():
            print(f"使用默认测试图片: {test_image}\n")
            asyncio.run(beautify_image_with_multimodal(
                image_path=str(test_image),
                conversation_id="default_test"
            ))
        else:
            print("错误: 未找到默认测试图片 1.png")
            print("请提供图片路径作为参数:")
            print(f"  python {sys.argv[0]} <图片路径> [-o <输出路径>]")
            sys.exit(1)
    else:
        asyncio.run(main())

