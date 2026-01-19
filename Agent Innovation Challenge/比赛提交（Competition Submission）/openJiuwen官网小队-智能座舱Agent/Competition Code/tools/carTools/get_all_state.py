"""
查询全部车机状态工具
返回所有车机设备的状态信息，包括空调、车窗、座椅、灯光、媒体、车辆、导航、乘客、摄像头等
"""

import json
from typing import Optional
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state


# ============ 核心实现函数（不被装饰器包装）============

def _get_all_state() -> dict:
    """获取全部车机状态（核心实现）"""
    state = get_car_state()
    
    # 使用 to_dict() 方法获取完整状态
    all_state = state.to_dict()
    
    # 添加一个描述性摘要
    ac = state.ac
    vehicle = state.vehicle
    navigation = state.navigation
    windows = state.windows
    seats = state.seats
    lights = state.lights
    media = state.media
    
    description_parts = []
    description_parts.append(f"空调: {'开启' if ac.power else '关闭'}, {ac.temperature}°C, {ac.mode}模式")
    description_parts.append(f"车辆: 电量{vehicle.battery_level}%, 续航{vehicle.range_km}km, 档位{vehicle.gear}, 胎压{vehicle.tire_pressure}bar")
    if navigation.active:
        description_parts.append(f"导航: 前往{navigation.destination}, 剩余{navigation.distance_km}km")
    else:
        description_parts.append("导航: 未激活")
    description_parts.append(f"车窗: 左前{windows.front_left}%, 左后{windows.rear_left}%, 右前{windows.front_right}%, 右后{windows.rear_right}%, 天窗{windows.sunroof}%")
    description_parts.append(f"座椅: 主驾{seats.driver_position}%, 副驾{seats.passenger_position}%, 主驾靠背{seats.driver_backrest}°, 副驾靠背{seats.passenger_backrest}°, 主驾加热{seats.driver_heating}档, 副驾加热{seats.passenger_heating}档, 主驾通风{seats.driver_ventilation}档, 副驾通风{seats.passenger_ventilation}档, 主驾按摩{seats.driver_massage}档, 副驾按摩{seats.passenger_massage}档")
    description_parts.append(f"灯光: 亮度{lights.brightness}%, 颜色{lights.color}, 模式{lights.mode}")
    description_parts.append(f"媒体: 播放{media.playing}状态, 音量{media.volume}%")
    
    all_state["summary"] = " | ".join(description_parts)
    
    return all_state.get("summary")


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_all_state",
      description="获取车机的全部状态信息，包括空调、车窗、座椅、灯光、媒体、车辆、导航、乘客、摄像头等所有设备的状态",
      params=[])
def get_all_state() -> dict:
    """获取全部车机状态"""
    return _get_all_state()


if __name__ == "__main__":
    # 测试
    print("全部车机状态:")
    state = _get_all_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))