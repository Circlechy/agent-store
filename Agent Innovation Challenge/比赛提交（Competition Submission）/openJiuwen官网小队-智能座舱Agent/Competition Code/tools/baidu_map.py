import http.client
import json
import os
import dotenv
from urllib.parse import quote, urlencode
from typing import Optional, Dict, Any

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

dotenv.load_dotenv(dotenv_path=".env")

# 百度地图API密钥
BAIDU_MAP_AK = os.environ.get("BAIDU_MAP_AK", "e5Ay2urYqMDW6RPNUIekvWZhp0iQMbi2")
BAIDU_MAP_BASE_URL = "api.map.baidu.com"


def _make_request(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """发送HTTP请求到百度地图API"""
    params['ak'] = BAIDU_MAP_AK
    params['output'] = 'json'
    
    query_string = urlencode(params, safe='', quote_via=quote)
    
    conn = http.client.HTTPSConnection(BAIDU_MAP_BASE_URL)
    headers = {'Accept': 'application/json'}
    
    try:
        conn.request("GET", f"{path}?{query_string}", "", headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        result = json.loads(data)
        return result
    except Exception as e:
        return {"status": -1, "message": f"请求失败: {str(e)}"}
    finally:
        conn.close()


@tool(name="baidu_place_search",
      description="使用百度地图搜索地点，支持搜索POI（兴趣点）、地址、公交站等",
      params=[
        Param(name="query", description="搜索关键字，如：'北京天安门'、'上海东方明珠'", type="str", required=True),
        Param(name="region", description="搜索区域，如：'北京'、'上海'，默认为全国", type="str", required=True),
        Param(name="city_limit", description="是否限制在指定城市内搜索，true/false，默认false", type="bool", required=False),
        Param(name="page_size", description="每页返回结果数量，默认10，最多20", type="int", required=False),
        Param(name="page_num", description="页码，默认0", type="int", required=False),
      ])
def baidu_place_search(query: str, region: Optional[str] = None, 
                      city_limit: Optional[bool] = None,
                      page_size: Optional[int] = None,
                      page_num: Optional[int] = None) -> Dict[str, Any]:
    """地点检索API"""
    params = {
        'query': query,
    }
    
    if region:
        params['region'] = region
    if city_limit is not None:
        params['city_limit'] = 'true' if city_limit else 'false'
    if page_size:
        params['page_size'] = min(page_size, 20)
    if page_num is not None:
        params['page_num'] = page_num
    
    return _make_request("/place/v2/search", params)


@tool(name="baidu_direction_driving",
      description="百度地图驾车路线规划，计算两点之间的驾车路线、距离、时间等。支持途经点（waypoints）进行多目的地路线规划",
      params=[
        Param(name="origin", description="起点，格式：'纬度,经度' 或 地址，如：'39.915,116.404' 或 '北京市海淀区中关村'", type="str", required=True),
        Param(name="destination", description="终点，格式：'纬度,经度' 或 地址，如：'39.915,116.404' 或 '北京市朝阳区三里屯'", type="str", required=True),
        Param(name="waypoints", description="途经点列表，多个途经点用|分隔，如：'地点1|地点2|地点3'，用于多目的地路线规划", type="str", required=False),
        Param(name="origin_region", description="起点所在城市，如：'北京'", type="str", required=False),
        Param(name="destination_region", description="终点所在城市，如：'北京'", type="str", required=False),
        Param(name="tactics", description="路线策略，11-不走高速，12-最短时间，13-最短距离，14-避开高速，默认12", type="int", required=False),
      ])
def baidu_direction_driving(origin: str, destination: str,
                           waypoints: Optional[str] = None,
                           origin_region: Optional[str] = None,
                           destination_region: Optional[str] = None,
                           tactics: Optional[int] = None) -> Dict[str, Any]:
    """驾车路线规划API，支持途经点"""
    params = {
        'origin': origin,
        'destination': destination,
    }
    
    if waypoints:
        params['waypoints'] = waypoints
    if origin_region:
        params['origin_region'] = origin_region
    if destination_region:
        params['destination_region'] = destination_region
    if tactics:
        params['tactics'] = tactics
    
    return _make_request("/direction/v2/driving", params)




@tool(name="baidu_geocoding",
      description="百度地图地理编码，将地址转换为经纬度坐标",
      params=[
        Param(name="address", description="地址，如：'北京市海淀区中关村大街1号'", type="str", required=True),
        Param(name="city", description="地址所在城市，如：'北京'，可选", type="str", required=False),
      ])
def baidu_geocoding(address: str, city: Optional[str] = None) -> Dict[str, Any]:
    """地理编码API（地址转坐标）"""
    params = {
        'address': address,
    }
    
    if city:
        params['city'] = city
    
    return _make_request("/geocoding/v3/", params)


@tool(name="baidu_reverse_geocoding",
      description="百度地图逆地理编码，将经纬度坐标转换为地址",
      params=[
        Param(name="location", description="坐标，格式：'纬度,经度'，如：'39.915,116.404'", type="str", required=True),
        Param(name="coordtype", description="坐标类型，bd09ll-百度坐标，gcj02ll-国测局坐标，wgs84ll-GPS坐标，默认bd09ll", type="str", required=False),
        Param(name="pois", description="是否返回周边POI，0-不返回，1-返回，默认0", type="int", required=False),
      ])
def baidu_reverse_geocoding(location: str, coordtype: Optional[str] = None,
                           pois: Optional[int] = None) -> Dict[str, Any]:
    """逆地理编码API（坐标转地址）"""
    params = {
        'location': location,
    }
    
    if coordtype:
        params['coordtype'] = coordtype
    if pois is not None:
        params['pois'] = pois
    
    return _make_request("/reverse_geocoding/v3/", params)


@tool(name="baidu_place_search_nearby",
      description="百度地图周边搜索，搜索指定位置周边的POI（兴趣点），如停车场、咖啡店、学校、超市等",
      params=[
        Param(name="location", description="中心点坐标，格式：'纬度,经度'，如：'39.915,116.404'", type="str", required=True),
        Param(name="query", description="搜索关键字，如：'停车场'、'咖啡店'、'学校'、'超市'等", type="str", required=True),
        Param(name="radius", description="搜索半径，单位米，默认2000，最大50000", type="int", required=True),
        Param(name="page_size", description="每页返回结果数量，默认10，最多20", type="int", required=False),
        Param(name="page_num", description="页码，默认0", type="int", required=False),
      ])
def baidu_place_search_nearby(location: str, query: str,
                             radius: Optional[int] = None,
                             page_size: Optional[int] = None,
                             page_num: Optional[int] = None) -> Dict[str, Any]:
    """周边搜索API"""
    params = {
        'location': location,
        'query': query,
    }
    
    if radius:
        # 确保 radius 是整数（LLM 可能传入字符串）
        params['radius'] = min(int(radius), 50000)
    if page_size:
        # 确保 page_size 是整数
        params['page_size'] = min(int(page_size), 20)
    if page_num is not None:
        params['page_num'] = int(page_num)
    
    return _make_request("/place/v2/search", params)


if __name__ == "__main__":
    # 测试地点搜索
    result = baidu_place_search.invoke(inputs={"query": "北京天安门", "region": "北京"})
    print("地点搜索结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 测试单点路线规划
    result = baidu_direction_driving.invoke(inputs={
        "origin": "北京天安门",
        "destination": "北京首都机场",
        "origin_region": "北京",
        "destination_region": "北京"
    })
    print("\n驾车路线规划结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 测试多目的地路线规划（途经点）
    result = baidu_direction_driving.invoke(inputs={
        "origin": "家",
        "destination": "公司",
        "waypoints": "学校|咖啡店",
        "origin_region": "北京",
        "destination_region": "北京"
    })
    print("\n多目的地路线规划结果（途经点）:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
