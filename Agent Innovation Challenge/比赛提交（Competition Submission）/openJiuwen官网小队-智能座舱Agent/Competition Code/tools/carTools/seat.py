"""
座椅控制工具
支持座椅位置调节、加热、通风、按摩等功能
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

def _get_seat_state(seat: str = None) -> dict:
    """获取座椅状态（核心实现）"""
    state = get_car_state()
    
    driver_state = {
        "position": state.seats.driver_position,
        "backrest": state.seats.driver_backrest,
        "heating": state.seats.driver_heating,
        "ventilation": state.seats.driver_ventilation,
        "massage": state.seats.driver_massage,
        "massage_mode": state.seats.driver_massage_mode
    }
    
    passenger_state = {
        "position": state.seats.passenger_position,
        "backrest": state.seats.passenger_backrest,
        "heating": state.seats.passenger_heating,
        "ventilation": state.seats.passenger_ventilation,
        "massage": state.seats.passenger_massage,
        "massage_mode": state.seats.passenger_massage_mode
    }
    
    if seat:
        seat_lower = seat.lower()
        if seat_lower in ["driver", "主驾", "驾驶座", "我的"]:
            return {"driver": driver_state}
        elif seat_lower in ["passenger", "副驾", "副驾驶", "乘客"]:
            return {"passenger": passenger_state}
    
    return {
        "driver": driver_state,
        "passenger": passenger_state,
        "description": f"主驾: 位置{driver_state['position']}%, 靠背{driver_state['backrest']}°, "
                      f"加热{driver_state['heating']}档, 通风{driver_state['ventilation']}档, "
                      f"按摩{'开启' if driver_state['massage'] else '关闭'}"
    }


def _control_seat(seat: str, settings: dict) -> dict:
    """控制座椅（核心实现）"""
    try:
        state = get_car_state()
        
        # 解析settings
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except json.JSONDecodeError:
                return {"success": False, "error": "无效的设置参数：无法解析JSON字符串"}
        
        # 确定是哪个座椅
        seat_lower = seat.lower() if isinstance(seat, str) else seat
        if seat_lower in ["driver", "主驾", "驾驶座", "我的"]:
            prefix = "driver"
        elif seat_lower in ["passenger", "副驾", "副驾驶", "乘客"]:
            prefix = "passenger"
        else:
            return {"success": False, "error": f"未知的座椅: {seat}。有效值: driver/passenger/主驾/副驾"}
        
        changes = []
        
        # 应用设置
        if "position" in settings:
            pos = max(0, min(100, int(settings["position"])))
            setattr(state.seats, f"{prefix}_position", pos)
            changes.append(f"位置调整到{pos}%")
        
        if "backrest" in settings:
            angle = max(0, min(100, int(settings["backrest"])))
            setattr(state.seats, f"{prefix}_backrest", angle)
            changes.append(f"靠背调整到{angle}°")
        
        if "heating" in settings:
            level = max(0, min(3, int(settings["heating"])))
            setattr(state.seats, f"{prefix}_heating", level)
            # 同步更新AC状态中的seat_heating（保持数据一致性）
            state.ac.seat_heating[prefix] = (level > 0)
            changes.append(f"加热{level}档" if level > 0 else "加热关闭")
        
        if "ventilation" in settings:
            level = max(0, min(3, int(settings["ventilation"])))
            setattr(state.seats, f"{prefix}_ventilation", level)
            # 同步更新AC状态中的seat_ventilation（保持数据一致性）
            state.ac.seat_ventilation[prefix] = (level > 0)
            changes.append(f"通风{level}档" if level > 0 else "通风关闭")
        
        if "massage" in settings:
            massage_val = settings["massage"]
            if isinstance(massage_val, str):
                massage_val = massage_val.lower() in ['true', '1', 'yes']
            on = bool(massage_val)
            setattr(state.seats, f"{prefix}_massage", on)
            changes.append(f"按摩{'开启' if on else '关闭'}")
        
        if "massage_mode" in settings:
            mode = settings["massage_mode"]
            if mode in ["wave", "pulse", "knead", "波浪", "脉冲", "揉捏"]:
                mode_map = {"波浪": "wave", "脉冲": "pulse", "揉捏": "knead"}
                mode = mode_map.get(mode, mode)
                setattr(state.seats, f"{prefix}_massage_mode", mode)
                changes.append(f"按摩模式设为{mode}")
        
        save_car_state()
        
        # 广播状态变化到UI
        sync_update_and_broadcast("seats")
        # 如果更新了加热/通风，也需要广播AC状态（因为AC状态中也包含座椅加热/通风信息）
        if "heating" in settings or "ventilation" in settings:
            sync_update_and_broadcast("ac")
        
        seat_name = "主驾座椅" if prefix == "driver" else "副驾座椅"
        return {
            "success": True,
            "message": f"{seat_name}: {', '.join(changes)}" if changes else f"{seat_name}无变化",
            "current_state": _get_seat_state(seat)
        }
    except ValueError as e:
        return {"success": False, "error": f"参数类型错误: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"控制座椅失败: {str(e)}"}


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_seat_state",
      description="获取座椅状态，包括位置、加热、通风、按摩等",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)，不填返回全部",
                type="str", required=False)
      ])
def get_seat_state(seat: str = None) -> dict:
    """获取座椅状态"""
    return _get_seat_state(seat)


@tool(name="control_seat",
      description="控制座椅设置，支持位置、靠背、加热、通风、按摩等",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)",
                type="str", required=True),
          Param(name="settings",
                description="要调整的设置字典，支持: position(0-100位置), backrest(0-100靠背角度), "
                           "heating(0-3加热档位), ventilation(0-3通风档位), "
                           "massage(bool开关), massage_mode(wave/pulse/knead按摩模式)",
                type="dict", required=True)
      ])
def control_seat(seat: str, settings: dict) -> dict:
    """控制座椅"""
    return _control_seat(seat, settings)


@tool(name="start_seat_massage",
      description="开启座椅按摩",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)，默认主驾",
                type="str", required=False),
          Param(name="mode",
                description="按摩模式：wave(波浪), pulse(脉冲), knead(揉捏)，默认wave",
                type="str", required=False)
      ])
def start_seat_massage(seat: str = "driver", mode: str = "wave") -> dict:
    """开启座椅按摩"""
    return _control_seat(seat, {"massage": True, "massage_mode": mode})


@tool(name="stop_seat_massage",
      description="关闭座椅按摩",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)，默认主驾",
                type="str", required=False)
      ])
def stop_seat_massage(seat: str = "driver") -> dict:
    """关闭座椅按摩"""
    return _control_seat(seat, {"massage": False})


@tool(name="set_seat_heating",
      description="设置座椅加热",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)",
                type="str", required=True),
          Param(name="level",
                description="加热档位：0(关闭), 1(低), 2(中), 3(高)",
                type="int", required=True)
      ])
def set_seat_heating(seat: str, level: int) -> dict:
    """设置座椅加热"""
    return _control_seat(seat, {"heating": level})


@tool(name="set_seat_ventilation",
      description="设置座椅通风",
      params=[
          Param(name="seat",
                description="座椅：driver(主驾) 或 passenger(副驾)",
                type="str", required=True),
          Param(name="level",
                description="通风档位：0(关闭), 1(低), 2(中), 3(高)",
                type="int", required=True)
      ])
def set_seat_ventilation(seat: str, level: int) -> dict:
    """设置座椅通风"""
    return _control_seat(seat, {"ventilation": level})


if __name__ == "__main__":
    print("当前座椅状态:", json.dumps(_get_seat_state(), ensure_ascii=False, indent=2))
    print("\n开启主驾按摩:", _control_seat("driver", {"massage": True, "massage_mode": "wave"}))
    print("\n设置主驾加热:", _control_seat("driver", {"heating": 2}))
