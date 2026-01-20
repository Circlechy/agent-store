# -*- coding: utf-8 -*-
"""
工作总结 Agent - 屏幕截图模块

支持功能：
1. 手动截图
2. 定时自动截图
3. 截图后自动分析和记录
"""

import os
import sys
import time
import threading
import asyncio
import inspect
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from openjiuwen.core.common.logging import logger


class ScreenCapture:
    """屏幕截图类"""
    
    def __init__(self, save_dir: Optional[Path] = None):
        """
        初始化截图模块
        
        Args:
            save_dir: 截图保存目录（默认使用临时目录）
        """
        # 确定保存目录
        if save_dir is None:
            # 默认保存到 work_summary_agent/frontend/uploads/screenshots
            current_file = Path(__file__).resolve()
            save_dir = current_file.parent.parent / "frontend" / "uploads" / "screenshots"
        
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 定时截图相关
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_running = False
        self._timer_interval = 0  # 秒
        self._callback: Optional[Callable] = None
        
        # 截图统计相关
        self._screenshot_count = 0  # 本次会话已截图数量
        self._session_start_time: Optional[float] = None  # 本次会话开始时间
        
        # 图片差异检测相关
        self._last_screenshot_path: Optional[Path] = None  # 上一张截图的路径
        self._enable_diff_check = True  # 是否启用差异检测
        self._diff_threshold = 0.005  # 差异阈值（0.5%），小于此值认为内容相同（降低阈值以提高对聊天窗口等小变化的敏感度）
        
        # 检查截图库是否可用
        self._screenshot_available = self._check_screenshot_availability()
    
    def _check_screenshot_availability(self) -> bool:
        """
        检查截图功能是否可用
        
        Returns:
            是否可用
        """
        try:
            # 尝试导入 mss（跨平台截图库）
            import mss  # type: ignore
            return True
        except ImportError:
            try:
                # 尝试导入 PIL + pyautogui（备选方案）
                import pyautogui  # type: ignore
                return True
            except ImportError:
                logger.warning(
                    "截图功能不可用，请安装截图库：\n"
                    "  pip install mss\n"
                    "  或\n"
                    "  pip install pyautogui pillow"
                )
                return False
    
    def _compare_images_fast(self, img1_path: Path, img2_path: Path) -> float:
        """
        快速比较两张图片的差异（使用缩略图加速）
        
        Args:
            img1_path: 第一张图片路径
            img2_path: 第二张图片路径
        
        Returns:
            差异百分比（0.0-1.0），0表示完全相同，1表示完全不同
        """
        try:
            from PIL import Image, ImageChops
            
            # 打开两张图片
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)
            
            # 确保尺寸相同
            if img1.size != img2.size:
                # 尺寸不同，认为是完全不同的图片
                return 1.0
            
            # 使用缩略图加速比较（缩放到较小尺寸，比如 200x200）
            # 这样可以大幅减少需要比较的像素数量
            thumbnail_size = (200, 200)
            img1_thumb = img1.copy()
            img1_thumb.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            img2_thumb = img2.copy()
            img2_thumb.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            
            # 转换为RGB模式（确保格式一致）
            img1_thumb = img1_thumb.convert('RGB')
            img2_thumb = img2_thumb.convert('RGB')
            
            # 使用ImageChops计算差异
            diff = ImageChops.difference(img1_thumb, img2_thumb)
            
            # 计算有差异的像素数量
            # 将差异图像转换为灰度，然后统计非零像素
            diff_gray = diff.convert('L')
            
            # 统计非零像素（有差异的像素）
            try:
                # 尝试使用numpy（如果可用，更快）
                import numpy as np
                diff_array = np.array(diff_gray)
                diff_pixels = np.count_nonzero(diff_array)
                total_pixels = diff_array.size
                diff_percentage = diff_pixels / total_pixels if total_pixels > 0 else 0.0
            except ImportError:
                # 如果没有numpy，使用PIL的getdata方法（但缩略图已经很小了，所以很快）
                diff_data = list(diff_gray.getdata())
                total_pixels = len(diff_data)
                diff_pixels = sum(1 for pixel in diff_data if pixel > 0)
                diff_percentage = diff_pixels / total_pixels if total_pixels > 0 else 0.0
            
            return float(diff_percentage)
            
        except ImportError:
            # 如果没有PIL，使用简单的文件大小比较（不准确，但总比没有好）
            try:
                size1 = img1_path.stat().st_size
                size2 = img2_path.stat().st_size
                if size1 == size2:
                    return 0.0  # 文件大小相同，假设内容相同
                else:
                    return 0.5  # 文件大小不同，假设有差异
            except Exception:
                return 0.5  # 无法比较，假设有差异
        except Exception as e:
            logger.warning(f"图片比较失败: {e}")
            return 0.5  # 比较失败，假设有差异
    
    def capture_screen(
        self, 
        filename: Optional[str] = None,
        check_diff: Optional[bool] = None
    ) -> Optional[Path]:
        """
        截取当前屏幕
        
        Args:
            filename: 保存的文件名（可选，默认使用时间戳）
            check_diff: 是否检查与上一张截图的差异（None时使用默认设置）
        
        Returns:
            保存的截图文件路径，如果失败或内容无变化返回None
        """
        if not self._screenshot_available:
            logger.error("截图功能不可用，请安装截图库")
            return None
        
        # 确定是否检查差异
        should_check = check_diff if check_diff is not None else self._enable_diff_check
        
        try:
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            filepath = self.save_dir / filename
            
            # 尝试使用 mss（优先，跨平台且高效）
            try:
                import mss  # type: ignore
                with mss.mss() as sct:
                    # 截取主显示器
                    monitor = sct.monitors[1]  # 0是所有显示器，1是主显示器
                    screenshot = sct.grab(monitor)
                    
                    # 保存为PNG
                    mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))
            except ImportError:
                # 备选方案：使用 pyautogui
                try:
                    import pyautogui  # type: ignore
                    screenshot = pyautogui.screenshot()
                    screenshot.save(str(filepath))
                except ImportError:
                    logger.error("无法使用任何截图库")
                    return None
            
            # 检查与上一张截图的差异（快速比较，不阻塞）
            if should_check and self._last_screenshot_path and self._last_screenshot_path.exists():
                # 先快速比较文件大小（如果大小相同，很可能内容也相同）
                try:
                    size1 = self._last_screenshot_path.stat().st_size
                    size2 = filepath.stat().st_size
                    size_diff = abs(size1 - size2) / max(size1, size2) if max(size1, size2) > 0 else 0
                    
                    # 如果文件大小差异很小（<0.5%），快速判断为相同，避免耗时的像素比较
                    # 注意：聊天窗口等场景可能文件大小变化不大，所以这个阈值不能太高
                    if size_diff < 0.005:
                        try:
                            filepath.unlink()
                            logger.debug(f"截图内容无变化（文件大小相同），已删除: {filepath.name}")
                            return None
                        except Exception as e:
                            logger.warning(f"删除重复截图失败: {e}")
                    
                    # 文件大小有差异，进行像素级比较（但使用缩略图加速）
                    diff_percentage = self._compare_images_fast(self._last_screenshot_path, filepath)
                    
                    if diff_percentage < self._diff_threshold:
                        # 内容相同，删除新截图
                        try:
                            filepath.unlink()
                            logger.debug(f"截图内容无变化（差异: {diff_percentage*100:.2f}%），已删除: {filepath.name}")
                            return None
                        except Exception as e:
                            logger.warning(f"删除重复截图失败: {e}")
                    else:
                        # 内容不同，保留新截图
                        logger.info(f"截图已保存（差异: {diff_percentage*100:.2f}%）: {filepath}")
                        self._last_screenshot_path = filepath
                        return filepath
                except Exception as e:
                    # 比较失败，保留截图
                    logger.warning(f"图片比较失败: {e}，保留截图")
                    self._last_screenshot_path = filepath
                    return filepath
            else:
                # 第一张截图或未启用差异检测，直接保存
                logger.info(f"截图已保存: {filepath}")
                self._last_screenshot_path = filepath
                return filepath
            
        except Exception as e:
            logger.error(f"截图失败: {e}", exc_info=True)
            return None
    
    def set_diff_check(self, enabled: bool, threshold: float = 0.005):
        """
        设置差异检测参数
        
        Args:
            enabled: 是否启用差异检测
            threshold: 差异阈值（0.0-1.0），小于此值认为内容相同，默认0.005（0.5%）
        """
        self._enable_diff_check = enabled
        self._diff_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"差异检测已{'启用' if enabled else '禁用'}，阈值: {self._diff_threshold*100:.2f}%")
    
    def start_auto_capture(
        self,
        interval: int,
        callback: Optional[Callable[[Path], None]] = None,
        check_diff: Optional[bool] = None
    ):
        """
        启动定时自动截图
        
        Args:
            interval: 截图间隔（秒）
            callback: 截图完成后的回调函数，接收截图文件路径作为参数
            check_diff: 是否检查与上一张截图的差异（None时使用默认设置）
        """
        if interval <= 0:
            logger.error("截图间隔必须大于0")
            return
        
        if self._timer_running:
            logger.warning("定时截图已在运行中，请先停止")
            return
        
        self._timer_interval = interval
        self._callback = callback
        self._timer_running = True
        # 重置统计信息
        self._screenshot_count = 0
        self._session_start_time = time.time()
        
        def timer_loop():
            """
            定时截图循环
            
            注意：回调函数应该快速返回，不应该阻塞。
            如果需要在回调中执行耗时操作（如分析），应该在回调内部启动后台线程/任务。
            """
            while self._timer_running:
                try:
                    # 记录开始时间，确保间隔准确
                    loop_start_time = time.time()
                    
                    # 执行截图（使用传入的check_diff参数，如果为None则使用默认设置）
                    filepath = self.capture_screen(check_diff=check_diff)
                    # 只有截图成功且内容有变化时才调用回调
                    if filepath:
                        # 增加截图计数
                        self._screenshot_count += 1
                        logger.info(f"自动截图 #{self._screenshot_count} 已保存: {filepath.name}")
                    
                    if filepath and self._callback:
                        try:
                            # 将Path对象转换为字符串，以匹配回调函数的参数类型
                            filepath_str = str(filepath) if isinstance(filepath, Path) else filepath
                            # 检查回调函数是否是协程
                            if inspect.iscoroutinefunction(self._callback):
                                # 如果是协程，在后台线程中异步执行，不阻塞截图循环
                                def run_async_callback():
                                    """在后台线程中运行异步回调"""
                                    try:
                                        # 使用 asyncio.run() 确保正确的异步上下文
                                        # asyncio.run() 会自动创建新的事件循环并设置正确的上下文
                                        asyncio.run(self._callback(filepath_str))
                                    except Exception as e:
                                        logger.error(f"异步回调执行失败: {e}", exc_info=True)
                                
                                # 在后台线程中执行，不阻塞截图循环
                                callback_thread = threading.Thread(target=run_async_callback, daemon=True)
                                callback_thread.start()
                            else:
                                # 普通函数，在后台线程中执行，避免阻塞
                                def run_sync_callback():
                                    try:
                                        self._callback(filepath_str)
                                    except Exception as e:
                                        logger.error(f"同步回调执行失败: {e}", exc_info=True)
                                
                                callback_thread = threading.Thread(target=run_sync_callback, daemon=True)
                                callback_thread.start()
                        except Exception as e:
                            logger.error(f"截图回调函数执行失败: {e}", exc_info=True)
                    
                    # 计算已用时间
                    elapsed_time = time.time() - loop_start_time
                    # 等待剩余时间，确保间隔准确
                    remaining_time = max(0, self._timer_interval - elapsed_time)
                    
                    # 使用多个短间隔来检查停止标志，提高响应性
                    elapsed = 0
                    while elapsed < remaining_time and self._timer_running:
                        sleep_time = min(1, remaining_time - elapsed)
                        time.sleep(sleep_time)
                        elapsed += sleep_time
                        
                except Exception as e:
                    logger.error(f"定时截图出错: {e}", exc_info=True)
                    # 即使出错也继续运行，等待完整间隔
                    time.sleep(self._timer_interval)
        
        self._timer_thread = threading.Thread(target=timer_loop, daemon=True)
        self._timer_thread.start()
        logger.info(f"定时截图已启动，间隔: {interval}秒")
    
    def stop_auto_capture(self):
        """停止定时自动截图"""
        if not self._timer_running:
            logger.warning("定时截图未在运行")
            return
        
        self._timer_running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=5)  # 等待最多5秒
        logger.info("定时截图已停止")
    
    def is_auto_capture_running(self) -> bool:
        """检查定时截图是否正在运行"""
        return self._timer_running
    
    def get_auto_capture_interval(self) -> int:
        """获取当前定时截图间隔"""
        return self._timer_interval
    
    def get_screenshot_stats(self) -> Dict[str, Any]:
        """
        获取截图统计信息
        
        Returns:
            统计信息字典：
                - total_count: 本次会话已截图总数
                - session_duration: 本次会话持续时间（秒）
                - session_start_time: 本次会话开始时间（时间戳）
        """
        return {
            "total_count": self._screenshot_count,
            "session_duration": int(time.time() - self._session_start_time) if self._session_start_time else 0,
            "session_start_time": self._session_start_time
        }
    
    def cleanup_old_screenshots(self, max_age_days: int = 7):
        """
        清理旧的截图文件
        
        Args:
            max_age_days: 保留天数（默认7天）
        """
        if not self.save_dir.exists():
            return
        
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        deleted_count = 0
        
        for filepath in self.save_dir.glob("*.png"):
            try:
                file_age = current_time - filepath.stat().st_mtime
                if file_age > max_age_seconds:
                    filepath.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"删除旧截图失败 {filepath}: {e}")
        
        if deleted_count > 0:
            logger.info(f"已清理 {deleted_count} 个旧截图文件")


# 全局截图实例（可选）
_global_capture: Optional[ScreenCapture] = None


def get_screen_capture(save_dir: Optional[Path] = None) -> ScreenCapture:
    """
    获取全局截图实例（单例模式）
    
    Args:
        save_dir: 截图保存目录
    
    Returns:
        ScreenCapture实例
    """
    global _global_capture
    if _global_capture is None:
        _global_capture = ScreenCapture(save_dir)
    return _global_capture


if __name__ == "__main__":
    """测试截图功能"""
    capture = ScreenCapture()
    
    print("=" * 50)
    print("屏幕截图测试")
    print("=" * 50)
    
    if not capture._screenshot_available:
        print("⚠ 截图功能不可用，请安装截图库：")
        print("  pip install mss")
        print("  或")
        print("  pip install pyautogui pillow")
        sys.exit(1)
    
    # 测试手动截图
    print("\n1. 测试手动截图...")
    filepath = capture.capture_screen()
    if filepath:
        print(f"✓ 截图成功: {filepath}")
    else:
        print("✗ 截图失败")
    
    # 测试定时截图（运行5秒后停止）
    print("\n2. 测试定时截图（5秒间隔，运行15秒）...")
    def on_screenshot(filepath: Path):
        print(f"  [定时截图] {filepath.name}")
    
    capture.start_auto_capture(interval=5, callback=on_screenshot)
    time.sleep(15)
    capture.stop_auto_capture()
    print("✓ 定时截图测试完成")
