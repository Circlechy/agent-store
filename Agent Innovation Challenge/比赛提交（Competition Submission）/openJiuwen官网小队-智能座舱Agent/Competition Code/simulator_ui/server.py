"""
车机模拟器 Web UI 服务器

提供:
1. RESTful API 获取/更新车机状态
2. WebSocket 实时推送状态变化
3. 静态文件服务（HTML/CSS/JS）
4. 图片上传与多模态问答API
5. 乘客管理API
"""

import asyncio
import json
import logging
import base64
import time
import uuid
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from carEmu.car_state import (
    get_car_state, save_car_state, reload_car_state,
    register_broadcast_callback, unregister_broadcast_callback
)

from smart_agent import run_agent

# 长期记忆
from memory.memory_manager import get_memory_manager

# 导入工具内部函数
from tools.carTools.passenger import (
    _get_all_profiles_internal,
    _get_profile_internal,
    _create_profile_internal,
    _update_profile_internal,
    _set_current_passenger_internal,
    _get_current_passengers_internal,
    _set_current_speaker_internal,
    _get_passenger_memory_internal,
    _record_history_internal
)
from tools.carTools.seat import _control_seat
from tools.carTools.tyres import _set_tire_pressure
from tools.carTools.tyres import _set_tire_pressure

from tools.vision_tools import (
    _set_camera_image_internal,
    _get_camera_image_internal,
    _analyze_image_internal,
    _analyze_camera_view_internal,
    _ask_about_image_internal,
    _identify_vehicle_internal,
    _analyze_video_internal
)

from tools.baidu_map import baidu_direction_driving
from tools.tts import set_tts_enabled, get_tts_status, synthesize_audio_base64_async

# 环境感知模块
from tools.carTools.environment import (
    load_environment_config,
    generate_all_alerts,
    get_environment_summary,
    ENVIRONMENT_CONFIG_FILE
)
from nodes.utils.utils import get_user_locations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def recalculate_navigation_if_active(new_origin_coords: str, new_origin_city: str = "杭州"):
    """
    如果导航处于活跃状态，使用新的起点位置重新计算导航时间和距离。
    这个函数在用户切换当前位置时调用。支持途经点。
    重要：会重新提取并更新 route_points（车道级导航路线点）
    """
    # 使用 get_car_state() 保持内存状态，避免从文件重新加载导致状态重置
    state = get_car_state()
    nav = state.navigation
    
    # 检查是否有活跃的导航
    if not nav.active or not nav.destination_coords:
        return None
    
    try:
        # 构建路线规划参数
        route_params = {
            "origin": new_origin_coords,
            "destination": nav.destination_coords,
            "origin_region": new_origin_city,
            "destination_region": state.vehicle.current_location_city or "杭州"
        }
        
        # 如果有途经点，添加到参数中
        if nav.waypoints_coords:
            route_params["waypoints"] = nav.waypoints_coords
        
        # 调用百度地图重新计算路线
        route_result = baidu_direction_driving.invoke(inputs=route_params)
        
        if route_result.get("status") == 0:
            routes = route_result.get("result", {}).get("routes", [])
            if routes:
                route = routes[0]
                distance_m = route.get("distance", 0)
                duration_s = route.get("duration", 0)
                
                distance_km = round(distance_m / 1000, 1)
                eta_minutes = round(duration_s / 60)
                
                # 更新导航状态
                state.navigation.eta_minutes = eta_minutes
                state.navigation.distance_km = distance_km
                
                # 获取路线步骤并提取 route_points（车道级导航）
                steps = route.get("steps", [])
                route_points = []
                
                if steps:
                    first_step = steps[0]
                    state.navigation.current_road = first_step.get("road_name", "")
                    if len(steps) > 1:
                        next_step = steps[1]
                        state.navigation.next_turn = next_step.get("instruction", "")[:50]
                        state.navigation.next_turn_distance = next_step.get("distance", 0)
                    
                    # 🔥 重要：从每个 step 的 path 中提取坐标点（车道级导航）
                    for step in steps:
                        path_str = step.get("path", "")
                        if path_str:
                            points = path_str.split(";")
                            for point in points:
                                if "," in point:
                                    try:
                                        lng, lat = point.split(",")
                                        # 转换为 [lat, lng] 格式（前端 Leaflet 使用的格式）
                                        route_points.append([float(lat), float(lng)])
                                    except (ValueError, IndexError):
                                        continue
                
                # 更新 route_points（保留车道级导航）
                state.navigation.route_points = route_points
                logger.info(f"已更新 route_points: {len(route_points)} 个坐标点")
                
                save_car_state()
                
                waypoints_info = f" (含{len(nav.waypoints)}个途经点)" if nav.waypoints else ""
                logger.info(f"导航时间已更新: {nav.destination}{waypoints_info} - {distance_km}km, {eta_minutes}分钟")
                
                return {
                    "destination": nav.destination,
                    "distance_km": distance_km,
                    "eta_minutes": eta_minutes,
                    "waypoints": nav.waypoints,
                    "route_points": route_points  # 返回 route_points 供前端使用
                }
    except Exception as e:
        logger.error(f"重新计算导航失败: {e}")
    
    return None


app = FastAPI(title="智能座舱模拟器", version="1.0.0")

# 静态资源压缩与缓存（提升前端加载速度）
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ============ 对话历史管理 ============
# 存储每个用户的对话历史 {session_id: [{"role": "user/assistant", "content": "..."}]}
conversation_histories: dict = {}
MAX_HISTORY_ROUNDS = 20  # 最多保留20轮对话（40条消息）

# ============ 临时视频上传管理 ============
VIDEO_UPLOAD_TTL_SECONDS = 60 * 60  # 1小时
VIDEO_UPLOAD_MAX_ITEMS = 20
VIDEO_UPLOAD_DIR = Path(tempfile.gettempdir()) / "jiuwen_video_uploads"
VIDEO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
video_uploads: dict = {}


def cleanup_video_uploads():
    now = time.time()
    expired_ids = [
        video_id for video_id, meta in video_uploads.items()
        if now - meta.get("uploaded_at", now) > VIDEO_UPLOAD_TTL_SECONDS
    ]
    for video_id in expired_ids:
        meta = video_uploads.pop(video_id, {})
        path = meta.get("path")
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except Exception:
                logger.warning(f"清理视频失败: {path}")

    if len(video_uploads) > VIDEO_UPLOAD_MAX_ITEMS:
        items = sorted(video_uploads.items(), key=lambda item: item[1].get("uploaded_at", 0))
        for video_id, meta in items[:len(video_uploads) - VIDEO_UPLOAD_MAX_ITEMS]:
            video_uploads.pop(video_id, None)
            path = meta.get("path")
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except Exception:
                    logger.warning(f"清理视频失败: {path}")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟歌曲库
SONG_LIBRARY = [
    {"name": "晴天", "artist": "周杰伦", "duration": 269},
    {"name": "七里香", "artist": "周杰伦", "duration": 299},
    {"name": "夜曲", "artist": "周杰伦", "duration": 226},
    {"name": "稻香", "artist": "周杰伦", "duration": 223},
    {"name": "青花瓷", "artist": "周杰伦", "duration": 239},
    {"name": "告白气球", "artist": "周杰伦", "duration": 215},
    {"name": "简单爱", "artist": "周杰伦", "duration": 270},
    {"name": "以父之名", "artist": "周杰伦", "duration": 340},
    {"name": "倒带", "artist": "蔡依林", "duration": 261},
    {"name": "说爱你", "artist": "蔡依林", "duration": 230},
    {"name": "日不落", "artist": "蔡依林", "duration": 257},
    {"name": "小幸运", "artist": "田馥甄", "duration": 293},
    {"name": "追光者", "artist": "岑宁儿", "duration": 252},
    {"name": "后来", "artist": "刘若英", "duration": 326},
    {"name": "知否知否", "artist": "郁可唯/胡夏", "duration": 261},
]

# 当前播放索引
current_song_index = 0


# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, ConnectionError, ConnectionResetError) as e:
                # 连接已断开，标记为需要移除
                # ConnectionResetError 是 Windows 上常见的连接重置错误，通常发生在客户端突然断开时
                if isinstance(e, ConnectionResetError):
                    logger.debug(f"客户端连接已重置（正常断开）: {e}")
                else:
                    logger.debug(f"连接已断开: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"广播失败: {e}")
                # 其他异常也标记为断开
                disconnected.append(connection)
        
        # 移除已断开的连接
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


# 注册广播回调
async def broadcast_callback(message: dict):
    await manager.broadcast(message)

register_broadcast_callback(broadcast_callback)


# 静态文件
class CachedStaticFiles(StaticFiles):
    def __init__(self, *args, cache_control: str = "public, max-age=86400", **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_control = cache_control

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # 仅对静态资源设置缓存，避免误缓存 HTML
            lowered = path.lower()
            if not lowered.endswith(".html"):
                response.headers.setdefault("Cache-Control", self._cache_control)
                response.headers.setdefault("Vary", "Accept-Encoding")
        return response

static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", CachedStaticFiles(directory=str(static_path)), name="static")


# ============ Pydantic 数据模型 ============
# 注意：所有 BaseModel 类必须在路由定义之前定义

class TirePressureSet(BaseModel):
    tire: str  # front_left / front_right / rear_left / rear_right
    pressure: float  # 胎压值（bar）


class TtsToggleRequest(BaseModel):
    enabled: bool

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页"""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>智能座舱模拟器</h1><p>静态文件未找到</p>")


@app.get("/api/state")
async def get_state():
    """获取完整车机状态（每次从文件重新加载，以检测Agent端的修改）"""
    state = reload_car_state()
    return state.to_dict()


@app.get("/api/tts/status")
async def get_tts_status_api():
    """获取TTS播报状态"""
    return get_tts_status.invoke(inputs={})


@app.post("/api/tts/enabled")
async def set_tts_enabled_api(data: TtsToggleRequest):
    """设置TTS播报开关"""
    return set_tts_enabled.invoke(inputs={"enabled": data.enabled})


@app.get("/api/state/{component}")
async def get_component_state(component: str):
    """获取指定组件状态"""
    state = reload_car_state()
    component_state = getattr(state, component, None)
    if component_state:
        from dataclasses import asdict
        return asdict(component_state)
    return {"error": f"未知组件: {component}"}


@app.post("/api/vehicle/tire-pressure")
async def set_tire_pressure_api(data: TirePressureSet):
    """设置轮胎胎压"""
    try:
        result = _set_tire_pressure(tire=data.tire, pressure=data.pressure)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except Exception as e:
        logger.error(f"设置胎压失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 环境感知配置 API ============

@app.get("/api/environment")
async def get_environment_config():
    """获取环境配置"""
    config = load_environment_config()
    if config:
        return config
    return {"enabled": False, "message": "环境配置文件不存在或已禁用"}


def _sync_vehicle_state_from_environment(config: dict) -> bool:
    """将环境配置中的车辆关键状态同步到车机状态"""
    vehicle_config = config.get("vehicle", {})
    if not isinstance(vehicle_config, dict):
        return False
    
    state = get_car_state()
    has_update = False
    
    battery = vehicle_config.get("battery", {})
    if isinstance(battery, dict):
        if "level_percent" in battery:
            state.vehicle.battery_level = battery["level_percent"]
            has_update = True
        if "range_km" in battery:
            state.vehicle.range_km = battery["range_km"]
            has_update = True
    
    tire_pressure = vehicle_config.get("tire_pressure", {})
    if isinstance(tire_pressure, dict):
        mapping = {
            "front_left": 0,
            "front_right": 1,
            "rear_left": 2,
            "rear_right": 3
        }
        if any(key in tire_pressure for key in mapping):
            current = list(state.vehicle.tire_pressure)
            while len(current) < 4:
                current.append(2.4)
            for key, index in mapping.items():
                if key in tire_pressure:
                    current[index] = tire_pressure[key]
                    has_update = True
            state.vehicle.tire_pressure = current[:4]
    
    if has_update:
        save_car_state()
    
    return has_update


@app.post("/api/environment")
async def update_environment_config(updates: dict):
    """更新环境配置"""
    try:
        # 读取当前配置
        config = load_environment_config()
        if not config:
            config = {"enabled": True}
        
        # 深度合并更新
        def deep_merge(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        config = deep_merge(config, updates)
        
        # 保存配置
        import json
        with open(ENVIRONMENT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"环境配置已更新: {list(updates.keys())}")
        
        # 若更新涉及车辆状态，同步到车机状态文件
        if "vehicle" in updates:
            vehicle_synced = _sync_vehicle_state_from_environment(config)
            if vehicle_synced:
                from dataclasses import asdict
                await manager.broadcast({
                    "type": "state_update",
                    "component": "vehicle",
                    "state": asdict(get_car_state().vehicle)
                })
        
        # 广播环境配置更新
        await manager.broadcast({
            "type": "environment_update",
            "config": config
        })
        
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"更新环境配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/environment/alerts")
async def get_environment_alerts():
    """获取环境提醒列表"""
    try:
        alerts = generate_all_alerts()
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "category": a.category,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "action_suggestion": a.action_suggestion,
                    "auto_action": a.auto_action
                }
                for a in alerts
            ]
        }
    except Exception as e:
        logger.error(f"获取环境提醒失败: {e}")
        return {"count": 0, "alerts": [], "error": str(e)}


@app.get("/api/environment/summary")
async def get_environment_summary_api():
    """获取环境状态摘要"""
    return get_environment_summary()


@app.post("/api/state/{component}")
async def update_component_state(component: str, updates: dict):
    """更新指定组件状态"""
    global current_song_index
    
    state = reload_car_state()
    component_obj = getattr(state, component, None)
    
    if not component_obj:
        return {"error": f"未知组件: {component}"}
    
    # 特殊处理座椅控制
    if component == "seats" and "seat" in updates and "settings" in updates:
        seat = updates["seat"]
        settings = updates["settings"]
        result = _control_seat(seat, settings)
        if result.get("success"):
            # 重新加载状态以获取最新值
            state = reload_car_state()
            from dataclasses import asdict
            await manager.broadcast({
                "type": "state_update",
                "component": "seats",
                "state": asdict(state.seats)
            })
            # 如果更新了加热/通风，也需要广播AC状态
            if "heating" in settings or "ventilation" in settings:
                await manager.broadcast({
                    "type": "state_update",
                    "component": "ac",
                    "state": asdict(state.ac)
                })
        return result
    
    # 特殊处理媒体控制动作
    if component == "media" and "action" in updates:
        action = updates.pop("action")
        
        if action == "next":
            current_song_index = (current_song_index + 1) % len(SONG_LIBRARY)
            song = SONG_LIBRARY[current_song_index]
            state.media.track_name = song["name"]
            state.media.track_artist = song["artist"]
            state.media.track_duration = song["duration"]
            state.media.track_position = 0
            state.media.playing = True
            logger.info(f"切换到下一首: {song['name']} - {song['artist']}")
        
        elif action == "prev":
            current_song_index = (current_song_index - 1) % len(SONG_LIBRARY)
            song = SONG_LIBRARY[current_song_index]
            state.media.track_name = song["name"]
            state.media.track_artist = song["artist"]
            state.media.track_duration = song["duration"]
            state.media.track_position = 0
            state.media.playing = True
            logger.info(f"切换到上一首: {song['name']} - {song['artist']}")
        
        elif action == "play":
            state.media.playing = True
        
        elif action == "pause":
            state.media.playing = False
    
    # 处理其他常规更新
    for key, value in updates.items():
        if hasattr(component_obj, key):
            setattr(component_obj, key, value)
    
    save_car_state()
    
    # 广播变化
    from dataclasses import asdict
    await manager.broadcast({
        "type": "state_update",
        "component": component,
        "state": asdict(component_obj)
    })
    
    return {"success": True, "state": asdict(component_obj)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    global current_song_index
    
    await manager.connect(websocket)
    
    try:
        # 连接后立即发送当前状态
        try:
            state = reload_car_state()
            await websocket.send_json({
                "type": "full_state",
                "state": state.to_dict()
            })
        except (WebSocketDisconnect, RuntimeError, ConnectionError, ConnectionResetError) as e:
            # ConnectionResetError 是客户端突然断开时的常见错误，属于正常情况
            if isinstance(e, ConnectionResetError):
                logger.debug(f"客户端连接已重置（发送初始状态时）: {e}")
            else:
                logger.warning(f"发送初始状态失败，连接可能已断开: {e}")
            manager.disconnect(websocket)
            return
        except Exception as e:
            logger.error(f"发送初始状态时出错: {e}")
            manager.disconnect(websocket)
            return
        
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理ping消息
                if message.get("type") == "ping":
                    try:
                        await websocket.send_json({"type": "pong"})
                    except (WebSocketDisconnect, RuntimeError, ConnectionError):
                        raise
                
                # 处理状态更新请求
                elif message.get("type") == "update":
                    component = message.get("component")
                    updates = message.get("updates", {})
                    
                    state = reload_car_state()
                    component_obj = getattr(state, component, None)
                    
                    if component_obj:
                        # 特殊处理媒体控制动作
                        if component == "media" and "action" in updates:
                            action = updates.pop("action")
                            
                            if action == "next":
                                current_song_index = (current_song_index + 1) % len(SONG_LIBRARY)
                                song = SONG_LIBRARY[current_song_index]
                                state.media.track_name = song["name"]
                                state.media.track_artist = song["artist"]
                                state.media.track_duration = song["duration"]
                                state.media.track_position = 0
                                state.media.playing = True
                            
                            elif action == "prev":
                                current_song_index = (current_song_index - 1) % len(SONG_LIBRARY)
                                song = SONG_LIBRARY[current_song_index]
                                state.media.track_name = song["name"]
                                state.media.track_artist = song["artist"]
                                state.media.track_duration = song["duration"]
                                state.media.track_position = 0
                                state.media.playing = True
                        
                        for key, value in updates.items():
                            if hasattr(component_obj, key):
                                setattr(component_obj, key, value)
                        save_car_state()
                        
                        from dataclasses import asdict
                        await manager.broadcast({
                            "type": "state_update",
                            "component": component,
                            "state": asdict(component_obj)
                        })
                
                # 处理获取完整状态请求
                elif message.get("type") == "get_state":
                    try:
                        state = reload_car_state()
                        await websocket.send_json({
                            "type": "full_state",
                            "state": state.to_dict()
                        })
                    except (WebSocketDisconnect, RuntimeError, ConnectionError):
                        raise
            
            except WebSocketDisconnect:
                # 客户端正常断开
                logger.debug("WebSocket客户端正常断开")
                break
            except (RuntimeError, ConnectionError, ConnectionResetError) as e:
                # 连接错误（包括连接重置）
                if isinstance(e, ConnectionResetError):
                    logger.debug(f"WebSocket连接已重置（客户端断开）: {e}")
                else:
                    logger.warning(f"WebSocket连接错误: {e}")
                break
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {e}")
                # 继续处理其他消息，不中断连接
    
    except WebSocketDisconnect:
        # 客户端断开连接
        logger.debug("WebSocket客户端断开连接")
    except (ConnectionResetError, RuntimeError, ConnectionError) as e:
        # 连接重置或连接错误（客户端突然断开）
        if isinstance(e, ConnectionResetError):
            logger.debug(f"WebSocket连接已重置: {e}")
        else:
            logger.debug(f"WebSocket连接错误: {e}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        # 确保断开连接（只调用一次）
        manager.disconnect(websocket)


# ============ 请求模型 ============

class PassengerCreate(BaseModel):
    name: str
    avatar_base64: Optional[str] = ""
    preferences: Optional[dict] = None

class PassengerUpdate(BaseModel):
    updates: dict

class SeatPassenger(BaseModel):
    seat: str  # driver / passenger
    passenger_id: str

class SpeakerSet(BaseModel):
    speaker: str  # driver / passenger / ""

class CameraImageSet(BaseModel):
    camera_type: str  # front / rear / interior / left / right
    image_data: str  # base64

class ImageQuestion(BaseModel):
    image_data: str  # base64 or URL
    question: str

class CameraQuestion(BaseModel):
    camera_type: str
    question: str

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "web_user"
    speaker_name: Optional[str] = None  # 说话者姓名
    speaker_seat: Optional[str] = None  # 说话者座位（主驾/副驾）
    use_memory: Optional[bool] = True
    image_data: Optional[str] = None  # 可选的图片数据
    video_id: Optional[str] = None  # 可选的视频上传ID
    tts_playback: Optional[str] = "browser"

class ClearHistoryRequest(BaseModel):
    session_id: Optional[str] = "default"

class ClearMemoryRequest(BaseModel):
    user_id: Optional[str] = None
    clear_all: Optional[bool] = False

class SetLocationRequest(BaseModel):
    location_name: str
    coords: str
    city: Optional[str] = "杭州"

class GeocodeLocationRequest(BaseModel):
    address: str
    city: Optional[str] = "杭州"

class ReverseGeocodeRequest(BaseModel):
    coords: str  # 格式: "纬度,经度"


def get_conversation_history(session_id: str) -> list:
    """获取对话历史"""
    if session_id not in conversation_histories:
        conversation_histories[session_id] = []
    return conversation_histories[session_id]


def add_to_history(session_id: str, role: str, content: str, image_data: str = None):
    """添加消息到历史"""
    history = get_conversation_history(session_id)
    
    message = {"role": role, "content": content}
    if image_data:
        message["image"] = image_data[:100] + "..."  # 只保存图片引用标识
    
    history.append(message)
    
    # 保持历史长度限制：最多保留最近 20 轮对话（40条消息）
    max_messages = MAX_HISTORY_ROUNDS * 2
    if len(history) > max_messages:
        conversation_histories[session_id] = history[-max_messages:]


def get_video_upload_meta(video_id: str) -> Optional[dict]:
    if not video_id:
        return None
    cleanup_video_uploads()
    return video_uploads.get(video_id)


def format_history_for_agent(session_id: str) -> list:
    """格式化历史记录供Agent使用，最多返回最近 20 轮对话"""
    history = get_conversation_history(session_id)
    # 只取最近的 20 轮对话（40条消息）
    max_messages = MAX_HISTORY_ROUNDS * 2
    recent_history = history[-max_messages:] if len(history) > max_messages else history
    formatted = []
    for msg in recent_history:
        formatted.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    return formatted


def _parse_tool_success(content) -> Optional[bool]:
    """从工具输出中解析 success 状态"""
    if content is None:
        return None
    if isinstance(content, dict):
        if "success" in content:
            return bool(content.get("success"))
        if "error" in content:
            return False
        return None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return _parse_tool_success(parsed)
        except json.JSONDecodeError:
            pass
        lowered = content.lower()
        if '"success": true' in lowered or "'success': true" in lowered:
            return True
        if '"success": false' in lowered or "'success': false" in lowered:
            return False
        if "error" in lowered or "failed" in lowered or "失败" in content:
            return False
        if "成功" in content and "失败" not in content:
            return True
    return None


def _summarize_tool_result(content, max_len: int = 120) -> Optional[str]:
    """生成工具输出的简短摘要"""
    if content is None:
        return None
    if isinstance(content, dict):
        text = json.dumps(content, ensure_ascii=False)
    else:
        text = str(content)
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def extract_tool_steps(messages: list) -> list:
    """从消息历史中提取工具调用步骤"""
    steps = []
    call_map = {}
    call_index = 0

    for msg in messages or []:
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            agent = msg.get("agent") or "unknown_agent"
            for tool_call in msg.get("tool_calls", []):
                call_index += 1
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_call_id = tool_call.get("id")
                step = {
                    "index": call_index,
                    "agent": agent,
                    "tool": tool_name,
                    "tool_call_id": tool_call_id,
                    "success": None,
                    "result_summary": None,
                }
                steps.append(step)
                if tool_call_id:
                    call_map[tool_call_id] = step
        elif role == "tool":
            tool_call_id = msg.get("tool_call_id")
            step = call_map.get(tool_call_id)
            if step is None:
                call_index += 1
                step = {
                    "index": call_index,
                    "agent": msg.get("agent") or "unknown_agent",
                    "tool": msg.get("name") or "",
                    "tool_call_id": tool_call_id,
                    "success": None,
                    "result_summary": None,
                }
                steps.append(step)
                if tool_call_id:
                    call_map[tool_call_id] = step

            content = msg.get("content")
            step["success"] = _parse_tool_success(content)
            step["result_summary"] = _summarize_tool_result(content)
            
            # 检测是否是举报表单工具
            if step.get("tool") == "create_traffic_report" and content:
                try:
                    content_data = json.loads(content) if isinstance(content, str) else content
                    if content_data.get("report_form"):
                        step["report_form"] = content_data["report_form"]
                except (json.JSONDecodeError, TypeError):
                    pass

    return steps


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取对话历史"""
    history = get_conversation_history(session_id)
    return {
        "success": True,
        "session_id": session_id,
        "messages": history,
        "count": len(history)
    }


@app.post("/api/chat/clear")
async def clear_chat_history(data: ClearHistoryRequest):
    """清空对话历史"""
    session_id = data.session_id or "default"
    if session_id in conversation_histories:
        conversation_histories[session_id] = []
    return {"success": True, "message": "对话历史已清空"}


@app.post("/api/memory/clear")
async def clear_memory_history(data: ClearMemoryRequest):
    """清空长期记忆中的历史对话"""
    memory_manager = await get_memory_manager()
    target_user = None if data.clear_all or not data.user_id else data.user_id
    result = await memory_manager.clear_conversation_history(target_user)
    if result.get("error"):
        return {"success": False, "error": result.get("error")}
    return {
        "success": True,
        "scope": "all" if target_user is None else "user",
        "user_id": target_user,
        "cleared": result
    }


@app.post("/api/chat")
async def chat(data: ChatRequest):
    """智能对话接口 - 支持多轮上下文"""
    session_id = data.session_id or "default"
    
    try:
        # 获取历史记录
        history_messages = format_history_for_agent(session_id)
        
        # 获取说话者信息
        speaker_info = None
        if data.user_id in ["driver", "passenger"]:
            # 设置当前说话者
            _set_current_speaker_internal(data.user_id)
            # 获取说话者详细信息
            current_passengers = _get_current_passengers_internal()
            speaker_data = current_passengers.get(data.user_id, {})
            
            speaker_info = {
                "seat": data.speaker_seat or ("主驾" if data.user_id == "driver" else "副驾"),
                "name": data.speaker_name or speaker_data.get("name") or ("主驾驶员" if data.user_id == "driver" else "副驾乘客"),
                "id": speaker_data.get("id"),
                "profile": speaker_data.get("profile")
            }
            logger.info(f"当前说话者: {speaker_info['name']} ({speaker_info['seat']})")
        
        # 构建用户消息
        user_message = data.question
        image_data_for_agent = None
        image_analysis_text = None
        video_analysis_text = None

        # 如果有图片，先进行图片分析
        if data.image_data:
            image_analysis = _ask_about_image_internal(data.image_data, data.question)
            if image_analysis.get("success"):
                image_analysis_text = image_analysis.get("analysis", "")
                image_data_for_agent = data.image_data

        # 如果有视频，进行抽帧分析
        if data.video_id:
            video_meta = get_video_upload_meta(data.video_id)
            if not video_meta:
                return {"success": False, "error": "视频已过期或不存在，请重新上传"}
            video_result = _analyze_video_internal(video_meta.get("path"), data.question)
            if not video_result.get("success"):
                return {"success": False, "error": video_result.get("error", "视频分析失败")}
            video_analysis_text = video_result.get("analysis", "")
            # 使用视频关键帧作为后续视觉工具的图片数据（如果没有图片上传）
            if not image_data_for_agent and video_result.get("key_frame_data"):
                image_data_for_agent = video_result["key_frame_data"]

        if image_analysis_text or video_analysis_text:
            items = []
            if image_analysis_text:
                items.append(f"图片分析结果: {image_analysis_text}")
            if video_analysis_text:
                items.append(f"视频抽帧分析结果: {video_analysis_text}")
            notice = "注意：视频为临时上传，仅基于抽帧画面推断。视频关键帧已作为当前图片数据传递，如需分析可使用analyze_image工具。" if video_analysis_text else ""
            image_notice = "注意：原始图片数据已通过全局状态传递，如需重新分析可使用analyze_image工具，参数image_path请使用全局状态中的current_image_data" if image_analysis_text and not video_analysis_text else ""
            notices = " ".join([n for n in [notice, image_notice] if n])
            user_message = f"[用户上传了{'图片' if image_analysis_text else ''}{'和' if image_analysis_text and video_analysis_text else ''}{'视频' if video_analysis_text else ''}并提问: {data.question}]\n" + "\n".join(items)
            if notices:
                user_message = f"{user_message}\n{notices}"
        
        # 添加用户消息到历史
        add_to_history(session_id, "user", data.question, data.image_data)
        
        # 调用Agent，传递图片数据和说话者信息
        result, _, tool_trace = await run_agent(
            query=user_message,
            history_messages=history_messages,
            user_id=data.user_id,
            enable_long_term_memory=data.use_memory,
            image_data=image_data_for_agent,
            speaker_info=speaker_info,
            tts_playback=data.tts_playback
        )

        tool_steps = extract_tool_steps(tool_trace or [])
        
        audio_payload = None
        if data.tts_playback == "browser_audio" and result:
            audio_payload = await synthesize_audio_base64_async(result)

        # 添加助手回复到历史
        add_to_history(session_id, "assistant", result)
        
        return {
            "success": True,
            "answer": result,
            "session_id": session_id,
            "history_length": len(get_conversation_history(session_id)),
            "tool_steps": tool_steps,
            "audio_base64": (audio_payload or {}).get("audio_base64"),
            "audio_mime": (audio_payload or {}).get("audio_mime")
        }
    except Exception as e:
        logger.error(f"对话执行失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ============ 流式对话API ============
@app.post("/api/chat/stream")
async def chat_stream(data: ChatRequest):
    """智能对话接口 - 流式返回工具调用进度"""
    session_id = data.session_id or "default"
    queue: asyncio.Queue = asyncio.Queue()
    done_event = asyncio.Event()

    async def emit(event: dict):
        await queue.put(event)

    async def run_chat():
        try:
            history_messages = format_history_for_agent(session_id)

            # 获取说话者信息
            speaker_info = None
            if data.user_id in ["driver", "passenger"]:
                _set_current_speaker_internal(data.user_id)
                current_passengers = _get_current_passengers_internal()
                speaker_data = current_passengers.get(data.user_id, {})

                speaker_info = {
                    "seat": data.speaker_seat or ("主驾" if data.user_id == "driver" else "副驾"),
                    "name": data.speaker_name or speaker_data.get("name") or ("主驾驶员" if data.user_id == "driver" else "副驾乘客"),
                    "id": speaker_data.get("id"),
                    "profile": speaker_data.get("profile")
                }
                logger.info(f"当前说话者: {speaker_info['name']} ({speaker_info['seat']})")

            user_message = data.question
            image_data_for_agent = None
            image_analysis_text = None
            video_analysis_text = None

            # 如果有图片，先进行图片分析
            if data.image_data:
                image_analysis = _ask_about_image_internal(data.image_data, data.question)
                if image_analysis.get("success"):
                    image_analysis_text = image_analysis.get("analysis", "")
                    image_data_for_agent = data.image_data

            # 如果有视频，进行抽帧分析
            if data.video_id:
                video_meta = get_video_upload_meta(data.video_id)
                if not video_meta:
                    await emit({"event": "error", "data": {"error": "视频已过期或不存在，请重新上传"}})
                    done_event.set()
                    return
                video_result = _analyze_video_internal(video_meta.get("path"), data.question)
                if not video_result.get("success"):
                    await emit({"event": "error", "data": {"error": video_result.get("error", "视频分析失败")}})
                    done_event.set()
                    return
                video_analysis_text = video_result.get("analysis", "")
                # 使用视频关键帧作为后续视觉工具的图片数据（如果没有图片上传）
                if not image_data_for_agent and video_result.get("key_frame_data"):
                    image_data_for_agent = video_result["key_frame_data"]

            if image_analysis_text or video_analysis_text:
                items = []
                if image_analysis_text:
                    items.append(f"图片分析结果: {image_analysis_text}")
                if video_analysis_text:
                    items.append(f"视频抽帧分析结果: {video_analysis_text}")
                notice = "注意：视频为临时上传，仅基于抽帧画面推断。视频关键帧已作为当前图片数据传递，如需分析可使用analyze_image工具。" if video_analysis_text else ""
                image_notice = "注意：原始图片数据已通过全局状态传递，如需重新分析可使用analyze_image工具，参数image_path请使用全局状态中的current_image_data" if image_analysis_text and not video_analysis_text else ""
                notices = " ".join([n for n in [notice, image_notice] if n])
                user_message = f"[用户上传了{'图片' if image_analysis_text else ''}{'和' if image_analysis_text and video_analysis_text else ''}{'视频' if video_analysis_text else ''}并提问: {data.question}]\n" + "\n".join(items)
                if notices:
                    user_message = f"{user_message}\n{notices}"

            # 添加用户消息到历史
            add_to_history(session_id, "user", data.question, data.image_data)

            result, _, tool_trace = await run_agent(
                query=user_message,
                history_messages=history_messages,
                user_id=data.user_id,
                enable_long_term_memory=data.use_memory,
                image_data=image_data_for_agent,
                speaker_info=speaker_info,
                event_emitter=emit,
                tts_playback=data.tts_playback
            )

            tool_steps = extract_tool_steps(tool_trace or [])
            add_to_history(session_id, "assistant", result)

            # 检查是否有举报表单
            report_form = None
            for step in tool_steps:
                if step.get("report_form"):
                    report_form = step["report_form"]
                    break

            audio_payload = None
            if data.tts_playback == "browser_audio" and result:
                audio_payload = await synthesize_audio_base64_async(result)

            final_response = {
                "type": "final",
                "answer": result,
                "session_id": session_id,
                "history_length": len(get_conversation_history(session_id)),
                "tool_steps": tool_steps,
                "audio_base64": (audio_payload or {}).get("audio_base64"),
                "audio_mime": (audio_payload or {}).get("audio_mime")
            }
            
            # 如果有举报表单，添加到响应中
            if report_form:
                final_response["report_form"] = report_form
            
            await emit(final_response)
        except Exception as e:
            logger.error(f"流式对话执行失败: {e}")
            await emit({"type": "error", "error": str(e)})
        finally:
            done_event.set()

    asyncio.create_task(run_chat())

    async def event_generator():
        while True:
            if done_event.is_set() and queue.empty():
                yield "event: done\ndata: {}\n\n"
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            event_type = event.get("type", "message")
            payload = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ============ 乘客管理API ============

@app.get("/api/passengers")
async def list_passengers():
    """列出所有乘客档案"""
    profiles = _get_all_profiles_internal()
    return {
        "success": True,
        "count": len(profiles),
        "passengers": [
            {
                "id": pid,
                "name": p.get("name", ""),
                "avatar_base64": p.get("avatar_base64", "")[:100] + "..." if p.get("avatar_base64", "") else "",
                "has_avatar": bool(p.get("avatar_base64", "")),
                "created_at": p.get("created_at", "")
            }
            for pid, p in profiles.items()
        ]
    }


@app.get("/api/passengers/current")
async def get_current_passengers():
    """获取当前车内乘客"""
    return _get_current_passengers_internal()


@app.post("/api/passengers")
async def create_passenger(data: PassengerCreate):
    """创建乘客档案"""
    profile = _create_profile_internal(
        name=data.name,
        avatar_base64=data.avatar_base64 or "",
        preferences=data.preferences
    )
    return {"success": True, "profile": profile}


@app.get("/api/passengers/{passenger_id}")
async def get_passenger(passenger_id: str):
    """获取乘客档案"""
    profile = _get_profile_internal(passenger_id)
    if profile:
        return {"success": True, "profile": profile}
    raise HTTPException(status_code=404, detail=f"乘客档案不存在: {passenger_id}")


@app.put("/api/passengers/{passenger_id}")
async def update_passenger(passenger_id: str, data: PassengerUpdate):
    """更新乘客档案"""
    result = _update_profile_internal(passenger_id, data.updates)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@app.post("/api/passengers/{passenger_id}/avatar")
async def upload_passenger_avatar(passenger_id: str, file: UploadFile = File(...)):
    """上传乘客头像"""
    content = await file.read()
    avatar_base64 = base64.b64encode(content).decode("utf-8")
    
    result = _update_profile_internal(passenger_id, {"avatar_base64": avatar_base64})
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    
    return {"success": True, "message": "头像上传成功"}


@app.post("/api/passengers/seat")
async def set_seat_passenger(data: SeatPassenger):
    """设置座位乘客"""
    result = _set_current_passenger_internal(data.seat, data.passenger_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/api/passengers/speaker")
async def set_speaker(data: SpeakerSet):
    """设置当前说话者"""
    result = _set_current_speaker_internal(data.speaker)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.get("/api/passengers/{passenger_id}/memory")
async def get_passenger_memory(passenger_id: str, memory_type: Optional[str] = None):
    """获取乘客记忆"""
    result = _get_passenger_memory_internal(passenger_id, memory_type)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


# ============ 摄像头与视觉API ============

@app.post("/api/camera/set")
async def set_camera_image(data: CameraImageSet):
    """设置摄像头图片（用于模拟）"""
    result = _set_camera_image_internal(data.camera_type, data.image_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/api/camera/upload/{camera_type}")
async def upload_camera_image(camera_type: str, file: UploadFile = File(...)):
    """上传摄像头图片"""
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")
    
    # 添加data URI前缀
    mime_type = file.content_type or "image/jpeg"
    image_data = f"data:{mime_type};base64,{image_base64}"
    
    result = _set_camera_image_internal(camera_type, image_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "camera": camera_type, "message": "图片上传成功"}


@app.get("/api/camera/{camera_type}")
async def get_camera_image(camera_type: str):
    """获取摄像头图片"""
    result = _get_camera_image_internal(camera_type)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/api/camera/analyze")
async def analyze_camera(data: CameraQuestion):
    """分析摄像头画面"""
    try:
        result = _analyze_camera_view_internal(data.camera_type, data.question)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/vision/ask")
async def ask_image_question(data: ImageQuestion):
    """图片问答"""
    try:
        result = _ask_about_image_internal(data.image_data, data.question)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/vision/upload-and-ask")
async def upload_and_ask(
    file: UploadFile = File(...),
    question: str = Form(...)
):
    """上传图片并提问"""
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")
    
    mime_type = file.content_type or "image/jpeg"
    image_data = f"data:{mime_type};base64,{image_base64}"
    
    try:
        result = _ask_about_image_internal(image_data, question)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/vision/video/upload")
async def upload_video(file: UploadFile = File(...)):
    """临时上传视频，返回视频ID用于后续提问"""
    cleanup_video_uploads()
    video_id = str(uuid.uuid4())
    suffix = Path(file.filename or "").suffix or ".mp4"
    target_path = VIDEO_UPLOAD_DIR / f"{video_id}{suffix}"
    content = await file.read()
    target_path.write_bytes(content)
    video_uploads[video_id] = {
        "path": str(target_path),
        "filename": file.filename,
        "content_type": file.content_type,
        "uploaded_at": time.time()
    }
    return {
        "success": True,
        "video_id": video_id,
        "filename": file.filename,
        "message": "视频上传成功"
    }


@app.post("/api/vision/identify-vehicle")
async def identify_vehicle(file: UploadFile = File(None), use_front_camera: bool = False):
    """识别车辆"""
    image_data = None
    
    if file:
        content = await file.read()
        image_base64 = base64.b64encode(content).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"
        image_data = f"data:{mime_type};base64,{image_base64}"
    
    try:
        result = _identify_vehicle_internal(image_data)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ 快捷API：多模态场景 ============

@app.post("/api/scenario/who-is-speaking")
async def who_is_speaking(seat: str = Form(...)):
    """场景：识别说话者并返回其个性化信息"""
    # 设置当前说话者
    speaker_result = _set_current_speaker_internal(seat)
    if not speaker_result.get("success"):
        return speaker_result
    
    # 获取当前乘客
    passengers = _get_current_passengers_internal()
    
    passenger_id = ""
    if seat == "driver":
        passenger_id = passengers["driver"]["id"]
    else:
        passenger_id = passengers["passenger"]["id"]
    
    if not passenger_id:
        return {
            "success": True,
            "seat": seat,
            "has_profile": False,
            "message": f"{seat}座位没有绑定乘客，无法提供个性化服务"
        }
    
    # 获取记忆
    memory = _get_passenger_memory_internal(passenger_id)
    
    return {
        "success": True,
        "seat": seat,
        "has_profile": True,
        "passenger_id": passenger_id,
        "passenger_name": memory.get("passenger_name", ""),
        "memories": memory.get("memories", {})
    }


@app.get("/api/location")
async def get_current_location():
    """获取当前位置"""
    state = reload_car_state()
    return {
        "success": True,
        "current_location": {
            "name": state.vehicle.current_location_name,
            "coords": state.vehicle.current_location_coords,
            "city": state.vehicle.current_location_city
        }
    }


@app.post("/api/location")
async def set_current_location(data: SetLocationRequest):
    """设置当前位置"""
    state = reload_car_state()
    
    state.vehicle.current_location_name = data.location_name
    state.vehicle.current_location_coords = data.coords
    if data.city:
        state.vehicle.current_location_city = data.city
    
    save_car_state()
    
    # 广播位置变化
    from dataclasses import asdict
    await manager.broadcast({
        "type": "state_update",
        "component": "vehicle",
        "state": asdict(state.vehicle)
    })
    
    logger.info(f"当前位置已设置为: {data.location_name} ({data.coords})")
    
    return {
        "success": True,
        "message": f"当前位置已设置为：{data.location_name}",
        "current_location": {
            "name": data.location_name,
            "coords": data.coords,
            "city": state.vehicle.current_location_city
        }
    }


@app.get("/api/locations/presets")
async def get_preset_locations():
    """获取预设的常用地点"""
    presets = get_user_locations() or {}
    return {
        "success": True,
        "presets": presets
    }


@app.post("/api/location/geocode")
async def geocode_and_set_location(data: GeocodeLocationRequest):
    """通过地址设置当前位置（自动进行地理编码）"""
    from tools.baidu_map import baidu_geocoding
    from dataclasses import asdict
    
    try:
        # 调用百度地图地理编码API
        result = baidu_geocoding.invoke(inputs={
            "address": data.address,
            "city": data.city or "杭州"
        })
        
        if result.get("status") == 0:
            location = result.get("result", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            
            if lat and lng:
                coords = f"{lat},{lng}"
                city = data.city or "杭州"
                
                # 更新车机状态
                state = reload_car_state()
                state.vehicle.current_location_name = data.address
                state.vehicle.current_location_coords = coords
                state.vehicle.current_location_city = city
                save_car_state()
                
                # 广播位置变化
                await manager.broadcast({
                    "type": "state_update",
                    "component": "vehicle",
                    "state": asdict(state.vehicle)
                })
                
                logger.info(f"当前位置已设置为: {data.address} ({coords})")
                
                # 如果有活跃导航，重新计算导航时间
                nav_update = await recalculate_navigation_if_active(coords, city)
                if nav_update:
                    # 获取当前状态并广播导航更新（不要 reload，保持内存状态）
                    state = get_car_state()
                    await manager.broadcast({
                        "type": "state_update",
                        "component": "navigation",
                        "state": asdict(state.navigation)
                    })
                    logger.info(f"导航已更新: 前往 {nav_update['destination']} - {nav_update['distance_km']}km, {nav_update['eta_minutes']}分钟")
                
                return {
                    "success": True,
                    "message": f"当前位置已设置为：{data.address}",
                    "location_name": data.address,
                    "coords": coords,
                    "city": city,
                    "navigation_updated": nav_update is not None,
                    "navigation": nav_update
                }
            else:
                return {
                    "success": False,
                    "error": "无法获取坐标信息"
                }
        else:
            error_msg = result.get("message", "地理编码失败")
            return {
                "success": False,
                "error": f"地址解析失败: {error_msg}"
            }
    except Exception as e:
        logger.error(f"地理编码失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/location/reverse-geocode")
async def reverse_geocode_and_set_location(data: ReverseGeocodeRequest):
    """通过坐标设置当前位置（逆地理编码，用于地图点击）"""
    from tools.baidu_map import baidu_reverse_geocoding
    from dataclasses import asdict
    
    try:
        # 调用百度地图逆地理编码API
        result = baidu_reverse_geocoding.invoke(inputs={
            "location": data.coords,
            "coordtype": "bd09ll"
        })
        
        if result.get("status") == 0:
            result_data = result.get("result", {})
            formatted_address = result_data.get("formatted_address", "")
            
            # 尝试获取更简短的地址描述
            address_component = result_data.get("addressComponent", {})
            sematic_description = result_data.get("sematic_description", "")
            city = address_component.get("city", "杭州")
            
            # 优先使用语义化描述，否则使用格式化地址
            location_name = sematic_description or formatted_address or f"位置({data.coords})"
            
            # 如果地址太长，截取一部分
            if len(location_name) > 30:
                location_name = location_name[:30] + "..."
            
            # 更新车机状态（使用 get_car_state() 保持内存状态，避免重置其他状态）
            state = get_car_state()
            state.vehicle.current_location_name = location_name
            state.vehicle.current_location_coords = data.coords
            state.vehicle.current_location_city = city
            save_car_state()
            
            # 广播位置变化
            await manager.broadcast({
                "type": "state_update",
                "component": "vehicle",
                "state": asdict(state.vehicle)
            })
            
            logger.info(f"当前位置已设置为: {location_name} ({data.coords})")
            
            # 如果有活跃导航，重新计算导航时间
            nav_update = await recalculate_navigation_if_active(data.coords, city)
            if nav_update:
                # 获取当前状态并广播导航更新（不要 reload，保持内存状态）
                state = get_car_state()
                await manager.broadcast({
                    "type": "state_update",
                    "component": "navigation",
                    "state": asdict(state.navigation)
                })
                logger.info(f"导航已更新: 前往 {nav_update['destination']} - {nav_update['distance_km']}km, {nav_update['eta_minutes']}分钟")
            
            return {
                "success": True,
                "location_name": location_name,
                "coords": data.coords,
                "full_address": formatted_address,
                "navigation_updated": nav_update is not None,
                "navigation": nav_update
            }
        else:
            # 即使逆地理编码失败，也设置位置（使用 get_car_state() 保持内存状态）
            location_name = f"位置({data.coords[:20]}...)"
            
            state = get_car_state()
            state.vehicle.current_location_name = location_name
            state.vehicle.current_location_coords = data.coords
            save_car_state()
            
            # 即使地址解析失败，也尝试更新导航
            nav_update = await recalculate_navigation_if_active(data.coords, "杭州")
            if nav_update:
                # 获取当前状态（不要 reload，保持内存状态）
                state = get_car_state()
                await manager.broadcast({
                    "type": "state_update",
                    "component": "navigation",
                    "state": asdict(state.navigation)
                })
            
            return {
                "success": True,
                "location_name": location_name,
                "coords": data.coords,
                "navigation_updated": nav_update is not None,
                "navigation": nav_update
            }
    except Exception as e:
        logger.error(f"逆地理编码失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/navigation/arrive-waypoint")
async def arrive_at_waypoint():
    """到达途经点，切换到下一个途经点或目的地"""
    from tools.carTools.navigation import arrive_at_waypoint
    from dataclasses import asdict
    
    try:
        result = arrive_at_waypoint.invoke(inputs={})
        
        if result.get("success"):
            # 广播状态更新
            state = get_car_state(reload=True)
            await manager.broadcast({
                "type": "state_update",
                "component": "vehicle",
                "state": asdict(state.vehicle)
            })
            await manager.broadcast({
                "type": "state_update",
                "component": "navigation",
                "state": asdict(state.navigation)
            })
            
            logger.info(f"已到达途经点: {result.get('message', '')}")
        
        return result
    except Exception as e:
        logger.error(f"到达途经点失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/scenario/what-is-ahead")
async def what_is_ahead(file: UploadFile = File(None), question: str = Form("前面是什么车？")):
    """场景：分析前方画面（如：前面是什么车）"""
    if file:
        # 用上传的图片
        content = await file.read()
        image_base64 = base64.b64encode(content).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"
        image_data = f"data:{mime_type};base64,{image_base64}"
        
        # 同时保存到前摄像头
        _set_camera_image_internal("front", image_data)
    else:
        # 用前摄像头的图片
        cam_result = _get_camera_image_internal("front")
        if not cam_result.get("has_image"):
            return {
                "success": False,
                "error": "前摄像头没有图片，请先上传图片"
            }
        image_data = cam_result["image_data"]
    
    try:
        result = _ask_about_image_internal(image_data, question)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """启动服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="智能座舱模拟器服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    args = parser.parse_args()
    
    print(f"\n🚗 智能座舱模拟器启动中...")
    print(f"📍 访问地址: http://localhost:{args.port}")
    print(f"📡 WebSocket: ws://localhost:{args.port}/ws\n")
    
    run_server(args.host, args.port)
