"""
场景联动工具
预设多种智能场景，一键执行多项车机设置
"""

import json
import asyncio
from typing import Optional, Dict, List
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast

# 导入各个控制模块的核心实现函数（不是被装饰的LocalFunction）
from tools.carTools.window import _control_window, _close_all_windows
from tools.carTools.seat import _control_seat
from tools.carTools.light import _control_ambient_light
from tools.carTools.media import _play_music, _set_volume, _pause_music


# 预设场景定义
PRESET_SCENES = {
    "回家模式": {
        "description": "下班回家，放松心情",
        "actions": [
            {"type": "ac", "settings": {"temperature": 24, "mode": "auto", "power": True}},
            {"type": "light", "settings": {"color": "#ffaa66", "brightness": 40, "mode": "static"}},
            {"type": "music", "settings": {"query": "轻松", "volume": 40}},
            {"type": "seat", "settings": {"seat": "driver", "massage": True, "massage_mode": "wave"}},
        ]
    },
    "home_mode": {
        "description": "Going home, relax",
        "alias": "回家模式"
    },
    
    "送娃模式": {
        "description": "送孩子上学，播放儿歌，后排舒适",
        "actions": [
            {"type": "ac", "settings": {"temperature": 25, "mode": "auto", "power": True}},
            {"type": "light", "settings": {"color": "#ffcc00", "brightness": 60, "mode": "static"}},
            {"type": "music", "settings": {"category": "kids", "volume": 50}},
            {"type": "window", "settings": {"window": "rear_left", "position": 0}},  # 关闭后排车窗
            {"type": "window", "settings": {"window": "rear_right", "position": 0}},
        ]
    },
    "kids_mode": {
        "description": "Taking kids to school",
        "alias": "送娃模式"
    },
    
    "上班模式": {
        "description": "早晨上班，提神醒脑",
        "actions": [
            {"type": "ac", "settings": {"temperature": 22, "mode": "cool", "power": True, "fan_speed": 3}},
            {"type": "light", "settings": {"color": "#ffffff", "brightness": 70, "mode": "static"}},
            {"type": "music", "settings": {"query": "起风了", "volume": 50}},
            {"type": "window", "settings": {"window": "front_left", "position": 30}},  # 微开车窗透气
        ]
    },
    "work_mode": {
        "description": "Going to work",
        "alias": "上班模式"
    },
    
    "约会模式": {
        "description": "浪漫约会，营造氛围",
        "actions": [
            {"type": "ac", "settings": {"temperature": 23, "mode": "auto", "power": True}},
            {"type": "light", "settings": {"color": "#ff66cc", "brightness": 30, "mode": "breathing"}},
            {"type": "music", "settings": {"query": "告白气球", "volume": 35}},
            {"type": "seat", "settings": {"seat": "passenger", "heating": 1}},  # 副驾微加热
        ]
    },
    "date_mode": {
        "description": "Romantic date",
        "alias": "约会模式"
    },
    "romantic_mode": {
        "alias": "约会模式"
    },
    "浪漫模式": {
        "alias": "约会模式"
    },
    
    "午休模式": {
        "description": "午间休息，安静舒适",
        "actions": [
            {"type": "ac", "settings": {"temperature": 25, "mode": "auto", "power": True, "fan_speed": 1}},
            {"type": "light", "settings": {"power": False}},
            {"type": "music", "settings": {"pause": True}},
            {"type": "window", "settings": {"window": "all", "position": 0}},  # 关闭所有车窗
            {"type": "seat", "settings": {"seat": "driver", "backrest": 40, "massage": True, "massage_mode": "pulse"}},
        ]
    },
    "nap_mode": {
        "description": "Nap time",
        "alias": "午休模式"
    },
    "rest_mode": {
        "alias": "午休模式"
    },
    
    "冬季模式": {
        "description": "冬天取暖，座椅加热",
        "actions": [
            {"type": "ac", "settings": {"temperature": 26, "mode": "heat", "power": True, "fan_speed": 3}},
            {"type": "seat", "settings": {"seat": "driver", "heating": 3}},
            {"type": "seat", "settings": {"seat": "passenger", "heating": 2}},
            {"type": "light", "settings": {"color": "#ffaa66", "brightness": 50, "mode": "static"}},
        ]
    },
    "winter_mode": {
        "alias": "冬季模式"
    },
    
    "夏季模式": {
        "description": "夏天降温，座椅通风",
        "actions": [
            {"type": "ac", "settings": {"temperature": 20, "mode": "cool", "power": True, "fan_speed": 4}},
            {"type": "seat", "settings": {"seat": "driver", "ventilation": 3}},
            {"type": "seat", "settings": {"seat": "passenger", "ventilation": 2}},
            {"type": "light", "settings": {"color": "#00ccff", "brightness": 40, "mode": "static"}},
        ]
    },
    "summer_mode": {
        "alias": "夏季模式"
    },
    
    "派对模式": {
        "description": "嗨起来！动感音乐和灯光",
        "actions": [
            {"type": "light", "settings": {"color": "#9900ff", "brightness": 100, "mode": "rhythm"}},
            {"type": "music", "settings": {"query": "random", "volume": 80}},
            {"type": "window", "settings": {"window": "sunroof", "position": 100}},  # 打开天窗
        ]
    },
    "party_mode": {
        "alias": "派对模式"
    },
    
    "静音模式": {
        "description": "安静模式，接电话",
        "actions": [
            {"type": "music", "settings": {"pause": True}},
            {"type": "ac", "settings": {"fan_speed": 1}},
            {"type": "window", "settings": {"window": "all", "position": 0}},
        ]
    },
    "quiet_mode": {
        "alias": "静音模式"
    },
    "mute_mode": {
        "alias": "静音模式"
    },
}


def _execute_action(action: dict) -> str:
    """执行单个动作（使用核心实现函数）"""
    action_type = action.get("type")
    settings = action.get("settings", {})
    
    try:
        if action_type == "ac":
            state = get_car_state()
            for key, value in settings.items():
                if hasattr(state.ac, key):
                    setattr(state.ac, key, value)
            # 注意：这里不广播，由场景函数统一广播
            return f"空调已调整"
        
        elif action_type == "light":
            _control_ambient_light(**settings)
            return f"氛围灯已调整"
        
        elif action_type == "music":
            if settings.get("pause"):
                _pause_music()
                return "音乐已暂停"
            else:
                if "volume" in settings:
                    _set_volume(str(settings["volume"]))
                if "query" in settings or "category" in settings:
                    _play_music(
                        query=settings.get("query"),
                        category=settings.get("category")
                    )
                return "音乐已调整"
        
        elif action_type == "seat":
            seat = settings.pop("seat", "driver")
            _control_seat(seat, settings)
            return "座椅已调整"
        
        elif action_type == "window":
            _control_window(settings.get("window", "all"), str(settings.get("position", 0)))
            return "车窗已调整"
        
        else:
            return f"未知动作类型: {action_type}"
    
    except Exception as e:
        return f"执行失败: {str(e)}"


# ============ 核心实现函数 ============

def _activate_scene(scene_name: str) -> dict:
    """激活预设场景（核心实现）"""
    # 查找场景
    scene = PRESET_SCENES.get(scene_name)
    
    # 如果没找到，尝试模糊匹配
    if not scene:
        scene_name_lower = scene_name.lower().replace(" ", "_").replace("模式", "_mode")
        for key in PRESET_SCENES:
            if key.lower() == scene_name_lower or scene_name in key:
                scene = PRESET_SCENES[key]
                scene_name = key
                break
    
    if not scene:
        return {
            "success": False,
            "error": f"未找到场景: {scene_name}",
            "available_scenes": [k for k in PRESET_SCENES.keys() if "alias" not in PRESET_SCENES.get(k, {})]
        }
    
    # 处理别名
    if "alias" in scene:
        scene_name = scene["alias"]
        scene = PRESET_SCENES[scene_name]
    
    # 执行所有动作
    results = []
    affected_components = set()  # 收集受影响的组件
    for action in scene.get("actions", []):
        # 复制settings以避免修改原始数据
        action_copy = {"type": action["type"], "settings": dict(action.get("settings", {}))}
        result = _execute_action(action_copy)
        results.append(result)
        
        # 记录受影响的组件
        action_type = action.get("type")
        component_map = {
            "ac": "ac",
            "light": "lights",
            "music": "media",
            "seat": "seats",
            "window": "windows"
        }
        if action_type in component_map:
            affected_components.add(component_map[action_type])
    
    # 保存状态
    save_car_state()
    
    # 广播所有受影响的组件
    for component in affected_components:
        sync_update_and_broadcast(component)
    
    return {
        "success": True,
        "scene": scene_name,
        "description": scene.get("description", ""),
        "message": f"已激活「{scene_name}」",
        "actions_completed": results
    }


def _list_available_scenes() -> dict:
    """列出可用场景（核心实现）"""
    scenes = []
    for name, config in PRESET_SCENES.items():
        if "alias" not in config:
            scenes.append({
                "name": name,
                "description": config.get("description", "")
            })
    
    return {
        "scenes": scenes,
        "count": len(scenes),
        "message": "可用场景：" + "、".join([s["name"] for s in scenes])
    }


def _get_current_scene_state() -> dict:
    """获取当前状态摘要（核心实现）"""
    state = get_car_state()
    
    return {
        "ac": {
            "power": state.ac.power,
            "temperature": state.ac.temperature,
            "mode": state.ac.mode
        },
        "lights": {
            "power": state.lights.power,
            "color": state.lights.color,
            "mode": state.lights.mode
        },
        "media": {
            "playing": state.media.playing,
            "track": state.media.track_name,
            "volume": state.media.volume
        },
        "seats": {
            "driver_massage": state.seats.driver_massage,
            "driver_heating": state.seats.driver_heating
        },
        "windows": {
            "front_left": state.windows.front_left,
            "sunroof": state.windows.sunroof
        }
    }


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="activate_scene",
      description="激活预设场景，一键完成多项车机设置。"
                  "可用场景：回家模式、送娃模式、上班模式、约会模式/浪漫模式、"
                  "午休模式、冬季模式、夏季模式、派对模式、静音模式",
      params=[
          Param(name="scene_name",
                description="场景名称，如'回家模式'、'送娃模式'、'约会模式'等",
                type="str", required=True)
      ])
def activate_scene(scene_name: str) -> dict:
    """激活预设场景"""
    return _activate_scene(scene_name)


@tool(name="list_available_scenes",
      description="列出所有可用的预设场景",
      params=[])
def list_available_scenes() -> dict:
    """列出可用场景"""
    return _list_available_scenes()


@tool(name="get_current_scene_state",
      description="获取当前车机的整体状态摘要",
      params=[])
def get_current_scene_state() -> dict:
    """获取当前状态摘要"""
    return _get_current_scene_state()


if __name__ == "__main__":
    print("可用场景:", json.dumps(_list_available_scenes(), ensure_ascii=False, indent=2))
    print("\n激活回家模式:", json.dumps(_activate_scene("回家模式"), ensure_ascii=False, indent=2))
    print("\n当前状态:", json.dumps(_get_current_scene_state(), ensure_ascii=False, indent=2))
