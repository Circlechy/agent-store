"""
多模态感知工具模块
支持图片 (Vision) 和文档 (File) 的智能解析

功能：
1. 图片识别 - 使用 OpenAI Vision API 解析图片内容
2. 文档解析 - 支持 PDF、Word、文本文件的内容提取
3. 智能截断 - 防止超长文本导致的性能问题
"""

import os
import base64
from pathlib import Path
from typing import Optional, BinaryIO
from io import BytesIO

# 导入配置
from src.config import get_model_config

# 尝试导入 OpenAI 客户端
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ 警告: openai 库未安装，Vision 功能不可用")

# 尝试导入文档解析库
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️ 警告: pdfplumber 未安装，PDF 解析功能不可用")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️ 警告: python-docx 未安装，Word 解析功能不可用")

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ 警告: Pillow 未安装，图片处理功能受限")


# ===================== 全局配置 =====================
MAX_TEXT_LENGTH = 8000  # 文本截断阈值
VISION_PROMPT = """请仔细分析这张图片，并根据图片类型执行相应操作：

**如果是代码截图：**
- 必须**原样提取**图片中的所有代码，保留完整的缩进、换行和注释
- 不要描述代码，不要总结代码，不要用伪代码表示
- 直接输出原始源代码文本

**如果是报错截图：**
- 提取完整的错误信息和堆栈跟踪

**如果是文档/文字截图：**
- OCR 识别并输出所有文字内容

**如果是架构图/流程图：**
- 描述图中的逻辑结构和关系

直接输出提取/识别的内容，不要添加额外说明。"""

# 音频配置 (Groq Whisper)
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_AUDIO_MODEL = "whisper-large-v3"


# ===================== OpenAI 客户端初始化 =====================
_openai_client: Optional[OpenAI] = None


def _init_openai_client() -> Optional[OpenAI]:
    """
    初始化 OpenAI 客户端（懒加载）
    
    Returns:
        OpenAI: 客户端实例，失败返回 None
    """
    global _openai_client
    
    if _openai_client is not None:
        return _openai_client
    
    if not OPENAI_AVAILABLE:
        print("❌ OpenAI 库不可用，无法初始化客户端")
        return None
    
    try:
        api_key = os.getenv("LLM_API_KEY")
        api_base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        
        if not api_key:
            print("❌ 错误: 未设置 LLM_API_KEY 环境变量")
            return None
        
        _openai_client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        print(f"✅ OpenAI 客户端初始化成功 (API: {api_base})")
        return _openai_client
        
    except Exception as e:
        print(f"❌ OpenAI 客户端初始化失败: {e}")
        return None


# ===================== 图片处理函数 =====================

def encode_image(image_file: BinaryIO) -> str:
    """
    将图片文件编码为 Base64 字符串
    
    Args:
        image_file: 文件对象（支持 BytesIO 或文件句柄）
    
    Returns:
        str: Base64 编码的图片数据
    """
    try:
        # 读取文件内容
        image_file.seek(0)  # 重置文件指针
        image_bytes = image_file.read()
        
        # Base64 编码
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return encoded
        
    except Exception as e:
        print(f"❌ 图片编码失败: {e}")
        raise


def process_image(image_file: BinaryIO, mime_type: str = "image/jpeg") -> str:
    """
    使用 OpenAI Vision API 解析图片内容
    
    Args:
        image_file: 图片文件对象
        mime_type: MIME 类型 (如 image/jpeg, image/png)
    
    Returns:
        str: 图片的文本描述
    
    Raises:
        Exception: 解析失败时抛出异常
    """
    # 检查依赖
    if not OPENAI_AVAILABLE:
        return "❌ 错误: OpenAI 库未安装，无法解析图片。请运行: pip install openai"
    
    # 初始化客户端
    client = _init_openai_client()
    if client is None:
        return "❌ 错误: OpenAI 客户端初始化失败，请检查 .env 配置"
    
    try:
        # 编码图片
        base64_image = encode_image(image_file)
        
        # 调用 Vision API
        print(f"🔍 正在调用 Vision API 解析图片...")
        
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL_NAME", "gpt-4-vision-preview"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # 提取结果
        result = response.choices[0].message.content
        print(f"✅ Vision API 解析成功")
        
        return result
        
    except Exception as e:
        error_msg = f"❌ 图片解析失败: {str(e)}"
        print(error_msg)
        return error_msg


# ===================== 文档解析函数 =====================

# ===================== 音频处理函数 =====================

def process_audio(audio_file: BinaryIO) -> str:
    """
    使用 Groq Whisper API 将音频转写为文本
    
    Args:
        audio_file: 音频文件对象 (支持 wav, mp3, m4a 等格式)
    
    Returns:
        str: 转写后的文本内容
    
    Raises:
        Exception: 转写失败时抛出异常
    """
    # 检查 OpenAI 库是否可用
    if not OPENAI_AVAILABLE:
        return "❌ 错误: OpenAI 库未安装，无法使用音频转写功能。请运行: pip install openai"
    
    # 获取 Groq API Key
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        return "❌ 错误: 请配置 GROQ_API_KEY 环境变量。访问 https://console.groq.com/keys 获取免费 API Key"
    
    try:
        # 创建独立的 Groq 客户端 (不复用主 LLM 客户端)
        groq_client = OpenAI(
            api_key=groq_api_key,
            base_url=GROQ_API_BASE
        )
        
        print(f"🎙️ 正在使用 Groq Whisper 转写音频...")
        
        # 重置文件指针
        audio_file.seek(0)
        
        # 调用 Groq Whisper API
        transcript = groq_client.audio.transcriptions.create(
            model=GROQ_AUDIO_MODEL,
            file=audio_file,
            response_format="text"
        )
        
        print(f"✅ 音频转写成功")
        
        # Groq 返回的是字符串，不是对象
        if isinstance(transcript, str):
            return transcript.strip()
        else:
            # 如果返回对象，提取 text 属性
            return transcript.text.strip() if hasattr(transcript, 'text') else str(transcript)
        
    except Exception as e:
        error_msg = f"❌ 音频转写失败: {str(e)}"
        print(error_msg)
        return error_msg


# ===================== 文档解析函数 =====================

def _truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    截断过长的文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
    
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + "\n\n...(已截断，原文过长)"


def _extract_pdf_text(file_obj: BinaryIO) -> str:
    """
    从 PDF 文件提取文本
    
    Args:
        file_obj: PDF 文件对象
    
    Returns:
        str: 提取的文本内容
    """
    if not PDF_AVAILABLE:
        return "❌ 错误: pdfplumber 未安装，无法解析 PDF。请运行: pip install pdfplumber"
    
    try:
        file_obj.seek(0)
        
        with pdfplumber.open(file_obj) as pdf:
            text_parts = []
            
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- 第 {i} 页 ---\n{page_text}")
            
            full_text = "\n\n".join(text_parts)
            
            if not full_text.strip():
                return "⚠️ 警告: PDF 文件为空或无法提取文本（可能是扫描件）"
            
            return _truncate_text(full_text)
            
    except Exception as e:
        return f"❌ PDF 解析失败: {str(e)}"


def _extract_docx_text(file_obj: BinaryIO) -> str:
    """
    从 Word 文档提取文本
    
    Args:
        file_obj: Word 文件对象
    
    Returns:
        str: 提取的文本内容
    """
    if not DOCX_AVAILABLE:
        return "❌ 错误: python-docx 未安装，无法解析 Word。请运行: pip install python-docx"
    
    try:
        file_obj.seek(0)
        
        doc = Document(file_obj)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        full_text = "\n\n".join(paragraphs)
        
        if not full_text.strip():
            return "⚠️ 警告: Word 文档为空"
        
        return _truncate_text(full_text)
        
    except Exception as e:
        return f"❌ Word 解析失败: {str(e)}"


def _extract_text_file(file_obj: BinaryIO) -> str:
    """
    从文本文件提取内容
    
    Args:
        file_obj: 文本文件对象
    
    Returns:
        str: 文件内容
    """
    try:
        file_obj.seek(0)
        
        # 尝试 UTF-8 解码
        try:
            content = file_obj.read().decode('utf-8')
        except UnicodeDecodeError:
            # 回退到 GBK（中文 Windows 常用）
            file_obj.seek(0)
            content = file_obj.read().decode('gbk', errors='ignore')
        
        if not content.strip():
            return "⚠️ 警告: 文件为空"
        
        return _truncate_text(content)
        
    except Exception as e:
        return f"❌ 文本文件读取失败: {str(e)}"


def process_file(uploaded_file) -> str:
    """
    智能解析上传的文件
    
    支持的文件类型：
    - PDF (.pdf)
    - Word (.docx)
    - 文本文件 (.txt, .md, .py, .js, .json, etc.)
    
    Args:
        uploaded_file: Streamlit 的 UploadedFile 对象
    
    Returns:
        str: 解析后的文本内容
    """
    try:
        # 获取文件名和后缀
        filename = uploaded_file.name
        file_ext = Path(filename).suffix.lower()
        
        print(f"📄 正在解析文件: {filename} (类型: {file_ext})")
        
        # 根据文件类型分发处理
        if file_ext == '.pdf':
            return _extract_pdf_text(uploaded_file)
        
        elif file_ext in ['.docx', '.doc']:
            return _extract_docx_text(uploaded_file)
        
        elif file_ext in ['.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml', 
                          '.toml', '.ini', '.cfg', '.conf', '.sh', '.bat', '.csv',
                          '.html', '.css', '.xml', '.sql', '.log']:
            return _extract_text_file(uploaded_file)
        
        else:
            return f"⚠️ 不支持的文件类型: {file_ext}\n支持的类型: PDF, Word, 文本文件"
        
    except Exception as e:
        error_msg = f"❌ 文件解析失败: {str(e)}"
        print(error_msg)
        return error_msg


# ===================== 测试代码 =====================
if __name__ == "__main__":
    print("=" * 60)
    print("多模态感知工具 - 功能测试")
    print("=" * 60)
    
    print(f"\n📦 依赖检查:")
    print(f"   - OpenAI: {'✅ 可用' if OPENAI_AVAILABLE else '❌ 不可用'}")
    print(f"   - pdfplumber: {'✅ 可用' if PDF_AVAILABLE else '❌ 不可用'}")
    print(f"   - python-docx: {'✅ 可用' if DOCX_AVAILABLE else '❌ 不可用'}")
    print(f"   - Pillow: {'✅ 可用' if PILLOW_AVAILABLE else '❌ 不可用'}")
    
    print(f"\n🔧 配置检查:")
    print(f"   - LLM_API_KEY: {'✅ 已设置' if os.getenv('LLM_API_KEY') else '❌ 未设置'}")
    print(f"   - LLM_API_BASE: {os.getenv('LLM_API_BASE', '未设置')}")
    print(f"   - LLM_MODEL_NAME: {os.getenv('LLM_MODEL_NAME', '未设置')}")
    
    print(f"\n✅ 模块加载成功！")
