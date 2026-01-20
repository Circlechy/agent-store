"""
DeepDigest 全局桌面弹窗提醒服务
独立后台进程，监控待办事项并触发系统级弹窗提醒

使用方法：
    uv run python deep_digest/src/services/notifier.py
    
    # 演示模式（每10秒弹一次）
    uv run python deep_digest/src/services/notifier.py --demo

依赖安装：
    pip install schedule
"""

import os
import sys
import json
import argparse
import ctypes
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime, date
from pathlib import Path
import schedule
import time
import webbrowser
import subprocess
import socket

# ==================== Windows 高分屏支持 ====================
# 解决 tkinter 在高 DPI 屏幕下字体模糊的问题
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass  # 非 Windows 系统忽略

# ==================== 路径配置 ====================
SCRIPT_DIR = Path(__file__).parent  # src/services/
SRC_DIR = SCRIPT_DIR.parent  # src/
DEEP_DIGEST_ROOT = SRC_DIR.parent  # deep_digest/
PROJECT_ROOT = DEEP_DIGEST_ROOT.parent  # 项目根目录
DATA_FILE = DEEP_DIGEST_ROOT / "data" / "memory_cards.json"
CONFIG_FILE = DEEP_DIGEST_ROOT / "data" / "notifier_config.json"
APP_FILE = SRC_DIR / "ui" / "app.py"  # Streamlit 应用路径

# ==================== 配色方案 (现代深色主题) ====================
COLORS = {
    "bg_dark": "#1a1a2e",       # 主背景（深紫蓝）
    "bg_header": "#16213e",     # 标题栏背景（深蓝）
    "bg_card": "#0f3460",       # 卡片背景
    "text_primary": "#EAEAEA",  # 主文字（柔和白）
    "text_secondary": "#94A3B8", # 次要文字（浅灰蓝）
    "accent": "#E94560",        # 强调色（柔和红）
    "accent_light": "#FF6B6B",  # 浅强调色
    "button_primary": "#00ADB5", # 主按钮（青色）
    "button_primary_hover": "#00C9C9",
    "button_secondary": "#393E46",  # 次要按钮（深灰）
    "button_secondary_hover": "#4A4F57",
    "border": "#2D3748",        # 边框色
    "checkbox": "#00ADB5",      # 复选框颜色
    "success": "#10B981",       # 成功色（绿）
}

# ==================== 默认配置 ====================
DEFAULT_CONFIG = {
    "reminder_times": ["09:00", "14:00"],
    "enabled": True,
    "show_empty_notification": False
}


def load_config() -> dict:
    """
    加载用户配置，如果不存在则创建默认配置
    
    Returns:
        dict: 配置字典
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 合并默认配置（确保新增配置项有默认值）
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"[警告] 配置文件读取失败，使用默认配置: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        # 创建默认配置文件
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """
    保存配置到文件
    
    Args:
        config: 配置字典
    """
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[配置] 已保存到: {CONFIG_FILE}")
    except Exception as e:
        print(f"[错误] 配置保存失败: {e}")


# ==================== 核心功能 ====================

def get_today_todos() -> list:
    """
    读取 memory_cards.json，筛选今日待办
    
    Returns:
        list: 今日待办列表，每项包含 {title, deadline, id}
    """
    today_str = date.today().isoformat()  # 格式: YYYY-MM-DD
    
    if not DATA_FILE.exists():
        print(f"[警告] 数据文件不存在: {DATA_FILE}")
        return []
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        cards = data.get("cards", [])
        
        # 筛选今日待办
        today_todos = []
        for card in cards:
            if card.get("type") == "todo" and card.get("deadline") == today_str:
                today_todos.append({
                    "title": card.get("title", "无标题"),
                    "deadline": card.get("deadline"),
                    "id": card.get("id", "unknown")
                })
        
        return today_todos
        
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败: {e}")
        return []
    except Exception as e:
        print(f"[错误] 读取数据失败: {e}")
        return []


# ==================== 端口检测与服务启动 ====================

def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用（通过尝试连接）"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(('localhost', port))
            return True  # 能连接说明服务在运行
        except (socket.error, socket.timeout):
            return False  # 连接失败说明没有服务


def start_streamlit_server():
    """启动 Streamlit 服务（无头模式，不自动打开浏览器）"""
    try:
        app_path = str(APP_FILE)
        
        if sys.platform == "win32":
            # Windows: 使用 start 命令在新窗口启动，确保窗口可见
            cmd = f'start "DeepDigest Server" cmd /k "cd /d {PROJECT_ROOT} && streamlit run "{app_path}" --server.headless=true"'
            os.system(cmd)
        else:
            # Linux/Mac: 无头模式
            subprocess.Popen(
                ["streamlit", "run", app_path, "--server.headless=true"],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        print("[服务] ✅ Streamlit 启动命令已发送")
        return True
        
    except Exception as e:
        print(f"[错误] Streamlit 启动失败: {e}")
        return False


# ==================== 现代化通知窗口类 ====================

class ModernNotificationWindow:
    """现代深色主题通知窗口（Streamlit 风格）"""
    
    def __init__(self, todos: list):
        self.todos = todos
        self.root = tk.Tk()
        self.scale = self._get_scale_factor()
        self._drag_x = 0
        self._drag_y = 0
        self._setup_window()
        self._create_ui()

    def _get_scale_factor(self):
        try:
            # 96 DPI is standard
            dpi = self.root.winfo_fpixels('1i')
            return dpi / 96
        except Exception:
            return 1.0

    def s(self, size):
        return int(size * self.scale)
    
    def _setup_window(self):
        """设置窗口属性"""
        self.root.title("DeepDigest")
        self.root.overrideredirect(True)  # 无边框
        self.root.attributes('-topmost', True)  # 置顶
        self.root.configure(bg=COLORS["bg_dark"])
        
        # 窗口尺寸
        self.window_width = self.s(380)
        self.window_height = min(self.s(300) + len(self.todos) * self.s(36), self.s(480))
        
        # 右下角定位
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - self.window_width - self.s(24)
        y = screen_height - self.window_height - self.s(80)
        
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        self.root.attributes('-alpha', 0.98)
    
    def _create_ui(self):
        """创建 UI 组件"""
        self._create_title_bar()
        self._create_content_area()
        self._create_button_area()
    
    def _create_title_bar(self):
        """创建自定义标题栏（可拖动，带关闭按钮）"""
        self.title_bar = tk.Frame(
            self.root,
            bg=COLORS["bg_header"],
            height=self.s(44)
        )
        self.title_bar.pack(fill='x')
        self.title_bar.pack_propagate(False)
        
        # 左侧图标 + 标题
        title_container = tk.Frame(self.title_bar, bg=COLORS["bg_header"])
        title_container.pack(side='left', padx=self.s(16), pady=self.s(10))
        
        # Logo 图标
        logo = tk.Label(
            title_container,
            text="🧠",
            font=("Segoe UI Emoji", 14),
            fg=COLORS["button_primary"],
            bg=COLORS["bg_header"]
        )
        logo.pack(side='left')
        
        # 标题文字
        self.title_label = tk.Label(
            title_container,
            text="DeepDigest",
            font=("Segoe UI Semibold", 13),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_header"],
            padx=self.s(8)
        )
        self.title_label.pack(side='left')
        
        # 关闭按钮 (✕)
        self.close_btn = tk.Label(
            self.title_bar,
            text="✕",
            font=("Segoe UI", 12),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_header"],
            padx=self.s(16),
            cursor="hand2"
        )
        self.close_btn.pack(side='right', fill='y')
        
        # 设置按钮 (⚙)
        self.settings_btn = tk.Label(
            self.title_bar,
            text="⚙",
            font=("Segoe UI", 12),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_header"],
            padx=self.s(8),
            cursor="hand2"
        )
        self.settings_btn.pack(side='right', fill='y')
        
        # 设置按钮悬停效果
        self.settings_btn.bind('<Enter>', lambda e: self.settings_btn.config(
            fg=COLORS["button_primary"]
        ))
        self.settings_btn.bind('<Leave>', lambda e: self.settings_btn.config(
            fg=COLORS["text_secondary"]
        ))
        self.settings_btn.bind('<Button-1>', lambda e: self._open_settings())
        
        # 关闭按钮悬停效果
        self.close_btn.bind('<Enter>', lambda e: self.close_btn.config(
            fg="#FFFFFF", bg=COLORS["accent"]
        ))
        self.close_btn.bind('<Leave>', lambda e: self.close_btn.config(
            fg=COLORS["text_secondary"], bg=COLORS["bg_header"]
        ))
        self.close_btn.bind('<Button-1>', lambda e: self.root.destroy())
        
        # 拖动支持
        self.title_bar.bind('<Button-1>', self._start_drag)
        self.title_bar.bind('<B1-Motion>', self._do_drag)
        self.title_label.bind('<Button-1>', self._start_drag)
        self.title_label.bind('<B1-Motion>', self._do_drag)
    
    def _start_drag(self, event):
        """开始拖动"""
        self._drag_x = event.x
        self._drag_y = event.y
    
    def _do_drag(self, event):
        """执行拖动"""
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")
    
    def _create_content_area(self):
        """创建内容区域"""
        content = tk.Frame(self.root, bg=COLORS["bg_dark"], padx=self.s(20), pady=self.s(14))
        content.pack(fill='both', expand=True)
        
        # 副标题区域
        header_row = tk.Frame(content, bg=COLORS["bg_dark"])
        header_row.pack(fill='x', pady=(0, self.s(14)))
        
        # 图标
        icon_label = tk.Label(
            header_row,
            text="📋",
            font=("Segoe UI Emoji", 12),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        icon_label.pack(side='left')
        
        # 文字
        subtitle = tk.Label(
            header_row,
            text=f"今日待办",
            font=("Microsoft YaHei UI", 11),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"],
            padx=self.s(6)
        )
        subtitle.pack(side='left')
        
        # 任务数量标签
        count_label = tk.Label(
            header_row,
            text=f"{len(self.todos)}",
            font=("Segoe UI Semibold", 10),
            fg=COLORS["bg_dark"],
            bg=COLORS["button_primary"],
            padx=self.s(8),
            pady=self.s(2)
        )
        count_label.pack(side='left', padx=(self.s(4), 0))
        
        # 分割线
        separator = tk.Frame(content, bg=COLORS["border"], height=1)
        separator.pack(fill='x', pady=(0, self.s(14)))
        
        # 待办列表容器
        todo_container = tk.Frame(content, bg=COLORS["bg_dark"])
        todo_container.pack(fill='both', expand=True)
        
        # 待办项
        for i, todo in enumerate(self.todos[:6]):
            self._create_todo_item(todo_container, todo, i)
        
        # 显示更多提示
        if len(self.todos) > 6:
            more_label = tk.Label(
                todo_container,
                text=f"还有 {len(self.todos) - 6} 项任务...",
                font=("Microsoft YaHei UI", 9),
                fg=COLORS["text_secondary"],
                bg=COLORS["bg_dark"],
                anchor='w'
            )
            more_label.pack(fill='x', pady=(10, 0))
    
    def _create_todo_item(self, parent, todo, index=0):
        """创建单个待办项"""
        item_frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        item_frame.pack(fill='x', pady=self.s(6))
        
        # 序号圆点
        dot = tk.Label(
            item_frame,
            text="●",
            font=("Segoe UI", 8),
            fg=COLORS["button_primary"],
            bg=COLORS["bg_dark"]
        )
        dot.pack(side='left', padx=(0, self.s(12)))
        
        # 任务标题
        title = tk.Label(
            item_frame,
            text=todo['title'],
            font=("Microsoft YaHei UI", 11),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"],
            anchor='w',
            wraplength=self.s(280)
        )
        title.pack(side='left', fill='x', expand=True)
    
    def _create_button_area(self):
        """创建按钮区域"""
        button_area = tk.Frame(self.root, bg=COLORS["bg_dark"], padx=self.s(20), pady=self.s(18))
        button_area.pack(fill='x')
        
        # 分割线
        separator = tk.Frame(button_area, bg=COLORS["border"], height=1)
        separator.pack(fill='x', pady=(0, self.s(18)))
        
        # 按钮容器
        btn_container = tk.Frame(button_area, bg=COLORS["bg_dark"])
        btn_container.pack(fill='x')
        
        # 主按钮：打开工作台（青色）
        self.primary_btn = self._create_button(
            btn_container,
            "✨ 打开工作台",
            COLORS["button_primary"],
            COLORS["button_primary_hover"],
            self._open_workspace
        )
        self.primary_btn.pack(side='left', expand=True, fill='x', padx=(0, self.s(10)))
        
        # 次要按钮：知道了
        self.secondary_btn = self._create_button(
            btn_container,
            "知道了",
            COLORS["button_secondary"],
            COLORS["button_secondary_hover"],
            self._dismiss
        )
        self.secondary_btn.pack(side='right', expand=True, fill='x', padx=(self.s(10), 0))
    
    def _create_button(self, parent, text, bg_color, hover_color, command):
        """创建扁平化按钮（使用 Label 模拟）"""
        btn = tk.Label(
            parent,
            text=text,
            font=("Microsoft YaHei UI", 10, "bold"),
            fg="#FFFFFF",
            bg=bg_color,
            padx=self.s(24),
            pady=self.s(10),
            cursor="hand2"
        )
        
        # 悬停效果
        btn.bind('<Enter>', lambda e: btn.config(bg=hover_color))
        btn.bind('<Leave>', lambda e: btn.config(bg=bg_color))
        btn.bind('<Button-1>', lambda e: command())
        
        return btn
    
    def _open_workspace(self):
        """打开工作台（带自动启动功能）"""
        port = 8501
        url = f"http://localhost:{port}"
        
        if is_port_in_use(port):
            # 服务已运行，直接打开浏览器
            print("[服务] ✅ Streamlit 已在运行，打开浏览器")
            webbrowser.open(url)
            self.root.destroy()
        else:
            # 服务未运行，尝试启动
            print("[服务] ⏳ Streamlit 未运行，正在启动...")
            self._show_loading()
            
            if start_streamlit_server():
                # 等待服务启动后打开浏览器
                self.root.after(3000, lambda: self._open_browser_and_close(url))
            else:
                self._show_error()
    
    def _show_loading(self):
        """显示加载状态"""
        self.primary_btn.config(text="⏳ 启动中...", bg=COLORS["button_secondary"])
    
    def _open_browser_and_close(self, url):
        """打开浏览器并关闭弹窗"""
        print("[服务] ✅ 正在打开浏览器...")
        webbrowser.open(url)
        self.root.destroy()
    
    def _show_error(self):
        """显示错误状态"""
        self.primary_btn.config(
            text="❌ 启动失败",
            bg=COLORS["accent"]
        )
    
    def _dismiss(self):
        """关闭弹窗"""
        self.root.destroy()
    
    def _open_settings(self):
        """打开设置窗口"""
        SettingsWindow(self.root)
    
    def show(self):
        """显示窗口"""
        self.root.mainloop()


class SettingsWindow:
    """设置窗口 - 带时间滚轮选择器"""
    
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.scale = self._get_scale_factor()
        self.config = load_config()
        self.time_slots = []  # 存储已添加的时间
        self._setup_window()
        self._create_ui()

    def _get_scale_factor(self):
        try:
            return self.window.winfo_fpixels('1i') / 96
        except Exception:
            return 1.0

    def s(self, size):
        return int(size * self.scale)
    
    def _setup_window(self):
        """设置窗口属性"""
        self.window.title("设置")
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.configure(bg=COLORS["bg_dark"])
        
        # 窗口尺寸 - 增加高度确保按钮显示
        width, height = self.s(360), self.s(520)
        
        # 居中于屏幕
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.grab_set()  # 模态窗口
    
    def _create_ui(self):
        """创建设置界面"""
        # 标题栏
        title_bar = tk.Frame(self.window, bg=COLORS["bg_header"], height=self.s(44))
        title_bar.pack(fill='x')
        title_bar.pack_propagate(False)
        
        title_label = tk.Label(
            title_bar,
            text="⚙  提醒设置",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_header"],
            padx=self.s(16)
        )
        title_label.pack(side='left', pady=self.s(10))
        
        close_btn = tk.Label(
            title_bar,
            text="✕",
            font=("Segoe UI", 12),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_header"],
            padx=self.s(16),
            cursor="hand2"
        )
        close_btn.pack(side='right', fill='y')
        close_btn.bind('<Enter>', lambda e: close_btn.config(fg=COLORS["accent"]))
        close_btn.bind('<Leave>', lambda e: close_btn.config(fg=COLORS["text_secondary"]))
        close_btn.bind('<Button-1>', lambda e: self.window.destroy())
        
        # ========== 底部固定区域（先创建，确保始终可见）==========
        bottom_frame = tk.Frame(self.window, bg=COLORS["bg_dark"], padx=self.s(24), pady=self.s(16))
        bottom_frame.pack(fill='x', side='bottom')
        
        # 按钮区域
        btn_frame = tk.Frame(bottom_frame, bg=COLORS["bg_dark"])
        btn_frame.pack(fill='x')
        
        save_btn = tk.Button(
            btn_frame, 
            text="💾 保存并关闭",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#FFFFFF", 
            bg=COLORS["button_primary"],
            activebackground=COLORS["button_primary_hover"],
            activeforeground="#FFFFFF",
            relief='flat',
            bd=0,
            padx=self.s(20), 
            pady=self.s(8),
            cursor="hand2",
            command=self._save_config
        )
        save_btn.pack(side='left', expand=True, fill='x', padx=(0, self.s(8)))
        
        cancel_btn = tk.Button(
            btn_frame, 
            text="取消",
            font=("Microsoft YaHei UI", 11),
            fg=COLORS["text_primary"], 
            bg=COLORS["button_secondary"],
            activebackground=COLORS["button_secondary_hover"],
            activeforeground=COLORS["text_primary"],
            relief='flat',
            bd=0,
            padx=self.s(20), 
            pady=self.s(8),
            cursor="hand2",
            command=self.window.destroy
        )
        cancel_btn.pack(side='right', expand=True, fill='x', padx=(self.s(8), 0))
        
        # ========== 主内容区域 ==========
        content = tk.Frame(self.window, bg=COLORS["bg_dark"], padx=self.s(24), pady=self.s(16))
        content.pack(fill='both', expand=True)
        
        # ========== 添加新时间区域 ==========
        add_section = tk.Frame(content, bg=COLORS["bg_dark"])
        add_section.pack(fill='x', pady=(0, self.s(16)))
        
        add_label = tk.Label(
            add_section,
            text="添加提醒时间",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        add_label.pack(anchor='w', pady=(0, self.s(10)))
        
        # 时间选择器容器
        picker_frame = tk.Frame(add_section, bg=COLORS["bg_header"], padx=self.s(16), pady=self.s(12))
        picker_frame.pack(fill='x')
        
        # 小时选择
        hour_frame = tk.Frame(picker_frame, bg=COLORS["bg_header"])
        hour_frame.pack(side='left', expand=True)
        
        hour_up = tk.Label(hour_frame, text="▲", font=("Segoe UI", 10), 
                          fg=COLORS["text_secondary"], bg=COLORS["bg_header"], cursor="hand2")
        hour_up.pack()
        
        self.hour_var = tk.StringVar(value="09")
        self.hour_label = tk.Label(
            hour_frame, textvariable=self.hour_var,
            font=("Consolas", 28, "bold"),
            fg=COLORS["button_primary"], bg=COLORS["bg_header"], width=2
        )
        self.hour_label.pack(pady=self.s(4))
        
        hour_down = tk.Label(hour_frame, text="▼", font=("Segoe UI", 10),
                            fg=COLORS["text_secondary"], bg=COLORS["bg_header"], cursor="hand2")
        hour_down.pack()
        
        hour_up.bind('<Button-1>', lambda e: self._adjust_hour(1))
        hour_down.bind('<Button-1>', lambda e: self._adjust_hour(-1))
        self.hour_label.bind('<MouseWheel>', lambda e: self._adjust_hour(1 if e.delta > 0 else -1))
        
        # 冒号分隔
        colon = tk.Label(picker_frame, text=":", font=("Consolas", 28, "bold"),
                        fg=COLORS["text_primary"], bg=COLORS["bg_header"])
        colon.pack(side='left', padx=self.s(8))
        
        # 分钟选择
        min_frame = tk.Frame(picker_frame, bg=COLORS["bg_header"])
        min_frame.pack(side='left', expand=True)
        
        min_up = tk.Label(min_frame, text="▲", font=("Segoe UI", 10),
                         fg=COLORS["text_secondary"], bg=COLORS["bg_header"], cursor="hand2")
        min_up.pack()
        
        self.min_var = tk.StringVar(value="00")
        self.min_label = tk.Label(
            min_frame, textvariable=self.min_var,
            font=("Consolas", 28, "bold"),
            fg=COLORS["button_primary"], bg=COLORS["bg_header"], width=2
        )
        self.min_label.pack(pady=self.s(4))
        
        min_down = tk.Label(min_frame, text="▼", font=("Segoe UI", 10),
                           fg=COLORS["text_secondary"], bg=COLORS["bg_header"], cursor="hand2")
        min_down.pack()
        
        min_up.bind('<Button-1>', lambda e: self._adjust_min(5))
        min_down.bind('<Button-1>', lambda e: self._adjust_min(-5))
        self.min_label.bind('<MouseWheel>', lambda e: self._adjust_min(5 if e.delta > 0 else -5))
        
        # 添加按钮
        add_btn = tk.Label(
            picker_frame, text="＋", font=("Segoe UI", 18, "bold"),
            fg="#FFFFFF", bg=COLORS["button_primary"],
            padx=self.s(14), pady=self.s(6), cursor="hand2"
        )
        add_btn.pack(side='right', padx=(self.s(16), 0))
        add_btn.bind('<Enter>', lambda e: add_btn.config(bg=COLORS["button_primary_hover"]))
        add_btn.bind('<Leave>', lambda e: add_btn.config(bg=COLORS["button_primary"]))
        add_btn.bind('<Button-1>', lambda e: self._add_time())
        
        # ========== 已添加时间列表（可滚动）==========
        list_label = tk.Label(
            content, text="已设置的提醒时间",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text_secondary"], bg=COLORS["bg_dark"], anchor='w'
        )
        list_label.pack(fill='x', pady=(self.s(8), self.s(8)))
        
        # 创建带滚动条的列表容器
        list_container = tk.Frame(content, bg=COLORS["bg_header"])
        list_container.pack(fill='both', expand=True)
        
        # Canvas + Scrollbar 实现滚动
        self.list_canvas = tk.Canvas(
            list_container, 
            bg=COLORS["bg_dark"],
            highlightthickness=0,
            height=self.s(90)  # 约2-3条时间的高度
        )
        scrollbar = tk.Scrollbar(
            list_container, 
            orient="vertical", 
            command=self.list_canvas.yview
        )
        
        self.time_list_frame = tk.Frame(self.list_canvas, bg=COLORS["bg_dark"])
        
        self.time_list_frame.bind(
            "<Configure>",
            lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))
        )
        
        self.list_canvas.create_window((0, 0), window=self.time_list_frame, anchor="nw", width=self.s(280))
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.list_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 鼠标滚轮支持
        self.list_canvas.bind_all("<MouseWheel>", lambda e: self.list_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # 加载已有时间
        current_times = self.config.get("reminder_times", ["09:00", "14:00"])
        for t in current_times:
            self.time_slots.append(t)
        self._refresh_time_list()
    
    def _adjust_hour(self, delta):
        """调整小时"""
        h = int(self.hour_var.get())
        h = (h + delta) % 24
        self.hour_var.set(f"{h:02d}")
    
    def _adjust_min(self, delta):
        """调整分钟（每次5分钟）"""
        m = int(self.min_var.get())
        m = (m + delta) % 60
        self.min_var.set(f"{m:02d}")
    
    def _add_time(self):
        """添加时间到列表"""
        time_str = f"{self.hour_var.get()}:{self.min_var.get()}"
        print(f"[设置] 添加时间: {time_str}")
        if time_str not in self.time_slots:
            self.time_slots.append(time_str)
            self.time_slots.sort()
            print(f"[设置] 当前时间列表: {self.time_slots}")
            self._refresh_time_list()
        else:
            print(f"[设置] 时间已存在: {time_str}")
    
    def _remove_time(self, time_str):
        """从列表移除时间"""
        if time_str in self.time_slots:
            self.time_slots.remove(time_str)
            self._refresh_time_list()
    
    def _refresh_time_list(self):
        """刷新时间列表显示"""
        for widget in self.time_list_frame.winfo_children():
            widget.destroy()
        
        if not self.time_slots:
            empty_label = tk.Label(
                self.time_list_frame, text="暂无提醒时间，请添加",
                font=("Microsoft YaHei UI", 9),
                fg=COLORS["text_secondary"], bg=COLORS["bg_dark"]
            )
            empty_label.pack(pady=self.s(10))
            return
        
        for t in self.time_slots:
            item = tk.Frame(self.time_list_frame, bg=COLORS["bg_header"], pady=self.s(2))
            item.pack(fill='x', pady=self.s(2))
            
            time_label = tk.Label(
                item, text=f"  🕐  {t}",
                font=("Consolas", 12),
                fg=COLORS["text_primary"], bg=COLORS["bg_header"],
                anchor='w'
            )
            time_label.pack(side='left', fill='x', expand=True, padx=self.s(8), pady=self.s(6))
            
            del_btn = tk.Label(
                item, text="✕",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg_header"],
                padx=self.s(12), cursor="hand2"
            )
            del_btn.pack(side='right', fill='y')
            del_btn.bind('<Enter>', lambda e, b=del_btn: b.config(fg=COLORS["accent"]))
            del_btn.bind('<Leave>', lambda e, b=del_btn: b.config(fg=COLORS["text_secondary"]))
            del_btn.bind('<Button-1>', lambda e, time=t: self._remove_time(time))
    
    def _save_config(self):
        """保存配置"""
        print(f"[设置] 保存配置中... 时间列表: {self.time_slots}")
        
        if not self.time_slots:
            self.time_slots = ["09:00", "14:00"]
        
        self.config["reminder_times"] = list(self.time_slots)  # 确保是新列表
        
        # 直接写入文件确保保存
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"[设置] ✅ 配置已保存: {self.config}")
        except Exception as e:
            print(f"[设置] ❌ 保存失败: {e}")
        
        self.window.destroy()


def show_notification(todos: list):
    """显示现代化通知窗口"""
    if not todos:
        return
    
    window = ModernNotificationWindow(todos)
    window.show()


def scan_and_notify():
    """
    扫描待办并触发通知（定时任务主函数）
    """
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] 🔍 正在扫描今日待办...")
    
    todos = get_today_todos()
    
    if todos:
        print(f"[{now}] ✅ 发现 {len(todos)} 个今日待办，触发弹窗")
        for todo in todos:
            print(f"    📌 {todo['title']}")
        show_notification(todos)
    else:
        print(f"[{now}] 💤 无今日待办")


def run_scheduler(demo_mode: bool = False):
    """
    启动定时调度器
    
    Args:
        demo_mode: 是否为演示模式（每10秒弹一次）
    """
    config = load_config()
    
    print("=" * 50)
    print("🧠 DeepDigest 桌面提醒服务已启动")
    print("=" * 50)
    print(f"📂 数据文件: {DATA_FILE}")
    print(f"⚙️  配置文件: {CONFIG_FILE}")
    print(f"📅 今日日期: {date.today().isoformat()}")
    
    if demo_mode:
        print(f"⏰ 模式: 🎬 演示模式 (每 10 秒)")
    else:
        print(f"⏰ 模式: 📅 生产模式")
        print(f"🔔 提醒时间: {', '.join(config['reminder_times'])}")
    
    print("=" * 50)
    print("💡 提示: 编辑配置文件可自定义提醒时间")
    print("   添加 --demo 参数可启用演示模式")
    print("=" * 50)
    print("按 Ctrl+C 停止服务\n")
    
    # 清除之前的任务
    schedule.clear()
    
    if demo_mode:
        # 演示模式：每 10 秒执行一次
        print("[模式] 🎬 演示模式已启用，每 10 秒扫描一次\n")
        scan_and_notify()
        schedule.every(10).seconds.do(scan_and_notify)
    else:
        # 生产模式：按配置的时间点提醒
        if config.get("enabled", True):
            for reminder_time in config.get("reminder_times", ["09:00", "14:00"]):
                schedule.every().day.at(reminder_time).do(scan_and_notify)
                print(f"[定时] ⏰ 已设置每日 {reminder_time} 提醒")
            print()
            
            # 启动时检查一次（如果当前时间刚好是提醒时间附近，立即提醒）
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            for reminder_time in config.get("reminder_times", []):
                if current_time == reminder_time:
                    scan_and_notify()
                    break
        else:
            print("[提示] ⚠️ 提醒功能已禁用，请在配置文件中启用")
    
    # 运行调度循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 服务已停止")


def print_config_help():
    """打印配置帮助信息"""
    print("""
📖 配置文件说明
================

配置文件位置: data/notifier_config.json

配置项说明:
{
  "reminder_times": ["09:00", "14:00"],  // 提醒时间列表，24小时制
  "enabled": true,                        // 是否启用提醒
  "show_empty_notification": false        // 无待办时是否也弹窗
}

示例配置:
- 每天 8:30, 12:00, 18:00 提醒:
  {"reminder_times": ["08:30", "12:00", "18:00"], "enabled": true}

- 只在早上 9 点提醒:
  {"reminder_times": ["09:00"], "enabled": true}
""")


# ==================== 入口点 ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DeepDigest 桌面提醒服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python notifier.py          # 生产模式，按配置时间提醒
  python notifier.py --demo   # 演示模式，每10秒提醒一次
  python notifier.py --help-config  # 查看配置帮助
        """
    )
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="启用演示模式（每10秒弹窗一次）"
    )
    parser.add_argument(
        "--help-config",
        action="store_true",
        help="显示配置文件帮助信息"
    )
    
    args = parser.parse_args()
    
    if args.help_config:
        print_config_help()
    else:
        run_scheduler(demo_mode=args.demo)
