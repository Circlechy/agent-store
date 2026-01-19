"""
Open Meteo 天气API工具测试用例

测试 Open Meteo 天气工具的各种功能：
- 当前天气查询
- 天气预报查询
- 地理编码（城市名称转坐标）
- 支持中文城市名称

注意：这些是集成测试，会实际调用 Open Meteo API，需要网络连接。
Open Meteo API 完全免费，无需 API Key。
"""

import pytest
import os
import sys
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入 Open Meteo 天气工具
from tools.open_meteo import (
    open_meteo_get_current_weather,
    open_meteo_get_forecast,
)


class TestOpenMeteoCurrentWeather:
    """测试当前天气查询功能"""
    
    def test_current_weather_binjiang_hangzhou(self):
        """测试查询浙江省杭州市滨江区当前天气（使用坐标：30.19, 120.21）"""
        result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.19,120.21"  # 滨江区坐标
        })
        
        print("\n=== 滨江区当前天气测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'location' in result
        assert 'temperature' in result
        assert 'weather_description' in result
        assert 'wind_speed' in result
        assert 'relative_humidity' in result
        assert result['temperature'] is not None
        assert isinstance(result['temperature'], (int, float))
        assert result['weather_description'] != ""
    
    def test_current_weather_xiaoshan_hangzhou(self):
        """测试查询浙江省杭州市萧山区当前天气（使用坐标：30.18, 120.27）"""
        result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.18,120.27"  # 萧山区坐标
        })
        
        print("\n=== 萧山区当前天气测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'location' in result
        assert 'temperature' in result
        assert 'weather_description' in result
        assert 'wind_speed' in result
        assert 'relative_humidity' in result
        assert result['temperature'] is not None
        assert isinstance(result['temperature'], (int, float))
        assert result['weather_description'] != ""
    
    def test_current_weather_binjiang_coordinates(self):
        """测试使用坐标查询滨江区天气（滨江区大致坐标：30.19, 120.21）"""
        result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.19,120.21"
        })
        
        print("\n=== 滨江区坐标天气测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'latitude' in result
        assert 'longitude' in result
        assert 'temperature' in result
        assert abs(result['latitude'] - 30.19) < 0.1  # 允许小范围误差
        assert abs(result['longitude'] - 120.21) < 0.1
    
    def test_current_weather_xiaoshan_coordinates(self):
        """测试使用坐标查询萧山区天气（萧山区大致坐标：30.18, 120.27）"""
        result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.18,120.27"
        })
        
        print("\n=== 萧山区坐标天气测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'latitude' in result
        assert 'longitude' in result
        assert 'temperature' in result
        assert abs(result['latitude'] - 30.18) < 0.1
        assert abs(result['longitude'] - 120.27) < 0.1
    
    def test_current_weather_temperature_unit(self):
        """测试温度单位参数（华氏度）"""
        result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.19,120.21",  # 使用滨江区坐标
            "temperature_unit": "fahrenheit"
        })
        
        print("\n=== 华氏度温度测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False)
        assert 'temperature' in result
        assert result['temperature'] is not None
        # 华氏度应该比摄氏度高（大约高32度以上）
        assert result['temperature'] > 32 or result['temperature'] < -40  # 合理的华氏度范围


class TestOpenMeteoForecast:
    """测试天气预报查询功能"""
    
    def test_forecast_binjiang_hangzhou(self):
        """测试查询浙江省杭州市滨江区天气预报（7天，使用坐标：30.19, 120.21）"""
        result = open_meteo_get_forecast.invoke(inputs={
            "location": "30.19,120.21",  # 滨江区坐标
            "days": 7
        })
        
        print("\n=== 滨江区7天天气预报测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'location' in result
        assert 'forecast' in result
        assert 'forecast_days' in result
        assert result['forecast_days'] == 7
        assert len(result['forecast']) == 7
        
        # 验证每一天的预报数据
        for day_forecast in result['forecast']:
            assert 'date' in day_forecast
            assert 'temperature_max' in day_forecast
            assert 'temperature_min' in day_forecast
            assert 'weather_description' in day_forecast
            assert day_forecast['temperature_max'] is not None
            assert day_forecast['temperature_min'] is not None
            assert day_forecast['temperature_max'] >= day_forecast['temperature_min']
    
    def test_forecast_xiaoshan_hangzhou(self):
        """测试查询浙江省杭州市萧山区天气预报（3天，使用坐标：30.18, 120.27）"""
        result = open_meteo_get_forecast.invoke(inputs={
            "location": "30.18,120.27",  # 萧山区坐标
            "days": 3
        })
        
        print("\n=== 萧山区3天天气预报测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False), f"查询失败: {result.get('message', '未知错误')}"
        assert 'location' in result
        assert 'forecast' in result
        assert 'forecast_days' in result
        assert result['forecast_days'] == 3
        assert len(result['forecast']) == 3
        
        # 验证每一天的预报数据
        for day_forecast in result['forecast']:
            assert 'date' in day_forecast
            assert 'temperature_max' in day_forecast
            assert 'temperature_min' in day_forecast
            assert 'weather_description' in day_forecast
    
    def test_forecast_max_days(self):
        """测试最大预报天数（16天）"""
        result = open_meteo_get_forecast.invoke(inputs={
            "location": "30.19,120.21",  # 使用滨江区坐标
            "days": 20  # 超过16天，应该被限制为16天
        })
        
        print("\n=== 最大预报天数测试结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        assert result is not None
        assert not result.get('error', False)
        assert result['forecast_days'] <= 16
        assert len(result['forecast']) <= 16


class TestOpenMeteoComparison:
    """测试滨江区和萧山区天气对比"""
    
    def test_compare_binjiang_xiaoshan_current_weather(self):
        """对比滨江区和萧山区的当前天气"""
        binjiang_result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.19,120.21"  # 滨江区坐标
        })
        
        xiaoshan_result = open_meteo_get_current_weather.invoke(inputs={
            "location": "30.18,120.27"  # 萧山区坐标
        })
        
        print("\n=== 滨江区 vs 萧山区当前天气对比 ===")
        print("滨江区:")
        print(json.dumps(binjiang_result, indent=2, ensure_ascii=False))
        print("\n萧山区:")
        print(json.dumps(xiaoshan_result, indent=2, ensure_ascii=False))
        
        assert binjiang_result is not None
        assert xiaoshan_result is not None
        assert not binjiang_result.get('error', False)
        assert not xiaoshan_result.get('error', False)
        
        # 两个区域应该都有有效的天气数据
        assert 'temperature' in binjiang_result
        assert 'temperature' in xiaoshan_result
        assert binjiang_result['temperature'] is not None
        assert xiaoshan_result['temperature'] is not None
        
        # 由于两个区域距离很近，温度差异应该不会太大（允许5度差异）
        temp_diff = abs(binjiang_result['temperature'] - xiaoshan_result['temperature'])
        assert temp_diff < 5, f"两个区域温度差异过大: {temp_diff}度"
    
    def test_compare_binjiang_xiaoshan_forecast(self):
        """对比滨江区和萧山区的天气预报"""
        binjiang_result = open_meteo_get_forecast.invoke(inputs={
            "location": "30.19,120.21",  # 滨江区坐标
            "days": 3
        })
        
        xiaoshan_result = open_meteo_get_forecast.invoke(inputs={
            "location": "30.18,120.27",  # 萧山区坐标
            "days": 3
        })
        
        print("\n=== 滨江区 vs 萧山区3天天气预报对比 ===")
        print("滨江区:")
        print(json.dumps(binjiang_result, indent=2, ensure_ascii=False))
        print("\n萧山区:")
        print(json.dumps(xiaoshan_result, indent=2, ensure_ascii=False))
        
        assert binjiang_result is not None
        assert xiaoshan_result is not None
        assert not binjiang_result.get('error', False)
        assert not xiaoshan_result.get('error', False)
        
        # 两个区域应该有相同数量的预报天数
        assert len(binjiang_result['forecast']) == len(xiaoshan_result['forecast'])
        
        # 对比每一天的最高温度（应该相近）
        for i in range(len(binjiang_result['forecast'])):
            binjiang_max = binjiang_result['forecast'][i]['temperature_max']
            xiaoshan_max = xiaoshan_result['forecast'][i]['temperature_max']
            temp_diff = abs(binjiang_max - xiaoshan_max)
            assert temp_diff < 5, f"第{i+1}天最高温度差异过大: {temp_diff}度"


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v", "-s"])
