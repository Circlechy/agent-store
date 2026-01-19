"""
媒体播放控制工具
支持音乐播放、电台、音量控制等
"""

import json
import asyncio
import random
from typing import Optional, List
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast


# 模拟歌曲库
SONG_LIBRARY = [
    {"name": "晴天", "artist": "周杰伦", "album": "叶惠美", "duration": 269},
    {"name": "七里香", "artist": "周杰伦", "album": "七里香", "duration": 299},
    {"name": "稻香", "artist": "周杰伦", "album": "魔杰座", "duration": 223},
    {"name": "简单爱", "artist": "周杰伦", "album": "范特西", "duration": 270},
    {"name": "夜曲", "artist": "周杰伦", "album": "十一月的萧邦", "duration": 225},
    {"name": "告白气球", "artist": "周杰伦", "album": "周杰伦的床边故事", "duration": 215},
    {"name": "青花瓷", "artist": "周杰伦", "album": "我很忙", "duration": 239},
    {"name": "起风了", "artist": "买辣椒也用券", "album": "起风了", "duration": 325},
    {"name": "孤勇者", "artist": "陈奕迅", "album": "孤勇者", "duration": 261},
    {"name": "富士山下", "artist": "陈奕迅", "album": "What's Going On...?", "duration": 284},
    {"name": "十年", "artist": "陈奕迅", "album": "黑白灰", "duration": 205},
    {"name": "浮夸", "artist": "陈奕迅", "album": "U87", "duration": 275},
    {"name": "光年之外", "artist": "邓紫棋", "album": "光年之外", "duration": 235},
    {"name": "泡沫", "artist": "邓紫棋", "album": "Xposed", "duration": 265},
    {"name": "平凡之路", "artist": "朴树", "album": "猎户星座", "duration": 285},
    {"name": "那些年", "artist": "胡夏", "album": "那些年", "duration": 262},
    {"name": "小幸运", "artist": "田馥甄", "album": "小幸运", "duration": 293},
    {"name": "演员", "artist": "薛之谦", "album": "绅士", "duration": 270},
    {"name": "丑八怪", "artist": "薛之谦", "album": "意外", "duration": 263},
    {"name": "像我这样的人", "artist": "毛不易", "album": "平凡的一天", "duration": 268},
]

# 模拟电台
RADIO_STATIONS = [
    {"name": "中国之声", "frequency": 106.1},
    {"name": "音乐之声", "frequency": 90.0},
    {"name": "经典音乐广播", "frequency": 101.8},
    {"name": "交通广播", "frequency": 99.6},
    {"name": "新闻广播", "frequency": 87.6},
    {"name": "都市之声", "frequency": 103.2},
    {"name": "文艺之声", "frequency": 107.3},
]

# 儿童歌曲
KIDS_SONGS = [
    {"name": "小星星", "artist": "儿歌", "album": "经典儿歌", "duration": 120},
    {"name": "两只老虎", "artist": "儿歌", "album": "经典儿歌", "duration": 60},
    {"name": "小燕子", "artist": "儿歌", "album": "经典儿歌", "duration": 90},
    {"name": "小兔子乖乖", "artist": "儿歌", "album": "经典儿歌", "duration": 75},
    {"name": "世上只有妈妈好", "artist": "儿歌", "album": "经典儿歌", "duration": 110},
    {"name": "让我们荡起双桨", "artist": "儿歌", "album": "经典儿歌", "duration": 150},
    {"name": "数鸭子", "artist": "儿歌", "album": "经典儿歌", "duration": 95},
    {"name": "采蘑菇的小姑娘", "artist": "儿歌", "album": "经典儿歌", "duration": 180},
]


# ============ 核心实现函数（不被装饰器包装）============

def _get_media_state() -> dict:
    """获取媒体状态（核心实现）"""
    state = get_car_state()
    media = state.media
    
    source_names = {
        "bluetooth": "蓝牙",
        "radio": "收音机",
        "usb": "USB",
        "online": "在线音乐"
    }
    
    if media.source == "radio":
        now_playing = f"FM {media.radio_frequency}"
    elif media.track_name:
        now_playing = f"{media.track_name} - {media.track_artist}"
    else:
        now_playing = "无"
    
    return {
        "playing": media.playing,
        "source": media.source,
        "source_name": source_names.get(media.source, media.source),
        "track_name": media.track_name,
        "track_artist": media.track_artist,
        "track_album": media.track_album,
        "duration": media.track_duration,
        "position": media.track_position,
        "volume": media.volume,
        "radio_frequency": media.radio_frequency,
        "now_playing": now_playing,
        "description": f"{'正在播放' if media.playing else '已暂停'}: {now_playing}, "
                      f"音量{media.volume}%"
    }


def _play_music(query: str = None, category: str = None) -> dict:
    """播放音乐（核心实现）"""
    state = get_car_state()
    
    # 选择歌曲库
    if category and category.lower() in ["kids", "儿歌", "儿童", "children"]:
        library = KIDS_SONGS
    else:
        library = SONG_LIBRARY
    
    # 搜索或随机选择歌曲
    if query and query.lower() not in ["random", "随机"]:
        # 搜索匹配的歌曲
        query_lower = query.lower()
        matches = [s for s in library 
                   if query_lower in s["name"].lower() 
                   or query_lower in s["artist"].lower()]
        if matches:
            song = matches[0]
        else:
            # 没找到就随机播放
            song = random.choice(library)
    else:
        song = random.choice(library)
    
    # 更新状态
    state.media.playing = True
    state.media.source = "online"
    state.media.track_name = song["name"]
    state.media.track_artist = song["artist"]
    state.media.track_album = song.get("album", "")
    state.media.track_duration = song["duration"]
    state.media.track_position = 0
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": f"正在播放: {song['name']} - {song['artist']}",
        "track": song,
        "current_state": _get_media_state()
    }


def _pause_music() -> dict:
    """暂停音乐（核心实现）"""
    state = get_car_state()
    state.media.playing = False
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": "已暂停播放",
        "current_state": _get_media_state()
    }


def _resume_music() -> dict:
    """继续播放（核心实现）"""
    state = get_car_state()
    state.media.playing = True
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": "继续播放",
        "current_state": _get_media_state()
    }


def _next_track() -> dict:
    """下一首（核心实现）"""
    state = get_car_state()
    
    # 根据当前类别选择库
    library = SONG_LIBRARY
    if state.media.track_artist == "儿歌":
        library = KIDS_SONGS
    
    song = random.choice(library)
    state.media.track_name = song["name"]
    state.media.track_artist = song["artist"]
    state.media.track_album = song.get("album", "")
    state.media.track_duration = song["duration"]
    state.media.track_position = 0
    state.media.playing = True
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": f"切换到: {song['name']} - {song['artist']}",
        "track": song,
        "current_state": _get_media_state()
    }


def _set_volume(volume: str) -> dict:
    """设置音量（核心实现）"""
    state = get_car_state()
    
    if isinstance(volume, str):
        vol_lower = volume.lower()
        if vol_lower in ["up", "调高", "大点", "大一点", "+"]:
            vol = min(100, state.media.volume + 10)
        elif vol_lower in ["down", "调低", "小点", "小一点", "-"]:
            vol = max(0, state.media.volume - 10)
        elif vol_lower in ["mute", "静音"]:
            vol = 0
        elif vol_lower in ["max", "最大"]:
            vol = 100
        else:
            try:
                vol = int(volume)
            except:
                vol = 50
    else:
        vol = int(volume)
    
    vol = max(0, min(100, vol))
    state.media.volume = vol
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": f"音量已设置为{vol}%",
        "current_state": _get_media_state()
    }


def _play_radio(frequency: str = None) -> dict:
    """播放电台（核心实现）"""
    state = get_car_state()
    
    if frequency:
        # 按名称搜索
        freq_lower = frequency.lower() if isinstance(frequency, str) else str(frequency)
        matched = None
        
        for station in RADIO_STATIONS:
            if freq_lower in station["name"].lower():
                matched = station
                break
        
        if not matched:
            # 尝试解析为频率
            try:
                freq = float(frequency)
                matched = {"name": f"FM {freq}", "frequency": freq}
            except:
                matched = random.choice(RADIO_STATIONS)
    else:
        matched = random.choice(RADIO_STATIONS)
    
    state.media.playing = True
    state.media.source = "radio"
    state.media.radio_frequency = matched["frequency"]
    state.media.track_name = matched["name"]
    state.media.track_artist = "电台"
    state.media.track_album = ""
    state.media.track_duration = 0
    state.media.track_position = 0
    
    save_car_state()
    
    # 广播状态变化到UI
    sync_update_and_broadcast("media")
    
    return {
        "success": True,
        "message": f"正在收听: {matched['name']} FM {matched['frequency']}",
        "station": matched,
        "current_state": _get_media_state()
    }


# ============ 被装饰的工具函数（用于Agent调用）============

@tool(name="get_media_state",
      description="获取当前媒体播放状态",
      params=[])
def get_media_state() -> dict:
    """获取媒体状态"""
    return _get_media_state()


@tool(name="play_music",
      description="播放音乐。可以搜索歌曲或随机播放",
      params=[
          Param(name="query",
                description="搜索词：歌名、歌手名，或'random'随机播放",
                type="str", required=False),
          Param(name="category",
                description="分类：'kids'/'儿歌' 播放儿童歌曲",
                type="str", required=False)
      ])
def play_music(query: str = None, category: str = None) -> dict:
    """播放音乐"""
    return _play_music(query, category)


@tool(name="pause_music",
      description="暂停音乐播放",
      params=[])
def pause_music() -> dict:
    """暂停音乐"""
    return _pause_music()


@tool(name="resume_music",
      description="继续播放音乐",
      params=[])
def resume_music() -> dict:
    """继续播放"""
    return _resume_music()


@tool(name="next_track",
      description="播放下一首歌曲",
      params=[])
def next_track() -> dict:
    """下一首"""
    return _next_track()


@tool(name="set_volume",
      description="设置音量",
      params=[
          Param(name="volume",
                description="音量大小：0-100，或'up'/'down'调高/调低",
                type="str", required=True)
      ])
def set_volume(volume: str) -> dict:
    """设置音量"""
    return _set_volume(volume)


@tool(name="play_radio",
      description="播放收音机/电台",
      params=[
          Param(name="frequency",
                description="FM频率如'99.6'，或电台名称如'交通广播'",
                type="str", required=False)
      ])
def play_radio(frequency: str = None) -> dict:
    """播放电台"""
    return _play_radio(frequency)


if __name__ == "__main__":
    print("当前媒体状态:", json.dumps(_get_media_state(), ensure_ascii=False, indent=2))
    print("\n播放周杰伦:", _play_music("周杰伦"))
    print("\n设置音量:", _set_volume("60"))
    print("\n下一首:", _next_track())
