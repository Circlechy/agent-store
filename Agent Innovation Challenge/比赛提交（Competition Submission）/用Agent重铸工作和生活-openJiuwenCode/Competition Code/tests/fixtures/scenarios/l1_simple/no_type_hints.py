"""缺少类型注解的函数 - 用于测试添加类型提示"""

def add_numbers(a, b):
    return a + b


def filter_positive(numbers):
    return [n for n in numbers if n > 0]


def get_user_info(user_id, include_email=False):
    user = {"id": user_id, "name": f"User_{user_id}"}
    if include_email:
        user["email"] = f"user_{user_id}@example.com"
    return user


def process_items(items, transformer=None):
    if transformer is None:
        return items
    return [transformer(item) for item in items]
