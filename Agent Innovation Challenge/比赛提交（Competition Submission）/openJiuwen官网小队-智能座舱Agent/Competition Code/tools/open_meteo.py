import http.client
import json
import logging
from urllib.parse import quote, urlencode
from typing import Optional, Dict, Any

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

# Open Meteo API 配置（完全免费，无需 API Key）
OPEN_METEO_BASE_URL = "api.open-meteo.com"
OPEN_METEO_GEOCODING_BASE_URL = "geocoding-api.open-meteo.com"


def _make_request(path: str, params: Dict[str, Any], base_url: str = OPEN_METEO_BASE_URL) -> Dict[str, Any]:
    """发送HTTP请求到 Open Meteo API"""
    query_string = urlencode(params, safe='', quote_via=quote)
    
    conn = http.client.HTTPSConnection(base_url)
    headers = {'Accept': 'application/json'}
    
    try:
        conn.request("GET", f"{path}?{query_string}", "", headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        result = json.loads(data)
        return result
    except Exception as e:
        return {"error": True, "message": f"请求失败: {str(e)}"}
    finally:
        conn.close()


def _geocode_location(location: str) -> Optional[Dict[str, float]]:
    """通过 Open Meteo 地理编码 API 获取位置的经纬度"""
    params = {
        'name': location,
        'count': 1,
        'language': 'zh',
        'format': 'json'
    }
    
    try:
        result = _make_request("/v1/search", params, base_url=OPEN_METEO_GEOCODING_BASE_URL)
        # Open Meteo 地理编码 API 返回格式
        if result.get("results") and len(result["results"]) > 0:
            first_result = result["results"][0]
            return {
                "latitude": first_result.get("latitude"),
                "longitude": first_result.get("longitude"),
                "name": first_result.get("name", location)
            }
        # 如果没有结果，尝试检查是否有错误
        if result.get("error"):
            return None
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"地理编码失败: {str(e)}")
    return None


@tool(name="open_meteo_get_current_weather",
      description="获取指定位置的当前天气信息，包括温度、湿度、天气状况、风速等",
      params=[
        Param(name="location", description="位置名称，如：'北京'、'上海'、'New York'，或经纬度坐标如：'39.9042,116.4074'", type="str", required=True),
        Param(name="temperature_unit", description="温度单位，'celsius' 或 'fahrenheit'，默认 'celsius'", type="str", required=False),
        Param(name="wind_speed_unit", description="风速单位，'kmh'、'ms' 或 'mph'，默认 'kmh'", type="str", required=False),
      ])
def open_meteo_get_current_weather(location: str, 
                                   temperature_unit: Optional[str] = None,
                                   wind_speed_unit: Optional[str] = None) -> Dict[str, Any]:
    """获取当前天气信息"""
    # 解析经纬度坐标（如果提供）
    latitude = None
    longitude = None
    location_name = location
    
    if ',' in location:
        try:
            parts = location.split(',')
            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())
        except ValueError:
            pass
    
    # 如果没有提供坐标，则进行地理编码
    if latitude is None or longitude is None:
        geocode_result = _geocode_location(location)
        if geocode_result:
            latitude = geocode_result["latitude"]
            longitude = geocode_result["longitude"]
            location_name = geocode_result["name"]
        else:
            return {"error": True, "message": f"无法找到位置: {location}"}
    
    # 构建请求参数
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day',
        'timezone': 'auto'
    }
    
    if temperature_unit:
        params['temperature_unit'] = temperature_unit
    else:
        params['temperature_unit'] = 'celsius'
    
    if wind_speed_unit:
        params['wind_speed_unit'] = wind_speed_unit
    else:
        params['wind_speed_unit'] = 'kmh'
    
    result = _make_request("/v1/forecast", params)
    
    if result.get("error"):
        return result
    
    # 格式化返回结果
    current = result.get("current", {})
    current_units = result.get("current_units", {})
    
    # 天气代码到描述的映射
    weather_codes = {
        0: "晴朗", 1: "大部分晴朗", 2: "部分多云", 3: "阴天",
        4: "雾", 5: "毛毛雨", 6: "雨", 7: "雪", 8: "阵雨",
        9: "雷暴", 10: "冰雹", 11: "强降雨", 12: "强降雪"
    }
    
    weather_code = current.get("weather_code", 0)
    weather_desc = weather_codes.get(weather_code, "未知")
    
    return {
        "location": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "temperature": current.get("temperature_2m"),
        "temperature_unit": current_units.get("temperature_2m", "°C"),
        "relative_humidity": current.get("relative_humidity_2m"),
        "humidity_unit": current_units.get("relative_humidity_2m", "%"),
        "weather_code": weather_code,
        "weather_description": weather_desc,
        "wind_speed": current.get("wind_speed_10m"),
        "wind_speed_unit": current_units.get("wind_speed_10m", "km/h"),
        "wind_direction": current.get("wind_direction_10m"),
        "is_day": current.get("is_day", 1) == 1,
        "time": current.get("time")
    }


@tool(name="open_meteo_get_forecast",
      description="获取指定位置的天气预报信息，包括未来几天的温度、天气状况等",
      params=[
        Param(name="location", description="位置名称，如：'北京'、'上海'、'New York'，或经纬度坐标如：'39.9042,116.4074'", type="str", required=True),
        Param(name="days", description="预报天数，1-16天，默认7天", type="int", required=False),
        Param(name="temperature_unit", description="温度单位，'celsius' 或 'fahrenheit'，默认 'celsius'", type="str", required=False),
      ])
def open_meteo_get_forecast(location: str,
                            days: Optional[int] = None,
                            temperature_unit: Optional[str] = None) -> Dict[str, Any]:
    """获取天气预报信息"""
    # 解析经纬度坐标（如果提供）
    latitude = None
    longitude = None
    location_name = location
    
    if ',' in location:
        try:
            parts = location.split(',')
            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())
        except ValueError:
            pass
    
    # 如果没有提供坐标，则进行地理编码
    if latitude is None or longitude is None:
        geocode_result = _geocode_location(location)
        if geocode_result:
            latitude = geocode_result["latitude"]
            longitude = geocode_result["longitude"]
            location_name = geocode_result["name"]
        else:
            return {"error": True, "message": f"无法找到位置: {location}"}
    
    # 构建请求参数
    forecast_days = min(days or 7, 16)  # 最多16天
    
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'daily': 'temperature_2m_max,temperature_2m_min,weather_code',
        'timezone': 'auto',
        'forecast_days': forecast_days
    }
    
    if temperature_unit:
        params['temperature_unit'] = temperature_unit
    else:
        params['temperature_unit'] = 'celsius'
    
    result = _make_request("/v1/forecast", params)
    
    if result.get("error"):
        return result
    
    # 格式化返回结果
    daily = result.get("daily", {})
    daily_units = result.get("daily_units", {})
    
    # 天气代码到描述的映射
    weather_codes = {
        0: "晴朗", 1: "大部分晴朗", 2: "部分多云", 3: "阴天",
        4: "雾", 5: "毛毛雨", 6: "雨", 7: "雪", 8: "阵雨",
        9: "雷暴", 10: "冰雹", 11: "强降雨", 12: "强降雪"
    }
    
    times = daily.get("time", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    weather_codes_list = daily.get("weather_code", [])
    
    forecast_list = []
    for i in range(len(times)):
        weather_code = weather_codes_list[i] if i < len(weather_codes_list) else 0
        forecast_list.append({
            "date": times[i],
            "temperature_max": temp_max[i] if i < len(temp_max) else None,
            "temperature_min": temp_min[i] if i < len(temp_min) else None,
            "temperature_unit": daily_units.get("temperature_2m_max", "°C"),
            "weather_code": weather_code,
            "weather_description": weather_codes.get(weather_code, "未知")
        })
    
    return {
        "location": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "forecast_days": forecast_days,
        "forecast": forecast_list
    }


if __name__ == "__main__":
    # 测试当前天气
    result = open_meteo_get_current_weather.invoke(inputs={"location": "北京"})
    print("当前天气结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 测试天气预报
    result = open_meteo_get_forecast.invoke(inputs={"location": "上海", "days": 3})
    print("\n天气预报结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
