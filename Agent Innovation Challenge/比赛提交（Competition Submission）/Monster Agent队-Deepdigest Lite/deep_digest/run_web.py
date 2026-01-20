#!/usr/bin/env python
"""
DeepDigest Lite - Web 启动脚本
使用 Streamlit 启动 Web 界面

使用方法:
    从 agent-core 根目录运行:
        uv run deep_digest/run_web.py
    
    或直接使用 streamlit:
        uv run streamlit run deep_digest/src/ui/app.py
"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
SCRIPT_DIR = Path(__file__).parent  # deep_digest/
PROJECT_ROOT = SCRIPT_DIR.parent     # agent-core/

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def main():
    """启动 Streamlit 应用"""
    # 切换到项目根目录
    os.chdir(PROJECT_ROOT)
    
    # 构建启动命令
    app_path = SCRIPT_DIR / "src" / "ui" / "app.py"
    
    print("=" * 50)
    print("🧠 DeepDigest Lite - Web Interface")
    print("=" * 50)
    print(f"📁 项目目录: {PROJECT_ROOT}")
    print(f"🚀 启动应用: {app_path}")
    print("=" * 50)
    print()
    
    # 启动 Streamlit
    cmd = f'streamlit run "{app_path}" --server.headless=true'
    
    print(f"执行命令: {cmd}")
    print()
    
    os.system(cmd)


if __name__ == "__main__":
    main()
