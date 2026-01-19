"""
环境主动感知模块

读取环境配置文件，生成主动提醒和建议。
当配置文件中的值与实时API/车机状态冲突时，以配置文件为准。

主要功能：
1. 读取环境配置
2. 根据配置生成主动提醒
3. 提供环境状态查询工具
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

logger = logging.getLogger(__name__)

# 环境配置文件路径
ENVIRONMENT_CONFIG_FILE = Path(__file__).parent.parent.parent / "carEmu" / "environment_config.json"


@dataclass
class Alert:
    """主动提醒"""
    category: str  # safety, vehicle_critical, weather, vehicle_maintenance, road, convenience
    severity: str  # critical, warning, info, suggestion
    title: str
    message: str
    action_suggestion: str = ""
    related_tools: List[str] = field(default_factory=list)
    auto_action: bool = False  # 是否建议自动执行
    

def load_environment_config() -> Optional[Dict]:
    """加载环境配置文件"""
    if not ENVIRONMENT_CONFIG_FILE.exists():
        logger.warning(f"环境配置文件不存在: {ENVIRONMENT_CONFIG_FILE}")
        return None
    
    try:
        with open(ENVIRONMENT_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检查是否启用
        if not config.get("enabled", False):
            logger.debug("环境感知功能已禁用")
            return None
            
        return config
    except json.JSONDecodeError as e:
        logger.error(f"环境配置文件JSON解析错误: {e}")
        return None
    except Exception as e:
        logger.error(f"加载环境配置文件失败: {e}")
        return None


def _get_severity_config(config: Dict) -> Dict:
    """获取严重级别配置"""
    return config.get("alerts_config", {}).get("severity_levels", {
        "critical": {"icon": "🚨", "prefix": "紧急提醒"},
        "warning": {"icon": "⚠️", "prefix": "注意"},
        "info": {"icon": "💡", "prefix": "温馨提示"},
        "suggestion": {"icon": "🌟", "prefix": "贴心建议"}
    })


def generate_weather_alerts(config: Dict) -> List[Alert]:
    """生成天气相关提醒"""
    alerts = []
    weather = config.get("weather", {})
    
    if not weather.get("enabled", False):
        return alerts
    
    condition = weather.get("condition", "")
    temperature = weather.get("temperature", 20)
    humidity = weather.get("humidity", 50)
    wind_speed = weather.get("wind_speed", 0)
    visibility = weather.get("visibility", 10)
    aqi = weather.get("air_quality_index", 50)
    
    # 下雨天提醒
    if condition in ["rainy", "heavy_rain", "thunderstorm"]:
        severity = "warning" if condition == "rainy" else "critical"
        rain_desc = {"rainy": "正在下雨", "heavy_rain": "正在下大雨", "thunderstorm": "有雷阵雨"}
        
        alerts.append(Alert(
            category="weather",
            severity=severity,
            title="雨天行车提醒",
            message=f"外面{rain_desc.get(condition, '正在下雨')}，路面湿滑，请注意行车安全。",
            action_suggestion="已为您关闭车窗，建议开启雨刮器并保持安全车距。",
            related_tools=["close_all_windows", "get_window_state"],
            auto_action=True
        ))
    
    # 下雪天提醒
    if condition == "snowy":
        alerts.append(Alert(
            category="weather",
            severity="warning",
            title="雪天行车提醒",
            message="外面正在下雪，路面可能结冰，请谨慎驾驶。",
            action_suggestion="建议开启座椅加热，保持低速行驶，避免急刹车。",
            related_tools=["set_seat_heating", "close_all_windows"],
            auto_action=False
        ))
    
    # 大雾天气提醒
    if condition == "foggy" or visibility < 1:
        alerts.append(Alert(
            category="weather",
            severity="critical",
            title="低能见度警告",
            message=f"当前能见度仅{visibility}公里，请开启雾灯，保持安全车距。",
            action_suggestion="建议降低车速，开启雾灯和双闪。",
            related_tools=[],
            auto_action=False
        ))
    
    # 低温提醒 (低于15度建议制热)
    if temperature < 15:
        severity = "warning" if temperature < 5 else "info"
        alerts.append(Alert(
            category="weather",
            severity=severity,
            title="低温提醒",
            message=f"当前室外温度{temperature}°C，体感温度{weather.get('feels_like', temperature)}°C，建议开启空调制热。",
            action_suggestion="建议将空调调至制热模式，温度设置为22-24°C。",
            related_tools=["update_ac_state", "set_seat_heating"],
            auto_action=True
        ))
    
    # 高温提醒 (高于26度建议制冷)
    if temperature > 26:
        severity = "warning" if temperature > 35 else "info"
        alerts.append(Alert(
            category="weather",
            severity=severity,
            title="高温提醒",
            message=f"当前室外温度{temperature}°C，天气炎热，建议开启空调制冷。",
            action_suggestion="建议将空调调至制冷模式，温度设置为24-26°C。",
            related_tools=["update_ac_state", "set_seat_ventilation"],
            auto_action=True
        ))
    
    # 空气质量提醒
    if aqi > 150:
        level = "轻度污染" if aqi <= 200 else ("中度污染" if aqi <= 300 else "重度污染")
        alerts.append(Alert(
            category="weather",
            severity="warning",
            title="空气质量提醒",
            message=f"当前空气质量指数{aqi}，{level}，PM2.5: {weather.get('pm25', 'N/A')}μg/m³。",
            action_suggestion="已为您开启空气净化和内循环模式。",
            related_tools=["update_ac_state"],
            auto_action=True
        ))
    
    # 大风提醒
    if wind_speed > 30:
        alerts.append(Alert(
            category="weather",
            severity="warning",
            title="大风预警",
            message=f"当前风速{wind_speed}m/s，{weather.get('wind_direction', '')}风力较大。",
            action_suggestion="请注意横风影响，稳住方向盘，减速慢行。",
            related_tools=[],
            auto_action=False
        ))
    
    return alerts


def generate_vehicle_alerts(config: Dict) -> List[Alert]:
    """生成车辆状态相关提醒"""
    alerts = []
    vehicle = config.get("vehicle", {})
    
    if not vehicle.get("enabled", False):
        return alerts
    
    # 电池/续航提醒
    battery = vehicle.get("battery", {})
    if battery.get("enabled", False) and battery.get("low_battery_warning", False):
        level = battery.get("level_percent", 100)
        range_km = battery.get("range_km", 500)
        
        if level <= 20:
            severity = "critical" if level <= 10 else "warning"
            alerts.append(Alert(
                category="vehicle_critical",
                severity=severity,
                title="电量不足提醒",
                message=f"当前电量{level}%，剩余续航约{range_km}公里。",
                action_suggestion="建议尽快前往充电站充电，附近1.2公里处有充电站。",
                related_tools=["baidu_place_search_nearby", "start_navigation"],
                auto_action=False
            ))
    
    # 燃油提醒
    fuel = vehicle.get("fuel", {})
    if fuel.get("enabled", False) and fuel.get("low_fuel_warning", False):
        level = fuel.get("level_percent", 100)
        range_km = fuel.get("range_km", 500)
        
        if level <= 20:
            severity = "critical" if level <= 10 else "warning"
            alerts.append(Alert(
                category="vehicle_critical",
                severity=severity,
                title="油量不足提醒",
                message=f"当前油量{level}%，剩余续航约{range_km}公里。",
                action_suggestion="建议尽快前往加油站加油。",
                related_tools=["baidu_place_search_nearby", "start_navigation"],
                auto_action=False
            ))
    
    # 机油提醒
    engine_oil = vehicle.get("engine_oil", {})
    if engine_oil.get("enabled", False) and engine_oil.get("warning", False):
        quality = engine_oil.get("quality", "")
        next_change = engine_oil.get("next_change_km", 0)
        
        if quality in ["需关注", "需更换"] or next_change < 1000:
            alerts.append(Alert(
                category="vehicle_maintenance",
                severity="warning",
                title="机油更换提醒",
                message=f"机油状态：{quality}，距下次更换还剩{next_change}公里。",
                action_suggestion="建议尽快到4S店或维修站更换机油。",
                related_tools=["baidu_place_search"],
                auto_action=False
            ))
    
    # 胎压提醒
    tire = vehicle.get("tire_pressure", {})
    if tire.get("enabled", False) and tire.get("warning", False):
        min_pressure = tire.get("normal_range_min", 2.2)
        max_pressure = tire.get("normal_range_max", 2.6)
        
        warnings = []
        low_warnings = []
        tire_names = {"front_left": "左前轮", "front_right": "右前轮", 
                      "rear_left": "左后轮", "rear_right": "右后轮"}
        
        for key, name in tire_names.items():
            pressure = tire.get(key, 2.4)
            if pressure < min_pressure:
                warning_msg = f"{name}胎压过低({pressure}bar)"
                warnings.append(warning_msg)
                low_warnings.append(warning_msg)
            elif pressure > max_pressure:
                warnings.append(f"{name}胎压过高({pressure}bar)")
        
        if warnings:
            extra_note = ""
            if low_warnings:
                extra_note = "胎压偏低会增加滚动阻力，可能导致能耗上升、续航下降。"
            alert_title = "胎压异常提醒"
            if low_warnings:
                alert_title = "胎压偏低提醒（能耗上升）"
            alerts.append(Alert(
                category="vehicle_critical",
                severity="warning",
                title=alert_title,
                message=f"检测到胎压异常：{'; '.join(warnings)}。正常范围{min_pressure}-{max_pressure}bar。{extra_note}",
                action_suggestion="建议尽快到附近轮胎店检查并补充胎压，确保行车安全和能耗表现。",
                related_tools=["get_tire_pressure", "baidu_place_search_nearby"],
                auto_action=False
            ))
    
    # 玻璃水提醒
    washer = vehicle.get("washer_fluid", {})
    if washer.get("enabled", False) and washer.get("warning", False):
        level = washer.get("level_percent", 100)
        if level < 30:
            alerts.append(Alert(
                category="vehicle_maintenance",
                severity="info",
                title="玻璃水不足",
                message=f"玻璃水剩余{level}%，建议及时添加。",
                action_suggestion="下次加油时顺便添加玻璃水。",
                related_tools=[],
                auto_action=False
            ))
    
    # 车灯故障提醒
    lights = vehicle.get("lights", {})
    if lights.get("enabled", False) and lights.get("warning", False):
        faulty = []
        light_names = {
            "headlight_left": "左前大灯", "headlight_right": "右前大灯",
            "taillight_left": "左后尾灯", "taillight_right": "右后尾灯",
            "brake_light": "刹车灯", "turn_signal_left": "左转向灯", 
            "turn_signal_right": "右转向灯"
        }
        
        for key, name in light_names.items():
            if lights.get(key, "正常") == "故障":
                faulty.append(name)
        
        if faulty:
            alerts.append(Alert(
                category="vehicle_critical",
                severity="warning",
                title="车灯故障提醒",
                message=f"检测到{', '.join(faulty)}故障，可能影响夜间行车安全。",
                action_suggestion="建议尽快到维修站检修更换。",
                related_tools=["baidu_place_search"],
                auto_action=False
            ))
    
    # 保养提醒
    maintenance = vehicle.get("maintenance", {})
    if maintenance.get("enabled", False) and maintenance.get("warning", False):
        next_km = maintenance.get("next_maintenance_km", 10000)
        next_days = maintenance.get("next_maintenance_days", 365)
        items = maintenance.get("items_due", [])
        
        if next_km < 1000 or next_days < 30:
            items_str = "、".join(items) if items else "常规保养"
            alerts.append(Alert(
                category="vehicle_maintenance",
                severity="info",
                title="保养提醒",
                message=f"距下次保养还剩{next_km}公里/{next_days}天，待保养项目：{items_str}。",
                action_suggestion="建议预约4S店进行保养。",
                related_tools=["baidu_place_search"],
                auto_action=False
            ))
    
    return alerts


def generate_safety_alerts(config: Dict) -> List[Alert]:
    """生成安全相关提醒"""
    alerts = []
    safety = config.get("safety", {})
    
    if not safety.get("enabled", False):
        return alerts
    
    # 安全带提醒
    if not safety.get("seatbelt_passenger", True):
        alerts.append(Alert(
            category="safety",
            severity="critical",
            title="安全带提醒",
            message="检测到副驾驶乘客未系安全带！",
            action_suggestion="请提醒副驾驶乘客系好安全带后再出发。",
            related_tools=["speak"],
            auto_action=True
        ))
    
    # 车门未关提醒
    if safety.get("door_ajar", False):
        position = safety.get("door_ajar_position", "")
        alerts.append(Alert(
            category="safety",
            severity="critical",
            title="车门未关提醒",
            message=f"检测到{position}车门未完全关闭！",
            action_suggestion="请检查并关好车门后再行驶。",
            related_tools=["speak"],
            auto_action=True
        ))
    
    # 后备箱/引擎盖提醒
    if safety.get("trunk_open", False):
        alerts.append(Alert(
            category="safety",
            severity="warning",
            title="后备箱未关",
            message="检测到后备箱处于打开状态。",
            action_suggestion="请确认后备箱已关闭后再行驶。",
            related_tools=[],
            auto_action=False
        ))
    
    if safety.get("hood_open", False):
        alerts.append(Alert(
            category="safety",
            severity="critical",
            title="引擎盖未关",
            message="检测到引擎盖处于打开状态！",
            action_suggestion="请立即停车检查并关闭引擎盖！",
            related_tools=["speak"],
            auto_action=True
        ))
    
    return alerts


def generate_road_alerts(config: Dict) -> List[Alert]:
    """生成道路相关提醒"""
    alerts = []
    road = config.get("road_conditions", {})
    
    if not road.get("enabled", False):
        return alerts
    
    # 路面状况提醒
    surface = road.get("surface", "dry")
    if surface in ["wet", "icy", "snowy", "flooded"]:
        surface_desc = {
            "wet": "路面湿滑",
            "icy": "路面结冰",
            "snowy": "路面积雪",
            "flooded": "前方道路积水"
        }
        severity = "critical" if surface in ["icy", "flooded"] else "warning"
        
        alerts.append(Alert(
            category="road",
            severity=severity,
            title="路面状况提醒",
            message=f"{surface_desc.get(surface, '路况异常')}，请减速慢行。",
            action_suggestion="建议保持安全车距，避免急刹车。",
            related_tools=[],
            auto_action=False
        ))
    
    # 测速提醒
    if road.get("speed_camera_ahead", False):
        distance = road.get("speed_camera_distance_m", 500)
        limit = road.get("speed_limit", 60)
        alerts.append(Alert(
            category="road",
            severity="info",
            title="测速提醒",
            message=f"前方{distance}米处有测速摄像头，限速{limit}km/h。",
            action_suggestion="请注意车速。",
            related_tools=[],
            auto_action=False
        ))
    
    # 施工/事故提醒
    if road.get("construction_ahead", False):
        distance = road.get("construction_distance_km", 0)
        alerts.append(Alert(
            category="road",
            severity="warning",
            title="前方施工",
            message=f"前方{distance}公里处道路施工，可能需要绕行。",
            action_suggestion="建议重新规划路线避开施工路段。",
            related_tools=["start_navigation"],
            auto_action=False
        ))
    
    if road.get("accident_ahead", False):
        distance = road.get("accident_distance_km", 0)
        alerts.append(Alert(
            category="road",
            severity="warning",
            title="前方事故",
            message=f"前方{distance}公里处发生交通事故，可能拥堵。",
            action_suggestion="建议重新规划路线或耐心等待。",
            related_tools=["start_navigation"],
            auto_action=False
        ))
    
    # 拥堵提醒
    congestion = road.get("congestion_level", "free")
    if congestion in ["heavy", "blocked"]:
        desc = "严重拥堵" if congestion == "heavy" else "道路阻塞"
        alerts.append(Alert(
            category="road",
            severity="warning",
            title="交通拥堵提醒",
            message=f"前方道路{desc}。",
            action_suggestion="建议查看替代路线或调整出行时间。",
            related_tools=["start_navigation"],
            auto_action=False
        ))
    
    return alerts


def generate_time_context_alerts(config: Dict) -> List[Alert]:
    """生成时间上下文相关提醒"""
    alerts = []
    time_ctx = config.get("time_context", {})
    
    if not time_ctx.get("enabled", False):
        return alerts
    
    # 疲劳驾驶提醒
    driving_minutes = time_ctx.get("driving_duration_minutes", 0)
    if time_ctx.get("fatigue_warning", False) or driving_minutes > 120:
        alerts.append(Alert(
            category="safety",
            severity="warning",
            title="疲劳驾驶提醒",
            message=f"您已连续驾驶{driving_minutes}分钟，建议休息一下。",
            action_suggestion="建议到服务区休息15-20分钟，喝杯咖啡提神。",
            related_tools=["baidu_place_search_nearby", "start_navigation"],
            auto_action=False
        ))
    
    # 夜间驾驶提醒
    if time_ctx.get("is_night_driving", False):
        alerts.append(Alert(
            category="convenience",
            severity="info",
            title="夜间驾驶模式",
            message="当前为夜间行车，已为您调暗氛围灯亮度。",
            action_suggestion="注意保持精神集中，必要时开窗通风。",
            related_tools=["control_ambient_light"],
            auto_action=True
        ))
    
    return alerts


def generate_environment_alerts(config: Dict) -> List[Alert]:
    """生成周边环境相关提醒"""
    alerts = []
    env = config.get("environment", {})
    vehicle = config.get("vehicle", {})
    
    if not env.get("enabled", False):
        return alerts
    
    # 电量低 + 附近有充电站
    battery = vehicle.get("battery", {})
    if battery.get("enabled", False) and battery.get("level_percent", 100) <= 30:
        if env.get("nearby_charging_station", False):
            distance = env.get("nearest_charging_station_km", 0)
            alerts.append(Alert(
                category="convenience",
                severity="suggestion",
                title="充电站提示",
                message=f"附近{distance}公里处有充电站，需要为您导航过去吗？",
                action_suggestion="如需导航，请说「导航去充电站」。",
                related_tools=["baidu_place_search_nearby", "start_navigation"],
                auto_action=False
            ))
    
    return alerts


def generate_all_alerts() -> List[Alert]:
    """生成所有主动提醒"""
    config = load_environment_config()
    if not config:
        return []
    
    all_alerts = []
    
    # 按优先级顺序生成提醒
    all_alerts.extend(generate_safety_alerts(config))
    all_alerts.extend(generate_vehicle_alerts(config))
    all_alerts.extend(generate_weather_alerts(config))
    all_alerts.extend(generate_road_alerts(config))
    all_alerts.extend(generate_time_context_alerts(config))
    all_alerts.extend(generate_environment_alerts(config))
    
    # 按优先级排序
    priority_order = ["safety", "vehicle_critical", "weather", "vehicle_maintenance", "road", "convenience"]
    severity_order = ["critical", "warning", "info", "suggestion"]
    
    def sort_key(alert):
        cat_idx = priority_order.index(alert.category) if alert.category in priority_order else 99
        sev_idx = severity_order.index(alert.severity) if alert.severity in severity_order else 99
        return (cat_idx, sev_idx)
    
    all_alerts.sort(key=sort_key)
    
    # 限制最大提醒数量
    max_alerts = config.get("alerts_config", {}).get("max_alerts_per_session", 5)
    return all_alerts[:max_alerts]


def format_alerts_for_prompt(alerts: List[Alert]) -> str:
    """将提醒格式化为 prompt 文本"""
    if not alerts:
        return ""
    
    config = load_environment_config()
    severity_config = _get_severity_config(config) if config else {}
    
    lines = ["# 🔔 主动感知提醒（请在回复中优先告知用户）\n"]
    lines.append("以下是基于当前环境检测到的情况，请在与用户交互时主动提醒：\n")

    has_low_tire = any(
        "胎压" in alert.title and "偏低" in alert.title for alert in alerts
    )
    
    for i, alert in enumerate(alerts, 1):
        sev_info = severity_config.get(alert.severity, {"icon": "📢", "prefix": "提醒"})
        icon = sev_info.get("icon", "📢")
        prefix = sev_info.get("prefix", "提醒")
        
        lines.append(f"## {icon} {prefix}{i}：{alert.title}")
        lines.append(f"- **情况**：{alert.message}")
        if alert.action_suggestion:
            lines.append(f"- **建议**：{alert.action_suggestion}")
        if alert.auto_action:
            lines.append(f"- **自动处理**：✅ 可自动执行相关操作")
        if alert.related_tools:
            lines.append(f"- **相关工具**：{', '.join(alert.related_tools)}")
        lines.append("")
    
    lines.append("---")
    lines.append("**重要**：请根据用户的具体问题，选择性地提醒上述内容。不要一次性输出所有提醒，而是自然地融入对话中。")
    if has_low_tire:
        lines.append("**强制要求**：如果出现“胎压偏低”提醒，回复中必须明确提及“能耗上升/续航下降”的影响。")
    lines.append("")
    
    return "\n".join(lines)


def get_environment_summary() -> Dict[str, Any]:
    """获取环境状态摘要"""
    config = load_environment_config()
    if not config:
        return {"enabled": False, "message": "环境感知功能未启用或配置文件不存在"}
    
    summary = {
        "enabled": True,
        "weather": {},
        "vehicle": {},
        "road": {},
        "safety": {},
        "alerts_count": 0
    }
    
    # 天气摘要
    weather = config.get("weather", {})
    if weather.get("enabled", False):
        summary["weather"] = {
            "condition": weather.get("condition", "unknown"),
            "temperature": weather.get("temperature", 20),
            "humidity": weather.get("humidity", 50),
            "aqi": weather.get("air_quality_index", 50)
        }
    
    # 车辆摘要
    vehicle = config.get("vehicle", {})
    if vehicle.get("enabled", False):
        battery = vehicle.get("battery", {})
        tire = vehicle.get("tire_pressure", {})
        summary["vehicle"] = {
            "battery_level": battery.get("level_percent", 100) if battery.get("enabled") else None,
            "range_km": battery.get("range_km", 500) if battery.get("enabled") else None,
            "tire_pressure": {
                "front_left": tire.get("front_left", 2.4),
                "front_right": tire.get("front_right", 2.4),
                "rear_left": tire.get("rear_left", 2.4),
                "rear_right": tire.get("rear_right", 2.4)
            } if tire.get("enabled") else None
        }
    
    # 道路摘要
    road = config.get("road_conditions", {})
    if road.get("enabled", False):
        summary["road"] = {
            "surface": road.get("surface", "dry"),
            "congestion": road.get("congestion_level", "free")
        }
    
    # 安全摘要
    safety = config.get("safety", {})
    if safety.get("enabled", False):
        summary["safety"] = {
            "seatbelt_driver": safety.get("seatbelt_driver", True),
            "seatbelt_passenger": safety.get("seatbelt_passenger", True),
            "doors_closed": not safety.get("door_ajar", False)
        }
    
    # 提醒数量
    alerts = generate_all_alerts()
    summary["alerts_count"] = len(alerts)
    
    return summary


# ============ 工具函数（供Agent调用）============

@tool(name="get_environment_status",
      description="获取当前环境状态摘要，包括天气、车辆状态、道路状况、安全状态等",
      params=[])
def get_environment_status() -> Dict:
    """获取环境状态摘要"""
    return get_environment_summary()


@tool(name="get_environment_alerts", 
      description="获取当前环境的主动提醒列表，包括天气提醒、车辆状态警告、安全提示等",
      params=[])
def get_environment_alerts() -> Dict:
    """获取环境提醒列表"""
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


@tool(name="get_simulated_weather",
      description="获取模拟环境配置中的天气信息（优先级高于实时API）",
      params=[])
def get_simulated_weather() -> Dict:
    """获取模拟天气信息"""
    config = load_environment_config()
    if not config:
        return {"enabled": False, "message": "环境配置未启用"}
    
    weather = config.get("weather", {})
    if not weather.get("enabled", False):
        return {"enabled": False, "message": "天气模拟未启用"}
    
    return {
        "enabled": True,
        "condition": weather.get("condition", "unknown"),
        "temperature": weather.get("temperature", 20),
        "feels_like": weather.get("feels_like", 20),
        "humidity": weather.get("humidity", 50),
        "wind_speed": weather.get("wind_speed", 0),
        "wind_direction": weather.get("wind_direction", ""),
        "visibility_km": weather.get("visibility", 10),
        "air_quality_index": weather.get("air_quality_index", 50),
        "air_quality_level": weather.get("air_quality_level", "良"),
        "pm25": weather.get("pm25", 35),
        "forecast_today": weather.get("forecast_today", ""),
        "forecast_tomorrow": weather.get("forecast_tomorrow", "")
    }


@tool(name="get_simulated_vehicle_status",
      description="获取模拟环境配置中的车辆状态（优先级高于car_state.json）",
      params=[])
def get_simulated_vehicle_status() -> Dict:
    """获取模拟车辆状态"""
    config = load_environment_config()
    if not config:
        return {"enabled": False, "message": "环境配置未启用"}
    
    vehicle = config.get("vehicle", {})
    if not vehicle.get("enabled", False):
        return {"enabled": False, "message": "车辆状态模拟未启用"}
    
    result = {"enabled": True}
    
    # 电池
    battery = vehicle.get("battery", {})
    if battery.get("enabled"):
        result["battery"] = {
            "level_percent": battery.get("level_percent", 100),
            "range_km": battery.get("range_km", 500),
            "charging": battery.get("charging", False),
            "health_percent": battery.get("battery_health_percent", 100),
            "warning": battery.get("low_battery_warning", False)
        }
    
    # 燃油
    fuel = vehicle.get("fuel", {})
    if fuel.get("enabled"):
        result["fuel"] = {
            "level_percent": fuel.get("level_percent", 100),
            "range_km": fuel.get("range_km", 500),
            "warning": fuel.get("low_fuel_warning", False)
        }
    
    # 胎压
    tire = vehicle.get("tire_pressure", {})
    if tire.get("enabled"):
        result["tire_pressure"] = {
            "front_left": tire.get("front_left", 2.4),
            "front_right": tire.get("front_right", 2.4),
            "rear_left": tire.get("rear_left", 2.4),
            "rear_right": tire.get("rear_right", 2.4),
            "unit": tire.get("unit", "bar"),
            "warning": tire.get("warning", False)
        }
    
    # 机油
    engine_oil = vehicle.get("engine_oil", {})
    if engine_oil.get("enabled"):
        result["engine_oil"] = {
            "level_percent": engine_oil.get("level_percent", 100),
            "quality": engine_oil.get("quality", "良好"),
            "next_change_km": engine_oil.get("next_change_km", 5000),
            "warning": engine_oil.get("warning", False)
        }
    
    # 保养
    maintenance = vehicle.get("maintenance", {})
    if maintenance.get("enabled"):
        result["maintenance"] = {
            "next_km": maintenance.get("next_maintenance_km", 10000),
            "next_days": maintenance.get("next_maintenance_days", 365),
            "items_due": maintenance.get("items_due", []),
            "warning": maintenance.get("warning", False)
        }
    
    return result


def execute_auto_environment_actions() -> Dict[str, Any]:
    """
    自动执行环境联动控制
    根据环境配置自动调整空调、车窗等设置
    返回执行的操作列表
    """
    actions_taken = []
    config = load_environment_config()
    
    if not config or not config.get("enabled", False):
        return {"success": False, "message": "环境感知未启用", "actions": []}
    
    weather = config.get("weather", {})
    
    try:
        # 导入空调控制模块
        from tools.carTools.AC import update_ac_state
        from tools.carTools.window import close_all_windows
        from carEmu.car_state import get_car_state
        
        # 获取当前空调状态
        car_state = get_car_state()
        current_mode = car_state.ac.mode if car_state.ac else "cooling"
        
        if weather.get("enabled", False):
            temperature = weather.get("temperature", 20)
            condition = weather.get("condition", "")
            
            # 根据环境温度自动调整空调模式
            if temperature > 26 and current_mode == "heating":
                # 环境温度高但空调在制热 -> 切换到制冷
                target_temp = max(22, min(26, temperature - 4))
                update_ac_state.invoke(inputs={"power": True, "mode": "cooling", "target_temperature": target_temp})
                actions_taken.append(f"检测到室外{temperature}°C，已将空调切换为制冷{target_temp}°C")
                logger.info(f"环境联动：室外{temperature}°C，空调切换为制冷{target_temp}°C")
                
            elif temperature < 15 and current_mode == "cooling":
                # 环境温度低但空调在制冷 -> 切换到制热
                target_temp = max(22, min(26, 24))
                update_ac_state.invoke(inputs={"power": True, "mode": "heating", "target_temperature": target_temp})
                actions_taken.append(f"检测到室外{temperature}°C，已将空调切换为制热{target_temp}°C")
                logger.info(f"环境联动：室外{temperature}°C，空调切换为制热{target_temp}°C")
            
            # 下雨天自动关窗
            if condition in ["rainy", "heavy_rain", "thunderstorm"]:
                close_all_windows.invoke(inputs={})
                actions_taken.append("检测到下雨，已自动关闭所有车窗")
                logger.info("环境联动：下雨天自动关闭车窗")
        
        return {
            "success": True,
            "actions_count": len(actions_taken),
            "actions": actions_taken
        }
        
    except Exception as e:
        logger.error(f"执行环境联动失败: {e}")
        return {"success": False, "error": str(e), "actions": actions_taken}


def get_recommended_ac_settings() -> Dict[str, Any]:
    """
    根据环境温度获取推荐的空调设置
    """
    config = load_environment_config()
    
    if not config or not config.get("enabled", False):
        return {"has_recommendation": False}
    
    weather = config.get("weather", {})
    if not weather.get("enabled", False):
        return {"has_recommendation": False}
    
    temperature = weather.get("temperature", 20)
    humidity = weather.get("humidity", 50)
    
    # 根据环境温度推荐空调设置
    if temperature > 30:
        return {
            "has_recommendation": True,
            "recommended_mode": "cooling",
            "recommended_temperature": 24,
            "reason": f"室外温度{temperature}°C，建议制冷24°C"
        }
    elif temperature > 26:
        return {
            "has_recommendation": True,
            "recommended_mode": "cooling",
            "recommended_temperature": 25,
            "reason": f"室外温度{temperature}°C，建议制冷25°C"
        }
    elif temperature < 10:
        return {
            "has_recommendation": True,
            "recommended_mode": "heating",
            "recommended_temperature": 24,
            "reason": f"室外温度{temperature}°C，建议制热24°C"
        }
    elif temperature < 15:
        return {
            "has_recommendation": True,
            "recommended_mode": "heating",
            "recommended_temperature": 22,
            "reason": f"室外温度{temperature}°C，建议制热22°C"
        }
    else:
        return {
            "has_recommendation": True,
            "recommended_mode": "auto",
            "recommended_temperature": 24,
            "reason": f"室外温度{temperature}°C适宜，建议自动模式"
        }


if __name__ == "__main__":
    # 测试
    print("=== 环境状态摘要 ===")
    print(json.dumps(get_environment_summary(), ensure_ascii=False, indent=2))
    
    print("\n=== 主动提醒列表 ===")
    alerts = generate_all_alerts()
    for alert in alerts:
        print(f"[{alert.severity}] {alert.title}: {alert.message}")
    
    print("\n=== Prompt格式化 ===")
    print(format_alerts_for_prompt(alerts))
    
    print("\n=== 推荐空调设置 ===")
    print(json.dumps(get_recommended_ac_settings(), ensure_ascii=False, indent=2))