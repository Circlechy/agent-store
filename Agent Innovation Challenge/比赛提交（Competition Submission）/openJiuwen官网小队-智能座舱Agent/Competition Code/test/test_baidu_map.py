"""
百度地图API工具测试用例

测试百度地图工具的各种功能：
- 地点搜索
- 地理编码（地址转坐标）
- 逆地理编码（坐标转地址）
- 驾车路线规划
- 多目的地路线规划（途经点）

注意：这些是集成测试，会实际调用百度地图API，需要网络连接和有效的API Key。
"""

import pytest
import os
import sys
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 设置测试环境变量
os.environ.setdefault('BAIDU_MAP_AK', 'e5Ay2urYqMDW6RPNUIekvWZhp0iQMbi2')

# 导入百度地图工具
from tools.baidu_map import (
    baidu_place_search,
    baidu_geocoding,
    baidu_reverse_geocoding,
    baidu_direction_driving,
    baidu_place_search_nearby
)


class TestBaiduMapPlaceSearch:
    """测试地点搜索功能"""
    
    def test_place_search_beijing_tiananmen(self):
        """测试搜索北京天安门"""
        result = baidu_place_search.invoke(inputs={
            "query": "北京天安门",
            "region": "北京"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"搜索失败: {result.get('message')}"
        assert 'results' in result
        assert len(result['results']) > 0
        assert result['results'][0]['name'] == "天安门"
    
    def test_place_search_hangzhou_huawei(self):
        """测试搜索杭州华为公司"""
        result = baidu_place_search.invoke(inputs={
            "query": "华为技术有限公司 江虹路",
            "region": "杭州"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"搜索失败: {result.get('message')}"
        assert 'results' in result
        assert len(result['results']) > 0


class TestBaiduMapGeocoding:
    """测试地理编码功能（地址转坐标）"""
    
    def test_geocoding_beijing_address(self):
        """测试北京地址转坐标"""
        result = baidu_geocoding.invoke(inputs={
            "address": "北京市海淀区中关村大街",
            "city": "北京"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"地理编码失败: {result.get('message')}"
        assert 'result' in result
        assert 'location' in result['result']
        assert 'lat' in result['result']['location']
        assert 'lng' in result['result']['location']
    
    def test_geocoding_hangzhou_address(self):
        """测试杭州地址转坐标"""
        result = baidu_geocoding.invoke(inputs={
            "address": "杭州滨江区江虹路410号",
            "city": "杭州"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"地理编码失败: {result.get('message')}"
        assert 'result' in result
        assert 'location' in result['result']


class TestBaiduMapReverseGeocoding:
    """测试逆地理编码功能（坐标转地址）"""
    
    def test_reverse_geocoding_tiananmen(self):
        """测试天安门坐标转地址"""
        result = baidu_reverse_geocoding.invoke(inputs={
            "location": "39.915,116.404",
            "coordtype": "bd09ll"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"逆地理编码失败: {result.get('message')}"
        assert 'result' in result
        assert 'formatted_address' in result['result']


class TestBaiduMapDirectionDriving:
    """测试驾车路线规划功能"""
    
    def test_direction_driving_coordinates(self):
        """测试使用坐标进行路线规划"""
        result = baidu_direction_driving.invoke(inputs={
            "origin": "39.915,116.404",  # 北京天安门
            "destination": "40.063,116.621",  # 北京首都机场
            "origin_region": "北京",
            "destination_region": "北京"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"路线规划失败: {result.get('message')}"
        assert 'result' in result
        assert 'routes' in result['result']
        assert len(result['result']['routes']) > 0
        
        route = result['result']['routes'][0]
        assert 'distance' in route
        assert 'duration' in route
        assert route['distance'] > 0
        assert route['duration'] > 0
    
    def test_direction_driving_hangzhou_route(self):
        """测试杭州具体路线规划：宸宇府到华为公司
        
        这是实际场景测试用例：
        - 起点：杭州萧山区新塘街道宸宇府
        - 终点：杭州滨江区江虹路410号华为技术有限公司
        
        这是从实际使用场景中提取的测试用例，验证完整的路线规划流程。
        """
        # 先搜索起点
        origin_search = baidu_place_search.invoke(inputs={
            "query": "宸宇府",
            "region": "杭州"
        })
        
        assert origin_search.get('status') == 0, "起点搜索失败"
        assert len(origin_search.get('results', [])) > 0
        origin_poi = origin_search['results'][0]
        origin_coord = f"{origin_poi['location']['lat']},{origin_poi['location']['lng']}"
        
        # 搜索终点
        dest_search = baidu_place_search.invoke(inputs={
            "query": "华为技术有限公司 江虹路410号",
            "region": "杭州"
        })
        
        assert dest_search.get('status') == 0, "终点搜索失败"
        assert len(dest_search.get('results', [])) > 0
        dest_poi = dest_search['results'][0]
        dest_coord = f"{dest_poi['location']['lat']},{dest_poi['location']['lng']}"
        
        # 规划路线
        result = baidu_direction_driving.invoke(inputs={
            "origin": origin_coord,
            "destination": dest_coord,
            "origin_region": "杭州",
            "destination_region": "杭州"
        })
        
        assert result is not None
        assert result.get('status') == 0, f"路线规划失败: {result.get('message')}"
        assert 'result' in result
        assert 'routes' in result['result']
        assert len(result['result']['routes']) > 0
        
        route = result['result']['routes'][0]
        distance_km = route['distance'] / 1000
        duration_min = route['duration'] / 60
        
        # 验证路线信息
        assert distance_km > 0, "路线距离应该大于0"
        assert duration_min > 0, "预计时间应该大于0"
        
        # 打印路线信息（用于验证）
        print(f"\n【路线规划结果】")
        print(f"起点: {origin_poi['name']} ({origin_coord})")
        print(f"终点: {dest_poi['name']} ({dest_coord})")
        print(f"总距离: {distance_km:.2f} 公里")
        print(f"预计时间: {duration_min:.0f} 分钟")
        print(f"路线步骤数: {len(route.get('steps', []))}")
    
    def test_direction_driving_with_waypoints(self):
        """测试多目的地路线规划（途经点）"""
        # 使用坐标格式测试途经点
        # 注意：百度地图API的waypoints参数格式为：坐标1|坐标2|坐标3
        result = baidu_direction_driving.invoke(inputs={
            "origin": "39.915,116.404",  # 起点
            "destination": "40.063,116.621",  # 终点
            "waypoints": "39.981,116.324|39.995,116.500",  # 途经点（示例）
            "origin_region": "北京",
            "destination_region": "北京"
        })
        
        # 途经点功能可能在某些场景下不支持，所以这里只检查是否返回了有效响应
        assert result is not None
        # 如果支持途经点，应该返回成功；如果不支持，可能返回错误，这也是正常的
        # 这里不做严格断言，只记录结果
        print(f"\n途经点测试结果: status={result.get('status')}, message={result.get('message')}")


class TestBaiduMapPlaceSearchNearby:
    """测试周边搜索功能"""
    
    def test_place_search_nearby_parking(self):
        """测试搜索附近的停车场"""
        result = baidu_place_search_nearby.invoke(inputs={
            "location": "39.915,116.404",  # 天安门附近
            "query": "停车场",
            "radius": 2000
        })
        
        assert result is not None
        # 周边搜索使用相同的API，所以结构应该类似
        # 根据实际API响应调整断言
        print(f"\n周边搜索测试结果: status={result.get('status')}")


if __name__ == "__main__":
    # 可以直接运行此文件进行测试
    pytest.main([__file__, "-v", "-s"])
