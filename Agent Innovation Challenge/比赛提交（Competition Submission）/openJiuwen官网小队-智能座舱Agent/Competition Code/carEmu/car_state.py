"""
车机模拟器 - 统一状态管理

提供所有车机设备的状态管理和WebSocket广播功能
"""

import json
import asyncio
import threading
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 状态文件路径
STATE_FILE = Path(__file__).parent / "car_state.json"

# WebSocket广播回调列表（用于实时推送状态变化到UI）
_broadcast_callbacks: List[Callable] = []

# 用于存储主事件循环的引用（由服务器设置）
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None
_main_event_loop_lock = threading.Lock()


def register_broadcast_callback(callback: Callable):
    """注册广播回调函数"""
    _broadcast_callbacks.append(callback)
    # 尝试保存主事件循环的引用
    global _main_event_loop
    try:
        loop = asyncio.get_running_loop()
        with _main_event_loop_lock:
            _main_event_loop = loop
    except RuntimeError:
        pass  # 不在事件循环中，忽略


def unregister_broadcast_callback(callback: Callable):
    """取消注册广播回调函数"""
    if callback in _broadcast_callbacks:
        _broadcast_callbacks.remove(callback)


async def broadcast_state_change(component: str, state: dict):
    """广播状态变化到所有注册的回调"""
    message = {
        "type": "state_update",
        "component": component,
        "state": state,
        "timestamp": datetime.now().isoformat()
    }
    for callback in _broadcast_callbacks:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error(f"广播回调执行失败: {e}")


@dataclass
class ACState:
    """空调状态"""
    power: bool = True
    temperature: int = 24
    mode: str = "auto"  # cool, heat, auto, fan
    fan_speed: int = 2  # 0-5
    internal_circulation: bool = False
    air_purification: bool = False
    seat_heating: Dict[str, bool] = field(default_factory=lambda: {"driver": False, "passenger": False})
    seat_ventilation: Dict[str, bool] = field(default_factory=lambda: {"driver": False, "passenger": False})


@dataclass
class WindowState:
    """车窗状态 (0=关闭, 100=全开)"""
    front_left: int = 0
    front_right: int = 0
    rear_left: int = 0
    rear_right: int = 0
    sunroof: int = 0  # 天窗


@dataclass
class SeatState:
    """座椅状态"""
    driver_position: int = 50  # 0-100 位置
    driver_backrest: int = 70  # 0-100 靠背角度
    driver_heating: int = 0  # 0-3 加热档位
    driver_ventilation: int = 0  # 0-3 通风档位
    driver_massage: bool = False
    driver_massage_mode: str = "wave"  # wave, pulse, knead
    
    passenger_position: int = 50
    passenger_backrest: int = 70
    passenger_heating: int = 0
    passenger_ventilation: int = 0
    passenger_massage: bool = False
    passenger_massage_mode: str = "wave"


@dataclass
class LightState:
    """氛围灯状态"""
    power: bool = False
    color: str = "#0066ff"  # 十六进制颜色
    brightness: int = 50  # 0-100
    mode: str = "static"  # static, breathing, rhythm


@dataclass
class MediaState:
    """媒体播放状态"""
    playing: bool = False
    source: str = "bluetooth"  # bluetooth, radio, usb, online
    track_name: str = ""
    track_artist: str = ""
    track_album: str = ""
    track_duration: int = 0  # 秒
    track_position: int = 0  # 秒
    volume: int = 50  # 0-100
    radio_frequency: float = 99.6  # FM频率


@dataclass
class VehicleState:
    """车辆状态"""
    battery_level: int = 80  # 电量百分比
    range_km: int = 320  # 续航里程
    tire_pressure: List[float] = field(default_factory=lambda: [2.4, 2.4, 2.4, 2.4])  # 四轮胎压
    odometer: int = 12580  # 总里程
    speed: int = 0  # 当前速度
    gear: str = "P"  # P, R, N, D
    # 当前位置信息
    current_location_name: str = "公司"  # 当前位置名称
    current_location_coords: str = "30.189789,120.212428"  # 当前位置坐标（纬度,经度）
    current_location_city: str = "杭州"  # 当前所在城市


@dataclass
class NavigationState:
    """导航状态"""
    active: bool = False
    destination: str = ""
    destination_coords: str = ""
    eta_minutes: int = 0
    distance_km: float = 0
    current_road: str = ""
    next_turn: str = ""
    next_turn_distance: int = 0  # 米
    # 途经点支持
    waypoints: List[Dict[str, str]] = field(default_factory=list)  # [{"name": "xxx", "coords": "lat,lng"}, ...]
    waypoints_coords: str = ""  # 途经点坐标字符串，用于百度地图API（格式: "lat1,lng1|lat2,lng2"）
    # 真实路线坐标点（用于前端绑定街道级路线）
    route_points: List[List[float]] = field(default_factory=list)  # [[lat1, lng1], [lat2, lng2], ...]


@dataclass
class PassengerProfile:
    """乘客档案"""
    id: str = ""  # 唯一标识
    name: str = ""  # 姓名
    avatar_base64: str = ""  # 头像base64（用于人脸识别）
    preferences: Dict[str, Any] = field(default_factory=dict)  # 偏好设置
    # 个性化记忆
    last_played_music: str = ""  # 上次播放的音乐
    last_played_video: str = ""  # 上次播放的视频
    last_destination: str = ""  # 上次导航目的地
    favorite_temperature: int = 24  # 偏好温度
    favorite_seat_position: int = 50  # 偏好座椅位置
    history: List[Dict[str, Any]] = field(default_factory=list)  # 操作历史


@dataclass
class PassengerState:
    """当前乘客状态"""
    driver_id: str = ""  # 当前主驾乘客ID
    driver_name: str = ""  # 当前主驾姓名
    passenger_id: str = ""  # 当前副驾乘客ID
    passenger_name: str = ""  # 当前副驾姓名
    current_speaker: str = ""  # 当前说话者: "driver" / "passenger" / ""
    profiles: Dict[str, Dict] = field(default_factory=dict)  # 所有乘客档案 {id: profile_dict}


@dataclass
class CameraState:
    """摄像头模拟状态 - 用于多模态交互"""
    front_camera_image: str = ""  # 前摄像头图片（base64或路径）
    rear_camera_image: str = ""  # 后摄像头图片
    interior_camera_image: str = ""  # 车内摄像头图片
    left_camera_image: str = ""  # 左侧摄像头
    right_camera_image: str = ""  # 右侧摄像头
    last_updated: str = ""  # 最后更新时间


@dataclass 
class CarState:
    """完整车机状态"""
    ac: ACState = field(default_factory=ACState)
    windows: WindowState = field(default_factory=WindowState)
    seats: SeatState = field(default_factory=SeatState)
    lights: LightState = field(default_factory=LightState)
    media: MediaState = field(default_factory=MediaState)
    vehicle: VehicleState = field(default_factory=VehicleState)
    navigation: NavigationState = field(default_factory=NavigationState)
    passengers: PassengerState = field(default_factory=PassengerState)
    cameras: CameraState = field(default_factory=CameraState)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "ac": asdict(self.ac),
            "windows": asdict(self.windows),
            "seats": asdict(self.seats),
            "lights": asdict(self.lights),
            "media": asdict(self.media),
            "vehicle": asdict(self.vehicle),
            "navigation": asdict(self.navigation),
            "passengers": asdict(self.passengers),
            "cameras": asdict(self.cameras)
        }
    
    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CarState':
        """从字典创建"""
        state = cls()
        
        if "ac" in data:
            state.ac = ACState(**data["ac"])
        if "windows" in data:
            state.windows = WindowState(**data["windows"])
        if "seats" in data:
            state.seats = SeatState(**data["seats"])
        if "lights" in data:
            state.lights = LightState(**data["lights"])
        if "media" in data:
            state.media = MediaState(**data["media"])
        if "vehicle" in data:
            state.vehicle = VehicleState(**data["vehicle"])
        if "navigation" in data:
            state.navigation = NavigationState(**data["navigation"])
        if "passengers" in data:
            state.passengers = PassengerState(**data["passengers"])
        if "cameras" in data:
            state.cameras = CameraState(**data["cameras"])
        
        return state
    
    @classmethod
    def load(cls) -> 'CarState':
        """从文件加载状态"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except Exception as e:
                logger.warning(f"加载车机状态失败，使用默认值: {e}")
        return cls()
    
    def save(self):
        """保存状态到文件"""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


# 全局单例
_car_state: Optional[CarState] = None


def get_car_state(reload: bool = False) -> CarState:
    """获取车机状态
    
    Args:
        reload: 是否强制从文件重新加载（用于跨进程同步）
    """
    global _car_state
    if _car_state is None or reload:
        _car_state = CarState.load()
    return _car_state


def reload_car_state() -> CarState:
    """强制从文件重新加载状态（用于检测外部修改）"""
    return get_car_state(reload=True)


def save_car_state():
    """保存车机状态"""
    if _car_state:
        _car_state.save()


async def update_and_broadcast(component: str):
    """更新状态并广播变化（异步版本）"""
    state = get_car_state()
    save_car_state()
    
    # 获取对应组件的状态
    component_state = getattr(state, component, None)
    if component_state:
        await broadcast_state_change(component, asdict(component_state))


def sync_update_and_broadcast(component: str):
    """更新状态并广播变化（同步版本，用于同步工具函数）"""
    state = get_car_state()
    save_car_state()
    
    # 获取对应组件的状态
    component_state = getattr(state, component, None)
    if component_state:
        state_dict = asdict(component_state)
        
        # 在同步函数中运行异步广播
        # 优先使用保存的主事件循环引用
        with _main_event_loop_lock:
            main_loop = _main_event_loop
        
        if main_loop is not None and main_loop.is_running():
            # 使用主事件循环，线程安全地调度任务
            try:
                future = asyncio.run_coroutine_threadsafe(
                    broadcast_state_change(component, state_dict),
                    main_loop
                )
                # 不等待完成，让任务在后台执行
            except Exception as e:
                logger.warning(f"使用主事件循环广播失败 {component}: {e}")
                main_loop = None
        
        # 如果主事件循环不可用，尝试其他方式
        if main_loop is None:
            try:
                # 尝试获取当前线程的事件循环
                try:
                    loop = asyncio.get_running_loop()
                    # 如果成功，说明在异步上下文中，创建任务
                    task = loop.create_task(broadcast_state_change(component, state_dict))
                except RuntimeError:
                    # 没有运行的事件循环，尝试获取事件循环（可能未运行）
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，创建任务
                        task = loop.create_task(broadcast_state_change(component, state_dict))
                    else:
                        # 如果事件循环未运行，直接运行
                        loop.run_until_complete(broadcast_state_change(component, state_dict))
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                try:
                    asyncio.run(broadcast_state_change(component, state_dict))
                except RuntimeError as e:
                    # 如果所有方式都失败，记录错误但不阻塞
                    # 状态已经保存到文件，前端可以通过轮询获取更新
                    logger.warning(f"无法广播状态变化 {component}: {e}。状态已保存到文件，前端将通过轮询获取更新。")


# 便捷函数：获取各组件状态
def get_ac() -> ACState:
    return get_car_state().ac

def get_windows() -> WindowState:
    return get_car_state().windows

def get_seats() -> SeatState:
    return get_car_state().seats

def get_lights() -> LightState:
    return get_car_state().lights

def get_media() -> MediaState:
    return get_car_state().media

def get_vehicle() -> VehicleState:
    return get_car_state().vehicle

def get_navigation() -> NavigationState:
    return get_car_state().navigation

def get_passengers() -> PassengerState:
    return get_car_state().passengers

def get_cameras() -> CameraState:
    return get_car_state().cameras


if __name__ == "__main__":
    # 测试
    state = get_car_state()
    print("当前车机状态:")
    print(state.to_json())
    
    # 修改并保存
    state.ac.temperature = 22
    state.lights.power = True
    state.lights.color = "#ff6600"
    save_car_state()
    
    print("\n修改后:")
    print(state.to_json())
