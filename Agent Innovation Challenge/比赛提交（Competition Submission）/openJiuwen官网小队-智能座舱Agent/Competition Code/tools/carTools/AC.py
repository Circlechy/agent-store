"""
汽车空调状态管理模块
使用统一的车机状态管理器
"""

import json
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast


# ============ 核心实现函数（不被装饰器包装）============

def _get_ac_state() -> dict:
    """获取当前空调状态（核心实现）"""
    state = get_car_state()
    ac = state.ac
    
    mode_names = {
        "cool": "制冷",
        "heat": "制热",
        "auto": "自动",
        "fan": "送风"
    }
    
    return {
        "power": ac.power,
        "temperature": ac.temperature,
        "mode": ac.mode,
        "mode_name": mode_names.get(ac.mode, ac.mode),
        "fan_speed": ac.fan_speed,
        "internal_circulation": ac.internal_circulation,
        "air_purification": ac.air_purification,
        "seat_heating": ac.seat_heating,
        "seat_ventilation": ac.seat_ventilation,
        "description": f"空调{'开启' if ac.power else '关闭'}, "
                      f"{ac.temperature}°C, {mode_names.get(ac.mode, ac.mode)}模式, "
                      f"风速{ac.fan_speed}"
    }


def _update_ac_state(updates: dict) -> dict:
    """批量更新空调状态（核心实现）"""
    try:
        # 处理LLM可能传入字符串的情况
        if isinstance(updates, str):
            try:
                updates = json.loads(updates)
            except json.JSONDecodeError:
                return {"success": False, "error": "无效的更新参数：无法解析JSON字符串"}
        
        # 处理嵌套字典可能是字符串的情况
        for key in ["seat_heating", "seat_ventilation"]:
            if isinstance(updates.get(key), str):
                try:
                    updates[key] = json.loads(updates[key])
                except json.JSONDecodeError:
                    pass
        
        state = get_car_state()
        ac = state.ac
        changes = []
        
        if "temperature" in updates:
            temp = int(updates["temperature"])
            temp = max(16, min(30, temp))  # 限制范围16-30
            ac.temperature = temp
            changes.append(f"温度设为{temp}°C")
        
        if "mode" in updates:
            mode = updates["mode"]
            valid_modes = ["cool", "heat", "auto", "fan"]
            if mode in valid_modes:
                ac.mode = mode
                mode_names = {"cool": "制冷", "heat": "制热", "auto": "自动", "fan": "送风"}
                changes.append(f"模式设为{mode_names.get(mode, mode)}")
            else:
                return {"success": False, "error": f"无效的空调模式: {mode}。有效模式: {', '.join(valid_modes)}"}
        
        if "power" in updates:
            power_val = updates["power"]
            if isinstance(power_val, str):
                power_val = power_val.lower() in ['true', '1', 'yes']
            ac.power = bool(power_val)
            changes.append(f"空调{'开启' if ac.power else '关闭'}")
        
        if "fan_speed" in updates:
            speed = int(updates["fan_speed"])
            speed = max(0, min(5, speed))
            ac.fan_speed = speed
            changes.append(f"风速设为{speed}")
        
        if "internal_circulation" in updates:
            ic_val = updates["internal_circulation"]
            if isinstance(ic_val, str):
                ic_val = ic_val.lower() in ['true', '1', 'yes']
            ac.internal_circulation = bool(ic_val)
            changes.append(f"内循环{'开启' if ac.internal_circulation else '关闭'}")
        
        if "air_purification" in updates:
            ap_val = updates["air_purification"]
            if isinstance(ap_val, str):
                ap_val = ap_val.lower() in ['true', '1', 'yes']
            ac.air_purification = bool(ap_val)
            changes.append(f"空气净化{'开启' if ac.air_purification else '关闭'}")
        
        if "seat_heating" in updates:
            for seat, enabled in updates["seat_heating"].items():
                if seat in ac.seat_heating:
                    ac.seat_heating[seat] = bool(enabled)
                    # 同步更新座椅状态（前端界面显示的是seats.driver_heating，不是ac.seat_heating）
                    if seat == "driver":
                        # 如果启用，设置为1档（低档），如果关闭，设置为0
                        state.seats.driver_heating = 1 if enabled else 0
                    elif seat == "passenger":
                        state.seats.passenger_heating = 1 if enabled else 0
                    seat_name = "主驾" if seat == "driver" else "副驾"
                    changes.append(f"{seat_name}座椅加热{'开启' if enabled else '关闭'}")
        
        if "seat_ventilation" in updates:
            for seat, enabled in updates["seat_ventilation"].items():
                if seat in ac.seat_ventilation:
                    ac.seat_ventilation[seat] = bool(enabled)
                    # 同步更新座椅状态（前端界面显示的是seats.driver_ventilation，不是ac.seat_ventilation）
                    if seat == "driver":
                        # 如果启用，设置为1档（低档），如果关闭，设置为0
                        state.seats.driver_ventilation = 1 if enabled else 0
                    elif seat == "passenger":
                        state.seats.passenger_ventilation = 1 if enabled else 0
                    seat_name = "主驾" if seat == "driver" else "副驾"
                    changes.append(f"{seat_name}座椅通风{'开启' if enabled else '关闭'}")
        
        # 保存状态
        save_car_state()
        
        # 广播状态变化到UI
        # 如果更新了座椅加热/通风，需要同时广播seats组件，因为前端显示的是seats状态
        if "seat_heating" in updates or "seat_ventilation" in updates:
            sync_update_and_broadcast("seats")
        sync_update_and_broadcast("ac")
        
        return {
            "success": True,
            "message": "、".join(changes) if changes else "空调无变化",
            "current_state": _get_ac_state()
        }
    except ValueError as e:
        return {"success": False, "error": f"参数类型错误: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"更新空调状态失败: {str(e)}"}


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_ac_state",
      description="获取当前汽车空调状态",
      params=[])
def get_ac_state() -> dict:
    """获取当前空调状态"""
    return _get_ac_state()


@tool(name="update_ac_state",
      description="批量更新汽车空调状态",
      params=[
        Param(
            name="updates", 
            description="需要更新的空调状态字段及其新值的字典，"
            "支持的字段有：temperature (int); internal_circulation (bool); power (bool); "
            "fan_speed (int, 0-5); mode (str: cool/heat/auto/fan); "
            "seat_heating (dict): {driver: bool, passenger: bool}; "
            "seat_ventilation (dict): {driver: bool, passenger: bool}; "
            "air_purification (bool)",
            type="dict", 
            required=True
        )
      ])
def update_ac_state(updates: dict) -> dict:
    """批量更新空调状态"""
    return _update_ac_state(updates)


@tool(name="set_ac_temperature",
      description="设置空调温度",
      params=[
        Param(name="temperature", description="目标温度(16-30°C)", type="int", required=True)
      ])
def set_ac_temperature(temperature: int) -> dict:
    """设置空调温度"""
    return _update_ac_state({"temperature": temperature, "power": True})


@tool(name="set_ac_mode",
      description="设置空调模式",
      params=[
        Param(name="mode", description="模式：cool(制冷)/heat(制热)/auto(自动)/fan(送风)", 
              type="str", required=True)
      ])
def set_ac_mode(mode: str) -> dict:
    """设置空调模式"""
    return _update_ac_state({"mode": mode, "power": True})


@tool(name="turn_on_ac",
      description="开启空调",
      params=[])
def turn_on_ac() -> dict:
    """开启空调"""
    return _update_ac_state({"power": True})


@tool(name="turn_off_ac",
      description="关闭空调",
      params=[])
def turn_off_ac() -> dict:
    """关闭空调"""
    return _update_ac_state({"power": False})


if __name__ == "__main__":
    print("当前空调状态:", json.dumps(_get_ac_state(), ensure_ascii=False, indent=2))
    print("\n设置温度24°C:", _update_ac_state({"temperature": 24, "mode": "heat"}))
