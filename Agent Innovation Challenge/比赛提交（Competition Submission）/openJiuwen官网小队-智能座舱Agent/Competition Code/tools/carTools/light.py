"""
氛围灯控制工具
支持颜色、亮度、模式调节
"""

import json
import asyncio
from typing import Optional
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast


# 预设颜色
PRESET_COLORS = {
    "red": "#ff0000",
    "红色": "#ff0000",
    "orange": "#ff6600",
    "橙色": "#ff6600",
    "yellow": "#ffcc00",
    "黄色": "#ffcc00",
    "green": "#00ff00",
    "绿色": "#00ff00",
    "cyan": "#00ffff",
    "青色": "#00ffff",
    "blue": "#0066ff",
    "蓝色": "#0066ff",
    "purple": "#9900ff",
    "紫色": "#9900ff",
    "pink": "#ff66cc",
    "粉色": "#ff66cc",
    "white": "#ffffff",
    "白色": "#ffffff",
    "warm": "#ffaa66",
    "暖色": "#ffaa66",
    "warm_white": "#fff5e6",
    "暖白": "#fff5e6",
    "cool_white": "#e6f0ff",
    "冷白": "#e6f0ff",
}

# 预设主题
PRESET_THEMES = {
    "romantic": {"color": "#ff66cc", "brightness": 40, "mode": "breathing"},
    "浪漫": {"color": "#ff66cc", "brightness": 40, "mode": "breathing"},
    "energetic": {"color": "#ff6600", "brightness": 80, "mode": "rhythm"},
    "活力": {"color": "#ff6600", "brightness": 80, "mode": "rhythm"},
    "calm": {"color": "#0066ff", "brightness": 30, "mode": "static"},
    "平静": {"color": "#0066ff", "brightness": 30, "mode": "static"},
    "focus": {"color": "#ffffff", "brightness": 60, "mode": "static"},
    "专注": {"color": "#ffffff", "brightness": 60, "mode": "static"},
    "night": {"color": "#ff3300", "brightness": 20, "mode": "static"},
    "夜间": {"color": "#ff3300", "brightness": 20, "mode": "static"},
    "party": {"color": "#9900ff", "brightness": 100, "mode": "rhythm"},
    "派对": {"color": "#9900ff", "brightness": 100, "mode": "rhythm"},
}


# ============ 核心实现函数（不被装饰器包装）============

def _get_ambient_light_state() -> dict:
    """获取氛围灯状态（核心实现）"""
    state = get_car_state()
    lights = state.lights
    
    mode_names = {
        "static": "静态",
        "breathing": "呼吸",
        "rhythm": "律动"
    }
    
    return {
        "power": lights.power,
        "color": lights.color,
        "brightness": lights.brightness,
        "mode": lights.mode,
        "description": f"氛围灯{'开启' if lights.power else '关闭'}, "
                      f"颜色{lights.color}, 亮度{lights.brightness}%, "
                      f"模式{mode_names.get(lights.mode, lights.mode)}"
    }


def _control_ambient_light(power: bool = None, color: str = None, 
                           brightness: int = None, mode: str = None) -> dict:
    """控制氛围灯（核心实现）"""
    state = get_car_state()
    changes = []
    
    if power is not None:
        if isinstance(power, str):
            power = power.lower() in ['true', '1', 'yes']
        state.lights.power = power
        changes.append(f"{'开启' if power else '关闭'}")
    
    if color is not None:
        # 检查是否是预设颜色
        if color.lower() in PRESET_COLORS:
            color = PRESET_COLORS[color.lower()]
        elif not color.startswith("#"):
            color = f"#{color}"
        state.lights.color = color
        changes.append(f"颜色设为{color}")
    
    if brightness is not None:
        brightness = max(0, min(100, int(brightness)))
        state.lights.brightness = brightness
        changes.append(f"亮度{brightness}%")
    
    if mode is not None:
        mode_map = {"静态": "static", "呼吸": "breathing", "律动": "rhythm"}
        mode = mode_map.get(mode, mode)
        if mode in ["static", "breathing", "rhythm"]:
            state.lights.mode = mode
            mode_names = {"static": "静态", "breathing": "呼吸", "rhythm": "律动"}
            changes.append(f"模式{mode_names.get(mode, mode)}")
    
    # 如果设置了任何非power参数且灯是关闭的，自动打开
    if (color or brightness or mode) and not state.lights.power:
        state.lights.power = True
        changes.insert(0, "自动开启")
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("lights")
    
    return {
        "success": True,
        "message": f"氛围灯: {', '.join(changes)}" if changes else "氛围灯无变化",
        "current_state": _get_ambient_light_state()
    }


def _set_ambient_light_theme(theme: str) -> dict:
    """设置氛围灯主题（核心实现）"""
    theme_lower = theme.lower()
    
    if theme_lower not in PRESET_THEMES:
        return {
            "success": False,
            "error": f"未知的主题: {theme}",
            "available_themes": list(set(k for k in PRESET_THEMES.keys() if not k.startswith("_")))
        }
    
    theme_settings = PRESET_THEMES[theme_lower]
    return _control_ambient_light(
        power=True,
        color=theme_settings["color"],
        brightness=theme_settings["brightness"],
        mode=theme_settings["mode"]
    )


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_ambient_light_state",
      description="获取氛围灯状态",
      params=[])
def get_ambient_light_state() -> dict:
    """获取氛围灯状态"""
    return _get_ambient_light_state()


@tool(name="control_ambient_light",
      description="控制氛围灯设置",
      params=[
          Param(name="power",
                description="开关：true/false，可选",
                type="bool", required=False),
          Param(name="color",
                description="颜色：十六进制如'#ff0000'，或预设颜色名如'红色/blue/warm'",
                type="str", required=False),
          Param(name="brightness",
                description="亮度：0-100",
                type="int", required=False),
          Param(name="mode",
                description="模式：static(静态), breathing(呼吸), rhythm(律动)",
                type="str", required=False)
      ])
def control_ambient_light(power: bool = None, color: str = None, 
                          brightness: int = None, mode: str = None) -> dict:
    """控制氛围灯"""
    return _control_ambient_light(power, color, brightness, mode)


@tool(name="set_ambient_light_theme",
      description="设置氛围灯主题",
      params=[
          Param(name="theme",
                description="主题名：romantic(浪漫), energetic(活力), calm(平静), "
                           "focus(专注), night(夜间), party(派对)",
                type="str", required=True)
      ])
def set_ambient_light_theme(theme: str) -> dict:
    """设置氛围灯主题"""
    return _set_ambient_light_theme(theme)


@tool(name="turn_on_ambient_light",
      description="开启氛围灯",
      params=[])
def turn_on_ambient_light() -> dict:
    """开启氛围灯"""
    return _control_ambient_light(power=True)


@tool(name="turn_off_ambient_light",
      description="关闭氛围灯",
      params=[])
def turn_off_ambient_light() -> dict:
    """关闭氛围灯"""
    return _control_ambient_light(power=False)


if __name__ == "__main__":
    print("当前氛围灯状态:", _get_ambient_light_state())
    print("\n设置浪漫主题:", _set_ambient_light_theme("romantic"))
    print("\n设置蓝色:", _control_ambient_light(color="blue", brightness=60))
