"""缺少错误处理的代码 - 用于测试添加错误处理"""

import json


def read_json_file(filepath):
    """读取 JSON 文件"""
    with open(filepath, 'r') as f:
        return json.load(f)


def parse_user_input(input_str):
    """解析用户输入"""
    parts = input_str.split(':')
    return {
        'name': parts[0],
        'age': int(parts[1]),
        'email': parts[2]
    }


def divide_values(a, b):
    """除法运算"""
    return a / b


def get_nested_value(data, keys):
    """获取嵌套字典的值"""
    result = data
    for key in keys:
        result = result[key]
    return result


def fetch_url_content(url):
    """获取 URL 内容"""
    import urllib.request
    response = urllib.request.urlopen(url)
    return response.read().decode('utf-8')
