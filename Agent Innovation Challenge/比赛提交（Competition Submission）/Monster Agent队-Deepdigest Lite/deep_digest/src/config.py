"""
配置管理模块
负责从 .env 加载 LLM 配置，并生成 OpenJiuwen 的 ModelConfig 对象
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

# 加载项目根目录的 .env 文件
PROJECT_ROOT = Path(__file__).parent.parent.parent  # deep_digest/../..
ENV_FILE = PROJECT_ROOT / ".env"

print(f"🔍 正在加载配置...")
print(f"   - .env 路径: {ENV_FILE}")
print(f"   - .env 存在: {ENV_FILE.exists()}")

if ENV_FILE.exists():
    # 强制重新加载，覆盖已有的环境变量
    load_dotenv(ENV_FILE, override=True)
    print(f"   - .env 已加载 ✅")
    
    # 调试输出：显示关键环境变量
    print(f"   - LLM_MODEL_NAME: {os.getenv('LLM_MODEL_NAME', '未设置')}")
    print(f"   - LLM_API_BASE: {os.getenv('LLM_API_BASE', '未设置')}")
else:
    print(f"⚠️ 警告: 未找到 .env 文件 ({ENV_FILE})")


# ===================== 项目路径配置 =====================
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "deep_digest.db"
MEMORY_JSON_PATH = DATA_DIR / "memory_cards.json"


# ===================== 音频配置 (Groq Whisper) =====================
def get_audio_config() -> dict:
    """
    获取音频转写配置 (使用 Groq 的免费 Whisper API)
    
    Returns:
        dict: 包含 api_key, base_url, model 的配置字典
    """
    return {
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "base_url": os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
        "model": os.getenv("GROQ_AUDIO_MODEL", "whisper-large-v3")
    }


# ===================== LLM 配置 =====================
def get_model_config() -> ModelConfig:
    """
    从环境变量读取 LLM 配置，返回 OpenJiuwen 的 ModelConfig 对象
    
    环境变量说明:
        LLM_MODEL_PROVIDER: 模型提供商 (openai, azure, etc.)
        LLM_API_KEY: API密钥
        LLM_API_BASE: API地址
        LLM_MODEL_NAME: 模型名称
        LLM_SSL_VERIFY: 是否启用SSL验证 (true/false)
    """
    model_provider = os.getenv("LLM_MODEL_PROVIDER", "openai")
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model_name = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    ssl_verify = os.getenv("LLM_SSL_VERIFY", "true").lower() == "true"
    
    # 调试：打印环境变量
    print(f"\n🔍 [config.py] 读取环境变量:")
    print(f"   - LLM_MODEL_PROVIDER: {model_provider}")
    print(f"   - LLM_MODEL_NAME: {model_name}")
    print(f"   - LLM_API_BASE: {api_base}")
    print(f"   - LLM_API_KEY: {api_key[:20]}..." if api_key else "None")
    
    if not api_key:
        raise ValueError("❌ 错误: 未设置 LLM_API_KEY 环境变量")
    
    if not api_base:
        raise ValueError("❌ 错误: 未设置 LLM_API_BASE 环境变量")
    
    # 构建 BaseModelInfo
    # 注意：BaseModelInfo 中 model_name 的别名是 "model"，所以这里要用 model 参数
    model_info = BaseModelInfo(
        api_key=api_key,
        api_base=api_base,
        model=model_name,  # 使用 model 而不是 model_name
        streaming=True
    )
    
    # 调试：检查 BaseModelInfo 是否正确设置
    print(f"\n🔍 [config.py] BaseModelInfo 创建后:")
    print(f"   - model_info.model_name: '{model_info.model_name}'")
    print(f"   - model_info.__dict__: {model_info.__dict__ if hasattr(model_info, '__dict__') else 'N/A'}")
    
    # 构建 OpenJiuwen 的 ModelConfig
    model_config = ModelConfig(
        model_provider=model_provider,
        model_info=model_info
    )
    
    # 如果禁用 SSL 验证，需要设置环境变量 (OpenJiuwen/httpx 会读取)
    if not ssl_verify:
        os.environ["HTTPX_SSL_VERIFY"] = "false"
        os.environ["SSL_CERT_FILE"] = ""
    
    print(f"✅ LLM 配置加载成功:")
    print(f"   - 提供商: {model_provider}")
    print(f"   - 模型: {model_name}")
    print(f"   - API: {api_base}")
    print(f"   - SSL验证: {'启用' if ssl_verify else '禁用'}")
    
    return model_config


# ===================== 数据库配置 =====================
INBOX_TABLE = "fragments"
INBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'
);
"""


# ===================== 记忆卡片模式 =====================
CARD_TYPES = ["tech", "todo", "idea"]  # 卡片类型


# ===================== 测试配置 =====================
if __name__ == "__main__":
    print("=" * 50)
    print("DeepDigest Lite 配置测试")
    print("=" * 50)
    
    print(f"\n📁 项目路径:")
    print(f"   - 根目录: {PROJECT_ROOT}")
    print(f"   - 数据目录: {DATA_DIR}")
    print(f"   - 数据库: {DB_PATH}")
    print(f"   - 记忆库: {MEMORY_JSON_PATH}")
    
    print(f"\n🤖 LLM 配置:")
    try:
        model_config = get_model_config()
        print("   配置对象创建成功 ✅")
    except Exception as e:
        print(f"   配置加载失败: {e}")
