#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""
MCP Server for Image Editing
Implements a Model Context Protocol server that provides image editing tools.
"""

import asyncio
import base64
import io
import json
import os


from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
)
from PIL import Image, ImageEnhance, ImageFilter


# Initialize the MCP server
app = Server("image-editor-mcp-server")


def encode_image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Encode PIL Image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


def decode_base64_to_image(base64_str: str) -> Image.Image:
    """Decode base64 string to PIL Image."""
    img_bytes = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(img_bytes))


def load_image_from_path(image_path: str) -> Image.Image:
    """Load image from file path."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    return Image.open(image_path)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available image editing tools."""
    return [
        Tool(
            name="adjust_brightness",
            description="Adjust the brightness of an image. Factor > 1.0 increases brightness, < 1.0 decreases it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Brightness adjustment factor (0.0 to 2.0, default: 1.0)",
                        "default": 1.0
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["output_path"]
            }
        ),
        Tool(
            name="adjust_contrast",
            description="Adjust the contrast of an image. Factor > 1.0 increases contrast, < 1.0 decreases it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Contrast adjustment factor (0.0 to 2.0, default: 1.0)",
                        "default": 1.0
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["output_path"]
            }
        ),
        Tool(
            name="adjust_saturation",
            description="Adjust the color saturation of an image. Factor > 1.0 increases saturation, < 1.0 decreases it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Saturation adjustment factor (0.0 to 2.0, default: 1.0)",
                        "default": 1.0
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["output_path"]
            }
        ),
        Tool(
            name="adjust_sharpness",
            description="Adjust the sharpness of an image. Factor > 1.0 increases sharpness, < 1.0 decreases it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Sharpness adjustment factor (0.0 to 2.0, default: 1.0)",
                        "default": 1.0
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["output_path"]
            }
        ),
        Tool(
            name="resize_image",
            description="Resize an image to specified dimensions. Maintains aspect ratio if only width or height is provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Target width in pixels (optional if height is provided)"
                    },
                    "height": {
                        "type": "integer",
                        "description": "Target height in pixels (optional if width is provided)"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["output_path"]
            }
        ),
        Tool(
            name="crop_image",
            description="Crop an image to specified rectangular region.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "left": {
                        "type": "integer",
                        "description": "Left coordinate of the crop box"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Top coordinate of the crop box"
                    },
                    "right": {
                        "type": "integer",
                        "description": "Right coordinate of the crop box"
                    },
                    "bottom": {
                        "type": "integer",
                        "description": "Bottom coordinate of the crop box"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["left", "top", "right", "bottom", "output_path"]
            }
        ),
        Tool(
            name="rotate_image",
            description="Rotate an image by specified angle in degrees (counter-clockwise).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "angle": {
                        "type": "number",
                        "description": "Rotation angle in degrees (counter-clockwise)"
                    },
                    "expand": {
                        "type": "boolean",
                        "description": "Whether to expand the image to fit the rotated content (default: False)",
                        "default": False
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["angle", "output_path"]
            }
        ),
        Tool(
            name="apply_filter",
            description="Apply a filter to an image (blur, sharpen, edge_enhance, emboss, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "filter_type": {
                        "type": "string",
                        "description": "Type of filter: blur, sharpen, edge_enhance, emboss, smooth, detail",
                        "enum": ["blur", "sharpen", "edge_enhance", "emboss", "smooth", "detail"]
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["filter_type", "output_path"]
            }
        ),
        Tool(
            name="convert_format",
            description="Convert image to a different format (PNG, JPEG, WEBP, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    },
                    "format": {
                        "type": "string",
                        "description": "Target format: PNG, JPEG, WEBP, etc.",
                        "enum": ["PNG", "JPEG", "WEBP", "BMP", "TIFF"]
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the output image (required)"
                    }
                },
                "required": ["format", "output_path"]
            }
        ),
        Tool(
            name="get_image_info",
            description="Get information about an image (dimensions, format, mode, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the input image file"
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Base64 encoded image data (alternative to image_path)"
                    }
                },
                "required": []
            }
        ),
    ]


def load_image_from_args(args: dict) -> Image.Image:
    """Load image from either file path or base64 string."""
    if "image_path" in args and args["image_path"]:
        return load_image_from_path(args["image_path"])
    elif "image_base64" in args and args["image_base64"]:
        return decode_base64_to_image(args["image_base64"])
    else:
        raise ValueError("Either 'image_path' or 'image_base64' must be provided")


def save_image_result(image: Image.Image, output_path: str = None, format: str = None) -> dict:
    """Save image and return result with file path only, no base64 encoding."""
    result = {}
    
    if output_path:
        image.save(output_path, format=format)
        result["saved_path"] = output_path
        result["format"] = format or image.format or "PNG"
        result["width"] = image.width
        result["height"] = image.height
    
    # Do NOT return base64 encoded image to prevent token explosion
    # Only return file path and basic info
    return result


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Handle tool calls."""
    try:
        # Load image
        image = load_image_from_args(arguments)
        output_path = arguments.get("output_path")
        
        if name == "adjust_brightness":
            factor = float(arguments.get("factor", 1.0))
            enhancer = ImageEnhance.Brightness(image)
            result_image = enhancer.enhance(factor)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "adjust_contrast":
            factor = float(arguments.get("factor", 1.0))
            enhancer = ImageEnhance.Contrast(image)
            result_image = enhancer.enhance(factor)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "adjust_saturation":
            factor = float(arguments.get("factor", 1.0))
            enhancer = ImageEnhance.Color(image)
            result_image = enhancer.enhance(factor)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "adjust_sharpness":
            factor = float(arguments.get("factor", 1.0))
            enhancer = ImageEnhance.Sharpness(image)
            result_image = enhancer.enhance(factor)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "resize_image":
            width = arguments.get("width")
            height = arguments.get("height")
            
            if width and height:
                size = (width, height)
            elif width:
                # Maintain aspect ratio
                ratio = width / image.width
                size = (width, int(image.height * ratio))
            elif height:
                # Maintain aspect ratio
                ratio = height / image.height
                size = (int(image.width * ratio), height)
            else:
                raise ValueError("Either 'width' or 'height' must be provided")
            
            result_image = image.resize(size, Image.Resampling.LANCZOS)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "crop_image":
            left = int(arguments["left"])
            top = int(arguments["top"])
            right = int(arguments["right"])
            bottom = int(arguments["bottom"])
            box = (left, top, right, bottom)
            result_image = image.crop(box)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "rotate_image":
            angle = float(arguments["angle"])
            expand = arguments.get("expand", False)
            result_image = image.rotate(angle, expand=expand)
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "apply_filter":
            filter_type = arguments["filter_type"]
            filter_map = {
                "blur": ImageFilter.BLUR,
                "sharpen": ImageFilter.SHARPEN,
                "edge_enhance": ImageFilter.EDGE_ENHANCE,
                "emboss": ImageFilter.EMBOSS,
                "smooth": ImageFilter.SMOOTH,
                "detail": ImageFilter.DETAIL,
            }
            if filter_type not in filter_map:
                raise ValueError(f"Unknown filter type: {filter_type}")
            result_image = image.filter(filter_map[filter_type])
            result = save_image_result(result_image, output_path)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "convert_format":
            format_name = arguments["format"]
            result = save_image_result(image, output_path, format=format_name)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_image_info":
            info = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image.tobytes()) if hasattr(image, 'tobytes') else None,
            }
            return [TextContent(
                type="text",
                text=json.dumps(info, indent=2)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        error_msg = {
            "error": str(e),
            "error_type": type(e).__name__
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_msg, indent=2)
        )]


async def main():
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

