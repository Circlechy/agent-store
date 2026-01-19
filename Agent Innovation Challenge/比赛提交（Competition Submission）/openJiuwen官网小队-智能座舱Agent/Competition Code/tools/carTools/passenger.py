"""
乘客管理工具
支持乘客身份识别、个性化记忆管理
"""

import os
import json
import base64
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from carEmu.car_state import get_car_state, save_car_state, reload_car_state

logger = logging.getLogger(__name__)


# ============ 内部函数 ============

def _get_all_profiles_internal() -> Dict[str, Dict]:
    """获取所有乘客档案（内部函数）"""
    state = reload_car_state()
    return state.passengers.profiles


def _get_profile_internal(passenger_id: str) -> Optional[Dict]:
    """获取单个乘客档案（内部函数）"""
    profiles = _get_all_profiles_internal()
    return profiles.get(passenger_id)


def _create_profile_internal(name: str, avatar_base64: str = "", 
                             preferences: Dict = None) -> Dict:
    """创建乘客档案（内部函数）"""
    state = reload_car_state()
    
    passenger_id = f"passenger_{uuid.uuid4().hex[:8]}"
    
    profile = {
        "id": passenger_id,
        "name": name,
        "avatar_base64": avatar_base64,
        "preferences": preferences or {},
        "last_played_music": "",
        "last_played_video": "",
        "last_destination": "",
        "favorite_temperature": 24,
        "favorite_seat_position": 50,
        "history": [],
        "created_at": datetime.now().isoformat()
    }
    
    state.passengers.profiles[passenger_id] = profile
    save_car_state()
    
    return profile


def _update_profile_internal(passenger_id: str, updates: Dict) -> Dict:
    """更新乘客档案（内部函数）"""
    import json
    
    # 处理 updates 可能是 JSON 字符串的情况
    if isinstance(updates, str):
        try:
            updates = json.loads(updates)
        except json.JSONDecodeError:
            return {"success": False, "error": f"无效的 updates 参数格式: {updates}"}
    
    state = reload_car_state()
    
    if passenger_id not in state.passengers.profiles:
        return {"success": False, "error": f"乘客档案不存在: {passenger_id}"}
    
    profile = state.passengers.profiles[passenger_id]
    
    # 更新允许的字段
    allowed_fields = [
        "name", "avatar_base64", "preferences", 
        "last_played_music", "last_played_video", "last_destination",
        "favorite_temperature", "favorite_seat_position"
    ]
    
    for field in allowed_fields:
        if field in updates:
            profile[field] = updates[field]
    
    profile["updated_at"] = datetime.now().isoformat()
    state.passengers.profiles[passenger_id] = profile
    save_car_state()
    
    return {"success": True, "profile": profile}


def _set_current_passenger_internal(seat: str, passenger_id: str) -> Dict:
    """设置当前座位的乘客（内部函数）"""
    state = reload_car_state()
    
    if passenger_id and passenger_id not in state.passengers.profiles:
        return {"success": False, "error": f"乘客档案不存在: {passenger_id}"}
    
    profile = state.passengers.profiles.get(passenger_id, {}) if passenger_id else {}
    name = profile.get("name", "") if profile else ""
    
    if seat == "driver":
        state.passengers.driver_id = passenger_id
        state.passengers.driver_name = name
    elif seat == "passenger":
        state.passengers.passenger_id = passenger_id
        state.passengers.passenger_name = name
    else:
        return {"success": False, "error": f"无效的座位: {seat}，应为 'driver' 或 'passenger'"}
    
    save_car_state()
    
    return {
        "success": True,
        "seat": seat,
        "passenger_id": passenger_id,
        "passenger_name": name
    }


def _get_current_passengers_internal() -> Dict:
    """获取当前车内乘客（内部函数）"""
    state = reload_car_state()
    
    driver_profile = None
    passenger_profile = None
    
    if state.passengers.driver_id:
        driver_profile = state.passengers.profiles.get(state.passengers.driver_id)
    if state.passengers.passenger_id:
        passenger_profile = state.passengers.profiles.get(state.passengers.passenger_id)
    
    return {
        "driver": {
            "id": state.passengers.driver_id,
            "name": state.passengers.driver_name,
            "profile": driver_profile
        },
        "passenger": {
            "id": state.passengers.passenger_id,
            "name": state.passengers.passenger_name,
            "profile": passenger_profile
        },
        "current_speaker": state.passengers.current_speaker
    }


def _set_current_speaker_internal(speaker: str) -> Dict:
    """设置当前说话者（内部函数）"""
    state = reload_car_state()
    
    if speaker not in ["driver", "passenger", ""]:
        return {"success": False, "error": "说话者应为 'driver'、'passenger' 或空"}
    
    state.passengers.current_speaker = speaker
    save_car_state()
    
    # 获取说话者信息
    speaker_info = {}
    if speaker == "driver" and state.passengers.driver_id:
        speaker_info = state.passengers.profiles.get(state.passengers.driver_id, {})
    elif speaker == "passenger" and state.passengers.passenger_id:
        speaker_info = state.passengers.profiles.get(state.passengers.passenger_id, {})
    
    return {
        "success": True,
        "speaker": speaker,
        "speaker_name": speaker_info.get("name", "未知"),
        "speaker_profile": speaker_info
    }


def _record_history_internal(passenger_id: str, action: str, details: Dict = None) -> Dict:
    """记录乘客操作历史（内部函数）"""
    import json
    
    # 处理 details 可能是 JSON 字符串的情况
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}
    
    state = reload_car_state()
    
    if passenger_id not in state.passengers.profiles:
        return {"success": False, "error": f"乘客档案不存在: {passenger_id}"}
    
    history_entry = {
        "action": action,
        "details": details or {},
        "timestamp": datetime.now().isoformat()
    }
    
    profile = state.passengers.profiles[passenger_id]
    if "history" not in profile:
        profile["history"] = []
    
    # 保留最近100条记录
    profile["history"].append(history_entry)
    if len(profile["history"]) > 100:
        profile["history"] = profile["history"][-100:]
    
    # 根据action类型更新快捷记忆
    if action == "play_music" and details:
        profile["last_played_music"] = details.get("track_name", "")
    elif action == "play_video" and details:
        profile["last_played_video"] = details.get("video_name", "")
    elif action == "navigate" and details:
        profile["last_destination"] = details.get("destination", "")
    
    state.passengers.profiles[passenger_id] = profile
    save_car_state()
    
    return {"success": True, "history_entry": history_entry}


def _get_passenger_memory_internal(passenger_id: str, memory_type: str = None) -> Dict:
    """获取乘客记忆（内部函数）"""
    profile = _get_profile_internal(passenger_id)
    
    if not profile:
        return {"success": False, "error": f"乘客档案不存在: {passenger_id}"}
    
    if memory_type:
        memory_map = {
            "music": "last_played_music",
            "video": "last_played_video",
            "destination": "last_destination",
            "temperature": "favorite_temperature",
            "seat": "favorite_seat_position"
        }
        field = memory_map.get(memory_type)
        if field:
            return {
                "success": True,
                "memory_type": memory_type,
                "value": profile.get(field, ""),
                "passenger_name": profile.get("name", "")
            }
        else:
            return {"success": False, "error": f"未知的记忆类型: {memory_type}"}
    
    # 返回所有记忆
    return {
        "success": True,
        "passenger_name": profile.get("name", ""),
        "memories": {
            "last_played_music": profile.get("last_played_music", ""),
            "last_played_video": profile.get("last_played_video", ""),
            "last_destination": profile.get("last_destination", ""),
            "favorite_temperature": profile.get("favorite_temperature", 24),
            "favorite_seat_position": profile.get("favorite_seat_position", 50),
            "preferences": profile.get("preferences", {}),
            "recent_history": profile.get("history", [])[-10:]  # 最近10条
        }
    }


# ============ Tool定义 ============

@tool(name="get_current_passengers",
      description="获取当前车内的乘客信息，包括主驾和副驾的身份",
      params=[])
def get_current_passengers() -> Dict:
    """获取当前车内乘客"""
    return _get_current_passengers_internal()


@tool(name="get_passenger_profile",
      description="获取指定乘客的详细档案信息",
      params=[
          Param(name="passenger_id",
                description="乘客ID",
                type="str", required=True)
      ])
def get_passenger_profile(passenger_id: str) -> Dict:
    """获取乘客档案"""
    profile = _get_profile_internal(passenger_id)
    if profile:
        return {"success": True, "profile": profile}
    return {"success": False, "error": f"乘客档案不存在: {passenger_id}"}


@tool(name="list_all_passengers",
      description="列出所有已注册的乘客档案",
      params=[])
def list_all_passengers() -> Dict:
    """列出所有乘客"""
    profiles = _get_all_profiles_internal()
    return {
        "success": True,
        "count": len(profiles),
        "passengers": [
            {"id": pid, "name": p.get("name", ""), "created_at": p.get("created_at", "")}
            for pid, p in profiles.items()
        ]
    }


@tool(name="create_passenger_profile",
      description="创建新的乘客档案，可以包含头像和偏好设置",
      params=[
          Param(name="name",
                description="乘客姓名",
                type="str", required=True),
          Param(name="avatar_base64",
                description="头像图片的base64编码（可选）",
                type="str", required=False),
          Param(name="preferences",
                description="偏好设置字典，如 {'music_genre': 'pop', 'seat_massage': True}",
                type="dict", required=False)
      ])
def create_passenger_profile(name: str, avatar_base64: str = "", 
                             preferences: Dict = None) -> Dict:
    """创建乘客档案"""
    profile = _create_profile_internal(name, avatar_base64, preferences)
    return {"success": True, "profile": profile}


@tool(name="update_passenger_profile",
      description="更新乘客档案信息",
      params=[
          Param(name="passenger_id",
                description="乘客ID",
                type="str", required=True),
          Param(name="updates",
                description="要更新的字段，如 {'name': '新名字', 'favorite_temperature': 26}",
                type="dict", required=True)
      ])
def update_passenger_profile(passenger_id: str, updates: Dict) -> Dict:
    """更新乘客档案"""
    return _update_profile_internal(passenger_id, updates)


@tool(name="set_seat_passenger",
      description="设置某个座位上的乘客，用于识别当前谁坐在主驾/副驾",
      params=[
          Param(name="seat",
                description="座位：'driver'(主驾) 或 'passenger'(副驾)",
                type="str", required=True),
          Param(name="passenger_id",
                description="乘客ID，传空字符串表示座位无人",
                type="str", required=True)
      ])
def set_seat_passenger(seat: str, passenger_id: str) -> Dict:
    """设置座位乘客"""
    return _set_current_passenger_internal(seat, passenger_id)


@tool(name="set_current_speaker",
      description="设置当前说话的是谁（主驾还是副驾），用于个性化响应",
      params=[
          Param(name="speaker",
                description="说话者：'driver'(主驾) 或 'passenger'(副驾) 或空字符串",
                type="str", required=True)
      ])
def set_current_speaker(speaker: str) -> Dict:
    """设置当前说话者"""
    return _set_current_speaker_internal(speaker)


@tool(name="get_passenger_memory",
      description="获取乘客的个性化记忆，如上次播放的音乐、视频、导航目的地等",
      params=[
          Param(name="passenger_id",
                description="乘客ID",
                type="str", required=True),
          Param(name="memory_type",
                description="记忆类型：'music'(上次音乐)/'video'(上次视频)/'destination'(上次目的地)/'temperature'(偏好温度)/'seat'(座椅位置)，不填返回全部",
                type="str", required=False)
      ])
def get_passenger_memory(passenger_id: str, memory_type: str = None) -> Dict:
    """获取乘客记忆"""
    return _get_passenger_memory_internal(passenger_id, memory_type)


@tool(name="record_passenger_action",
      description="记录乘客的操作到历史记录，用于个性化推荐",
      params=[
          Param(name="passenger_id",
                description="乘客ID",
                type="str", required=True),
          Param(name="action",
                description="操作类型：'play_music'/'play_video'/'navigate'/'adjust_ac'/'other'",
                type="str", required=True),
          Param(name="details",
                description="操作详情，如 {'track_name': '稻香', 'artist': '周杰伦'}",
                type="dict", required=False)
      ])
def record_passenger_action(passenger_id: str, action: str, details: Dict = None) -> Dict:
    """记录乘客操作"""
    return _record_history_internal(passenger_id, action, details)


@tool(name="get_current_speaker_info",
      description="获取当前说话者的完整信息和个性化记忆",
      params=[])
def get_current_speaker_info() -> Dict:
    """获取当前说话者信息"""
    state = reload_car_state()
    speaker = state.passengers.current_speaker
    
    if not speaker:
        return {
            "success": False,
            "error": "当前没有设置说话者"
        }
    
    passenger_id = ""
    if speaker == "driver":
        passenger_id = state.passengers.driver_id
    elif speaker == "passenger":
        passenger_id = state.passengers.passenger_id
    
    if not passenger_id:
        return {
            "success": True,
            "speaker": speaker,
            "has_profile": False,
            "message": f"{speaker}座位有人说话，但未绑定乘客档案"
        }
    
    memory = _get_passenger_memory_internal(passenger_id)
    
    return {
        "success": True,
        "speaker": speaker,
        "has_profile": True,
        "passenger_id": passenger_id,
        "passenger_name": memory.get("passenger_name", ""),
        "memories": memory.get("memories", {})
    }


@tool(name="identify_speaker_by_seat",
      description="根据座位识别说话者并获取其信息，用于处理类似'帮我播放上次的音乐'这样的请求",
      params=[
          Param(name="seat",
                description="座位：'driver' 或 'passenger'",
                type="str", required=True)
      ])
def identify_speaker_by_seat(seat: str) -> Dict:
    """根据座位识别说话者"""
    result = _set_current_speaker_internal(seat)
    if not result.get("success"):
        return result
    
    state = reload_car_state()
    passenger_id = ""
    if seat == "driver":
        passenger_id = state.passengers.driver_id
    else:
        passenger_id = state.passengers.passenger_id
    
    if not passenger_id:
        return {
            "success": True,
            "speaker": seat,
            "has_profile": False,
            "message": f"{seat}座位没有绑定乘客档案，无法获取个性化信息"
        }
    
    memory = _get_passenger_memory_internal(passenger_id)
    return {
        "success": True,
        "speaker": seat,
        "has_profile": True,
        "passenger_id": passenger_id,
        **memory
    }


if __name__ == "__main__":
    # 测试
    print("乘客管理工具加载成功")
    
    # 创建测试乘客
    # profile = _create_profile_internal("张三", preferences={"music_genre": "pop"})
    # print(f"创建乘客: {profile}")
