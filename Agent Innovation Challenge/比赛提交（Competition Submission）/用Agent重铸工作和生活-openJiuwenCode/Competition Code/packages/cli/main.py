#!/usr/bin/env python3
"""
jiuwen - AI 编程助手

基于 openJiuwen agent-core SDK 的智能编程助手
类似 Claude Code 的交互式命令行工具
"""

import asyncio
import sys
import os
import getpass
from pathlib import Path
from typing import List, Optional

from packages.server.utils.platform_compat import set_file_permissions

# prompt_toolkit 用于支持完整的行编辑功能（退格、光标移动等）
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.completion import Completer, Completion

# 设置 SSL 验证为 false（避免 SDK 要求提供 SSL 证书）
os.environ.setdefault("LLM_SSL_VERIFY", "false")

# 敏感模式：true=隐藏LLM输入输出，false=打印完整LLM输入输出（调试用）
# os.environ.setdefault("IS_SENSITIVE", "false")  # 取消注释以启用调试

# 智能路径处理：支持开发环境和全局安装环境
def setup_project_paths():
    """设置项目路径，优先使用本地源码，确保代码修改立即生效"""
    import sys
    from pathlib import Path
    import shutil

    # 策略：优先查找本地的 agent-core，确保开发时修改立即生效
    # 只有在找不到本地代码时，才使用已安装的版本

    found_local = False
    project_root = None
    agent_core_path = None

    # 1. 从当前文件位置向上查找项目根目录
    # packages/cli/main.py -> project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent

    agent_core_path = project_root / "agent-core"
    if agent_core_path.exists() and (agent_core_path / "openjiuwen").exists():
        # 找到本地 agent-core，优先使用
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        if str(agent_core_path) not in sys.path:
            sys.path.insert(0, str(agent_core_path))
        found_local = True

    # 2. 检查当前工作目录
    if not found_local:
        cwd = Path.cwd()
        agent_core_in_cwd = cwd / "agent-core"
        if agent_core_in_cwd.exists() and (agent_core_in_cwd / "openjiuwen").exists():
            project_root = cwd
            agent_core_path = agent_core_in_cwd
            if str(cwd) not in sys.path:
                sys.path.insert(0, str(cwd))
            if str(agent_core_in_cwd) not in sys.path:
                sys.path.insert(0, str(agent_core_in_cwd))
            found_local = True

    # 3. 清除 Python 缓存，确保代码修改立即生效
    if found_local and agent_core_path:
        try:
            # 清除 agent-core 的 __pycache__
            pycache_dirs = list(agent_core_path.rglob("__pycache__"))
            for pycache in pycache_dirs:
                if pycache.is_dir():
                    shutil.rmtree(pycache)

            # 清除 packages 的 __pycache__
            packages_dir = project_root / "packages"
            if packages_dir.exists():
                pycache_dirs = list(packages_dir.rglob("__pycache__"))
                for pycache in pycache_dirs:
                    if pycache.is_dir():
                        shutil.rmtree(pycache)
        except Exception:
            # 清除缓存失败不影响运行
            pass

setup_project_paths()

# ============================================================================
# 配置常量
# ============================================================================

VERSION = "0.1.0"
JIUWEN_CONFIG_DIR = Path.home() / ".jiuwen"
JIUWEN_CONFIG_FILE = JIUWEN_CONFIG_DIR / "config.yaml"


# ============================================================================
# ANSI 颜色代码（用于欢迎界面）
# ============================================================================

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# 工具名称映射 - 将内部名称转换为友好显示名称
TOOL_DISPLAY_NAMES = {
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "bash": "Bash",
    "grep": "Grep",
    "glob": "Glob",
    "ls": "LS",
    "todo_write": "TodoWrite",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
}


def get_tool_display_name(tool_name: str, args: dict = None) -> str:
    """获取工具的友好显示名称

    Args:
        tool_name: 工具内部名称
        args: 工具参数（用于动态判断，如 write_file 区分 Write/Update）
    """
    # write_file 特殊处理：根据文件是否存在显示 Write 或 Update
    if tool_name == "write_file" and args:
        file_path = args.get("file_path", "")
        if file_path and os.path.exists(file_path):
            return "Update"
        return "Write"

    return TOOL_DISPLAY_NAMES.get(tool_name, tool_name.title().replace("_", ""))


# ASCII 艺术字 - JIUWEN CODE (砖块风格) - 用于首次登录
LOGO_ART = r'''
    ██╗██╗██╗   ██╗██╗    ██╗███████╗███╗   ██╗
    ██║██║██║   ██║██║    ██║██╔════╝████╗  ██║
    ██║██║██║   ██║██║ █╗ ██║█████╗  ██╔██╗ ██║
██  ██║██║██║   ██║██║███╗██║██╔══╝  ██║╚██╗██║
╚████╔╝██║╚██████╔╝╚███╔███╔╝███████╗██║ ╚████║
 ╚═══╝ ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝

 ██████╗ ██████╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗
██║     ██║   ██║██║  ██║██╔══╝
╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
'''

# ASCII 艺术字 - 紧凑版 JIUWEN CODE (单行风格) - 用于已登录状态
LOGO_ART_COMPACT = r'''
     ██╗██╗██╗   ██╗██╗    ██╗███████╗███╗   ██╗       ██████╗ ██████╗ ██████╗ ███████╗
     ██║██║██║   ██║██║    ██║██╔════╝████╗  ██║      ██╔════╝██╔═══██╗██╔══██╗██╔════╝
     ██║██║██║   ██║██║ █╗ ██║█████╗  ██╔██╗ ██║      ██║     ██║   ██║██║  ██║█████╗
██   ██║██║██║   ██║██║███╗██║██╔══╝  ██║╚██╗██║      ██║     ██║   ██║██║  ██║██╔══╝
╚█████╔╝██║╚██████╔╝╚███╔███╔╝███████╗██║ ╚████║      ╚██████╗╚██████╔╝██████╔╝███████╗
 ╚════╝ ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝       ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
'''

# 小型 Logo - Claude Code 风格
LOGO_MINI = r'''
 ▐▛███▜▌   Jiuwen Code v{version}
▝▜█████▛▘  {model} · {provider}
  ▘▘ ▝▝    {cwd}
'''


# ============================================================================
# 配置管理
# ============================================================================

def get_default_api_base(provider: str) -> str:
    """获取默认 API Base URL"""
    defaults = {
        "anthropic": "https://api.anthropic.com",
        "openai": "https://api.openai.com/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "custom": ""
    }
    return defaults.get(provider, "")


def get_default_model(provider: str) -> str:
    """获取默认模型"""
    defaults = {
        "anthropic": "claude-sonnet-4-5-20250929",
        "openai": "gpt-4o",
        "zhipu": "glm-4",
        "custom": ""
    }
    return defaults.get(provider, "")


def get_config() -> dict:
    """读取配置文件

    优先级：配置文件 > 环境变量 > 默认值
    """
    config = {
        "api_key": None,
        "api_base_url": None,
        "provider": "anthropic",
        "model": "claude-sonnet-4-5-20250929"
    }

    # 1. 首先从配置文件读取（最高优先级）
    if JIUWEN_CONFIG_FILE.exists():
        try:
            import yaml
            with open(JIUWEN_CONFIG_FILE, 'r') as f:
                file_config = yaml.safe_load(f) or {}
                if file_config.get("api_key"):
                    config["api_key"] = file_config["api_key"]
                if file_config.get("api_base_url"):
                    config["api_base_url"] = file_config["api_base_url"]
                if file_config.get("provider"):
                    config["provider"] = file_config["provider"]
                if file_config.get("model"):
                    config["model"] = file_config["model"]
        except Exception:
            pass

    # 2. 如果配置文件没有 api_key，从环境变量读取
    if not config["api_key"]:
        # 根据 provider 选择对应的环境变量
        env_key_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
        }
        env_var = env_key_map.get(config["provider"])
        if env_var:
            config["api_key"] = os.environ.get(env_var)

        # 如果还是没有，尝试所有环境变量
        if not config["api_key"]:
            config["api_key"] = (os.environ.get("ANTHROPIC_API_KEY") or
                                 os.environ.get("OPENAI_API_KEY") or
                                 os.environ.get("ZHIPU_API_KEY"))

    # 3. 如果配置文件没有 api_base_url，从环境变量读取
    if not config["api_base_url"]:
        config["api_base_url"] = (os.environ.get("API_BASE_URL") or
                                  os.environ.get("ANTHROPIC_API_BASE") or
                                  os.environ.get("OPENAI_API_BASE"))

    # 4. 如果还是没有 api_base_url，使用默认值
    if not config["api_base_url"]:
        config["api_base_url"] = get_default_api_base(config["provider"])

    return config


def save_config(api_key: str, provider: str = "anthropic", 
                model: str = None, api_base_url: str = None):
    """保存配置到文件"""
    JIUWEN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    config = {
        "api_key": api_key,
        "provider": provider,
    }
    if api_base_url:
        config["api_base_url"] = api_base_url
    if model:
        config["model"] = model
    
    try:
        import yaml
        with open(JIUWEN_CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except ImportError:
        with open(JIUWEN_CONFIG_FILE, 'w') as f:
            f.write(f"api_key: {api_key}\n")
            f.write(f"provider: {provider}\n")
            if api_base_url:
                f.write(f"api_base_url: {api_base_url}\n")
            if model:
                f.write(f"model: {model}\n")
    
    set_file_permissions(JIUWEN_CONFIG_FILE, 0o600)


def prompt_api_key_setup() -> bool:
    """交互式提示用户配置 API Key"""
    print()
    print(f"  {Colors.BRIGHT_YELLOW}⚠{Colors.RESET}  未检测到 API Key 配置")
    print()
    print(f"  {Colors.DIM}Jiuwen Code 需要 API Key 才能运行。{Colors.RESET}")
    print(f"  {Colors.DIM}您可以从 https://console.anthropic.com 获取 Anthropic API Key。{Colors.RESET}")
    print()
    
    while True:
        try:
            response = input(
                f"  {Colors.BRIGHT_CYAN}?{Colors.RESET} 是否现在配置 API Key? "
                f"{Colors.DIM}(Y/n){Colors.RESET} "
            ).strip().lower()
            if response in ('', 'y', 'yes', '是'):
                break
            elif response in ('n', 'no', '否'):
                print()
                print(f"  {Colors.DIM}您可以稍后通过以下方式配置:{Colors.RESET}")
                print(f"    • 运行 {Colors.BRIGHT_WHITE}jiuwen --config{Colors.RESET}")
                print(f"    • 设置环境变量 {Colors.BRIGHT_WHITE}ANTHROPIC_API_KEY{Colors.RESET}")
                print(f"    • 编辑配置文件 {Colors.BRIGHT_WHITE}~/.jiuwen/config.yaml{Colors.RESET}")
                print()
                return False
        except (KeyboardInterrupt, EOFError):
            print()
            return False
    
    print()
    
    # 选择 Provider
    print(f"  {Colors.BRIGHT_CYAN}?{Colors.RESET} 选择 API 提供商:")
    print(f"    {Colors.BRIGHT_WHITE}1{Colors.RESET}. Anthropic (Claude)")
    print(f"    {Colors.BRIGHT_WHITE}2{Colors.RESET}. OpenAI (GPT)")
    print(f"    {Colors.BRIGHT_WHITE}3{Colors.RESET}. 智谱 (GLM-4) {Colors.DIM}[国产推荐]{Colors.RESET}")
    print(f"    {Colors.BRIGHT_WHITE}4{Colors.RESET}. 其他 (自定义)")
    print()
    
    provider = "anthropic"
    model = None
    api_base_url = None
    
    while True:
        try:
            choice = input(f"  {Colors.DIM}请输入选项 (1-4) [1]:{Colors.RESET} ").strip()
            if choice in ('', '1'):
                provider = "anthropic"
                model = get_default_model("anthropic")
                break
            elif choice == '2':
                provider = "openai"
                model = get_default_model("openai")
                break
            elif choice == '3':
                provider = "zhipu"
                model = get_default_model("zhipu")
                break
            elif choice == '4':
                provider = "custom"
                break
            else:
                print(f"  {Colors.RED}无效选项，请输入 1-4{Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print()
            return False
    
    print()
    
    # 输入 API Base URL
    default_api_base = get_default_api_base(provider)
    print(f"  {Colors.BRIGHT_CYAN}?{Colors.RESET} 请输入 API Base URL:")
    if default_api_base:
        print(f"  {Colors.DIM}按 Enter 使用默认值: {default_api_base}{Colors.RESET}")
    else:
        print(f"  {Colors.DIM}例如: https://api.example.com/v1{Colors.RESET}")
    print()
    
    try:
        api_base_input = input(f"  {Colors.DIM}API Base URL:{Colors.RESET} ").strip()
        if api_base_input:
            api_base_url = api_base_input
        else:
            api_base_url = default_api_base
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    
    print()
    
    # 输入 API Key
    api_key_label = {
        "anthropic": "Anthropic API Key",
        "openai": "OpenAI API Key",
        "zhipu": "智谱 API Key",
        "custom": "API Key"
    }.get(provider, "API Key")
    
    print(f"  {Colors.BRIGHT_CYAN}?{Colors.RESET} 请输入 {api_key_label}:")
    print(f"  {Colors.DIM}(输入内容不会显示在屏幕上){Colors.RESET}")
    print()
    
    try:
        api_key = getpass.getpass(f"  {Colors.DIM}API Key:{Colors.RESET} ")
        if not api_key.strip():
            print(f"  {Colors.RED}API Key 不能为空{Colors.RESET}")
            return False
        api_key = api_key.strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    
    # 验证 API Key 格式
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        print()
        print(f"  {Colors.BRIGHT_YELLOW}⚠{Colors.RESET}  API Key 格式看起来不正确")
        print(f"  {Colors.DIM}Anthropic API Key 通常以 'sk-ant-' 开头{Colors.RESET}")
        try:
            confirm = input(
                f"  {Colors.DIM}是否仍要保存? (y/N):{Colors.RESET} "
            ).strip().lower()
            if confirm not in ('y', 'yes', '是'):
                return False
        except (KeyboardInterrupt, EOFError):
            print()
            return False
    
    # 保存配置
    print()
    print(f"  {Colors.DIM}正在保存配置...{Colors.RESET}")
    
    try:
        save_config(api_key, provider, model, api_base_url)
        print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} 配置已保存到 "
              f"{Colors.BRIGHT_WHITE}~/.jiuwen/config.yaml{Colors.RESET}")
        print()
        
        # 设置环境变量
        env_var = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "zhipu": "ZHIPU_API_KEY"
        }.get(provider, "API_KEY")
        os.environ[env_var] = api_key
        if api_base_url:
            os.environ["API_BASE_URL"] = api_base_url
        
        return True
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} 保存配置失败: {e}")
        return False


def check_and_setup_config() -> bool:
    """检查配置，如果需要则引导用户设置"""
    config = get_config()
    if config.get("api_key"):
        return True
    return prompt_api_key_setup()


# ============================================================================
# 欢迎界面
# ============================================================================

def print_welcome_screen():
    """打印欢迎界面 - Claude Code 风格"""
    print("\033[2J\033[H", end="")
    
    print()
    print(f"  {Colors.DIM}●{Colors.RESET} Welcome to the "
          f"{Colors.BRIGHT_CYAN}Jiuwen Code{Colors.RESET} research preview!")
    print()
    
    lines = LOGO_ART.strip().split('\n')
    brick_colors = [
        "\033[38;5;196m", "\033[38;5;202m", "\033[38;5;208m",
        "\033[38;5;214m", "\033[38;5;220m", "\033[38;5;226m",
    ]
    
    color_idx = 0
    for line in lines:
        if line.strip():
            color = brick_colors[color_idx % len(brick_colors)]
            print(f"  {color}{line}{Colors.RESET}")
            color_idx += 1
        else:
            print()
    
    print()
    print(f"  {Colors.BRIGHT_GREEN}●{Colors.RESET} Login successful. "
          f"Press {Colors.BOLD}Enter{Colors.RESET} to continue")
    print()


# ============================================================================
# 命令自动补全
# ============================================================================

class SlashCommandCompleter(Completer):
    """/ 命令自动补全器"""

    COMMANDS = [
        ("/help", "显示帮助信息"),
        ("/mode", "显示当前模式"),
        ("/tools", "显示可用工具"),
        ("/skills", "显示可用 skills"),
        ("/skill", "激活指定 skill"),
        ("/skill install", "安装远程 skill 插件"),
        ("/skill uninstall", "卸载 skill 插件"),
        ("/skill update", "更新 skill 插件"),
        ("/skill list-installed", "列出已安装的插件"),
        ("/build", "切换到 BUILD 模式"),
        ("/plan", "切换到 PLAN 模式"),
        ("/review", "切换到 REVIEW 模式"),
        ("/config", "显示配置信息"),
        ("/install-gitcode-app", "显示 GitCode App 安装指南"),
        ("/clear", "清屏"),
        ("/exit", "退出程序"),
        ("/quit", "退出程序"),
    ]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # 只在输入以 / 开头时提供补全
        if not text.startswith("/"):
            return

        # 获取当前输入的命令部分
        word = text.lower()

        for cmd, desc in self.COMMANDS:
            if cmd.startswith(word):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display_meta=desc
                )


# ============================================================================
# 交互式 CLI (使用 openJiuwen SDK)
# ============================================================================

class JiuwenCLI:
    """Jiuwen Code 交互式命令行界面
    
    基于 openJiuwen SDK 集成
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.running = True
        self.session_id = f"session_{os.getpid()}"
        
        # 延迟导入 Rich
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.markdown import Markdown
            from rich.table import Table
            self.console = Console()
            self.has_rich = True
        except ImportError:
            self.console = None
            self.has_rich = False
        
        # 初始化 openJiuwen Agent
        self.agent = None
        self._init_agent()
    
    def _init_agent(self):
        """初始化 openJiuwen Agent"""
        try:
            from packages.server.agents.openjiuwen_agent import JiuwenCodeAgent

            api_key = self.config.get("api_key")
            provider = self.config.get("provider", "openai")
            model = self.config.get("model")
            api_base = self.config.get("api_base_url")

            # 创建 Agent
            self.agent = JiuwenCodeAgent(
                model_provider=provider,
                api_key=api_key,
                api_base=api_base,
                model_name=model or "gpt-4o",
                session_id=self.session_id,
            )
            # Agent 初始化成功，不打印消息（保持界面简洁）

        except Exception as e:
            self._print(f"  {Colors.BRIGHT_YELLOW}⚠{Colors.RESET} Agent 初始化警告: {e}")
            self.agent = None
    
    def _print(self, text: str, **kwargs):
        """打印输出"""
        if self.has_rich and self.console:
            # 将 ANSI 颜色代码转换为 Rich 格式或直接打印
            import re
            # 检查是否包含 ANSI 码
            if '\033[' in text:
                print(text)
            else:
                self.console.print(text, **kwargs)
        else:
            # 移除 Rich 标记
            import re
            clean_text = re.sub(r'\[.*?\]', '', text)
            print(clean_text)
    
    def show_welcome(self, style: str = "compact"):
        """显示欢迎信息

        Args:
            style: 界面风格
                - "compact": 紧凑版（用户提供的示例风格）
                - "mini": Claude Code 风格（极简）
        """
        # 清屏
        print("\033[2J\033[H", end="")

        # 获取配置信息
        provider = self.config.get("provider", "unknown")
        model = self.config.get("model", "unknown")
        mode = self.agent.get_current_mode().value.upper() if self.agent else "BUILD"
        cwd = os.getcwd()
        # 缩短路径显示
        home = str(Path.home())
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]

        if style == "mini":
            # Claude Code 极简风格
            print()
            print(f" {Colors.BRIGHT_CYAN}▐▛███▜▌{Colors.RESET}   {Colors.BOLD}Jiuwen Code{Colors.RESET} v{VERSION}")
            print(f"{Colors.BRIGHT_CYAN}▝▜█████▛▘{Colors.RESET}  {Colors.BRIGHT_WHITE}{model}{Colors.RESET} · {Colors.DIM}{provider}{Colors.RESET}")
            print(f"  {Colors.BRIGHT_CYAN}▘▘ ▝▝{Colors.RESET}    {Colors.DIM}{cwd}{Colors.RESET}")
            print()
            print(f"  {Colors.BRIGHT_GREEN}Welcome to {model}{Colors.RESET}")
            print()
            # 分隔线
            term_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
            print(f"{Colors.DIM}{'─' * term_width}{Colors.RESET}")
        else:
            # 紧凑版风格 - 马年主题
            # Logo 和马并排显示
            logo_lines = [line for line in LOGO_ART_COMPACT.splitlines() if line.strip()]

            # 可爱卡通马头 ASCII 艺术 (马年主题) - 侧面马头
            horse_lines = [
                "    ,/|            ",
                "   / ' \\    🐴    ",
                "  /  ◕  \\         ",
                " /_______\\  马年  ",
                "    ||  ||   大吉  ",
                "   _||  ||_  🎊   ",
            ]

            gradient_colors = [
                "\033[38;5;226m",  # 亮黄色
                "\033[38;5;220m",  # 金黄色
                "\033[38;5;214m",  # 橙黄色
                "\033[38;5;208m",  # 深橙色
                "\033[38;5;202m",  # 橙红色
                "\033[38;5;196m",  # 红色
            ]

            # 马的颜色 - 棕色渐变
            horse_color = "\033[38;5;208m"  # 橙棕色

            print()
            # 并排打印 Logo 和马
            max_lines = max(len(logo_lines), len(horse_lines))
            for i in range(max_lines):
                # Logo 部分
                if i < len(logo_lines):
                    logo_color = gradient_colors[i % len(gradient_colors)]
                    logo_part = f"{logo_color}{logo_lines[i]}{Colors.RESET}"
                else:
                    logo_part = " " * 90  # Logo 宽度占位

                # 马的部分
                if i < len(horse_lines):
                    horse_part = f"{horse_color}{horse_lines[i]}{Colors.RESET}"
                else:
                    horse_part = ""

                print(f"{logo_part}  {horse_part}")

            # 状态行
            print()
            print(f"  {Colors.DIM}v{VERSION}{Colors.RESET} | "
                  f"{Colors.DIM}Provider:{Colors.RESET} {Colors.BRIGHT_CYAN}{provider}{Colors.RESET} | "
                  f"{Colors.DIM}Model:{Colors.RESET} {Colors.BRIGHT_CYAN}{model}{Colors.RESET} | "
                  f"{Colors.DIM}Mode:{Colors.RESET} {Colors.BRIGHT_GREEN}{mode}{Colors.RESET} | "
                  f"{Colors.BRIGHT_YELLOW}🐴 马到成功{Colors.RESET}")
            # SDK 信息行
            print(f"  {Colors.DIM}Powered by{Colors.RESET} {Colors.BRIGHT_MAGENTA}openJiuwen SDK{Colors.RESET} "
                  f"{Colors.DIM}v0.1.0{Colors.RESET} "
                  f"{Colors.DIM}({Colors.RESET}{Colors.CYAN}https://gitcode.com/openJiuwen/agent-core{Colors.RESET}{Colors.DIM}){Colors.RESET}")
            print()

            # 快捷命令框
            box_width = 80
            border_char = "─"

            print(f"{Colors.DIM}╭─ 快捷命令 {border_char * (box_width - 14)}╮{Colors.RESET}")
            print(f"{Colors.DIM}│{Colors.RESET}  "
                  f"{Colors.BRIGHT_WHITE}/help{Colors.RESET} {Colors.DIM}- 查看帮助{Colors.RESET}    "
                  f"{Colors.BRIGHT_WHITE}/mode{Colors.RESET} {Colors.DIM}- 切换模式{Colors.RESET}    "
                  f"{Colors.BRIGHT_WHITE}/tools{Colors.RESET} {Colors.DIM}- 可用工具{Colors.RESET}    "
                  f"{Colors.BRIGHT_WHITE}/exit{Colors.RESET} {Colors.DIM}- 退出{Colors.RESET}   "
                  f"{Colors.DIM}│{Colors.RESET}")
            print(f"{Colors.DIM}╰{border_char * box_width}╯{Colors.RESET}")

            # 提示信息
            print(f"  {Colors.DIM}💡 运行 /install-gitcode-app 在 GitCode Issues 和 MR 中直接 @jiuwen{Colors.RESET}")
            print()
    
    def show_help(self):
        """显示帮助"""
        if not self.has_rich:
            print("\n可用命令:")
            print("  /help                - 显示帮助")
            print("  /mode                - 显示当前模式")
            print("  /tools               - 显示可用工具")
            print("  /skills              - 显示可用 skills")
            print("  /skill <name>        - 激活指定 skill")
            print("  /skill install <plugin>@<marketplace> - 安装远程插件")
            print("  /skill uninstall <plugin>@<marketplace> - 卸载插件")
            print("  /skill update <plugin>@<marketplace> - 更新插件")
            print("  /skill list-installed - 列出已安装插件")
            print("  /build               - 切换到 BUILD 模式")
            print("  /plan                - 切换到 PLAN 模式")
            print("  /review              - 切换到 REVIEW 模式")
            print("  /config              - 显示配置信息")
            print("  /install-gitcode-app - 安装 GitCode App")
            print("  /clear               - 清除屏幕")
            print("  /exit                - 退出程序")
            print()
            return

        from rich.table import Table

        table = Table(title="📖 可用命令", border_style="cyan")
        table.add_column("命令", style="cyan", width=40)
        table.add_column("说明")

        commands = [
            ("/help", "显示此帮助"),
            ("/mode", "显示当前模式信息"),
            ("/tools", "显示可用工具列表"),
            ("/skills", "显示可用 skills 列表"),
            ("/skill <name>", "激活指定 skill"),
            ("/skill install <plugin>@<marketplace>", "安装远程 skill 插件"),
            ("/skill uninstall <plugin>@<marketplace>", "卸载 skill 插件"),
            ("/skill update <plugin>@<marketplace>", "更新 skill 插件"),
            ("/skill list-installed", "列出已安装的插件"),
            ("/build", "切换到 BUILD 模式 - 完全开发权限"),
            ("/plan", "切换到 PLAN 模式 - 只读分析"),
            ("/review", "切换到 REVIEW 模式 - 代码审查"),
            ("/config", "显示配置信息"),
            ("/install-gitcode-app", "安装 GitCode App，在 Issues/MR 中 @jiuwen"),
            ("/clear", "清除屏幕"),
            ("/exit", "退出程序"),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self.console.print(table)
    
    def show_mode(self):
        """显示当前模式"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return
        
        info = self.agent.get_mode_info()
        mode = info['mode'].upper()
        
        if not self.has_rich:
            print(f"\n当前模式: {mode}")
            print(f"只读: {'是' if info['read_only'] else '否'}")
            print()
            return
        
        from rich.panel import Panel
        from rich.markdown import Markdown
        
        mode_desc = {
            "BUILD": ("🔨", "完全开发权限，可以修改文件和执行命令"),
            "PLAN": ("🔍", "只读模式，用于代码探索和规划"),
            "REVIEW": ("📝", "代码审查模式，专注于代码质量分析"),
        }
        
        emoji, desc = mode_desc.get(mode, ("❓", "未知模式"))
        
        panel_content = f"""
{emoji} **{mode} 模式**

{desc}

**只读**: {'是' if info['read_only'] else '否'}
**可用工具**: {len(info['allowed_tools'])} 个
"""
        
        self.console.print(Panel(
            Markdown(panel_content),
            title="当前模式",
            border_style="green" if mode == "BUILD" else "blue"
        ))
    
    def show_tools(self):
        """显示可用工具"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return
        
        tools = self.agent.get_available_tools()
        mode = self.agent.get_current_mode().value.upper()
        
        if not self.has_rich:
            print(f"\n可用工具 ({mode} 模式):")
            for tool in tools:
                print(f"  - {tool}")
            print()
            return
        
        from rich.table import Table
        
        table = Table(title=f"🔧 可用工具 ({mode} 模式)", border_style="cyan")
        table.add_column("工具", style="cyan")
        table.add_column("类型", style="dim")
        
        tool_types = {
            "read_file": "低层 - 文件读取",
            "write_file": "低层 - 文件写入",
            "edit_file": "中层 - 文件编辑",
            "bash": "低层 - Shell 命令",
            "grep": "中层 - 内容搜索",
            "glob": "中层 - 文件匹配",
            "ls": "中层 - 目录列表",
        }
        
        for tool in sorted(tools):
            tool_type = tool_types.get(tool, "其他")
            table.add_row(tool, tool_type)
        
        self.console.print(table)

    def show_skills(self):
        """显示可用 skills"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        skills = self.agent.list_skills()
        current_skill = self.agent.get_current_skill()

        if not skills:
            print(f"\n  {Colors.DIM}暂无可用的 skills{Colors.RESET}")
            print(f"  {Colors.DIM}在 ~/.jiuwen/skills/ 目录下创建 skill{Colors.RESET}\n")
            return

        if not self.has_rich:
            print(f"\n可用 Skills:")
            for skill in skills:
                active = " (激活)" if current_skill and skill.name == current_skill.name else ""
                print(f"  - {skill.name}{active}")
                if skill.description:
                    print(f"    {skill.description[:60]}...")
            print()
            return

        from rich.table import Table

        table = Table(title="🎯 可用 Skills", border_style="magenta")
        table.add_column("名称", style="magenta")
        table.add_column("来源", style="dim")
        table.add_column("描述", style="white")
        table.add_column("状态", style="green")

        for skill in skills:
            source = skill.source.value
            desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
            status = "✓ 激活" if current_skill and skill.name == current_skill.name else ""
            table.add_row(skill.name, source, desc, status)

        self.console.print(table)
        print(f"\n  {Colors.DIM}使用 /skill <name> 激活 skill{Colors.RESET}\n")

    def activate_skill(self, skill_name: str):
        """激活指定的 skill"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        if self.agent.activate_skill(skill_name):
            skill = self.agent.get_current_skill()
            print(f"\n  {Colors.GREEN}✓ 已激活 skill: {skill_name}{Colors.RESET}")
            if skill and skill.allowed_tools:
                tools_str = ", ".join(sorted(skill.allowed_tools))
                print(f"  {Colors.DIM}允许的工具: {tools_str}{Colors.RESET}")
            print()
        else:
            print(f"\n  {Colors.YELLOW}未找到 skill: {skill_name}{Colors.RESET}")
            print(f"  {Colors.DIM}使用 /skills 查看可用的 skills{Colors.RESET}\n")

    def deactivate_skill(self):
        """停用当前 skill"""
        if not self.agent:
            return

        current = self.agent.get_current_skill()
        if current:
            self.agent.deactivate_skill()
            print(f"\n  {Colors.YELLOW}已停用 skill: {current.name}{Colors.RESET}\n")
        else:
            print(f"\n  {Colors.DIM}当前没有激活的 skill{Colors.RESET}\n")

    def install_plugin(self, spec: str):
        """安装远程插件

        Args:
            spec: 插件规格，如 example-skills@anthropics
        """
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        print(f"\n  {Colors.CYAN}正在安装插件: {spec}{Colors.RESET}")
        print(f"  {Colors.DIM}这可能需要一些时间...{Colors.RESET}\n")

        try:
            plugin = self.agent.skill_manager.install_plugin(spec)
            print(f"  {Colors.GREEN}✓ 安装成功!{Colors.RESET}")
            print(f"    插件: {plugin.plugin_name}")
            print(f"    来源: {plugin.marketplace}")
            print(f"    Skills: {', '.join(plugin.skills)}")
            print(f"    路径: {plugin.install_path}")
            print()
        except ValueError as e:
            print(f"  {Colors.YELLOW}⚠ {e}{Colors.RESET}\n")
        except RuntimeError as e:
            print(f"  {Colors.RED}✗ 安装失败: {e}{Colors.RESET}\n")
        except Exception as e:
            print(f"  {Colors.RED}✗ 安装失败: {e}{Colors.RESET}\n")

    def uninstall_plugin(self, spec: str):
        """卸载插件

        Args:
            spec: 插件规格，如 example-skills@anthropics
        """
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        print(f"\n  {Colors.CYAN}正在卸载插件: {spec}{Colors.RESET}\n")

        try:
            self.agent.skill_manager.uninstall_plugin(spec)
            print(f"  {Colors.GREEN}✓ 卸载成功!{Colors.RESET}\n")
        except ValueError as e:
            print(f"  {Colors.YELLOW}⚠ {e}{Colors.RESET}\n")
        except Exception as e:
            print(f"  {Colors.RED}✗ 卸载失败: {e}{Colors.RESET}\n")

    def update_plugin(self, spec: str):
        """更新插件

        Args:
            spec: 插件规格，如 example-skills@anthropics
        """
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        print(f"\n  {Colors.CYAN}正在更新插件: {spec}{Colors.RESET}")
        print(f"  {Colors.DIM}这可能需要一些时间...{Colors.RESET}\n")

        try:
            plugin = self.agent.skill_manager.update_plugin(spec)
            print(f"  {Colors.GREEN}✓ 更新成功!{Colors.RESET}")
            print(f"    插件: {plugin.plugin_name}")
            print(f"    Skills: {', '.join(plugin.skills)}")
            print()
        except ValueError as e:
            print(f"  {Colors.YELLOW}⚠ {e}{Colors.RESET}\n")
        except RuntimeError as e:
            print(f"  {Colors.RED}✗ 更新失败: {e}{Colors.RESET}\n")
        except Exception as e:
            print(f"  {Colors.RED}✗ 更新失败: {e}{Colors.RESET}\n")

    def list_installed_plugins(self):
        """列出已安装的插件"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return

        plugins = self.agent.skill_manager.list_installed_plugins()

        if not plugins:
            print(f"\n  {Colors.DIM}暂无已安装的插件{Colors.RESET}")
            print(f"  {Colors.DIM}使用 /skill install <plugin>@<marketplace> 安装插件{Colors.RESET}\n")
            return

        if not self.has_rich:
            print(f"\n已安装的插件:")
            for plugin in plugins:
                print(f"  - {plugin.spec}")
                print(f"    Skills: {', '.join(plugin.skills)}")
                print(f"    安装时间: {plugin.installed_at.strftime('%Y-%m-%d %H:%M')}")
            print()
            return

        from rich.table import Table

        table = Table(title="📦 已安装的插件", border_style="green")
        table.add_column("插件", style="green")
        table.add_column("Skills", style="cyan")
        table.add_column("安装时间", style="dim")

        for plugin in plugins:
            skills_str = ", ".join(plugin.skills[:3])
            if len(plugin.skills) > 3:
                skills_str += f" (+{len(plugin.skills) - 3})"
            table.add_row(
                plugin.spec,
                skills_str,
                plugin.installed_at.strftime('%Y-%m-%d %H:%M')
            )

        self.console.print(table)
        print()

    def show_config(self):
        """显示配置信息"""
        config = self.config
        api_key = config.get("api_key", "")
        masked_key = f"{'*' * 16}...{api_key[-4:]}" if api_key else "未配置"
        
        print()
        print(f"  {Colors.BOLD}配置信息{Colors.RESET}")
        print(f"    Provider:     {Colors.BRIGHT_CYAN}{config.get('provider', 'unknown')}{Colors.RESET}")
        print(f"    API Base URL: {Colors.DIM}{config.get('api_base_url', 'default')}{Colors.RESET}")
        print(f"    API Key:      {Colors.DIM}{masked_key}{Colors.RESET}")
        print(f"    Model:        {Colors.BRIGHT_CYAN}{config.get('model', 'unknown')}{Colors.RESET}")
        print(f"    Config File:  {Colors.DIM}{JIUWEN_CONFIG_FILE}{Colors.RESET}")
        print()

    def show_install_gitcode_app(self):
        """显示 GitCode App 安装指南"""
        if not self.has_rich:
            print()
            print(f"  {Colors.BOLD}🔗 安装 Jiuwen GitCode App{Colors.RESET}")
            print()
            print("  在 GitCode Issues 和 Merge Requests 中直接 @jiuwen 获取 AI 帮助")
            print()
            print(f"  {Colors.BOLD}安装步骤:{Colors.RESET}")
            print("  1. 访问 GitCode App 市场")
            print("  2. 搜索 'Jiuwen Code' 或访问:")
            print(f"     {Colors.CYAN}https://gitcode.com/apps/jiuwen-code{Colors.RESET}")
            print("  3. 点击 '安装' 并授权到你的仓库")
            print("  4. 在 Issue 或 MR 中 @jiuwen 即可使用")
            print()
            print(f"  {Colors.BOLD}使用示例:{Colors.RESET}")
            print(f"     {Colors.DIM}@jiuwen 请帮我审查这个 MR{Colors.RESET}")
            print(f"     {Colors.DIM}@jiuwen 这个 bug 怎么修复？{Colors.RESET}")
            print(f"     {Colors.DIM}@jiuwen 帮我优化这段代码{Colors.RESET}")
            print()
            return

        from rich.panel import Panel
        from rich.markdown import Markdown

        content = """
## 🔗 安装 Jiuwen GitCode App

在 GitCode Issues 和 Merge Requests 中直接 **@jiuwen** 获取 AI 编程帮助！

### 安装步骤

1. **访问 GitCode App 市场**
2. **搜索** 'Jiuwen Code' 或直接访问:
   - https://gitcode.com/apps/jiuwen-code
3. **点击安装** 并授权到你的仓库
4. **开始使用** - 在 Issue 或 MR 中 @jiuwen

### 使用示例

```
@jiuwen 请帮我审查这个 MR
@jiuwen 这个 bug 怎么修复？
@jiuwen 帮我优化这段代码
@jiuwen 解释一下这个函数的作用
```

### 功能特性

- 🔍 **代码审查** - 自动分析 MR 中的代码变更
- 🐛 **Bug 分析** - 帮助定位和修复问题
- 💡 **代码建议** - 提供优化和改进建议
- 📝 **文档生成** - 自动生成代码注释和文档
"""

        self.console.print(Panel(
            Markdown(content),
            title="[bold cyan]GitCode App 安装指南[/bold cyan]",
            border_style="cyan"
        ))

    
    def switch_mode(self, mode_name: str):
        """切换模式"""
        if not self.agent:
            self._print("[yellow]Agent 未初始化[/yellow]")
            return
        
        from packages.server.agents.mode_manager import AgentMode
        
        mode_map = {
            "build": AgentMode.BUILD,
            "plan": AgentMode.PLAN,
            "review": AgentMode.REVIEW
        }
        
        if mode_name not in mode_map:
            self._print(f"[red]无效模式: {mode_name}[/red]")
            return
        
        old = self.agent.get_current_mode()
        new = mode_map[mode_name]
        
        if self.agent.switch_mode(new):
            print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} 模式切换: "
                  f"{old.value.upper()} → {new.value.upper()}")
            
            tips = {
                "build": f"  {Colors.DIM}💡 BUILD 模式: 完全开发权限{Colors.RESET}",
                "plan": f"  {Colors.DIM}🔍 PLAN 模式: 只读模式{Colors.RESET}",
                "review": f"  {Colors.DIM}📝 REVIEW 模式: 代码审查{Colors.RESET}"
            }
            print(tips.get(mode_name, ''))
        else:
            print(f"  {Colors.YELLOW}已经是 {new.value.upper()} 模式{Colors.RESET}")
    
    def handle_command(self, user_input: str) -> bool:
        """处理斜杠命令，返回 True 表示是命令"""
        if not user_input.startswith("/"):
            return False

        parts = user_input.split()
        cmd = parts[0].lower()

        if cmd == "/exit" or cmd == "/quit":
            self.running = False
            print(f"\n  {Colors.YELLOW}👋 再见！{Colors.RESET}\n")
            return True
        elif cmd == "/help":
            self.show_help()
            return True
        elif cmd == "/mode":
            self.show_mode()
            return True
        elif cmd == "/tools":
            self.show_tools()
            return True
        elif cmd == "/skills":
            self.show_skills()
            return True
        elif cmd == "/skill":
            # /skill 子命令处理
            if len(parts) < 2:
                print(f"  {Colors.YELLOW}用法:{Colors.RESET}")
                print(f"    /skill <name>                    - 激活指定 skill")
                print(f"    /skill install <plugin>@<marketplace> - 安装远程插件")
                print(f"    /skill uninstall <plugin>@<marketplace> - 卸载插件")
                print(f"    /skill update <plugin>@<marketplace> - 更新插件")
                print(f"    /skill list-installed            - 列出已安装插件")
                print(f"  {Colors.DIM}使用 /skills 查看可用的 skills{Colors.RESET}")
                return True

            subcmd = parts[1].lower()

            if subcmd == "install":
                if len(parts) < 3:
                    print(f"  {Colors.YELLOW}用法: /skill install <plugin>@<marketplace>{Colors.RESET}")
                    print(f"  {Colors.DIM}示例: /skill install example-skills@anthropics{Colors.RESET}")
                else:
                    self.install_plugin(parts[2])
                return True
            elif subcmd == "uninstall":
                if len(parts) < 3:
                    print(f"  {Colors.YELLOW}用法: /skill uninstall <plugin>@<marketplace>{Colors.RESET}")
                else:
                    self.uninstall_plugin(parts[2])
                return True
            elif subcmd == "update":
                if len(parts) < 3:
                    print(f"  {Colors.YELLOW}用法: /skill update <plugin>@<marketplace>{Colors.RESET}")
                else:
                    self.update_plugin(parts[2])
                return True
            elif subcmd == "list-installed":
                self.list_installed_plugins()
                return True
            else:
                # 假设是 skill 名称
                self.activate_skill(subcmd)
            return True
        elif cmd == "/build":
            self.switch_mode("build")
            return True
        elif cmd == "/plan":
            self.switch_mode("plan")
            return True
        elif cmd == "/review":
            self.switch_mode("review")
            return True
        elif cmd == "/config":
            self.show_config()
            return True
        elif cmd == "/install-gitcode-app":
            self.show_install_gitcode_app()
            return True
        elif cmd == "/clear":
            print("\033[2J\033[H", end="")
            self.show_welcome()
            return True
        else:
            # 检查是否是 skill 名称作为命令
            if self.agent:
                skill_name = cmd[1:]  # 去掉 /
                skill = self.agent.skill_manager.get_skill(skill_name)
                if skill:
                    self.activate_skill(skill_name)
                    return True
            print(f"  {Colors.YELLOW}未知命令: {cmd}，使用 /help 查看可用命令{Colors.RESET}")
            return True

        return False
    
    async def process_message(self, user_input: str):
        """处理用户消息"""
        if not self.agent:
            print(f"\n  {Colors.YELLOW}⚠️  Agent 未初始化{Colors.RESET}")
            return
        
        if not self.agent.api_key:
            print(f"\n  {Colors.YELLOW}⚠️  LLM 未配置，无法处理请求{Colors.RESET}")
            print(f"  {Colors.DIM}请运行 jiuwen --config 配置 API Key{Colors.RESET}\n")
            return
        
        try:
            # 使用 openJiuwen Agent 处理
            from packages.server.agents.openjiuwen_agent import AgentEvent
            import sys
            import time
            
            current_tool = None  # 当前正在执行的工具
            current_tool_args = {}  # 当前工具的参数
            content_buffer = ""  # 流式内容缓冲
            
            async for event in self.agent.stream(user_input, self.session_id):
                if event.type == "thinking":
                    # 显示思考状态（带 spinner）
                    if self.has_rich:
                        self.console.print(f"\n[dim]● 思考中...[/dim]", end="\r")
                    else:
                        print(f"\n● 思考中...", end="\r")
                
                elif event.type == "tool_call":
                    # 工具调用开始 - Claude Code 风格
                    tool_info = event.data
                    if isinstance(tool_info, dict):
                        tool_name = tool_info.get("name", "unknown")
                        tool_args = tool_info.get("arguments", {})
                        if isinstance(tool_args, str):
                            import json
                            try:
                                tool_args = json.loads(tool_args)
                            except:
                                pass

                        current_tool = tool_name
                        current_tool_args = tool_args  # 保存参数供结果显示使用

                        # 获取友好的工具显示名称（传递 args 用于动态判断 Write/Update）
                        display_name = get_tool_display_name(tool_name, tool_args)

                        # TodoWrite 特殊处理 - 不显示括号内容
                        if tool_name == "todo_write":
                            print(f"\n{Colors.CYAN}● {display_name}{Colors.RESET}")
                        else:
                            # 格式化参数显示
                            args_display = self._format_tool_args(tool_name, tool_args)
                            print(f"\n{Colors.CYAN}● {display_name}{Colors.RESET}({Colors.DIM}{args_display}{Colors.RESET})")
                    else:
                        current_tool = str(event.data)
                        current_tool_args = {}
                        display_name = get_tool_display_name(current_tool, {})
                        print(f"\n{Colors.CYAN}● {display_name}{Colors.RESET}")
                
                elif event.type == "tool_result":
                    # 工具执行完成 - 显示结果
                    result = str(event.data)

                    # TodoWrite 特殊处理 - 显示 checkbox 列表
                    if current_tool == "todo_write":
                        self._display_todo_checkboxes(current_tool_args)
                    elif current_tool == "write_file":
                        # Write/Update 特殊处理 - 显示多行预览
                        self._display_write_result(result)
                    else:
                        # 根据工具类型格式化结果摘要
                        result_summary = self._format_tool_result(current_tool, result)
                        print(f"  {Colors.DIM}⎿  {result_summary}{Colors.RESET}")

                    current_tool = None
                    current_tool_args = {}
                
                elif event.type == "content_chunk":
                    # 流式内容输出 - 逐字显示
                    chunk = str(event.data)
                    if content_buffer == "":
                        # 新段落开始，添加 bullet point
                        print(f"\n{Colors.GREEN}● {Colors.RESET}", end="")
                    sys.stdout.write(f"{Colors.GREEN}{chunk}{Colors.RESET}")
                    sys.stdout.flush()
                    content_buffer += chunk

                elif event.type == "content":
                    # 完整内容输出
                    content = str(event.data)
                    if content:
                        # 将内容按段落分割，每段添加 bullet point
                        paragraphs = content.strip().split('\n\n')
                        for i, para in enumerate(paragraphs):
                            if para.strip():
                                if i > 0:
                                    print()  # 段落间空行
                                print(f"\n{Colors.GREEN}● {para.strip()}{Colors.RESET}")
                
                elif event.type == "error":
                    # 清除可能的执行中状态
                    if current_tool:
                        print(f"  {' ' * 20}", end="\r")
                    print(f"\n{Colors.RED}● 错误: {event.data}{Colors.RESET}")
            
            # 如果有流式内容缓冲，添加换行
            if content_buffer:
                print()
            
        except Exception as e:
            print(f"\n{Colors.RED}● 处理失败: {str(e)}{Colors.RESET}")
            import traceback
            print(f"  {Colors.DIM}{traceback.format_exc()}{Colors.RESET}")
    
    def _format_tool_args(self, tool_name: str, args: dict) -> str:
        """格式化工具参数显示"""
        if not isinstance(args, dict):
            return str(args)[:50]
        
        # 根据工具类型显示关键参数
        if tool_name == "read_file":
            path = args.get("file_path", "")
            limit = args.get("limit", "")
            if limit:
                return f"{path}, limit={limit}"
            return path
        elif tool_name == "write_file":
            path = args.get("file_path", "")
            content = args.get("content", "")
            preview = content[:30] + "..." if len(content) > 30 else content
            preview = preview.replace('\n', '\\n')
            return f"{path}"
        elif tool_name == "edit_file":
            path = args.get("file_path", "")
            return path
        elif tool_name == "bash":
            cmd = args.get("command", "")
            if len(cmd) > 60:
                cmd = cmd[:60] + "..."
            return cmd
        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            return f'"{pattern}" {path}'
        elif tool_name == "glob":
            pattern = args.get("pattern", "")
            return pattern
        elif tool_name == "ls":
            path = args.get("path", ".")
            return path
        else:
            # 通用格式化
            parts = []
            for k, v in list(args.items())[:3]:
                v_str = str(v)[:20]
                parts.append(f"{k}={v_str}")
            return ", ".join(parts)

    def _display_todo_checkboxes(self, tool_args: dict) -> None:
        """显示 TodoWrite 的 checkbox 列表"""
        if not isinstance(tool_args, dict):
            print(f"  {Colors.DIM}⎿  Updated todos{Colors.RESET}")
            return

        todos = tool_args.get("todos", [])

        # 如果没有 todos 参数，尝试从持久化存储读取
        if not todos:
            # 尝试从 tasks 参数获取（兼容旧格式）
            tasks = tool_args.get("tasks", "")
            if isinstance(tasks, str) and tasks:
                todos = [{"content": t.strip(), "status": "pending"} for t in tasks.split(";") if t.strip()]

        # 如果还是没有 todos，从文件读取最新状态
        if not todos:
            try:
                todos_dir = Path.home() / ".jiuwen" / "todos"
                todo_file = todos_dir / f"{self.session_id}.json"
                if todo_file.exists():
                    import json
                    with open(todo_file, 'r', encoding='utf-8') as f:
                        todos = json.load(f)
            except Exception:
                pass

        if not todos:
            print(f"  {Colors.DIM}⎿  Updated todos{Colors.RESET}")
            return

        # 显示每个任务的 checkbox
        for todo in todos:
            if isinstance(todo, dict):
                content = todo.get("content", str(todo))
                status = todo.get("status", "pending")
            else:
                content = str(todo)
                status = "pending"

            # 根据状态显示不同的 checkbox
            if status == "completed":
                checkbox = f"{Colors.GREEN}☑{Colors.RESET}"
            elif status == "in_progress":
                checkbox = f"{Colors.YELLOW}◐{Colors.RESET}"
            else:
                checkbox = f"{Colors.DIM}☐{Colors.RESET}"

            print(f"  {Colors.DIM}⎿{Colors.RESET}  {checkbox} {Colors.DIM}{content}{Colors.RESET}")

    def _display_write_result(self, result: str) -> None:
        """显示 Write/Update 的结果 - 包含多行预览

        格式类似 Claude Code:
          ⎿  Wrote 10 lines to /path/to/file.py
             1 def hello():
             2     print("Hello")
             ...
             … +5 lines
        """
        if not result:
            print(f"  {Colors.DIM}⎿  Done{Colors.RESET}")
            return

        lines = result.strip().split('\n')
        if not lines:
            print(f"  {Colors.DIM}⎿  Done{Colors.RESET}")
            return

        # 第一行是摘要（如 "Wrote 10 lines to /path/to/file.py"）
        summary = lines[0]
        print(f"  {Colors.DIM}⎿  {summary}{Colors.RESET}")

        # 后续行是内容预览
        for line in lines[1:]:
            print(f"  {Colors.DIM}   {line}{Colors.RESET}")

    def _format_tool_result(self, tool_name: str, result: str) -> str:
        """格式化工具结果显示 - Claude Code 风格"""
        if not result:
            return "Done"

        result_lines = result.strip().split('\n')
        line_count = len(result_lines)

        # 根据工具类型生成友好的结果摘要
        if tool_name == "read_file":
            return f"Read {line_count} lines"
        elif tool_name == "write_file":
            # 直接返回工具返回的格式化结果（包含行数和预览）
            return result
        elif tool_name == "edit_file":
            if "成功" in result or "success" in result.lower():
                return result_lines[0]
            return f"Edited file"
        elif tool_name == "bash":
            if line_count == 0:
                return "Command completed"
            elif line_count == 1:
                # 单行结果直接显示
                return result_lines[0][:80] + ("..." if len(result_lines[0]) > 80 else "")
            else:
                # 多行结果显示行数
                return f"{result_lines[0][:60]}... (+{line_count - 1} lines)"
        elif tool_name == "grep":
            if "No matches" in result or line_count == 0:
                return "No matches found"
            return f"Found {line_count} matches"
        elif tool_name == "glob":
            if line_count == 0:
                return "No files found"
            return f"Found {line_count} files"
        elif tool_name == "ls":
            return f"Listed {line_count} items"
        else:
            # 通用格式化
            if line_count == 1:
                return result_lines[0][:80] + ("..." if len(result_lines[0]) > 80 else "")
            else:
                return f"{result_lines[0][:60]}... (+{line_count - 1} lines)"

    def handle_plan_approval(self, user_input: str) -> tuple[bool, str]:
        """处理 Plan 审批响应

        检测用户输入是否是对 Plan 的审批响应（approve/yes/reject/no）。
        如果是，则执行相应的模式切换。

        Args:
            user_input: 用户输入

        Returns:
            (is_approval, continue_prompt):
            - is_approval: True 如果是审批响应
            - continue_prompt: 如果批准，返回继续执行的提示词；否则为空字符串
        """
        if not self.agent:
            return False, ""

        # 检查当前是否在 PLAN 模式
        from packages.server.agents.mode_manager import AgentMode
        if self.agent.get_current_mode() != AgentMode.PLAN:
            return False, ""

        # 检查是否有待审批的 Plan
        from packages.server.tools.plan_tools import PlanFileManager
        plan_manager = PlanFileManager(self.session_id)
        if not plan_manager.is_pending_approval():
            return False, ""

        # 检测审批响应
        input_lower = user_input.lower().strip()
        approve_keywords = ['approve', 'yes', 'y', '是', '批准', '同意', 'ok', 'lgtm']
        reject_keywords = ['reject', 'no', 'n', '否', '拒绝', '不同意']

        if input_lower in approve_keywords:
            # 获取 Plan 文件路径
            plan_file = plan_manager.get_current_plan_file()
            plan_content = ""
            if plan_file and plan_file.exists():
                plan_content = plan_manager.read_plan_file(plan_file)

            # 批准 Plan
            if plan_manager.approve_plan():
                # 切换到 BUILD 模式
                self.agent.switch_mode(AgentMode.BUILD)
                print(f"\n  {Colors.BRIGHT_GREEN}✓ Plan 已批准！{Colors.RESET}")
                print(f"  {Colors.DIM}已切换到 BUILD 模式，开始实施...{Colors.RESET}\n")

                # 构建继续执行的提示词
                continue_prompt = f"""用户已批准 Plan，请立即开始实施。

Plan 文件内容：
{plan_content}

请按照 Plan 中的步骤逐一实施，使用 TodoWrite 跟踪进度。开始执行第一个步骤。"""

                return True, continue_prompt
            else:
                print(f"\n  {Colors.YELLOW}⚠ 无法批准 Plan{Colors.RESET}\n")
                return True, ""

        elif input_lower in reject_keywords:
            # 拒绝 Plan
            if plan_manager.reject_plan():
                print(f"\n  {Colors.YELLOW}✗ Plan 已拒绝{Colors.RESET}")
                print(f"  {Colors.DIM}请提供反馈或修改建议...{Colors.RESET}\n")
                return True, ""
            else:
                print(f"\n  {Colors.YELLOW}⚠ 无法拒绝 Plan{Colors.RESET}\n")
                return True, ""

        # 不是审批响应
        return False, ""

    async def run(self):
        """主交互循环"""
        self.show_welcome()

        # 创建带补全功能的 session（移到循环外以复用）
        session = PromptSession(completer=SlashCommandCompleter())

        while self.running:
            try:
                # 获取当前模式
                mode = "BUILD"
                if self.agent:
                    mode = self.agent.get_current_mode().value.upper()

                # 构建提示符并使用 prompt_toolkit 获取输入（支持退格、光标移动等）
                if self.has_rich:
                    prompt_text = f"\n\033[1;36m[{mode}]\033[0m ❯ "
                else:
                    prompt_text = f"\n[{mode}] ❯ "

                # 使用 PromptSession 的异步方法，避免与 asyncio 事件循环冲突
                user_input = await session.prompt_async(ANSI(prompt_text))

                user_input = user_input.strip()

                if not user_input:
                    continue

                # 处理命令
                if self.handle_command(user_input):
                    continue

                # 处理 Plan 审批响应
                is_approval, continue_prompt = self.handle_plan_approval(user_input)
                if is_approval:
                    if continue_prompt:
                        # 批准后自动继续执行 Plan
                        await self.process_message(continue_prompt)
                    continue

                # 处理普通消息
                await self.process_message(user_input)

            except KeyboardInterrupt:
                print(f"\n  {Colors.YELLOW}⚠️  使用 /exit 退出{Colors.RESET}")
            except EOFError:
                self.running = False
            except Exception as e:
                print(f"  {Colors.RED}❌ 错误: {str(e)}{Colors.RESET}")


# ============================================================================
# 主入口
# ============================================================================

def _format_tool_args_simple(tool_name: str, args: dict) -> str:
    """格式化工具参数显示（用于非交互模式）

    与 JiuwenCLI._format_tool_args 保持一致的格式
    """
    if not isinstance(args, dict):
        return str(args)[:50]

    # 根据工具类型显示关键参数
    if tool_name == "read_file":
        path = args.get("file_path", "")
        limit = args.get("limit", "")
        if limit:
            return f"{path}, limit={limit}"
        return path
    elif tool_name == "write_file":
        path = args.get("file_path", "")
        return path
    elif tool_name == "edit_file":
        path = args.get("file_path", "")
        return path
    elif tool_name == "bash":
        cmd = args.get("command", "")
        if len(cmd) > 60:
            cmd = cmd[:60] + "..."
        return cmd
    elif tool_name == "grep":
        pattern = args.get("pattern", "")
        path = args.get("path", ".")
        return f'"{pattern}" {path}'
    elif tool_name == "glob":
        pattern = args.get("pattern", "")
        return pattern
    elif tool_name == "ls":
        path = args.get("path", ".")
        return path
    else:
        # 通用格式化
        parts = []
        for k, v in list(args.items())[:3]:
            v_str = str(v)[:20]
            parts.append(f"{k}={v_str}")
        return ", ".join(parts)


def render_todo_progress(todos_dir: Path, session_id: str) -> str:
    """渲染 todo 进度条

    Args:
        todos_dir: todos 目录
        session_id: 会话 ID

    Returns:
        格式化的进度条字符串
    """
    import json

    # 查找当前会话的 todo 文件
    todo_file = None
    for f in todos_dir.glob("*.json"):
        if session_id in f.name or f.name.startswith("noninteractive_"):
            todo_file = f
            break

    if not todo_file or not todo_file.exists():
        return ""

    try:
        with open(todo_file, 'r', encoding='utf-8') as f:
            todos = json.load(f)
    except:
        return ""

    if not todos:
        return ""

    total = len(todos)
    completed = sum(1 for t in todos if t.get("status") == "completed")
    in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
    pending = total - completed - in_progress

    # 构建进度条
    bar_width = 20
    filled = int(bar_width * completed / total) if total > 0 else 0
    current = 1 if in_progress > 0 and filled < bar_width else 0
    empty = bar_width - filled - current

    bar = f"{Colors.BRIGHT_GREEN}{'█' * filled}{Colors.RESET}"
    if current:
        bar += f"{Colors.BRIGHT_YELLOW}{'▓'}{Colors.RESET}"
    bar += f"{Colors.DIM}{'░' * empty}{Colors.RESET}"

    # 当前任务
    current_task = ""
    for t in todos:
        if t.get("status") == "in_progress":
            current_task = t.get("activeForm", t.get("content", ""))[:30]
            break

    progress_text = f"[{bar}] {completed}/{total}"
    if current_task:
        progress_text += f" {Colors.DIM}• {current_task}{Colors.RESET}"

    return progress_text


async def run_non_interactive(config: dict, query: str):
    """非交互式执行单个查询

    Args:
        config: 配置字典
        query: 用户查询
    """
    import sys

    # 初始化 Agent
    try:
        from packages.server.agents.openjiuwen_agent import JiuwenCodeAgent

        api_key = config.get("api_key")
        provider = config.get("provider", "openai")
        model = config.get("model")
        api_base = config.get("api_base_url")

        agent = JiuwenCodeAgent(
            model_provider=provider,
            api_key=api_key,
            api_base=api_base,
            model_name=model or "gpt-4o",
            session_id=f"noninteractive_{os.getpid()}",
        )
    except Exception as e:
        print(f"{Colors.RED}● Agent 初始化失败: {e}{Colors.RESET}")
        sys.exit(1)

    if not agent.api_key:
        print(f"{Colors.RED}● 未配置 API Key，请运行 jiuwen --config{Colors.RESET}")
        sys.exit(1)

    # 执行查询
    current_tool = None
    current_tool_args = {}
    content_buffer = ""
    session_id = f"noninteractive_{os.getpid()}"
    todos_dir = Path.home() / ".jiuwen" / "todos"

    try:
        async for event in agent.stream(query, session_id):
            if event.type == "thinking":
                print(f"{Colors.DIM}● 思考中...{Colors.RESET}", end="\r")

            elif event.type == "tool_call":
                tool_info = event.data
                if isinstance(tool_info, dict):
                    tool_name = tool_info.get("name", "unknown")
                    tool_args = tool_info.get("arguments", {})
                    if isinstance(tool_args, str):
                        import json
                        try:
                            tool_args = json.loads(tool_args)
                        except:
                            pass

                    current_tool = tool_name
                    current_tool_args = tool_args

                    # 使用与交互模式一致的格式化
                    display_name = get_tool_display_name(tool_name)
                    args_str = _format_tool_args_simple(tool_name, tool_args)

                    # TodoWrite 特殊处理 - 不显示括号内容
                    if tool_name == "todo_write":
                        print(f"{Colors.CYAN}● {display_name}{Colors.RESET}")
                    else:
                        print(f"{Colors.CYAN}● {display_name}{Colors.RESET}({Colors.DIM}{args_str}{Colors.RESET})")
                else:
                    current_tool = str(event.data)
                    current_tool_args = {}
                    display_name = get_tool_display_name(current_tool)
                    print(f"{Colors.CYAN}● {display_name}{Colors.RESET}")

            elif event.type == "tool_result":
                result = str(event.data)

                # 如果是 todo_write 的结果，显示进度条
                if current_tool == "todo_write":
                    progress = render_todo_progress(todos_dir, session_id)
                    if progress:
                        print(f"  {Colors.DIM}⎿{Colors.RESET}  {progress}")
                    else:
                        # 显示简短结果
                        first_line = result.split('\n')[0]
                        print(f"  {Colors.DIM}⎿  {first_line}{Colors.RESET}")
                else:
                    result_lines = result.split('\n')
                    if len(result_lines) > 3:
                        print(f"  {Colors.DIM}⎿  {result_lines[0]}{Colors.RESET}")
                        print(f"     {Colors.DIM}… +{len(result_lines)-1} lines{Colors.RESET}")
                    elif result_lines:
                        print(f"  {Colors.DIM}⎿  {result_lines[0]}{Colors.RESET}")
                current_tool = None

            elif event.type == "content_chunk":
                chunk = str(event.data)
                if content_buffer == "":
                    print()
                sys.stdout.write(f"{Colors.GREEN}{chunk}{Colors.RESET}")
                sys.stdout.flush()
                content_buffer += chunk

            elif event.type == "content":
                content = str(event.data)
                if content:
                    print()
                    print(f"{Colors.GREEN}{content}{Colors.RESET}")

            elif event.type == "error":
                print(f"\n{Colors.RED}● 错误: {event.data}{Colors.RESET}")

        if content_buffer:
            print()

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}● 已中断{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}● 执行失败: {e}{Colors.RESET}")
        sys.exit(1)


def main():
    """主入口函数 - jiuwen 命令"""
    import argparse

    parser = argparse.ArgumentParser(
        prog='jiuwen',
        description='Jiuwen Code - AI 编程助手',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  jiuwen                    启动交互式会话
  jiuwen "你的问题"         非交互式执行
  jiuwen -p "你的问题"      非交互式执行
  jiuwen --config           配置 API Key
  jiuwen --test             运行快速测试
        '''
    )
    parser.add_argument('query', nargs='?', help='直接执行的查询（非交互式）')
    parser.add_argument('-p', '--prompt', help='直接执行的查询（非交互式）')
    parser.add_argument('--config', action='store_true', help='配置 API Key')
    parser.add_argument('--test', action='store_true', help='运行快速测试')
    parser.add_argument('--version', action='version', version=f'Jiuwen Code v{VERSION}')
    parser.add_argument('--no-color', action='store_true', help='禁用颜色输出')
    parser.add_argument('--skip-welcome', action='store_true', help='跳过欢迎界面')

    args = parser.parse_args()
    
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

    # 处理 --test 参数
    if args.test:
        print(f"  {Colors.BRIGHT_CYAN}🧪 运行快速测试...{Colors.RESET}")
        try:
            from packages.server.agents.openjiuwen_agent import create_agent_from_env
            from packages.server.tools.openjiuwen_tools import create_all_tools
            agent = create_agent_from_env()
            tools = create_all_tools()
            print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} Agent: 模式={agent.get_current_mode().value}")
            print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} 工具: {[t.name for t in tools]}")
            print(f"  {Colors.BRIGHT_GREEN}🎉 测试通过!{Colors.RESET}")
        except Exception as e:
            print(f"  {Colors.RED}❌ 测试失败: {e}{Colors.RESET}")
            sys.exit(1)
        return

    # 处理 --config 参数
    if args.config:
        print()
        print(f"  {Colors.BRIGHT_CYAN}Jiuwen Code{Colors.RESET} - API 配置")
        print(f"  {Colors.DIM}{'─' * 40}{Colors.RESET}")

        config = get_config()
        if config.get("api_key"):
            print()
            print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} 当前已配置 API")
            print(f"    Provider:     {Colors.BRIGHT_WHITE}{config.get('provider', 'anthropic')}{Colors.RESET}")
            print(f"    API Base URL: {Colors.BRIGHT_WHITE}{config.get('api_base_url', 'default')}{Colors.RESET}")
            print(f"    API Key:      {Colors.DIM}{'*' * 16}...{config['api_key'][-4:]}{Colors.RESET}")
            print()
            try:
                response = input(
                    f"  {Colors.BRIGHT_CYAN}?{Colors.RESET} 是否重新配置? "
                    f"{Colors.DIM}(y/N){Colors.RESET} "
                ).strip().lower()
                if response not in ('y', 'yes', '是'):
                    return
            except (KeyboardInterrupt, EOFError):
                print()
                return

        prompt_api_key_setup()
        return

    # 处理非交互式执行（位置参数或 -p 参数）
    query = args.query or args.prompt
    if query:
        # 检查配置
        if not check_and_setup_config():
            print(f"  {Colors.DIM}未配置 API Key，退出程序。{Colors.RESET}")
            return

        config = get_config()
        asyncio.run(run_non_interactive(config, query))
        return

    # 交互式模式
    # 检查是否已配置 API Key
    config = get_config()

    if config.get("api_key"):
        # 已登录：直接启动 CLI，显示紧凑界面
        cli = JiuwenCLI(config)
        try:
            asyncio.run(cli.run())
        except KeyboardInterrupt:
            print(f"\n\n  {Colors.YELLOW}👋 再见！{Colors.RESET}\n")
        except Exception as e:
            print(f"\n  {Colors.RED}❌ 异常: {str(e)}{Colors.RESET}")
            sys.exit(1)
    else:
        # 未登录：显示完整欢迎界面，引导配置
        if not args.skip_welcome:
            print_welcome_screen()
            try:
                input()  # 等待用户按 Enter
            except (KeyboardInterrupt, EOFError):
                print()
                return

        # 引导用户配置 API Key
        if not check_and_setup_config():
            print()
            print(f"  {Colors.DIM}未配置 API Key，退出程序。{Colors.RESET}")
            print()
            return

        # 配置完成后启动 CLI
        config = get_config()
        cli = JiuwenCLI(config)

        try:
            asyncio.run(cli.run())
        except KeyboardInterrupt:
            print(f"\n\n  {Colors.YELLOW}👋 再见！{Colors.RESET}\n")
        except Exception as e:
            print(f"\n  {Colors.RED}❌ 异常: {str(e)}{Colors.RESET}")
            sys.exit(1)


if __name__ == "__main__":
    main()
