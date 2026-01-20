"""有 Bug 的计算器模块"""

def calculate_total(items, tax_rate=0.1):
    """计算总价（含税）

    Bug: 税率计算错误，应该是 subtotal * (1 + tax_rate)
    """
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    # Bug: 这里应该是乘法，不是加法
    total = subtotal + tax_rate
    return total


def calculate_discount(price, discount_percent):
    """计算折扣后价格

    Bug: 折扣百分比处理错误
    """
    # Bug: discount_percent 应该除以 100
    return price * (1 - discount_percent)


def calculate_average_price(items):
    """计算平均价格

    Bug: 空列表会导致除零错误
    """
    total = sum(item['price'] for item in items)
    # Bug: 没有检查空列表
    return total / len(items)
