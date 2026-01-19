"""
胎压控制工具
支持四个轮胎的胎压查询和设置
"""

import json
import asyncio
from typing import Optional, List
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast


# 标准胎压范围（单位：bar）
NORMAL_PRESSURE_MIN = 2.2
NORMAL_PRESSURE_MAX = 2.6
NORMAL_PRESSURE_RECOMMENDED = 2.4


# ============ 核心实现函数（不被装饰器包装）============

def _get_tire_pressure_state() -> dict:
    """获取胎压状态（核心实现）"""
    state = get_car_state()
    tire_pressure = state.vehicle.tire_pressure
    
    # 确保有4个轮胎的数据
    if len(tire_pressure) < 4:
        tire_pressure = tire_pressure + [NORMAL_PRESSURE_RECOMMENDED] * (4 - len(tire_pressure))
    
    # 检查每个轮胎的状态
    tire_names = ["左前轮", "右前轮", "左后轮", "右后轮"]
    tire_status = []
    warnings = []
    
    for i, pressure in enumerate(tire_pressure):
        if pressure < NORMAL_PRESSURE_MIN:
            status = "过低"
            warnings.append(f"{tire_names[i]}胎压过低({pressure}bar)")
        elif pressure > NORMAL_PRESSURE_MAX:
            status = "过高"
            warnings.append(f"{tire_names[i]}胎压过高({pressure}bar)")
        else:
            status = "正常"
        tire_status.append(status)
    
    description = f"左前轮:{tire_pressure[0]}bar({tire_status[0]}), " \
                  f"右前轮:{tire_pressure[1]}bar({tire_status[1]}), " \
                  f"左后轮:{tire_pressure[2]}bar({tire_status[2]}), " \
                  f"右后轮:{tire_pressure[3]}bar({tire_status[3]})"
    
    if warnings:
        description += f" | 警告: {'; '.join(warnings)}"
    
    return {
        "front_left": tire_pressure[0],
        "front_right": tire_pressure[1],
        "rear_left": tire_pressure[2],
        "rear_right": tire_pressure[3],
        "all_pressures": tire_pressure,
        "status": tire_status,
        "warnings": warnings,
        "description": description
    }


def _set_tire_pressure(tire: str = None, pressure: float = None, all_pressure: float = None) -> dict:
    """设置胎压（核心实现）"""
    state = get_car_state()
    tire_pressure = list(state.vehicle.tire_pressure)
    
    # 确保有4个轮胎的数据
    if len(tire_pressure) < 4:
        tire_pressure = tire_pressure + [NORMAL_PRESSURE_RECOMMENDED] * (4 - len(tire_pressure))
    
    changes = []
    
    # 轮胎名称映射
    tire_map = {
        "front_left": 0,
        "左前": 0,
        "左前轮": 0,
        "前左": 0,
        "front_right": 1,
        "右前": 1,
        "右前轮": 1,
        "前右": 1,
        "rear_left": 2,
        "左后": 2,
        "左后轮": 2,
        "后左": 2,
        "rear_right": 3,
        "右后": 3,
        "右后轮": 3,
        "后右": 3,
    }
    
    tire_names = ["左前轮", "右前轮", "左后轮", "右后轮"]
    
    if all_pressure is not None:
        # 设置所有轮胎的胎压
        pressure_value = float(all_pressure)
        pressure_value = max(1.5, min(3.5, pressure_value))  # 限制在合理范围内
        for i in range(4):
            tire_pressure[i] = pressure_value
        changes.append(f"所有轮胎已设置为{pressure_value}bar")
    elif tire is not None and pressure is not None:
        # 设置单个轮胎的胎压
        tire_lower = tire.lower() if isinstance(tire, str) else tire
        if tire_lower in tire_map:
            idx = tire_map[tire_lower]
            pressure_value = float(pressure)
            pressure_value = max(1.5, min(3.5, pressure_value))  # 限制在合理范围内
            tire_pressure[idx] = pressure_value
            changes.append(f"{tire_names[idx]}已设置为{pressure_value}bar")
        else:
            return {
                "success": False,
                "error": f"未知的轮胎: {tire}",
                "available_tires": list(tire_map.keys())
            }
    else:
        return {
            "success": False,
            "error": "请指定轮胎和胎压，或使用all_pressure设置所有轮胎"
        }
    
    # 更新状态
    state.vehicle.tire_pressure = tire_pressure
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("vehicle")
    
    return {
        "success": True,
        "message": ", ".join(changes) if changes else "胎压无变化",
        "current_state": _get_tire_pressure_state()
    }


def _reset_tire_pressure_to_normal() -> dict:
    """重置所有轮胎胎压到标准值（核心实现）"""
    return _set_tire_pressure(all_pressure=NORMAL_PRESSURE_RECOMMENDED)


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_tire_pressure",
      description="获取四个轮胎的胎压状态，包括每个轮胎的胎压值和状态（正常/过低/过高）",
      params=[])
def get_tire_pressure() -> dict:
    """获取胎压状态"""
    return _get_tire_pressure_state()


@tool(name="set_tire_pressure",
      description="设置指定轮胎的胎压值（单位：bar，正常范围2.2-2.6bar）",
      params=[
          Param(name="tire",
                description="轮胎位置：front_left(左前)/front_right(右前)/rear_left(左后)/rear_right(右后)，或中文：左前/右前/左后/右后",
                type="str", required=True),
          Param(name="pressure",
                description="胎压值（单位：bar），正常范围2.2-2.6，推荐2.4",
                type="float", required=True)
      ])
def set_tire_pressure(tire: str, pressure: float) -> dict:
    """设置单个轮胎的胎压"""
    return _set_tire_pressure(tire=tire, pressure=pressure)


@tool(name="set_all_tire_pressure",
      description="设置所有四个轮胎的胎压值（单位：bar）",
      params=[
          Param(name="pressure",
                description="胎压值（单位：bar），正常范围2.2-2.6，推荐2.4",
                type="float", required=True)
      ])
def set_all_tire_pressure(pressure: float) -> dict:
    """设置所有轮胎的胎压"""
    return _set_tire_pressure(all_pressure=pressure)


@tool(name="reset_tire_pressure",
      description="重置所有轮胎胎压到标准值（2.4bar）",
      params=[])
def reset_tire_pressure() -> dict:
    """重置所有轮胎胎压到标准值"""
    return _reset_tire_pressure_to_normal()


if __name__ == "__main__":
    print("当前胎压状态:", _get_tire_pressure_state())
    print("\n设置左前轮为2.5bar:", _set_tire_pressure(tire="front_left", pressure=2.5))
    print("\n重置所有轮胎:", _reset_tire_pressure_to_normal())
