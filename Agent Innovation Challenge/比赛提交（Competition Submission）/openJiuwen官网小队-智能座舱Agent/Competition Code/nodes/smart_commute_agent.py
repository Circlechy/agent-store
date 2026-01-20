"""
智能通勤Agent节点

这是一个真正的智能Agent，用户只需要用自然语言描述需求，
Agent会自主决定调用哪些工具来完成任务。

支持长期记忆：
- 自动记住用户偏好
- 语义搜索历史对话
- 个性化回复

示例输入：
- "导航去公司，我希望九点之前到，要先去送一下小孩上学，然后顺道去买杯瑞幸"
- "今天天气怎么样？帮我调一下空调"
- "我要去华为上班，帮我规划路线"
"""
import os
import json
import logging
import datetime
import dotenv
import uuid

from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage

from nodes.base_node import BaseNode
from prompts.template import apply_template
from tools.tool_exec import process_tool_exec
from nodes.utils.utils import (
    trim_tool_trace,
    detect_location_update,
    format_user_locations_for_prompt,
    UserLocationState,
    requires_tool_call,
)

# 导入所有可用工具
from tools.open_meteo import open_meteo_get_current_weather, open_meteo_get_forecast
from tools.carTools.AC import (
    get_ac_state,
    update_ac_state,
    set_ac_temperature,
    set_ac_mode,
    turn_on_ac,
    turn_off_ac,
)
from tools.baidu_map import (
    baidu_place_search, 
    baidu_geocoding,
    baidu_reverse_geocoding,
    baidu_place_search_nearby
)
from tools.tavily import tavily_search, tavily_extract

# 新增：车窗控制工具
from tools.carTools.window import (
    get_window_state, control_window, 
    open_all_windows, close_all_windows
)
# 新增：座椅控制工具
from tools.carTools.seat import (
    get_seat_state, control_seat,
    start_seat_massage, stop_seat_massage,
    set_seat_heating, set_seat_ventilation
)
# 新增：氛围灯控制工具
from tools.carTools.light import (
    get_ambient_light_state, control_ambient_light,
    set_ambient_light_theme, turn_on_ambient_light, turn_off_ambient_light
)
# 新增：媒体播放工具
from tools.carTools.media import (
    get_media_state, play_music, pause_music, resume_music,
    next_track, set_volume, play_radio
)
# 新增：场景联动工具
from tools.carTools.scene import (
    activate_scene, list_available_scenes, get_current_scene_state
)
# 新增：多模态视觉工具
from tools.vision_tools import (
    analyze_image, identify_location, check_parking_spot,
    read_road_sign, analyze_dashcam_frame, scan_car_interior,
    set_camera_image, analyze_camera_view,
    identify_vehicle_ahead, check_surroundings, ask_about_image,
    create_traffic_report
)
# 新增：乘客管理工具
from tools.carTools.passenger import (
    get_current_passengers, get_passenger_profile, list_all_passengers,
    create_passenger_profile, update_passenger_profile, set_seat_passenger,
    set_current_speaker, get_passenger_memory, record_passenger_action,
    get_current_speaker_info, identify_speaker_by_seat
)
# 新增：获取全部车机状态
from tools.carTools.get_all_state import _get_all_state, get_all_state
# 新增：胎压控制工具
from tools.carTools.tyres import (
    get_tire_pressure, set_tire_pressure,
    set_all_tire_pressure, reset_tire_pressure
)
# 新增：导航工具（封装百度地图，会更新车机状态和前端地图显示）
from tools.carTools.navigation import (
    start_navigation, stop_navigation, get_navigation_status,
    update_navigation_display, get_current_location, set_current_location
)
# 新增：环境主动感知工具
from tools.carTools.environment import (
    get_environment_status, get_environment_alerts,
    get_simulated_weather, get_simulated_vehicle_status,
    generate_all_alerts, format_alerts_for_prompt, load_environment_config,
    execute_auto_environment_actions, get_recommended_ac_settings
)

dotenv.load_dotenv(dotenv_path=".env")

logger = logging.getLogger(__name__)
factory = ModelFactory()
model_name = os.getenv("MODEL_NAME")
max_tool_loop = int(os.getenv("MAX_TOOL_LOOP", 15))  # 增加循环次数，让agent有足够的步骤完成复杂任务（如搜索服务区+启动导航）



class SmartCommuteAgent(BaseNode):
    """智能通勤Agent - 真正的AI Agent
    
    用户只需要用自然语言描述需求，Agent会：
    1. 理解用户意图
    2. 自主决定调用哪些工具
    3. 根据实际情况给出建议
    """
    
    def __init__(self):
        super().__init__()
        
        # 注册所有可用工具
        self.tools = [
            # 天气工具
            open_meteo_get_current_weather.get_tool_info(),
            open_meteo_get_forecast.get_tool_info(),
            # 空调工具
            get_ac_state.get_tool_info(),
            update_ac_state.get_tool_info(),
            set_ac_temperature.get_tool_info(),
            set_ac_mode.get_tool_info(),
            turn_on_ac.get_tool_info(),
            turn_off_ac.get_tool_info(),
            # 车窗工具
            get_window_state.get_tool_info(),
            control_window.get_tool_info(),
            open_all_windows.get_tool_info(),
            close_all_windows.get_tool_info(),
            # 座椅工具
            get_seat_state.get_tool_info(),
            control_seat.get_tool_info(),
            start_seat_massage.get_tool_info(),
            stop_seat_massage.get_tool_info(),
            set_seat_heating.get_tool_info(),
            set_seat_ventilation.get_tool_info(),
            # 氛围灯工具
            get_ambient_light_state.get_tool_info(),
            control_ambient_light.get_tool_info(),
            set_ambient_light_theme.get_tool_info(),
            turn_on_ambient_light.get_tool_info(),
            turn_off_ambient_light.get_tool_info(),
            # 媒体播放工具
            get_media_state.get_tool_info(),
            play_music.get_tool_info(),
            pause_music.get_tool_info(),
            resume_music.get_tool_info(),
            next_track.get_tool_info(),
            set_volume.get_tool_info(),
            play_radio.get_tool_info(),
            # 场景联动工具
            activate_scene.get_tool_info(),
            list_available_scenes.get_tool_info(),
            get_current_scene_state.get_tool_info(),
            # 导航工具（会更新前端地图显示，优先使用）
            start_navigation.get_tool_info(),
            stop_navigation.get_tool_info(),
            get_navigation_status.get_tool_info(),
            update_navigation_display.get_tool_info(),
            get_current_location.get_tool_info(),
            set_current_location.get_tool_info(),
            # 地图工具（底层API，用于地点搜索和地理编码）
            baidu_place_search.get_tool_info(),
            baidu_place_search_nearby.get_tool_info(),
            baidu_geocoding.get_tool_info(),
            baidu_reverse_geocoding.get_tool_info(),
            # 互联网搜索工具
            tavily_search.get_tool_info(),
            tavily_extract.get_tool_info(),
            # 多模态视觉工具
            analyze_image.get_tool_info(),
            identify_location.get_tool_info(),
            check_parking_spot.get_tool_info(),
            read_road_sign.get_tool_info(),
            analyze_dashcam_frame.get_tool_info(),
            scan_car_interior.get_tool_info(),
            set_camera_image.get_tool_info(),
            analyze_camera_view.get_tool_info(),
            identify_vehicle_ahead.get_tool_info(),
            check_surroundings.get_tool_info(),
            ask_about_image.get_tool_info(),
            create_traffic_report.get_tool_info(),
            # 乘客识别工具
            get_current_passengers.get_tool_info(),
            get_passenger_profile.get_tool_info(),
            list_all_passengers.get_tool_info(),
            create_passenger_profile.get_tool_info(),
            update_passenger_profile.get_tool_info(),
            set_seat_passenger.get_tool_info(),
            set_current_speaker.get_tool_info(),
            get_passenger_memory.get_tool_info(),
            record_passenger_action.get_tool_info(),
            get_current_speaker_info.get_tool_info(),
            identify_speaker_by_seat.get_tool_info(),
            # 获取全部车机状态
            get_all_state.get_tool_info(),
            # 胎压控制工具
            get_tire_pressure.get_tool_info(),
            set_tire_pressure.get_tool_info(),
            set_all_tire_pressure.get_tool_info(),
            reset_tire_pressure.get_tool_info(),
            # 环境感知工具
            get_environment_status.get_tool_info(),
            get_environment_alerts.get_tool_info(),
            get_simulated_weather.get_tool_info(),
            get_simulated_vehicle_status.get_tool_info(),
        ]
        
        self.tools_dict = {
            # 天气
            "open_meteo_get_current_weather": open_meteo_get_current_weather,
            "open_meteo_get_forecast": open_meteo_get_forecast,
            # 空调
            "get_ac_state": get_ac_state,
            "update_ac_state": update_ac_state,
            "set_ac_temperature": set_ac_temperature,
            "set_ac_mode": set_ac_mode,
            "turn_on_ac": turn_on_ac,
            "turn_off_ac": turn_off_ac,
            # 车窗
            "get_window_state": get_window_state,
            "control_window": control_window,
            "open_all_windows": open_all_windows,
            "close_all_windows": close_all_windows,
            # 座椅
            "get_seat_state": get_seat_state,
            "control_seat": control_seat,
            "start_seat_massage": start_seat_massage,
            "stop_seat_massage": stop_seat_massage,
            "set_seat_heating": set_seat_heating,
            "set_seat_ventilation": set_seat_ventilation,
            # 氛围灯
            "get_ambient_light_state": get_ambient_light_state,
            "control_ambient_light": control_ambient_light,
            "set_ambient_light_theme": set_ambient_light_theme,
            "turn_on_ambient_light": turn_on_ambient_light,
            "turn_off_ambient_light": turn_off_ambient_light,
            # 媒体
            "get_media_state": get_media_state,
            "play_music": play_music,
            "pause_music": pause_music,
            "resume_music": resume_music,
            "next_track": next_track,
            "set_volume": set_volume,
            "play_radio": play_radio,
            # 场景
            "activate_scene": activate_scene,
            "list_available_scenes": list_available_scenes,
            "get_current_scene_state": get_current_scene_state,
            # 导航
            "start_navigation": start_navigation,
            "stop_navigation": stop_navigation,
            "get_navigation_status": get_navigation_status,
            "update_navigation_display": update_navigation_display,
            "get_current_location": get_current_location,
            "set_current_location": set_current_location,
            # 地图
            "baidu_place_search": baidu_place_search,
            "baidu_place_search_nearby": baidu_place_search_nearby,
            "baidu_geocoding": baidu_geocoding,
            "baidu_reverse_geocoding": baidu_reverse_geocoding,
            # 搜索
            "tavily_search": tavily_search,
            "tavily_extract": tavily_extract,
            # 视觉
            "analyze_image": analyze_image,
            "identify_location": identify_location,
            "check_parking_spot": check_parking_spot,
            "read_road_sign": read_road_sign,
            "analyze_dashcam_frame": analyze_dashcam_frame,
            "scan_car_interior": scan_car_interior,
            "set_camera_image": set_camera_image,
            "analyze_camera_view": analyze_camera_view,
            "identify_vehicle_ahead": identify_vehicle_ahead,
            "check_surroundings": check_surroundings,
            "ask_about_image": ask_about_image,
            "create_traffic_report": create_traffic_report,
            # 乘客识别
            "get_current_passengers": get_current_passengers,
            "get_passenger_profile": get_passenger_profile,
            "list_all_passengers": list_all_passengers,
            "create_passenger_profile": create_passenger_profile,
            "update_passenger_profile": update_passenger_profile,
            "set_seat_passenger": set_seat_passenger,
            "set_current_speaker": set_current_speaker,
            "get_passenger_memory": get_passenger_memory,
            "record_passenger_action": record_passenger_action,
            "get_current_speaker_info": get_current_speaker_info,
            "identify_speaker_by_seat": identify_speaker_by_seat,
            # 获取全部车机状态
            "get_all_state": get_all_state,
            # 胎压控制
            "get_tire_pressure": get_tire_pressure,
            "set_tire_pressure": set_tire_pressure,
            "set_all_tire_pressure": set_all_tire_pressure,
            "reset_tire_pressure": reset_tire_pressure,
            # 环境感知
            "get_environment_status": get_environment_status,
            "get_environment_alerts": get_environment_alerts,
            "get_simulated_weather": get_simulated_weather,
            "get_simulated_vehicle_status": get_simulated_vehicle_status,
        }
    
    def _build_system_prompt(self, user_id: str = "default_user", long_term_memory: str = "", speaker_info: dict = None) -> str:
        """构建系统提示词，使用外置模板文件"""
        now = datetime.datetime.now()
        
        # 格式化用户常用地点（包含完整坐标信息）
        locations_str = format_user_locations_for_prompt()
        
        # 获取当前位置状态
        current_location = UserLocationState.get_location_str()
        
        # 获取当前车机状态
        current_car_state = _get_all_state()
        
        # 生成环境感知提醒
        environment_alerts_section = ""
        auto_actions_info = ""
        try:
            env_config = load_environment_config()
            if env_config and env_config.get("enabled", False):
                # 执行环境自动联动（如根据温度调整空调）
                auto_result = execute_auto_environment_actions()
                if auto_result.get("success") and auto_result.get("actions"):
                    auto_actions_info = "\n## 🔄 已自动执行的操作\n"
                    for action in auto_result["actions"]:
                        auto_actions_info += f"- {action}\n"
                    logger.info(f"环境联动: 执行了 {len(auto_result['actions'])} 个自动操作")
                
                # 获取推荐空调设置
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
        
        # 准备模板变量
        context_vars = {
            "current_time": now.strftime("%H:%M"),
            "current_date": now.strftime("%Y年%m月%d日 %A"),
            "user_id": user_id,
            "current_location": current_location,
            "long_term_memory": long_term_memory if long_term_memory else None,
            "current_car_state": current_car_state,
            "user_locations": locations_str,
        }
        
        # 使用模板系统加载 prompt
        messages = apply_template("smart_commute_agent", context_vars)
        base_prompt = messages[0]["content"] if messages else ""
        
        # 构建说话者信息部分（放在最醒目的位置）
        # 由于模板文件中没有 speaker_info 部分，我们在渲染后手动插入
        if speaker_info:
            speaker_name = speaker_info.get("name", "")
            speaker_seat = speaker_info.get("seat", "")
            logger.info(f"构建 prompt 时使用的说话者: {speaker_name} ({speaker_seat})")
            speaker_context_vars = {
                "speaker_name": speaker_name,
                "speaker_seat": speaker_seat,
            }
            speaker_messages = apply_template("speaker_info", speaker_context_vars)
            speaker_section = ""
            if isinstance(speaker_messages, list) and speaker_messages:
                speaker_section = speaker_messages[0].get("content", "")

            # 将说话者信息插入到 # Current Context 之前
            insert_marker = "# Current Context"
            if insert_marker in base_prompt and speaker_section:
                base_prompt = base_prompt.replace(insert_marker, f"{speaker_section}\n{insert_marker}")
        
        # 插入环境感知提醒（放在 Current Context 之后）
        if environment_alerts_section:
            # 找到 "# Current Car State" 或 "# User's Saved Locations" 之前插入
            insert_markers = ["# Current Car State", "# User's Saved Locations"]
            inserted = False
            for marker in insert_markers:
                if marker in base_prompt:
                    base_prompt = base_prompt.replace(marker, environment_alerts_section + "\n" + marker)
                    inserted = True
                    break
            if not inserted:
                # 如果找不到合适的位置，就追加到末尾
                base_prompt += "\n\n" + environment_alerts_section
        
        return base_prompt
    
    def _detect_location_update(self, query: str) -> bool:
        """检测用户是否在更新当前位置"""
        return detect_location_update(query)
    
    def _requires_tool_call(self, query: str, has_image: bool = False) -> bool:
        """
        检查用户指令是否明确要求调用工具
        
        返回 True 表示需要调用工具，False 表示可能不需要
        """
        return requires_tool_call(query, has_image=has_image)
    
    def _should_remember(self, query: str, result: str) -> bool:
        """
        智能判断这轮对话是否值得记忆
        
        值得记忆的内容：
        - 用户偏好（喜欢什么、常去哪里、习惯等）
        - 用户明确要求记住的信息
        - 重要个人信息（名字、生日等）
        - 重要习惯和行为模式
        
        不值得记忆的内容：
        - 一次性查询（天气、时间、导航等）
        - 简单问候
        - 工具执行结果
        """
        import re
        
        query_lower = query.lower()
        
        # 值得记忆的关键词模式
        remember_patterns = [
            r'记住|记下|记一下|别忘',  # 明确要求记忆
            r'我喜欢|我爱|我偏好|我习惯',  # 用户偏好
            r'我一般|我通常|我常常|我经常',  # 习惯
            r'我叫|我是|我的名字',  # 个人信息
            r'我的.*是|我.*叫',  # 个人属性
            r'以后.*帮我|下次.*记得',  # 未来指令
        ]
        
        # 不值得记忆的关键词模式
        skip_patterns = [
            r'^(你好|hi|hello|嗨|在吗|在不在)',  # 简单问候
            r'^(谢谢|感谢|好的|嗯|ok|行)',  # 简单回应
            r'^(天气|温度|气温|下雨|晴天).*[?？]$',  # 天气查询
            r'^(几点|时间|现在|今天).*[?？]$',  # 时间查询
            r'^(导航|路线|怎么走|怎么去)(?!.*记)',  # 纯导航请求（不包含"记"）
            r'^(查|搜|找|帮我看).*新闻',  # 一次性新闻查询
        ]
        
        # 先检查是否匹配跳过模式
        for pattern in skip_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"跳过记忆（匹配跳过模式）: {query[:30]}...")
                return False
        
        # 检查是否匹配记忆模式
        for pattern in remember_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"值得记忆（匹配记忆模式）: {query[:30]}...")
                return True
        
        # 对于其他情况，检查内容长度和复杂度
        # 较长的用户输入通常包含有价值的信息
        if len(query) > 20 and any(kw in query for kw in ['我', '喜欢', '习惯', '一般', '通常', '经常', '偏好', '爱']):
            logger.info(f"值得记忆（包含个人信息）: {query[:30]}...")
            return True
        
        # 检查 result 中是否包含确认记忆的内容（如"记住"、"我会记住"等）
        if result and len(result) > 10:
            result_lower = result.lower()
            if any(kw in result_lower for kw in ['记住', '我会', '已记录', '已保存', '下次']):
                logger.info(f"值得记忆（助手确认会记住）: {query[:30]}...")
                return True
        
        logger.debug(f"跳过记忆（默认）: {query[:30]}...")
        return False
    
    async def _do_invoke(self, inputs, runtime, context):
        """执行Agent推理"""
        
        model = factory.get_model(
            model_provider=os.getenv("MODEL_PROVIDER"),
            api_base=os.getenv("API_BASE"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=120,
        )
        
        # 获取用户查询和用户ID
        query = runtime.get_global_state("query")
        user_id = runtime.get_global_state("user_id") or "default_user"
        logger.info(f"SmartCommuteAgent 收到用户输入: {query} (用户: {user_id})")
        
        # 检测用户是否在更新位置
        self._detect_location_update(query)
        current_loc = UserLocationState.get_location()
        if current_loc:
            logger.info(f"当前位置: {current_loc['name']}")
        
        # 获取历史消息（支持多轮对话上下文）
        history_messages = runtime.get_global_state("messages") or []
        
        # 尝试获取长期记忆
        long_term_memory = ""
        enable_long_term_memory = runtime.get_global_state("enable_long_term_memory")
        # 确保 enable_long_term_memory 是明确的 True，而不是 None 或其他值
        if enable_long_term_memory is True:
            try:
                from memory.memory_manager import get_memory_manager
                memory_manager = await get_memory_manager()
                logger.info(f"开始检索长期记忆 (user_id: {user_id}, query: {query[:50]}...)")
                long_term_memory = await memory_manager.get_relevant_memories(user_id, query, top_k=20)
                if long_term_memory:
                    logger.info(f"检索到相关长期记忆:\n{long_term_memory[:200]}...")
                else:
                    logger.info("长期记忆为空（可能是首次对话或没有相关历史记录）")
            except Exception as e:
                logger.warning(f"长期记忆检索失败: {e}", exc_info=True)
        else:
            logger.debug(f"长期记忆未启用 (enable_long_term_memory={enable_long_term_memory})")
        
        # 获取说话者信息
        speaker_info = runtime.get_global_state("speaker_info")
        if speaker_info:
            # 过滤掉 avatar_base64 字段（太长，不适合打印/传递）
            speaker_info_filtered = {k: v for k, v in speaker_info.items() if k != 'avatar_base64'}
            # 递归过滤 profile 中的 avatar_base64
            if 'profile' in speaker_info_filtered and isinstance(speaker_info_filtered['profile'], dict):
                speaker_info_filtered['profile'] = {k: v for k, v in speaker_info_filtered['profile'].items() if k != 'avatar_base64'}
            logger.info(f"当前说话者: {speaker_info.get('name', '未知')} ({speaker_info.get('seat', '未知')})")
            logger.info(f"speaker_info 详细信息: {speaker_info_filtered}")
            # 使用过滤后的 speaker_info 传递给后续处理
            speaker_info = speaker_info_filtered
        else:
            logger.warning("未获取到 speaker_info，将使用默认处理")
        
        # 构建消息：系统提示 + 历史对话 + 当前用户输入
        messages = [{"role": "system", "content": self._build_system_prompt(user_id, long_term_memory, speaker_info)}]
        
        # 添加历史对话（保留工具调用上下文，这是关键修复！）
        for msg in history_messages:
            role = msg.get("role")
            
            if role == "user":
                # 保留用户消息
                if msg.get("content"):
                    messages.append({"role": "user", "content": msg["content"]})
            
            elif role == "assistant":
                # 保留 assistant 消息，包括 tool_calls（工具调用）
                assistant_msg = {"role": "assistant"}
                if msg.get("content"):
                    assistant_msg["content"] = msg["content"]
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = msg["tool_calls"]
                messages.append(assistant_msg)
            
            elif role == "tool":
                # 保留工具执行结果（这是关键！）
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id"),
                    "name": msg.get("name"),
                    "content": msg.get("content")
                }
                messages.append(tool_msg)
        
        # 添加当前用户输入（带上说话者标识）
        user_message = query
        if speaker_info:
            speaker_name = speaker_info.get("name", "")
            speaker_seat = speaker_info.get("seat", "")
            # 在用户消息前添加说话者标识，让模型更清楚是谁在说话
            user_message = f"[{speaker_seat}乘客 {speaker_name} 说]: {query}"
        messages.append({"role": "user", "content": user_message})
        
        result = None
        tool_calls_made = False  # 记录本轮是否调用了工具
        
        # Agent循环 - 让大模型自主决定调用什么工具
        for i in range(max_tool_loop):
            logger.info(f"Agent Loop: {i+1}/{max_tool_loop}")
            
            response = await model.ainvoke(
                model_name=model_name, 
                messages=messages, 
                tools=self.tools
            )
            
            # 检查是否有工具调用
            if response and response.tool_calls != []:
                tool_calls_made = True
                response_dict = response.model_dump(exclude_none=True)
                tool_names = [tc.get('function', {}).get('name', '') for tc in response_dict.get('tool_calls', [])]
                logger.info(f"Agent决定调用工具: {tool_names}")
                # 执行工具调用并将结果加入消息（传递runtime以支持current_image_data引用）
                messages = await process_tool_exec(response_dict, self.tools_dict, messages, runtime)
            else:
                # 没有工具调用，检查是否真的需要调用工具
                has_image = bool(runtime.get_global_state("current_image_data"))
                if i == 0 and self._requires_tool_call(query, has_image=has_image) and not tool_calls_made:
                    # 第一轮且需要工具调用但没有调用，强制提醒
                    logger.warning(f"⚠️ 用户指令需要工具调用，但Agent未调用工具。强制提醒...")
                    messages.append(SystemMessage(
                        content="⚠️⚠️⚠️ 重要提醒：用户指令需要调用工具才能完成！\n\n" +
                               "请按照以下步骤执行：\n" +
                               "1. 先调用对应的 get_xxx_state 工具查询当前状态\n" +
                               "2. 根据查询结果，调用相应的控制工具执行操作\n" +
                               "3. 不要直接回复'已完成'，必须通过工具调用完成操作\n\n" +
                               "4. 不要反复调用同一个工具，除非有新的信息需要查询\n\n" +
                               "这是强制要求，请立即调用工具！"
                    ).model_dump(exclude_none=True))
                    if has_image:
                        messages.append(SystemMessage(
                            content="⚠️⚠️⚠️ 重要提醒：用户输入了图片/视频，需要调用视觉工具分析当前视觉信息，再调用相应的工具执行操作。"
                        ).model_dump(exclude_none=True))
                    continue  # 继续循环，不 break
                
                # 没有工具调用，说明Agent已经完成任务
                messages.append(response.model_dump(exclude_none=True))
                result = response.model_dump(exclude_none=True).get("content", "")
                logger.info(f"Agent完成任务，共执行 {i+1} 轮")
                break
        
        # 如果循环结束还没有结果，强制生成最终回答
        if result is None:
            messages.append(SystemMessage(
                content="请根据以上信息，给用户一个完整的回答。不要再调用任何工具。"
            ).model_dump(exclude_none=True))
            response = await model.ainvoke(model_name=model_name, messages=messages)
            messages.append(response.model_dump(exclude_none=True))
            result = response.model_dump(exclude_none=True).get("content", "")
        
        # 更新历史消息（仅保留最终结果，避免上下文膨胀）
        new_history = history_messages.copy()
        new_history.append({"role": "user", "content": user_message})
        if result:
            new_history.append({"role": "assistant", "content": result})
        
        # 从 messages 中提取这一轮对话的完整信息（包括工具调用）
        # 找到当前 user_message 在 messages 中的位置
        query_idx = -1
        for idx, msg in enumerate(messages):
            if msg.get("role") == "user" and msg.get("content") == user_message:
                query_idx = idx
                break
        
        # 收集本轮工具调用轨迹，独立存储用于前端展示
        agent_name = getattr(self, "name", self.__class__.__name__)
        tool_trace = runtime.get_global_state("tool_trace") or []
        if query_idx >= 0:
            round_messages = messages[query_idx + 1:]
            for msg in round_messages:
                role = msg.get("role")
                if role == "assistant" and msg.get("tool_calls"):
                    tool_trace.append({
                        "role": "assistant",
                        "agent": agent_name,
                        "tool_calls": msg.get("tool_calls")
                    })
                elif role == "tool":
                    tool_trace.append({
                        "role": "tool",
                        "agent": agent_name,
                        "tool_call_id": msg.get("tool_call_id"),
                        "name": msg.get("name"),
                        "content": msg.get("content")
                    })
        runtime.update_global_state({"tool_trace": trim_tool_trace(tool_trace)})
        
        # 智能保存到长期记忆（只记住有价值的对话）
        if enable_long_term_memory is True:
            should_remember = self._should_remember(query, result)
            logger.debug(f"判断是否保存记忆: should_remember={should_remember}, query={query[:50]}...")
            if should_remember:
                try:
                    from memory.memory_manager import get_memory_manager
                    memory_manager = await get_memory_manager()
                    await memory_manager.add_conversation(
                        user_id=user_id,
                        messages=[
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": result}
                        ]
                    )
                    logger.info(f"✓ 已保存到长期记忆 (user_id: {user_id})")
                except Exception as e:
                    logger.warning(f"保存长期记忆失败: {e}", exc_info=True)
            else:
                logger.debug(f"跳过记忆保存（不满足记忆条件）")
        else:
            logger.debug(f"长期记忆未启用，跳过保存 (enable_long_term_memory={enable_long_term_memory})")
        
        # 保存结果和更新后的历史消息
        runtime.update_global_state({"messages": new_history})
        runtime.update_global_state({"result": result})
        
        logger.info(f"SmartCommuteAgent 完成，结果长度: {len(result)}，历史轮数: {len(new_history)//2}")
        
        return inputs
