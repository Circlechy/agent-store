#!/usr/bin/env python
"""
智能座舱模拟器启动脚本

同时启动：
1. Web UI 模拟器（可视化界面）
2. 智能Agent（命令行交互）

使用方法：
    python run_simulator.py           # 同时启动UI和Agent
    python run_simulator.py --ui-only  # 仅启动UI
    python run_simulator.py --agent-only # 仅启动Agent
"""

import asyncio
import sys
import os
import signal
import threading
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def run_web_ui(host: str = "0.0.0.0", port: int = 8080):
    """启动Web UI服务器"""
    import uvicorn
    from simulator_ui.server import app
    
    print(f"\n🖥️  Web UI 启动中...")
    print(f"📍 访问地址: http://localhost:{port}")
    print(f"📡 WebSocket: ws://localhost:{port}/ws\n")
    
    uvicorn.run(app, host=host, port=port, log_level="warning")


async def run_agent_interactive(force_next_node: str = None):
    """启动交互式Agent"""
    from smart_agent import interactive_mode
    await interactive_mode(enable_memory=True, force_next_node=force_next_node)


def main():
    parser = argparse.ArgumentParser(description="🚗 智能座舱模拟器")
    parser.add_argument("--ui-only", action="store_true", help="仅启动Web UI")
    parser.add_argument("--agent-only", action="store_true", help="仅启动Agent")
    parser.add_argument("--multi-agent", action="store_true", help="强制走MultiAgent流程（测试用）")
    parser.add_argument("--port", type=int, default=8080, help="Web UI端口")
    parser.add_argument("--host", default="0.0.0.0", help="Web UI监听地址")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🚗 智能座舱模拟器 v2.0")
    print("="*60)
    
    if args.ui_only:
        # 仅启动UI
        run_web_ui(args.host, args.port)
    elif args.agent_only:
        # 仅启动Agent
        force_next_node = "multi_agent" if args.multi_agent else None
        asyncio.run(run_agent_interactive(force_next_node=force_next_node))
    else:
        # 同时启动
        print("\n📌 提示：")
        print(f"   1. 打开浏览器访问 http://localhost:{args.port} 查看车机状态")
        print("   2. 在下方命令行与智能助手对话")
        print("   3. 对话时车机状态会实时更新到Web界面")
        print("="*60)
        
        # 在后台线程启动Web UI
        ui_thread = threading.Thread(
            target=run_web_ui, 
            args=(args.host, args.port),
            daemon=True
        )
        ui_thread.start()
        
        # 等待UI启动
        import time
        time.sleep(2)
        
        # 在主线程运行Agent
        try:
            force_next_node = "multi_agent" if args.multi_agent else None
            asyncio.run(run_agent_interactive(force_next_node=force_next_node))
        except KeyboardInterrupt:
            print("\n\n👋 再见！")


if __name__ == "__main__":
    main()
