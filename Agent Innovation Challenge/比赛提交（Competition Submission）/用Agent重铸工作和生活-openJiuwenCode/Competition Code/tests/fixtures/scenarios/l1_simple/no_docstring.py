"""缺少文档字符串的函数 - 用于测试添加 docstring"""

def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def find_max(items, key=None):
    if not items:
        return None
    if key:
        return max(items, key=key)
    return max(items)


def merge_dicts(dict1, dict2):
    result = dict1.copy()
    result.update(dict2)
    return result
