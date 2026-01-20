"""
多模态感知工具测试脚本
用于验证图片识别和文档解析功能
"""

import sys
from pathlib import Path

# 添加项目路径
DEEP_DIGEST_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(DEEP_DIGEST_ROOT))

from src.tools.sense_tools import (
    OPENAI_AVAILABLE,
    PDF_AVAILABLE,
    DOCX_AVAILABLE,
    PILLOW_AVAILABLE,
    process_file,
    process_image,
    _init_openai_client
)


def test_dependencies():
    """测试依赖库是否安装"""
    print("=" * 60)
    print("📦 依赖检查")
    print("=" * 60)
    
    deps = {
        "OpenAI": OPENAI_AVAILABLE,
        "pdfplumber": PDF_AVAILABLE,
        "python-docx": DOCX_AVAILABLE,
        "Pillow": PILLOW_AVAILABLE
    }
    
    for name, available in deps.items():
        status = "✅ 已安装" if available else "❌ 未安装"
        print(f"   {name}: {status}")
    
    print()


def test_openai_client():
    """测试 OpenAI 客户端初始化"""
    print("=" * 60)
    print("🔧 OpenAI 客户端测试")
    print("=" * 60)
    
    client = _init_openai_client()
    
    if client:
        print("✅ OpenAI 客户端初始化成功")
    else:
        print("❌ OpenAI 客户端初始化失败")
        print("   请检查 .env 文件中的 LLM_API_KEY 和 LLM_API_BASE")
    
    print()


def test_text_file():
    """测试文本文件解析"""
    print("=" * 60)
    print("📄 文本文件解析测试")
    print("=" * 60)
    
    # 创建一个临时测试文件
    from io import BytesIO
    
    class MockUploadedFile:
        def __init__(self, name, content):
            self.name = name
            self.file = BytesIO(content.encode('utf-8'))
        
        def read(self):
            return self.file.read()
        
        def seek(self, pos):
            return self.file.seek(pos)
    
    test_content = """# 测试文档
这是一个测试文本文件。
包含多行内容。

## 功能列表
- 功能 1
- 功能 2
"""
    
    mock_file = MockUploadedFile("test.md", test_content)
    result = process_file(mock_file)
    
    print(f"解析结果:\n{result}")
    print()


def main():
    """主测试函数"""
    print("\n🧪 多模态感知工具 - 功能测试\n")
    
    test_dependencies()
    test_openai_client()
    test_text_file()
    
    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    print("\n💡 提示:")
    print("   1. 如果依赖缺失，请运行: pip install -r requirements.txt")
    print("   2. 如果 OpenAI 客户端失败，请检查 .env 配置")
    print("   3. 在 Streamlit 界面中上传文件进行完整测试")
    print()


if __name__ == "__main__":
    main()
