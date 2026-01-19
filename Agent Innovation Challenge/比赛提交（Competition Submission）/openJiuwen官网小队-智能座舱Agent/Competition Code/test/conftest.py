import pytest
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 设置环境变量（在导入任何模块之前）
os.environ.setdefault('MODEL_PROVIDER', 'test')
os.environ.setdefault('MODEL_NAME', 'test-model')
os.environ.setdefault('API_BASE', 'https://test.api')
os.environ.setdefault('API_KEY', 'test-key')
os.environ.setdefault('TAVILY_API_KEY', 'test-tavily-key')

# Patch logging 和 dotenv 以避免在导入时执行
import logging
import dotenv

original_basicConfig = logging.basicConfig
original_load_dotenv = dotenv.load_dotenv

def patched_basicConfig(**kwargs):
    """不执行任何操作的 logging.basicConfig"""
    pass

def patched_load_dotenv(**kwargs):
    """不执行任何操作的 dotenv.load_dotenv"""
    pass

logging.basicConfig = patched_basicConfig
dotenv.load_dotenv = patched_load_dotenv

# 配置 pytest
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# 清理：恢复原始函数
@pytest.fixture(scope="session", autouse=True)
def restore_original_functions():
    """在测试会话结束后恢复原始函数"""
    yield
    logging.basicConfig = original_basicConfig
    dotenv.load_dotenv = original_load_dotenv
