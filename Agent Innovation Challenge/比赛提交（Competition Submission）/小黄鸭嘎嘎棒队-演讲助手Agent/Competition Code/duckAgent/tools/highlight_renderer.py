#!/usr/bin/env python3
import tkinter as tk
import warnings
import threading
import queue
import sys
from typing import Optional, Dict, Set

warnings.filterwarnings("ignore", category=UserWarning, module="tkinter")

DEFAULT_OFFSET_Y = -20  # 负数向上偏移，正数向下偏移


class HighlightRenderer:
    """高亮框渲染层（实时渲染版，解决卡顿延迟 + 自动坐标缩放）"""

    _instance: Optional["HighlightRenderer"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def pre_init(cls) -> "HighlightRenderer":
        with cls._instance_lock:
            if cls._instance is None:
                if threading.current_thread() != threading.main_thread():
                    raise RuntimeError("pre_init必须在主线程执行！")
                cls._instance = cls(pre_init_mode=True)
            return cls._instance

    @classmethod
    def get_instance(cls) -> "HighlightRenderer":
        with cls._instance_lock:
            if cls._instance is None:
                raise RuntimeError("请先调用pre_init()预初始化！")
            return cls._instance

    def __init__(self, pre_init_mode: bool = False):
        if HighlightRenderer._instance is not None and not pre_init_mode:
            raise RuntimeError("请通过pre_init()/get_instance()获取实例！")

        if threading.current_thread() != threading.main_thread():
            raise RuntimeError("macOS必须在主线程创建TK窗口！")

        self.elem_coords: Dict = {}
        self.selected_elems: Set = set()
        self.highlight_items: Dict = {}
        self.ui_queue = queue.Queue(maxsize=200)
        self.is_running = True

        # 坐标缩放相关
        self.ppt_screen_width = None
        self.ppt_screen_height = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_y = DEFAULT_OFFSET_Y  # ✅ Y轴偏移量（可调整）

        # 计时显示相关
        self.timing_text_id = None

        print(f"[Renderer] 预初始化TK窗口（主线程）...")
        self.root = tk.Tk()
        self.root.option_add("*tearOff", False)
        self.root.option_clear()

        # ✅ 获取真正的全屏尺寸（包括 Dock 和菜单栏区域）
        try:
            from AppKit import NSScreen

            main_screen = NSScreen.mainScreen()
            frame = main_screen.frame()
            screen_width = int(frame.size.width)
            screen_height = int(frame.size.height)
            print(
                f"[Renderer] 📺 使用 NSScreen 真实全屏: {screen_width}x{screen_height}"
            )
        except:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(
                f"[Renderer] 📺 使用 Tkinter 屏幕尺寸: {screen_width}x{screen_height}"
            )

        self.screen_width = screen_width
        self.screen_height = screen_height

        # ✅ 设置窗口属性：覆盖 Dock 和菜单栏
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.3)  # ✅ 恢复透明度
        self.root.config(bg="black")
        self.root.attributes("-transparent", True)
        self.root.attributes("-fullscreen", True)  # 真正的全屏

        # ✅ 设置窗口大小和位置（从 (0,0) 开始，覆盖整个屏幕）
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        self.root.update_idletasks()
        self.root.config(cursor="none")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        print(f"[Renderer] TK窗口预初始化完成：{screen_width}x{screen_height}")

        self.root.after(5, self.process_ui_queue)

    def set_elem_coords(self, elem_coords: Dict, ppt_screen_size=None):
        """
        设置元素坐标

        Args:
            elem_coords: 元素坐标字典 {index: (x, y, w, h)}
            ppt_screen_size: PPT解析时使用的屏幕尺寸 (width, height)
        """
        if not isinstance(elem_coords, dict):
            raise ValueError("elem_coords必须是字典类型！")
        self.elem_coords = {str(k): v for k, v in elem_coords.items()}

        print(f"[Renderer] 📐 已更新元素坐标，共{len(self.elem_coords)}个元素")
        print(f"[Renderer]     元素索引: {list(self.elem_coords.keys())[:10]}...")

        # 自动检测坐标范围，判断是否需要缩放
        if elem_coords:
            max_x = max(coords[0] + coords[2] for coords in elem_coords.values())
            max_y = max(coords[1] + coords[3] for coords in elem_coords.values())
            print(f"[Renderer] 📏 坐标最大范围: x={max_x:.1f}, y={max_y:.1f}")

            # 如果坐标超出 TK 窗口，尝试自动计算缩放
            if max_x > self.screen_width or max_y > self.screen_height:
                print(
                    f"[Renderer] ⚠️  坐标超出TK窗口 ({self.screen_width}x{self.screen_height})"
                )

                if not ppt_screen_size:
                    # 自动推断 PPT 屏幕尺寸（假设是常见分辨率）
                    possible_sizes = [
                        (2560, 1440),
                        (1920, 1080),
                        (3840, 2160),
                        (2880, 1800),
                    ]
                    for width, height in possible_sizes:
                        if max_x <= width and max_y <= height:
                            ppt_screen_size = (width, height)
                            print(
                                f"[Renderer] 🔍 自动推断PPT屏幕尺寸: {width}x{height}"
                            )
                            break

        # 设置坐标缩放
        if ppt_screen_size:
            self.ppt_screen_width, self.ppt_screen_height = ppt_screen_size
            self.scale_x = self.screen_width / self.ppt_screen_width
            self.scale_y = self.screen_height / self.ppt_screen_height

            print(
                f"[Renderer] 📺 PPT坐标系: {self.ppt_screen_width}x{self.ppt_screen_height}"
            )
            print(f"[Renderer] 📺 TK窗口: {self.screen_width}x{self.screen_height}")

            if abs(self.scale_x - 1.0) > 0.01 or abs(self.scale_y - 1.0) > 0.01:
                print(
                    f"[Renderer] 🔧 启用坐标缩放: x*{self.scale_x:.3f}, y*{self.scale_y:.3f}"
                )
            else:
                print(f"[Renderer] ✅ 坐标系匹配，无需缩放")
        else:
            print(f"[Renderer] ℹ️  未提供PPT屏幕尺寸，使用原始坐标")

    def _scale_coords(self, x, y, w, h):
        """缩放坐标到TK窗口尺寸并应用偏移"""
        scaled_x = x * self.scale_x
        scaled_y = y * self.scale_y + self.offset_y  # ✅ 应用 Y 轴偏移
        scaled_w = w * self.scale_x
        scaled_h = h * self.scale_y
        return scaled_x, scaled_y, scaled_w, scaled_h

    def process_ui_queue(self):
        """批量处理队列"""
        if not self.is_running:
            return

        process_count = 0
        max_process_per_loop = 10

        queue_size = self.ui_queue.qsize()
        if queue_size > 0:
            print(f"[Renderer] 🔄 队列中有 {queue_size} 个待处理指令")

        while process_count < max_process_per_loop:
            try:
                cmd, args = self.ui_queue.get_nowait()
                print(f"[Renderer] 📦 处理队列命令: {cmd}, args: {args}")

                if cmd == "show":
                    self._show_highlight(*args)
                elif cmd == "clear":
                    self._clear_all()
                elif cmd == "quit":
                    self.is_running = False
                    self.root.quit()
                elif cmd == "update_timing":
                    self._update_timing_display(*args)
                elif cmd == "show_reminder":
                    self._show_reminder(*args)
                process_count += 1
            except queue.Empty:
                break
            except Exception as e:
                print(f"[Renderer] ❌ 处理队列失败：{e}")
                import traceback

                traceback.print_exc()
                break

        self.root.update_idletasks()
        self.root.after(5, self.process_ui_queue)

    def _show_highlight(self, elem_index, elem_type="text", coords=None):
        print(
            f"[Renderer] 🖼️  开始绘制高亮: elem_index={elem_index}, elem_type={elem_type}"
        )
        try:
            elem_index_str = str(elem_index)
            text_color = "#00FF00"  # 亮绿色，更醒目

            if elem_type == "text":
                if elem_index_str not in self.elem_coords:
                    print(
                        f"[Renderer] ⚠️  跳过: elem_coords中无此元素 '{elem_index_str}'"
                    )
                    print(f"[Renderer]     可用的keys: {list(self.elem_coords.keys())}")
                    return

                x, y, w, h = self.elem_coords[elem_index_str]

            elif elem_type == "image":
                if not coords:
                    print(f"[Renderer] ⚠️  跳过: image类型但coords为空")
                    return

                x, y, w, h = coords
                elem_index_str = f"img_{elem_index_str}"

            else:
                print(f"[Renderer] ⚠️  跳过: 未知类型 '{elem_type}'")
                return

            print(f"[Renderer] 📍 原始坐标: x={x:.1f}, y={y:.1f}, w={w:.1f}, h={h:.1f}")

            # 应用坐标缩放
            x, y, w, h = self._scale_coords(x, y, w, h)
            print(
                f"[Renderer] 🔧 缩放后坐标: x={x:.1f}, y={y:.1f}, w={w:.1f}, h={h:.1f} (Y偏移: {self.offset_y})"
            )

            # 检查坐标是否在屏幕内
            in_bounds = True
            if x < 0:
                print(f"[Renderer] ⚠️  X坐标为负: {x:.1f}")
                in_bounds = False
            if y < 0:
                print(f"[Renderer] ⚠️  Y坐标为负: {y:.1f}")
                in_bounds = False
            if x > self.screen_width:
                print(f"[Renderer] ⚠️  X坐标超出屏幕宽度: {x:.1f} > {self.screen_width}")
                in_bounds = False
            if y > self.screen_height:
                print(
                    f"[Renderer] ⚠️  Y坐标超出屏幕高度: {y:.1f} > {self.screen_height}"
                )
                in_bounds = False
            if x + w > self.screen_width:
                print(f"[Renderer] ⚠️  右边界超出: {x+w:.1f} > {self.screen_width}")
            if y + h > self.screen_height:
                print(f"[Renderer] ⚠️  下边界超出: {y+h:.1f} > {self.screen_height}")

            if in_bounds:
                print(f"[Renderer] ✅ 坐标在屏幕范围内")
            else:
                print(f"[Renderer] ❌ 坐标超出屏幕范围！")

            # 如果已经存在，先删除
            if elem_index_str in self.highlight_items:
                print(f"[Renderer] 🔄 元素已存在，先删除旧的")
                old_rect, old_text = self.highlight_items[elem_index_str]
                self.canvas.delete(old_rect)
                self.canvas.delete(old_text)
                del self.highlight_items[elem_index_str]

            # 绘制高亮框（更鲜艳的橙红色）
            outline_color = "#FF4500"  # ✅ 橙红色（更鲜艳）
            rect = self.canvas.create_rectangle(
                x,
                y,
                x + w,
                y + h,
                outline=outline_color,
                width=8,  # ✅ 更粗的边框（从6改为8）
                fill="",
                tag=f"highlight_{elem_index_str}",
            )

            # 绘制文字标签
            text = self.canvas.create_text(
                x + 20,
                y + 30,
                fill="#FFD700",  # ✅ 金黄色文字（更亮）
                font=("Arial", 26, "bold"),  # ✅ 更大字体（从24改为26）
                tag=f"text_{elem_index_str}",
            )

            self.highlight_items[elem_index_str] = (rect, text)
            self.selected_elems.add(elem_index_str)

            print(f"[Renderer] ✅ 高亮绘制完成: {elem_index_str}")

        except Exception as e:
            print(f"[Renderer] ❌ 绘制高亮失败：{e}")
            import traceback

            traceback.print_exc()

    def _clear_all(self):
        print(f"[Renderer] 🧹 开始清除所有高亮，当前有 {len(self.selected_elems)} 个")
        try:
            for idx_str in list(self.selected_elems):
                if idx_str in self.highlight_items:
                    self.canvas.delete(f"highlight_{idx_str}")
                    self.canvas.delete(f"text_{idx_str}")
                    del self.highlight_items[idx_str]
                    print(f"[Renderer]   ✓ 删除高亮: {idx_str}")

            self.selected_elems.clear()
            print(f"[Renderer] ✅ 清除完成，剩余 {len(self.highlight_items)} 个高亮项")
        except Exception as e:
            print(f"[Renderer] ❌ 清空高亮失败：{e}")
            import traceback

            traceback.print_exc()

    def show_highlight(self, elem_index, elem_type="text", coords=None):
        print(
            f"[Renderer] 🎯 收到高亮请求: elem_index={elem_index}, elem_type={elem_type}, coords={coords}"
        )
        try:
            self.ui_queue.put(("show", (elem_index, elem_type, coords)), timeout=0.01)
            print(f"[Renderer] ✅ 已放入队列，当前队列大小: {self.ui_queue.qsize()}")
        except queue.Full:
            print(f"[Renderer] ❌ 队列满，跳过高亮：{elem_index}")
        except Exception as e:
            print(f"[Renderer] ❌ 放入队列失败：{e}")

    def clear_all(self):
        try:
            self.ui_queue.put(("clear", ()), timeout=0.01)
        except queue.Full:
            print("[Renderer] 队列满，跳过清空")
        except Exception as e:
            print(f"[Renderer] 放入队列失败：{e}")

    def _update_timing_display(self, display_text):
        """更新计时显示"""
        try:
            # 如果已经存在，先删除
            if self.timing_text_id:
                self.canvas.delete(self.timing_text_id)

            # 在左上角显示计时信息
            self.timing_text_id = self.canvas.create_text(
                50,
                50,
                text=display_text,
                fill="#00FF00",  # 绿色文字
                font=("Arial", 24, "bold"),  # 大字体
                tag="timing_display",
                anchor="nw",
            )

            print(f"[Renderer] ⏰ 计时显示已更新: {display_text}")

        except Exception as e:
            print(f"[Renderer] ❌ 更新计时显示失败：{e}")

    def _show_reminder(self, message):
        """显示提醒（在 Canvas 上绘制，不创建新窗口）"""
        try:
            # 如果已经存在旧的提醒，先删除
            self.canvas.delete("reminder")

            # 计算提醒框位置（右上角，更靠右，更紧凑）
            window_width = 350  # ✅ 更窄，更紧凑
            window_height = 120  # ✅ 更矮
            x = self.screen_width - window_width - 10  # ✅ 更靠右（30→10）
            y = 80

            # ✅ 绘制更显眼的提醒框
            # 绘制阴影
            shadow = self.canvas.create_rectangle(
                x + 6,
                y + 6,
                x + window_width + 6,
                y + window_height + 6,
                fill="#000000",
                outline="",
                tag="reminder",
            )

            # 绘制背景矩形（更亮的背景）
            bg_rect = self.canvas.create_rectangle(
                x,
                y,
                x + window_width,
                y + window_height,
                fill="#3D3D3D",  # ✅ 更亮的背景
                outline="#FF6B00",  # ✅ 更鲜艳的橙色
                width=5,  # ✅ 更粗的边框
                tag="reminder",
            )

            # 添加内边框（双层边框更醒目）
            inner_border = self.canvas.create_rectangle(
                x + 8,
                y + 8,
                x + window_width - 8,
                y + window_height - 8,
                fill="",
                outline="#FFB84D",  # ✅ 浅橙色内边框
                width=2,
                tag="reminder",
            )

            # 绘制文字（调整大小避免超出）
            text = self.canvas.create_text(
                x + window_width / 2,
                y + window_height / 2,
                text=message,
                fill="#FFCC00",  # ✅ 亮黄色文字（更显眼）
                font=("Arial", 18, "bold"),  # ✅ 18号字体（从22改小）
                width=window_width - 50,
                justify="center",
                tag="reminder",
            )

            # 5秒后自动关闭
            self.root.after(5000, lambda: self.canvas.delete("reminder"))

            print(f"[Renderer] 📢 提醒已显示（Canvas模式）")

        except Exception as e:
            print(f"[Renderer] ❌ 显示提醒失败：{e}")

    def quit(self):
        self.is_running = False
        try:
            self.ui_queue.put(("quit", ()), timeout=0.01)
        except:
            pass
        self.root.quit()

    def run(self):
        """启动主循环"""
        self.root.mainloop()
