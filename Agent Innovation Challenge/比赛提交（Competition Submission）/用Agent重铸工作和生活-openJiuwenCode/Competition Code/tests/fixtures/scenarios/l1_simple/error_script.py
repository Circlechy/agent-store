"""会产生运行时错误的脚本 - 用于测试运行并解释错误"""

def divide_numbers(a, b):
    """除法运算"""
    return a / b


def access_list_item(items, index):
    """访问列表元素"""
    return items[index]


def parse_json_data(json_str):
    """解析 JSON 数据"""
    import json
    return json.loads(json_str)


if __name__ == "__main__":
    # 这会产生 ZeroDivisionError
    result = divide_numbers(10, 0)
    print(f"Result: {result}")
