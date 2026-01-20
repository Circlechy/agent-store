"""OpenJiuwen 自动化 Agent 主程序入口"""

import sys
import io

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from agent import OpenJiuwenAgent
from config.settings import validate_config, get_settings


def print_banner():
    """打印欢迎横幅"""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║     OpenJiuwen 自动化 Agent - 文件操作助手            ║
    ╚═══════════════════════════════════════════════════════╝
    """
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
    可用命令:
      help, h      - 显示此帮助信息
      exit, quit   - 退出程序
      clear        - 清屏
    
    示例任务:
      - "列出当前目录的内容"
      - "读取文件 example.txt"
      - "创建一个名为 test.txt 的文件，内容为 'Hello World'"
      - "在项目根目录创建一个名为 data 的目录"
    """
    print(help_text)


def main():
    """主函数"""
    print_banner()
    
    # 验证配置
    is_valid, message = validate_config()
    if not is_valid:
        print(f"\n❌ {message}")
        print("\n请检查 .env 文件配置，或参考 .env.example 文件。")
        sys.exit(1)
    
    print("✅ 配置验证通过\n")
    
    # 初始化 Agent
    try:
        print("正在初始化 Agent...")
        agent = OpenJiuwenAgent()
        print("✅ Agent 初始化成功\n")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {str(e)}")
        sys.exit(1)
    
    # 交互式循环
    print("输入 'help' 查看帮助，输入 'exit' 退出程序\n")
    
    while True:
        try:
            # 获取用户输入
            user_input = input("🤖 > ").strip()
            
            if not user_input:
                continue
            
            # 处理特殊命令
            if user_input.lower() in ["exit", "quit"]:
                print("\n再见！")
                break
            elif user_input.lower() in ["help", "h"]:
                print_help()
                continue
            elif user_input.lower() == "clear":
                import os
                os.system("cls" if os.name == "nt" else "clear")
                print_banner()
                continue
            
            # 执行 Agent 任务
            print("\n正在处理...\n")
            response = agent.run(user_input)
            print(f"\n📝 响应:\n{response}\n")
            print("-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n程序被用户中断。再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}\n")


if __name__ == "__main__":
    main()
