# -*- coding: utf-8 -*-
"""
工作总结 Agent - 输入处理模块

支持多种输入格式：
1. 文字输入
2. 文档输入（Word、PDF、TXT、MD等）
3. 图片输入（截图，支持OCR）
"""

import os
import base64
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Union, List
from enum import Enum

from openjiuwen.core.common.logging import logger
from openjiuwen.core.retrieval.indexing.processor.parser.auto_file_parser import AutoFileParser
import sys

# 导入 prompt 加载器
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent
sys.path.insert(0, str(_backend_dir))
from backend.prompts.prompt_loader import load_prompt


class InputType(Enum):
    """输入类型枚举"""
    TEXT = "text"
    DOCUMENT = "document"
    IMAGE = "image"


class InputProcessor:
    """输入处理器 - 统一处理各种输入格式"""
    
    def __init__(self):
        """初始化输入处理器"""
        self.file_parser = AutoFileParser()
        ocr_check = self._check_ocr_availability()
        if isinstance(ocr_check, tuple):
            self._ocr_available, self._ocr_method = ocr_check
        else:
            self._ocr_available = ocr_check
            self._ocr_method = None
    
    def _check_ocr_availability(self):
        """
        检查OCR功能是否可用
        
        只支持PaddleOCR - 百度开源，中文识别效果好
        
        Returns:
            tuple: (是否可用, OCR方法名称) 或 (False, None)
        """
        # 检查PaddleOCR
        try:
            import paddleocr  # type: ignore
            return True, "paddleocr"
        except ImportError:
            return False, None
    
    async def process_input(
        self,
        input_type: Union[str, InputType],
        content: str,
        file_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理输入内容
        
        Args:
            input_type: 输入类型 ("text", "document", "image")
            content: 输入内容（文字内容或文件路径）
            file_path: 文件路径（如果输入类型为document或image）
            **kwargs: 其他参数
        
        Returns:
            处理后的内容字典，包含：
            - text: 提取的文本内容
            - metadata: 元数据信息
            - input_type: 输入类型
        """
        # 规范化输入类型
        if isinstance(input_type, str):
            input_type = InputType(input_type.lower())
        
        if input_type == InputType.TEXT:
            return await self._process_text_input(content, **kwargs)
        elif input_type == InputType.DOCUMENT:
            file_path = file_path or content
            return await self._process_document_input(file_path, **kwargs)
        elif input_type == InputType.IMAGE:
            file_path = file_path or content
            return await self._process_image_input(file_path, **kwargs)
        else:
            raise ValueError(f"不支持的输入类型: {input_type}")
    
    async def _process_text_input(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        处理文字输入
        
        Args:
            text: 文字内容
            **kwargs: 其他参数
        
        Returns:
            处理后的内容字典
        """
        if not text or not text.strip():
            raise ValueError("文字输入不能为空")
        
        return {
            "text": text.strip(),
            "metadata": {
                "input_type": InputType.TEXT.value,
                "length": len(text),
                "word_count": len(text.split()),
            },
            "input_type": InputType.TEXT.value,
        }
    
    async def _process_document_input(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        处理文档输入（Word、PDF、TXT、MD等）
        
        Args:
            file_path: 文档文件路径
            **kwargs: 其他参数
        
        Returns:
            处理后的内容字典
        """
        if not file_path:
            raise ValueError("文档路径不能为空")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 检查文件是否支持
        if not self.file_parser.supports(file_path):
            file_ext = os.path.splitext(file_path)[-1].lower()
            raise ValueError(f"不支持的文档格式: {file_ext}")
        
        try:
            # 使用AutoFileParser解析文档
            documents = await self.file_parser.parse(
                file_path,
                doc_id=kwargs.get("doc_id", ""),
                file_name=kwargs.get("file_name", os.path.basename(file_path))
            )
            
            if not documents:
                logger.warning(f"文档解析结果为空: {file_path}")
                return {
                    "text": "",
                    "metadata": {
                        "input_type": InputType.DOCUMENT.value,
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                    },
                    "input_type": InputType.DOCUMENT.value,
                }
            
            # 合并所有文档内容
            text_parts = [doc.text for doc in documents if doc.text]
            combined_text = "\n\n".join(text_parts)
            
            # 提取元数据
            metadata = documents[0].metadata if documents else {}
            metadata.update({
                "input_type": InputType.DOCUMENT.value,
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "doc_count": len(documents),
                "length": len(combined_text),
                "word_count": len(combined_text.split()),
            })
            
            return {
                "text": combined_text,
                "metadata": metadata,
                "input_type": InputType.DOCUMENT.value,
            }
        
        except Exception as e:
            logger.error(f"解析文档失败: {file_path}, 错误: {e}")
            raise RuntimeError(f"解析文档失败: {e}") from e
    
    async def _process_image_input(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        处理图片输入（支持OCR和多模态模型）
        
        支持的图片理解方式：
        1. OCR: 使用PaddleOCR识别文字
        2. Multimodal: 使用多模态模型理解图片（如qwen3-vl-plus）
        3. Caption: 使用多模态模型生成图片描述
        
        Args:
            file_path: 图片文件路径
            **kwargs: 其他参数
                - enable_ocr: 是否启用OCR（默认True）
                - use_multimodal: 是否使用多模态模型（默认False）
                - multimodal_method: 多模态方法 ("caption" 或 "direct_analysis", 默认"caption")
                - image_processing_mode: 处理模式 ("ocr", "multimodal", "both", 默认"ocr")
                - is_auto_screenshot: 是否是自动截图（默认False），影响多模态模型的prompt
        
        Returns:
            处理后的内容字典
        """
        if not file_path:
            raise ValueError("图片路径不能为空")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 检查是否为图片文件
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
        file_ext = os.path.splitext(file_path)[-1].lower()
        
        if file_ext not in image_extensions:
            raise ValueError(f"不支持的图片格式: {file_ext}，支持的格式: {image_extensions}")
        
        # 获取图片基本信息
        try:
            from PIL import Image  # type: ignore
            with Image.open(file_path) as img:
                width, height = img.size
                format_name = img.format
                file_size = os.path.getsize(file_path)
        except ImportError:
            logger.warning("PIL/Pillow未安装，无法获取图片信息")
            width, height, format_name = None, None, None
            file_size = os.path.getsize(file_path)
        except Exception as e:
            logger.warning(f"获取图片信息失败: {e}")
            width, height, format_name = None, None, None
            file_size = os.path.getsize(file_path)
        
        # 确定处理模式
        processing_mode = kwargs.get("image_processing_mode", "ocr")
        use_multimodal = kwargs.get("use_multimodal", False) or processing_mode in ("multimodal", "both")
        enable_ocr = kwargs.get("enable_ocr", True) and processing_mode in ("ocr", "both")
        fallback_to_ocr = kwargs.get("fallback_to_ocr", True)  # 默认启用OCR降级
        
        # 提取文本内容
        extracted_text_parts = []
        ocr_text = ""
        caption_text = ""
        multimodal_text = ""
        ocr_method = None
        multimodal_method = None
        multimodal_failed = False
        
        # 1. OCR识别文字（如果启用）
        if enable_ocr and self._ocr_available:
            ocr_text = await self._extract_text_from_image(file_path, **kwargs)
            if ocr_text:
                ocr_method = self._ocr_method
                extracted_text_parts.append(f"[OCR识别]\n{ocr_text}")
        
        # 2. 多模态模型理解图片
        if use_multimodal:
            # 传递 is_auto_screenshot 参数给多模态处理
            multimodal_result = await self._process_with_multimodal(
                file_path, 
                is_auto_screenshot=kwargs.get("is_auto_screenshot", False),
                **{k: v for k, v in kwargs.items() if k != "is_auto_screenshot"}
            )
            if multimodal_result:
                multimodal_method = multimodal_result.get("method")
                if multimodal_method == "caption":
                    caption_text = multimodal_result.get("caption", "")
                    if caption_text:
                        extracted_text_parts.append(f"[图片描述]\n{caption_text}")
                elif multimodal_method == "direct_analysis":
                    multimodal_text = multimodal_result.get("analysis", "")
                    if multimodal_text:
                        extracted_text_parts.append(f"[图片分析]\n{multimodal_text}")
            else:
                multimodal_failed = True
                logger.warning("多模态模型处理失败或返回空结果")
        
        # 3. 降级处理：如果multimodal失败且没有OCR结果，尝试使用OCR作为备选
        if multimodal_failed and not ocr_text and fallback_to_ocr and self._ocr_available:
            if processing_mode == "multimodal":  # 仅在multimodal模式下降级
                logger.info("多模态模型处理失败，降级使用OCR")
                ocr_text = await self._extract_text_from_image(file_path, **kwargs)
                if ocr_text:
                    ocr_method = self._ocr_method
                    extracted_text_parts.append(f"[OCR识别]\n{ocr_text}")
        
        # 合并所有提取的文本
        combined_text = "\n\n".join(extracted_text_parts) if extracted_text_parts else ""
        
        # 将图片转换为base64（用于后续处理或展示）
        image_base64 = None
        if kwargs.get("include_base64", False):
            image_base64 = self._image_to_base64(file_path)
        
        return {
            "text": combined_text,
            "metadata": {
                "input_type": InputType.IMAGE.value,
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "width": width,
                "height": height,
                "format": format_name,
                "file_size": file_size,
                "ocr_method": ocr_method,
                "multimodal_method": multimodal_method,
                "has_text": bool(combined_text),
                "has_ocr_text": bool(ocr_text),
                "has_caption": bool(caption_text),
                "has_multimodal_analysis": bool(multimodal_text),
                "processing_mode": processing_mode,
                "multimodal_failed": multimodal_failed,
                "fallback_to_ocr": multimodal_failed and bool(ocr_method) and processing_mode == "multimodal",
            },
            "input_type": InputType.IMAGE.value,
            "image_base64": image_base64,
        }
    
    async def _extract_text_from_image(self, image_path: str, **kwargs) -> str:
        """
        从图片中提取文字（OCR）
        
        使用PaddleOCR进行文字识别，中文识别效果好
        
        Args:
            image_path: 图片路径
            **kwargs: OCR参数
                - lang: 识别语言（默认'ch'中文+英文）
                - score_threshold: 置信度阈值（默认0.5）
        
        Returns:
            提取的文字内容
        """
        if not self._ocr_available:
            logger.warning(
                "OCR功能不可用，请安装PaddleOCR：\n"
                "  pip install paddlepaddle paddleocr"
            )
            return ""
        
        try:
            if self._ocr_method == "paddleocr":
                return await self._extract_with_paddleocr(image_path, **kwargs)
            else:
                logger.warning(f"未知的OCR方法: {self._ocr_method}")
                return ""
        except Exception as e:
            logger.error(f"OCR识别失败: {e}", exc_info=True)
            return ""
    
    async def _extract_with_paddleocr(self, image_path: str, **kwargs) -> str:
        """使用PaddleOCR提取文字
        
        根据 PaddleOCR 3.3.2 版本的API：
        - 使用 predict() 方法而不是 ocr() 方法
        - 初始化参数已更改，不再支持 use_angle_cls, show_log, use_gpu
        """
        try:
            from paddleocr import PaddleOCR  # type: ignore
            
            # 语言设置：ch=中文+英文，en=英文
            lang = kwargs.get("lang", "ch")
            
            # 初始化OCR（首次运行会下载模型）
            # PaddleOCR 3.x 版本使用新的API
            # 参考文档：https://www.paddleocr.ai/main/quick_start.html
            ocr = PaddleOCR(lang=lang)
            
            # 处理中文路径问题：先使用PIL读取图片并保存为临时文件
            import tempfile
            import os
            
            try:
                from PIL import Image
                
                # 使用PIL读取（支持中文路径）
                img = Image.open(image_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # PaddleOCR 3.x 使用 predict() 方法，需要文件路径
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img.save(tmp.name)
                    temp_path = tmp.name
                
                try:
                    # PaddleOCR 3.x 使用 predict() 方法
                    # 返回格式：包含 'rec_texts', 'rec_scores' 等字段的字典
                    result = ocr.predict(temp_path)
                finally:
                    # 清理临时文件
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                        
            except Exception as pil_error:
                # 如果PIL处理失败，直接使用路径
                logger.warning(f"使用PIL读取图片失败，尝试直接使用路径: {pil_error}")
                result = ocr.predict(image_path)
            
            # 提取文字
            # PaddleOCR 3.x 返回格式：{'rec_texts': [...], 'rec_scores': [...], ...}
            # 或列表格式：[{'rec_texts': [...], 'rec_scores': [...]}, ...]
            texts = []
            score_threshold = kwargs.get('score_threshold', 0.5)  # 默认置信度阈值
            if result and isinstance(result, dict):

                # 新版本返回字典格式
                rec_texts = result.get('rec_texts', [])
                if rec_texts:
                    # 过滤空文本和置信度低的文本
                    rec_scores = result.get('rec_scores', [])
                    for i, text in enumerate(rec_texts):
                        if text and text.strip():
                            # 可选：根据置信度过滤
                            score = rec_scores[i] if i < len(rec_scores) else 1.0
                            if score >= score_threshold:
                                texts.append(text.strip())
            elif result and isinstance(result, list) and len(result) > 0:
                # PaddleOCR 3.x 可能返回列表，第一个元素是字典
                first_item = result[0]
                if isinstance(first_item, dict) and 'rec_texts' in first_item:
                    # 从字典中提取文本
                    rec_texts = first_item.get('rec_texts', [])
                    rec_scores = first_item.get('rec_scores', [])
                    for i, text in enumerate(rec_texts):
                        if text and text.strip():
                            score = rec_scores[i] if i < len(rec_scores) else 1.0
                            if score >= score_threshold:
                                texts.append(text.strip())
                else:
                    for line in result[0] if isinstance(result[0], list) else result:
                        if line:
                            # 安全地访问 line
                            if isinstance(line, dict):
                                # 如果是字典，尝试提取文本
                                text = line.get('text') or line.get('rec_text')
                                if text and text.strip():
                                    texts.append(text.strip())
                            elif isinstance(line, (list, tuple)) and len(line) >= 2:
                                text_info = line[1]
                                if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                    text = text_info[0]  # 提取文字
                                    score = text_info[1] if len(text_info) > 1 else 1.0
                                    if text and text.strip() and score >= score_threshold:
                                        texts.append(text.strip())
                                else:
                                    text = str(text_info)
                                    if text and text.strip():
                                        texts.append(text.strip())
            
            return "\n".join(texts)
        except ImportError:
            logger.error("PaddleOCR未安装，请运行: pip install paddlepaddle paddleocr")
            return ""
        except Exception as e:
            logger.error(f"PaddleOCR识别失败: {e}", exc_info=True)
            return ""
    
    async def _process_with_multimodal(self, image_path: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        使用多模态模型处理图片
        
        支持的模式：
        1. caption: 生成图片描述
        2. direct_analysis: 直接分析图片内容（针对工作总结场景）
        
        Args:
            image_path: 图片路径
            **kwargs: 其他参数
                - multimodal_method: 方法 ("caption" 或 "direct_analysis", 默认"caption")
                - is_auto_screenshot: 是否是自动截图（默认False），如果是True会使用专门的prompt先识别重点区域
                - model_name: 模型名称（默认从环境变量读取）
                - api_key: API密钥（默认从环境变量读取）
                - api_base: API地址（默认从环境变量读取）
        
        Returns:
            处理结果字典，包含 method 和 caption/analysis
        """
        try:
            import os
            from openai import OpenAI  # type: ignore
            
            # 获取配置
            api_key = kwargs.get("api_key") or os.getenv("API_KEY", "")
            api_base = kwargs.get("api_base") or os.getenv("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            
            # 模型选择逻辑：优先使用MULTIMODAL_MODEL，如果没有则检查MODEL_NAME是否为视觉模型
            model_name = kwargs.get("model_name")
            if not model_name:
                model_name = os.getenv("MULTIMODAL_MODEL")
                if not model_name:
                    # 检查MODEL_NAME是否是视觉模型
                    model_name_candidate = os.getenv("MODEL_NAME", "")
                    if model_name_candidate and ("vl" in model_name_candidate.lower() or "vision" in model_name_candidate.lower()):
                        model_name = model_name_candidate
                        logger.info(f"使用MODEL_NAME中的视觉模型: {model_name}")
                    else:
                        # 默认使用qwen3-vl-plus
                        model_name = "qwen3-vl-plus"
                        if model_name_candidate:
                            logger.warning(
                                f"MODEL_NAME ({model_name_candidate}) 不是视觉模型，"
                                f"多模态处理将使用默认模型 {model_name}。"
                                f"建议设置 MULTIMODAL_MODEL 环境变量指定视觉模型。"
                            )
                        else:
                            logger.info(f"未指定多模态模型，使用默认: {model_name}")
            
            method = kwargs.get("multimodal_method", "caption")
            
            if not api_key:
                logger.warning("多模态模型API密钥未配置，跳过多模态处理")
                return None
            
            # 将图片转换为base64或使用文件路径
            image_base64 = self._image_to_base64(image_path)
            if not image_base64:
                logger.warning("图片转base64失败，跳过多模态处理")
                return None
            
            # 构建图片URL（使用base64 data URI）
            # 需要根据图片格式设置正确的MIME类型
            file_ext = os.path.splitext(image_path)[1][1:].lower()
            image_format_map = {
                "png": "png",
                "jpg": "jpeg",
                "jpeg": "jpeg",
                "webp": "webp",
                "gif": "gif",
                "bmp": "bmp",
            }
            image_format = image_format_map.get(file_ext, "png")  # 默认PNG
            image_url = f"data:image/{image_format};base64,{image_base64}"
            
            # 初始化OpenAI客户端
            client = OpenAI(api_key=api_key, base_url=api_base)
            
            # 判断是否是自动截图
            is_auto_screenshot = kwargs.get("is_auto_screenshot", False)
            
            # 根据方法构建提示词（从文件加载）
            if method == "caption":
                if is_auto_screenshot:
                    # 自动截图：先识别重点区域，再描述
                    prompt = load_prompt("multimodal/caption_auto_screenshot.txt")
                else:
                    # 用户上传：默认是重点内容，直接描述
                    prompt = load_prompt("multimodal/caption_user_upload.txt")
            elif method == "direct_analysis":
                if is_auto_screenshot:
                    # 自动截图：先识别重点区域，再分析
                    prompt = load_prompt("multimodal/direct_analysis_auto_screenshot.txt")
                else:
                    # 用户上传：默认是重点内容，直接分析
                    prompt = load_prompt("multimodal/direct_analysis_user_upload.txt")
            else:
                logger.warning(f"未知的多模态方法: {method}，使用默认caption")
                method = "caption"
                if is_auto_screenshot:
                    prompt = load_prompt("multimodal/caption_default_auto_screenshot.txt")
                else:
                    prompt = load_prompt("multimodal/caption_default_user_upload.txt")
            
            # 调用多模态模型
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            # 检查是否是 Qwen-Omni 模型（必须使用流式输出）
            # 参考：https://help.aliyun.com/zh/model-studio/qwen-omni
            is_omni_model = "omni" in model_name.lower()
            
            if is_omni_model:
                # Qwen-Omni 必须使用流式输出
                # modalities 指定输出格式（text、audio等）
                # stream_options 指定流式选项
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    modalities=["text"],  # 指定输出文本（也可以包含 "audio"）
                    stream=True,  # Qwen-Omni 必须设置为 True
                    stream_options={"include_usage": True}  # 包含使用信息
                )
                
                # 流式处理响应
                result_text = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        result_text += chunk.choices[0].delta.content
            else:
                # 非 Omni 模型使用普通调用（如 qwen3-vl-plus）
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages
                )
                result_text = response.choices[0].message.content
            
            if method == "caption":
                return {
                    "method": "caption",
                    "caption": result_text
                }
            else:
                return {
                    "method": "direct_analysis",
                    "analysis": result_text
                }
                
        except ImportError:
            logger.warning(
                "OpenAI库未安装，无法使用多模态模型。请安装: pip install openai"
            )
            return None
        except Exception as e:
            logger.error(f"多模态模型处理失败: {e}", exc_info=True)
            return None
    
    def _image_to_base64(self, image_path: str) -> str:
        """
        将图片转换为base64字符串
        
        Args:
            image_path: 图片路径
        
        Returns:
            base64编码的字符串
        """
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            logger.error(f"图片转base64失败: {e}")
            return ""
    
    def get_supported_document_formats(self) -> List[str]:
        """
        获取支持的文档格式列表
        
        Returns:
            支持的文档格式扩展名列表
        """
        # 从AutoFileParser获取支持的格式
        # 这里需要访问_PARSER_REGISTRY，但它是私有的
        # 所以返回已知支持的格式
        return [".pdf", ".docx", ".txt", ".md", ".json"]
    
    def get_supported_image_formats(self) -> List[str]:
        """
        获取支持的图片格式列表
        
        Returns:
            支持的图片格式扩展名列表
        """
        return [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]


# 便捷函数
async def process_input(
    input_type: Union[str, InputType],
    content: str,
    file_path: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    便捷函数：处理输入内容
    
    Args:
        input_type: 输入类型 ("text", "document", "image")
        content: 输入内容
        file_path: 文件路径（可选）
        **kwargs: 其他参数
    
    Returns:
        处理后的内容字典
    """
    processor = InputProcessor()
    return await processor.process_input(input_type, content, file_path, **kwargs)


if __name__ == "__main__":
    """测试输入处理功能"""
    import asyncio
    
    async def test():
        processor = InputProcessor()
        
        # 测试1: 文字输入
        print("=" * 50)
        print("测试1: 文字输入")
        print("=" * 50)
        try:
            result = await processor.process_input(
                InputType.TEXT,
                "今天完成了项目A的需求分析，梳理了用户反馈，制定了开发计划。"
            )
            print(f"提取的文字: {result['text'][:100]}...")
            print(f"元数据: {result['metadata']}")
        except Exception as e:
            print(f"错误: {e}")
        
        # 测试2: 文档输入（需要实际文件）
        print("\n" + "=" * 50)
        print("测试2: 文档输入")
        print("=" * 50)
        print("支持的文档格式:", processor.get_supported_document_formats())
        # 示例：如果有文件可以测试
        # result = await processor.process_input(
        #     InputType.DOCUMENT,
        #     "path/to/document.pdf"
        # )
        
        # 测试3: 图片输入
        print("\n" + "=" * 50)
        print("测试3: 图片输入")
        print("=" * 50)
        print("支持的图片格式:", processor.get_supported_image_formats())
        print("OCR功能可用:", processor._ocr_available)
    
    asyncio.run(test())
