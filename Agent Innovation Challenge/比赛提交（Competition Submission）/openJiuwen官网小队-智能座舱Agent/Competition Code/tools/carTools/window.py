"""
车窗控制工具
支持四个车窗和天窗的独立控制
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


# ============ 核心实现函数（不被装饰器包装）============

def _get_window_state() -> dict:
    """获取所有车窗状态（核心实现）"""
    state = get_car_state()
    return {
        "front_left": state.windows.front_left,
        "front_right": state.windows.front_right,
        "rear_left": state.windows.rear_left,
        "rear_right": state.windows.rear_right,
        "sunroof": state.windows.sunroof,
        "description": f"前左窗:{state.windows.front_left}%, 前右窗:{state.windows.front_right}%, "
                      f"后左窗:{state.windows.rear_left}%, 后右窗:{state.windows.rear_right}%, "
                      f"天窗:{state.windows.sunroof}%"
    }


def _control_window(window: str, position: str) -> dict:
    """控制车窗（核心实现）"""
    state = get_car_state()
    
    # 解析position
    if isinstance(position, str):
        position_lower = position.lower()
        if position_lower in ['open', '打开', '开']:
            pos = 100
        elif position_lower in ['close', '关闭', '关']:
            pos = 0
        elif position_lower in ['half', '一半', '半开']:
            pos = 50
        else:
            try:
                pos = int(position)
            except:
                pos = 50
    else:
        pos = int(position)
    
    pos = max(0, min(100, pos))
    
    # 车窗名称映射
    window_map = {
        "front_left": "front_left",
        "主驾": "front_left",
        "前左": "front_left",
        "driver": "front_left",
        "front_right": "front_right",
        "副驾": "front_right", 
        "前右": "front_right",
        "passenger": "front_right",
        "rear_left": "rear_left",
        "后左": "rear_left",
        "rear_right": "rear_right",
        "后右": "rear_right",
        "sunroof": "sunroof",
        "天窗": "sunroof",
    }
    
    window_lower = window.lower() if isinstance(window, str) else window
    results = []
    
    if window_lower == "all" or window_lower == "全部":
        # 控制所有车窗
        state.windows.front_left = pos
        state.windows.front_right = pos
        state.windows.rear_left = pos
        state.windows.rear_right = pos
        state.windows.sunroof = pos
        results.append(f"所有车窗已调整到{pos}%")
    elif window_lower in window_map:
        target = window_map[window_lower]
        setattr(state.windows, target, pos)
        window_names = {
            "front_left": "前左窗(主驾)",
            "front_right": "前右窗(副驾)",
            "rear_left": "后左窗",
            "rear_right": "后右窗",
            "sunroof": "天窗"
        }
        results.append(f"{window_names[target]}已调整到{pos}%")
    else:
        return {"success": False, "error": f"未知的车窗: {window}"}
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("windows")
    
    return {
        "success": True,
        "message": ", ".join(results),
        "current_state": _get_window_state()
    }


def _open_all_windows(include_sunroof: bool = True) -> dict:
    """一键开窗（核心实现）"""
    state = get_car_state()
    state.windows.front_left = 50
    state.windows.front_right = 50
    state.windows.rear_left = 50
    state.windows.rear_right = 50
    if include_sunroof:
        state.windows.sunroof = 50
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("windows")
    
    return {
        "success": True,
        "message": f"已打开所有车窗{'（含天窗）' if include_sunroof else ''}，开度50%",
        "current_state": _get_window_state()
    }


def _close_all_windows() -> dict:
    """一键关窗（核心实现）"""
    state = get_car_state()
    state.windows.front_left = 0
    state.windows.front_right = 0
    state.windows.rear_left = 0
    state.windows.rear_right = 0
    state.windows.sunroof = 0
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("windows")
    
    return {
        "success": True,
        "message": "已关闭所有车窗",
        "current_state": _get_window_state()
    }


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_window_state",
      description="获取当前车窗状态，返回所有车窗的开合程度(0=关闭, 100=全开)",
      params=[])
def get_window_state() -> dict:
    """获取所有车窗状态"""
    return _get_window_state()


@tool(name="control_window",
      description="控制指定车窗的开合程度。可以开窗、关窗、或调整到指定开度",
      params=[
          Param(name="window", 
                description="要控制的车窗：front_left(前左/主驾), front_right(前右/副驾), "
                           "rear_left(后左), rear_right(后右), sunroof(天窗), all(全部)",
                type="str", required=True),
          Param(name="position", 
                description="车窗开度：0=完全关闭, 100=完全打开, 或者使用'open'/'close'",
                type="str", required=True)
      ])
def control_window(window: str, position: str) -> dict:
    """控制车窗"""
    return _control_window(window, position)


@tool(name="open_all_windows",
      description="一键打开所有车窗（通风换气）",
      params=[
          Param(name="include_sunroof",
                description="是否包含天窗，默认True",
                type="bool", required=False)
      ])
def open_all_windows(include_sunroof: bool = True) -> dict:
    """一键开窗"""
    # 处理字符串类型的布尔值
    if isinstance(include_sunroof, str):
        include_sunroof = include_sunroof.lower() in ['true', '1', 'yes']
    return _open_all_windows(include_sunroof)


@tool(name="close_all_windows",
      description="一键关闭所有车窗",
      params=[])
def close_all_windows() -> dict:
    """一键关窗"""
    return _close_all_windows()


if __name__ == "__main__":
    print("当前车窗状态:", _get_window_state())
    print("\n打开主驾车窗:", _control_window("主驾", "open"))
    print("\n关闭所有:", _close_all_windows())
