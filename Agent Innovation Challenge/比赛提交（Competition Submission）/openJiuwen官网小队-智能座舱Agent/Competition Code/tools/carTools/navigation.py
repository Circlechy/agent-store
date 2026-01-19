"""
导航控制工具 - 控制车机导航状态并与前端UI同步

当调用百度地图路线规划后，需要使用这些工具更新车机导航状态，
前端会自动通过状态轮询显示导航信息。
"""

import logging
from typing import Optional, Dict, Any, List

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

from carEmu.car_state import get_car_state, save_car_state, sync_update_and_broadcast
from tools.baidu_map import baidu_direction_driving, baidu_place_search

logger = logging.getLogger(__name__)


def _update_navigation_state(
    active: bool = True,
    destination: str = "",
    destination_coords: str = "",
    eta_minutes: int = 0,
    distance_km: float = 0,
    current_road: str = "",
    next_turn: str = "",
    next_turn_distance: int = 0,
    waypoints: List[Dict[str, str]] = None,
    waypoints_coords: str = "",
    route_points: List[List[float]] = None
) -> Dict[str, Any]:
    """内部函数：更新导航状态"""
    state = get_car_state(reload=True)
    
    state.navigation.active = active
    if destination:
        state.navigation.destination = destination
    if destination_coords:
        state.navigation.destination_coords = destination_coords
    state.navigation.eta_minutes = eta_minutes
    state.navigation.distance_km = distance_km
    if current_road:
        state.navigation.current_road = current_road
    if next_turn:
        state.navigation.next_turn = next_turn
    state.navigation.next_turn_distance = next_turn_distance
    
    # 更新途经点
    state.navigation.waypoints = waypoints or []
    state.navigation.waypoints_coords = waypoints_coords or ""
    
    # 更新真实路线坐标点
    state.navigation.route_points = route_points or []
    
    save_car_state()
    sync_update_and_broadcast("navigation")
    
    return {
        "success": True,
        "navigation": {
            "active": state.navigation.active,
            "destination": state.navigation.destination,
            "eta_minutes": state.navigation.eta_minutes,
            "distance_km": state.navigation.distance_km,
            "current_road": state.navigation.current_road,
            "waypoints": state.navigation.waypoints,
            "waypoints_coords": state.navigation.waypoints_coords,
            # 注意：route_points 不返回给 Agent（数据太大会超出 LLM 输入限制）
            # route_points 已保存在 car_state 中，前端会通过 WebSocket 获取
            "route_points_count": len(state.navigation.route_points),
        }
    }


@tool(name="start_navigation",
      description="启动导航到指定目的地，支持设置途经点。会自动调用百度地图获取路线并在前端显示导航状态。这是启动导航的主要接口，会同时更新车机导航状态供前端显示。支持坐标格式（如'30.139,120.292'）或地址名称（如'北京首都机场'）。起点默认使用用户在前端设置的当前位置。",
      params=[
        Param(name="destination", description="目的地，可以是坐标（格式：'纬度,经度'如'30.139,120.292'）或地址名称（如'北京首都机场'）", type="str", required=True),
        Param(name="destination_name", description="目的地名称，用于在前端显示，如：'家'、'公司'、'常用地点'", type="str", required=False),
        Param(name="origin", description="起点，可以是坐标或地址。如不指定，将自动使用用户在前端设置的当前位置", type="str", required=False),
        Param(name="origin_city", description="起点所在城市，如：'杭州'", type="str", required=False),
        Param(name="destination_city", description="终点所在城市，如：'杭州'", type="str", required=False),
        Param(name="waypoints", description="途经点列表，每个元素可以是坐标字符串（如'30.149,120.273'）或包含name和coords的字典。例如: [{'name': '幼儿园', 'coords': '30.149,120.273'}]", type="list", required=False),
      ])
def start_navigation(
    destination: str,
    destination_name: Optional[str] = None,
    origin: Optional[str] = None,
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None,
    waypoints: Optional[List] = None
) -> Dict[str, Any]:
    """启动导航并更新车机状态，支持途经点"""
    
    # 获取车机状态中的当前位置
    state = get_car_state(reload=True)
    
    # 如果没有指定起点，使用车机状态中的当前位置
    if not origin:
        origin = state.vehicle.current_location_coords or "30.2741,120.1551"
        origin_city = origin_city or state.vehicle.current_location_city or "杭州"
        logger.info(f"使用当前位置作为起点: {state.vehicle.current_location_name} ({origin})")
    
    # 如果没有提供目的地名称，使用destination作为显示名称
    display_name = destination_name or destination
    # 如果destination是坐标格式，尝试简化显示
    if display_name and ',' in display_name and display_name.replace(',', '').replace('.', '').replace('-', '').isdigit():
        display_name = "目的地"  # 坐标格式时使用通用名称
    
    # 处理途经点
    waypoints_list = []  # 用于存储格式化的途经点信息
    waypoints_coords_str = ""  # 用于百度地图API的坐标字符串
    
    if waypoints:
        # 如果waypoints是字符串（JSON格式），先解析为列表
        if isinstance(waypoints, str):
            try:
                import json
                waypoints = json.loads(waypoints)
                logger.info(f"解析waypoints JSON字符串成功: {waypoints}")
            except json.JSONDecodeError as e:
                logger.warning(f"waypoints JSON解析失败: {e}, 原始值: {waypoints}")
                # 尝试作为单个坐标处理
                if ',' in waypoints and waypoints.replace(',', '').replace('.', '').replace('-', '').isdigit():
                    waypoints = [waypoints]
                else:
                    waypoints = []
        
        waypoint_coords = []
        for i, wp in enumerate(waypoints):
            if isinstance(wp, dict):
                # 格式: {"name": "xxx", "coords": "lat,lng"}
                coords = wp.get("coords", "")
                name = wp.get("name", f"途经点{i+1}")
                if coords:
                    waypoint_coords.append(coords)
                    waypoints_list.append({"name": name, "coords": coords})
            elif isinstance(wp, str):
                # 格式: "lat,lng" 或坐标字符串
                # 检查是否是有效的坐标格式
                if ',' in wp and wp.replace(',', '').replace('.', '').replace('-', '').isdigit():
                    waypoint_coords.append(wp)
                    waypoints_list.append({"name": f"途经点{i+1}", "coords": wp})
                else:
                    logger.warning(f"跳过无效的途经点坐标: {wp}")
        
        # 百度地图API的途经点格式是用 | 分隔的坐标
        waypoints_coords_str = "|".join(waypoint_coords)
        logger.info(f"设置途经点: {waypoints_list}")
    
    try:
        # 调用百度地图路线规划
        route_params = {
            "origin": origin,
            "destination": destination,
            "origin_region": origin_city or "杭州",
            "destination_region": destination_city or "杭州"
        }
        
        # 添加途经点参数
        if waypoints_coords_str:
            route_params["waypoints"] = waypoints_coords_str
        
        route_result = baidu_direction_driving.invoke(inputs=route_params)
        
        # 解析路线结果
        if route_result.get("status") == 0:
            routes = route_result.get("result", {}).get("routes", [])
            if routes:
                route = routes[0]
                distance_m = route.get("distance", 0)  # 米
                duration_s = route.get("duration", 0)  # 秒
                
                distance_km = round(distance_m / 1000, 1)
                eta_minutes = round(duration_s / 60)
                
                # 获取路线步骤
                steps = route.get("steps", [])
                current_road = ""
                next_turn = ""
                next_turn_distance = 0
                
                # 提取真实路线坐标点（用于前端绘制街道级路线）
                route_points = []
                if steps:
                    first_step = steps[0]
                    current_road = first_step.get("road_name", "")
                    if len(steps) > 1:
                        next_step = steps[1]
                        next_turn = next_step.get("instruction", "")[:50]  # 截取前50字符
                        next_turn_distance = next_step.get("distance", 0)
                    
                    # 从每个 step 的 path 中提取坐标点
                    # 百度地图 path 格式: "lng1,lat1;lng2,lat2;..." （经度,纬度）
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
                    
                    logger.info(f"提取到 {len(route_points)} 个路线坐标点")
                
                # 更新车机导航状态（包含途经点信息和真实路线坐标）
                nav_state = _update_navigation_state(
                    active=True,
                    destination=display_name,
                    destination_coords=destination if ',' in destination else "",
                    eta_minutes=eta_minutes,
                    distance_km=distance_km,
                    current_road=current_road,
                    next_turn=next_turn,
                    next_turn_distance=next_turn_distance,
                    waypoints=waypoints_list,
                    waypoints_coords=waypoints_coords_str,
                    route_points=route_points
                )
                
                # 构建返回消息
                waypoints_info = ""
                if waypoints_list:
                    waypoints_names = [wp.get("name", "途经点") for wp in waypoints_list]
                    waypoints_info = f"，途经: {' → '.join(waypoints_names)}"
                
                return {
                    "success": True,
                    "message": f"导航已启动，前往 {display_name}{waypoints_info}，全程约{distance_km}公里，预计{eta_minutes}分钟到达",
                    "route_info": {
                        "destination": display_name,
                        "distance_km": distance_km,
                        "eta_minutes": eta_minutes,
                        "current_road": current_road,
                        "steps_count": len(steps),
                        "waypoints": waypoints_list
                    },
                    "navigation_state": nav_state.get("navigation")
                }
            else:
                return {
                    "success": False,
                    "error": "未找到可用路线"
                }
        else:
            error_msg = route_result.get("message", "路线规划失败")
            return {
                "success": False,
                "error": error_msg
            }
            
    except Exception as e:
        logger.error(f"启动导航失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool(name="stop_navigation",
      description="停止当前导航，清除导航状态",
      params=[])
def stop_navigation() -> Dict[str, Any]:
    """停止导航"""
    _update_navigation_state(
        active=False,
        destination="",
        eta_minutes=0,
        distance_km=0,
        current_road="",
        next_turn="",
        next_turn_distance=0,
        waypoints=[],
        waypoints_coords=""
    )
    
    return {
        "success": True,
        "message": "导航已停止"
    }


@tool(name="get_navigation_status",
      description="获取当前导航状态",
      params=[])
def get_navigation_status() -> Dict[str, Any]:
    """获取导航状态"""
    state = get_car_state(reload=True)
    nav = state.navigation
    
    return {
        "success": True,
        "navigation": {
            "active": nav.active,
            "destination": nav.destination,
            "destination_coords": nav.destination_coords,
            "eta_minutes": nav.eta_minutes,
            "distance_km": nav.distance_km,
            "current_road": nav.current_road,
            "next_turn": nav.next_turn,
            "next_turn_distance": nav.next_turn_distance,
            "waypoints": nav.waypoints,
            "waypoints_coords": nav.waypoints_coords
        }
    }


@tool(name="update_navigation_display",
      description="手动更新导航显示信息，用于在已经获取到路线信息后更新前端显示",
      params=[
        Param(name="destination", description="目的地名称", type="str", required=True),
        Param(name="eta_minutes", description="预计到达时间（分钟）", type="int", required=True),
        Param(name="distance_km", description="距离（公里）", type="float", required=False),
        Param(name="current_road", description="当前道路名称", type="str", required=False),
      ])
def update_navigation_display(
    destination: str,
    eta_minutes: int,
    distance_km: Optional[float] = None,
    current_road: Optional[str] = None
) -> Dict[str, Any]:
    """手动更新导航显示"""
    return _update_navigation_state(
        active=True,
        destination=destination,
        eta_minutes=eta_minutes,
        distance_km=distance_km or 0,
        current_road=current_road or ""
    )


@tool(name="arrive_at_waypoint",
      description="标记已到达当前途经点，自动切换到下一个途经点或最终目的地。当用户到达某个途经点后调用此函数，系统会自动移除已完成的途经点，并重新计算到下一个途经点（或最终目的地）的路线。",
      params=[])
def arrive_at_waypoint() -> Dict[str, Any]:
    """到达途经点，切换到下一个途经点或目的地"""
    state = get_car_state(reload=True)
    nav = state.navigation
    
    # 检查是否有活跃的导航
    if not nav.active:
        return {
            "success": False,
            "error": "当前没有活跃的导航"
        }
    
    # 检查是否有途经点
    if not nav.waypoints or len(nav.waypoints) == 0:
        return {
            "success": False,
            "error": "当前导航没有途经点"
        }
    
    # 移除第一个途经点（已到达）
    completed_waypoint = nav.waypoints.pop(0)
    completed_name = completed_waypoint.get("name", "途经点")
    completed_coords = completed_waypoint.get("coords", "")
    
    # 更新当前位置为刚到达的途经点
    state.vehicle.current_location_name = completed_name
    state.vehicle.current_location_coords = completed_coords
    save_car_state()
    
    # 重新构建途经点坐标字符串
    remaining_waypoints_coords = []
    for wp in nav.waypoints:
        if wp.get("coords"):
            remaining_waypoints_coords.append(wp["coords"])
    
    nav.waypoints_coords = "|".join(remaining_waypoints_coords) if remaining_waypoints_coords else ""
    
    # 确定下一个目标
    if nav.waypoints:
        # 还有途经点，导航到下一个途经点
        next_waypoint = nav.waypoints[0]
        next_destination = next_waypoint.get("coords", "")
        next_destination_name = next_waypoint.get("name", "下一个途经点")
        
        # 重新计算路线
        try:
            route_params = {
                "origin": completed_coords,
                "destination": next_destination,
                "origin_region": state.vehicle.current_location_city or "杭州",
                "destination_region": state.vehicle.current_location_city or "杭州"
            }
            
            # 如果还有更多途经点，添加剩余的途经点
            if len(nav.waypoints) > 1:
                remaining_coords = [wp.get("coords", "") for wp in nav.waypoints[1:] if wp.get("coords")]
                if remaining_coords:
                    route_params["waypoints"] = "|".join(remaining_coords)
            
            route_result = baidu_direction_driving.invoke(inputs=route_params)
            
            if route_result.get("status") == 0:
                routes = route_result.get("result", {}).get("routes", [])
                if routes:
                    route = routes[0]
                    distance_m = route.get("distance", 0)
                    duration_s = route.get("duration", 0)
                    
                    distance_km = round(distance_m / 1000, 1)
                    eta_minutes = round(duration_s / 60)
                    
                    steps = route.get("steps", [])
                    current_road = ""
                    next_turn = ""
                    next_turn_distance = 0
                    
                    if steps:
                        first_step = steps[0]
                        current_road = first_step.get("road_name", "")
                        if len(steps) > 1:
                            next_step = steps[1]
                            next_turn = next_step.get("instruction", "")[:50]
                            next_turn_distance = next_step.get("distance", 0)
                    
                    # 更新导航状态（保持最终目的地不变）
                    nav_state = _update_navigation_state(
                        active=True,
                        destination=nav.destination,  # 保持最终目的地
                        destination_coords=nav.destination_coords,
                        eta_minutes=eta_minutes,
                        distance_km=distance_km,
                        current_road=current_road,
                        next_turn=next_turn,
                        next_turn_distance=next_turn_distance,
                        waypoints=nav.waypoints,
                        waypoints_coords=nav.waypoints_coords
                    )
                    
                    remaining_count = len(nav.waypoints)
                    return {
                        "success": True,
                        "message": f"已到达 {completed_name}，继续导航到 {next_destination_name}（还有{remaining_count}个途经点），距离{distance_km}公里，预计{eta_minutes}分钟",
                        "completed_waypoint": completed_name,
                        "next_waypoint": next_destination_name,
                        "remaining_waypoints": remaining_count,
                        "navigation_state": nav_state.get("navigation")
                    }
        except Exception as e:
            logger.error(f"重新计算导航失败: {e}")
            return {
                "success": False,
                "error": f"重新计算导航失败: {str(e)}"
            }
    else:
        # 没有途经点了，导航到最终目的地
        try:
            route_result = baidu_direction_driving.invoke(inputs={
                "origin": completed_coords,
                "destination": nav.destination_coords,
                "origin_region": state.vehicle.current_location_city or "杭州",
                "destination_region": state.vehicle.current_location_city or "杭州"
            })
            
            if route_result.get("status") == 0:
                routes = route_result.get("result", {}).get("routes", [])
                if routes:
                    route = routes[0]
                    distance_m = route.get("distance", 0)
                    duration_s = route.get("duration", 0)
                    
                    distance_km = round(distance_m / 1000, 1)
                    eta_minutes = round(duration_s / 60)
                    
                    steps = route.get("steps", [])
                    current_road = ""
                    next_turn = ""
                    next_turn_distance = 0
                    
                    if steps:
                        first_step = steps[0]
                        current_road = first_step.get("road_name", "")
                        if len(steps) > 1:
                            next_step = steps[1]
                            next_turn = next_step.get("instruction", "")[:50]
                            next_turn_distance = next_step.get("distance", 0)
                    
                    # 更新导航状态（清除途经点）
                    nav_state = _update_navigation_state(
                        active=True,
                        destination=nav.destination,
                        destination_coords=nav.destination_coords,
                        eta_minutes=eta_minutes,
                        distance_km=distance_km,
                        current_road=current_road,
                        next_turn=next_turn,
                        next_turn_distance=next_turn_distance,
                        waypoints=[],
                        waypoints_coords=""
                    )
                    
                    return {
                        "success": True,
                        "message": f"已到达 {completed_name}，所有途经点已完成，继续导航到最终目的地 {nav.destination}，距离{distance_km}公里，预计{eta_minutes}分钟",
                        "completed_waypoint": completed_name,
                        "next_waypoint": None,
                        "remaining_waypoints": 0,
                        "navigation_state": nav_state.get("navigation")
                    }
        except Exception as e:
            logger.error(f"重新计算导航失败: {e}")
            return {
                "success": False,
                "error": f"重新计算导航失败: {str(e)}"
            }
    
    return {
        "success": False,
        "error": "路线规划失败"
    }


@tool(name="get_current_location",
      description="获取用户当前位置信息（用户在前端设置的位置）",
      params=[])
def get_current_location() -> Dict[str, Any]:
    """获取当前位置"""
    state = get_car_state(reload=True)
    
    return {
        "success": True,
        "current_location": {
            "name": state.vehicle.current_location_name,
            "coords": state.vehicle.current_location_coords,
            "city": state.vehicle.current_location_city
        }
    }


@tool(name="set_current_location",
      description="设置用户当前位置（通常由前端调用，或用户语音说'我现在在公司'时使用）",
      params=[
        Param(name="location_name", description="位置名称，如：'家'、'公司'、'学校'", type="str", required=True),
        Param(name="coords", description="位置坐标，格式：'纬度,经度'，如：'30.189789,120.212428'", type="str", required=True),
        Param(name="city", description="所在城市，如：'杭州'", type="str", required=False),
      ])
def set_current_location(
    location_name: str,
    coords: str,
    city: Optional[str] = None
) -> Dict[str, Any]:
    """设置当前位置"""
    state = get_car_state(reload=True)
    
    state.vehicle.current_location_name = location_name
    state.vehicle.current_location_coords = coords
    if city:
        state.vehicle.current_location_city = city
    
    save_car_state()
    sync_update_and_broadcast("vehicle")
    
    return {
        "success": True,
        "message": f"当前位置已设置为：{location_name}",
        "current_location": {
            "name": location_name,
            "coords": coords,
            "city": state.vehicle.current_location_city
        }
    }


if __name__ == "__main__":
    # 测试
    import json
    
    # 测试设置当前位置
    set_result = set_current_location.invoke(inputs={
        "location_name": "公司",
        "coords": "30.189789,120.212428",
        "city": "杭州"
    })
    print("设置当前位置结果:")
    print(json.dumps(set_result, indent=2, ensure_ascii=False))
    
    # 测试获取当前位置
    loc_result = get_current_location.invoke(inputs={})
    print("\n当前位置:")
    print(json.dumps(loc_result, indent=2, ensure_ascii=False))
    
    # 测试启动导航
    result = start_navigation.invoke(inputs={
        "destination": "30.139311,120.292348",
        "destination_name": "家",
        "destination_city": "杭州"
    })
    print("\n启动导航结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 测试获取状态
    status = get_navigation_status.invoke(inputs={})
    print("\n导航状态:")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    # 测试停止导航
    stop_result = stop_navigation.invoke(inputs={})
    print("\n停止导航:")
    print(json.dumps(stop_result, indent=2, ensure_ascii=False))
