"""同步代码 - 用于测试转换为异步"""

import time
import requests


def fetch_user(user_id):
    """获取用户信息"""
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()


def fetch_posts(user_id):
    """获取用户帖子"""
    response = requests.get(f"https://api.example.com/users/{user_id}/posts")
    return response.json()


def fetch_user_with_posts(user_id):
    """获取用户及其帖子"""
    user = fetch_user(user_id)
    posts = fetch_posts(user_id)
    user['posts'] = posts
    return user


def process_data(data):
    """处理数据（模拟耗时操作）"""
    time.sleep(0.1)  # 模拟 IO 操作
    return {'processed': True, 'data': data}


def batch_process(items):
    """批量处理"""
    results = []
    for item in items:
        result = process_data(item)
        results.append(result)
    return results
