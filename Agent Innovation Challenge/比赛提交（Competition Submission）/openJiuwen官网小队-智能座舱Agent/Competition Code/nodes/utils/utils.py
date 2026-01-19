import asyncio
import logging
import os

from tools.carTools.environment import (
    generate_all_alerts,
    format_alerts_for_prompt,
    load_environment_config,
    execute_auto_environment_actions,
    get_recommended_ac_settings,
)

logger = logging.getLogger(__name__)


_LOCATION_RESOLVE_CACHE: dict[str, dict] = {}


def _resolve_location_coords(address: str) -> dict:
    if not address:
        return {}
    cached = _LOCATION_RESOLVE_CACHE.get(address)
    if cached:
        return cached
    try:
        from tools.baidu_map import baidu_geocoding
        result = baidu_geocoding.invoke(inputs={"address": address})
        if result.get("status") == 0:
            location = result.get("result", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            city = result.get("result", {}).get("city") or result.get("result", {}).get("addressComponent", {}).get("city")
            if lat is not None and lng is not None:
                resolved = {"coords": f"{lat},{lng}"}
                if city:
                    resolved["city"] = city
                _LOCATION_RESOLVE_CACHE[address] = resolved
                return resolved
    except Exception as exc:
        logger.debug(f"地理编码失败: {exc}")
    return {}


def _normalize_user_locations(raw_locations: dict) -> dict:
    normalized = {}
    for key, info in raw_locations.items():
        if isinstance(info, str):
            info = {"name": info, "address": info}
        if not isinstance(info, dict):
            continue
        entry = dict(info)
        if not entry.get("name") and entry.get("address"):
            entry["name"] = entry["address"]
        if not entry.get("address") and entry.get("name"):
            entry["address"] = entry["name"]
        if not entry.get("coords"):
            resolved = _resolve_location_coords(entry.get("address") or entry.get("name", ""))
            entry.update({k: v for k, v in resolved.items() if k not in entry or not entry.get(k)})
        normalized[key] = entry
    return normalized


def _load_locations_from_environment_config() -> dict:
    try:
        config = load_environment_config()
        if not config:
            return {}
        locations = config.get("user_locations", {})
        if not isinstance(locations, dict):
            return {}
        return _normalize_user_locations(locations)
    except Exception as exc:
        logger.debug(f"从环境感知配置读取常用地点失败: {exc}")
        return {}


def _load_locations_from_memory() -> dict:
    try:
        from carEmu.car_state import get_car_state
        state = get_car_state(reload=True)
        profile_ids = []
        if state.passengers.driver_id:
            profile_ids.append(state.passengers.driver_id)
        if state.passengers.passenger_id and state.passengers.passenger_id not in profile_ids:
            profile_ids.append(state.passengers.passenger_id)
        profile_ids.extend([pid for pid in state.passengers.profiles.keys() if pid not in profile_ids])
        for pid in profile_ids:
            profile = state.passengers.profiles.get(pid, {})
            prefs = profile.get("preferences", {}) if isinstance(profile, dict) else {}
            for key in ("locations", "user_locations", "common_locations"):
                locations = prefs.get(key)
                if isinstance(locations, dict) and locations:
                    return _normalize_user_locations(locations)
    except Exception as exc:
        logger.debug(f"从记忆读取常用地点失败: {exc}")
    return {}


def get_user_locations() -> dict:
    locations = _load_locations_from_environment_config()
    if locations:
        return locations
    return _load_locations_from_memory()


class UserLocationState:
    _current_location = None  # 格式: {"name": "公司", "coords": "30.189789,120.212428"}
    
    @classmethod
    def set_location(cls, location_name: str):
        """设置当前位置（根据常用地点名称）"""
        locations = get_user_locations()
        if location_name in locations:
            loc = locations[location_name]
            cls._current_location = {
                "name": location_name,
                "coords": loc.get("coords"),
                "address": loc.get("address", loc.get("name"))
            }
            return True
        return False
    
    @classmethod
    def get_location(cls):
        """获取当前位置"""
        return cls._current_location
    
    @classmethod
    def get_location_str(cls):
        """获取当前位置描述"""
        if cls._current_location:
            return f"当前位置：{cls._current_location['name']} ({cls._current_location.get('address', '')})"
        return "当前位置：未知（请告诉我您现在在哪里）"


def detect_location_update(query: str) -> bool:
    """检测用户是否在更新当前位置"""
    import re

    # 匹配模式：我在xxx、我现在在xxx、当前位置xxx、位置在xxx
    locations = get_user_locations()
    if not locations:
        return False
    location_names = list(locations.keys())
    if "小孩学校" in location_names and "学校" not in location_names:
        location_names.append("学校")
    escaped = [re.escape(name) for name in location_names]
    name_group = "|".join(escaped)
    patterns = [
        rf"我(?:现在)?在({name_group})",
        rf"我(?:现在)?(?:的)?位置(?:是|在)?({name_group})",
        rf"(?:当前|现在)位置(?:是|在)?({name_group})",
        rf"从({name_group})出发",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            location_name = match.group(1)
            # 处理"小孩学校"的情况
            if location_name == "学校" and "小孩学校" in locations and "学校" not in locations:
                location_name = "小孩学校"
            if UserLocationState.set_location(location_name):
                logger.info(f"检测到位置更新: {location_name}")
                return True

    return False


def _format_user_locations() -> str:
    lines = []
    locations = get_user_locations()
    for name, info in locations.items():
        line = f"- {name}: {info.get('name', '')}"
        if info.get("coords"):
            line += f" | 坐标: {info['coords']}"
        if info.get("address"):
            line += f" | 地址: {info['address']}"
        lines.append(line)
    return "\n".join(lines)


def format_user_locations_for_prompt() -> str:
    return _format_user_locations()


def get_user_location_prompt() -> str | None:
    """生成用于提示的用户位置信息"""
    lines = []
    location_str = UserLocationState.get_location_str()
    if location_str:
        lines.append(location_str)
    locations_str = _format_user_locations()
    if locations_str:
        lines.append("常用地点：\n" + locations_str)
    if not lines:
        return None
    return "关键用户信息：\n" + "\n".join(lines)


def requires_tool_call(query: str, has_image: bool = False) -> bool:
    """
    检查用户指令是否明确要求调用工具
    
    返回 True 表示需要调用工具，False 表示可能不需要
    """
    import re
    
    if has_image:
        logger.debug("检测到图片输入，需要调用视觉工具")
        return True

    # 控制操作关键词
    control_patterns = [
        r'关闭|打开|开启|关闭',  # 开关操作
        r'设置|调节|调整|调一下',  # 设置操作
        r'播放|暂停|继续|下一首',  # 媒体操作
        r'导航|路线|去.*|到.*',  # 导航操作
        r'状态|开了吗|怎么样|如何',  # 查询状态
        r'加热|通风|按摩',  # 座椅操作
        r'温度|风速|模式',  # 空调操作
        r'查询|获取|查看',  # 查询操作
        r'搜索|搜一下|查一下|查查',  # 网络搜索
        r'联网|上网|百度|谷歌|bing|tavily',  # 搜索平台/指令
        r'新闻|资讯|资料|百科|评测|对比',  # 需要外部信息
    ]
    
    query_lower = query.lower()
    for pattern in control_patterns:
        if re.search(pattern, query_lower):
            logger.debug(f"检测到需要工具调用: {query[:50]}... (匹配模式: {pattern})")
            return True
    
    return False

def extract_json_content(raw_content: str) -> str:
    if not raw_content:
        return ""
    if "```" not in raw_content:
        return raw_content.strip()
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw_content.strip()


def trim_internal_messages(messages: list, max_len: int | None = None) -> list:
    """裁剪内部消息，避免上下文爆炸"""
    if messages is None:
        return []
    if max_len is None:
        raw_value = os.getenv("MAX_INTERNAL_MESSAGES")
        try:
            max_len = int(raw_value) if raw_value is not None else 200
        except ValueError:
            max_len = 200
    if max_len <= 0:
        return messages
    if len(messages) <= max_len:
        return messages
    return messages[-max_len:]


def trim_tool_trace(messages: list, max_len: int | None = None) -> list:
    """裁剪工具调用轨迹，避免前端展示过长"""
    if messages is None:
        return []
    if max_len is None:
        raw_value = os.getenv("MAX_TOOL_TRACE")
        try:
            max_len = int(raw_value) if raw_value is not None else 200
        except ValueError:
            max_len = 200
    if max_len <= 0:
        return messages
    if len(messages) <= max_len:
        return messages
    return messages[-max_len:]

def build_environment_alerts_section() -> str:
    environment_alerts_section = ""
    auto_actions_info = ""
    try:
        env_config = load_environment_config()
        if env_config and env_config.get("enabled", False):
            auto_result = execute_auto_environment_actions()
            if auto_result.get("success") and auto_result.get("actions"):
                auto_actions_info = "\n## 🔄 已自动执行的操作\n"
                for action in auto_result["actions"]:
                    auto_actions_info += f"- {action}\n"
                logger.info(f"环境联动: 执行了 {len(auto_result['actions'])} 个自动操作")

            ac_recommendation = get_recommended_ac_settings()
            if ac_recommendation.get("has_recommendation"):
                auto_actions_info += f"\n**空调建议**: {ac_recommendation.get('reason', '')}\n"

            alerts = generate_all_alerts()
            if alerts:
                environment_alerts_section = format_alerts_for_prompt(alerts)
                if auto_actions_info:
                    environment_alerts_section = auto_actions_info + "\n" + environment_alerts_section
                logger.info(f"环境感知: 生成了 {len(alerts)} 条主动提醒")
            else:
                logger.debug("环境感知: 无需要提醒的内容")
        else:
            logger.debug("环境感知: 功能未启用")
    except Exception as e:
        logger.warning(f"生成环境感知提醒失败: {e}")

    return environment_alerts_section


def _filter_plan_for_ui(plan: list) -> list:
    if not plan:
        return []
    return [item for item in plan if item.get("node") != "end"]


async def emit_plan_update(runtime, plan: list, current_node: str | None = None):
    if runtime is None:
        return
    try:
        emitter = runtime.get_global_state("event_emitter")
    except Exception:
        emitter = None
    if not emitter:
        return
    payload = {
        "type": "plan_update",
        "plan": _filter_plan_for_ui(plan),
    }
    if current_node:
        payload["current_node"] = current_node
    try:
        result = emitter(payload)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.debug(f"Plan event emit failed: {e}")