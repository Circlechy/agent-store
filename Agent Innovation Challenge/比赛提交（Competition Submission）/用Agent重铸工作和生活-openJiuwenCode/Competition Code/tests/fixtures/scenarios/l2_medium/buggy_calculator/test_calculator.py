"""计算器测试"""
import pytest
from calculator import calculate_total, calculate_discount, calculate_average_price


def test_calculate_total():
    """测试总价计算"""
    items = [
        {'name': 'Apple', 'price': 1.0, 'quantity': 3},
        {'name': 'Banana', 'price': 0.5, 'quantity': 6},
    ]
    # 预期: (1.0 * 3 + 0.5 * 6) * 1.1 = 6.0 * 1.1 = 6.6
    result = calculate_total(items, tax_rate=0.1)
    assert result == pytest.approx(6.6, rel=0.01)


def test_calculate_discount():
    """测试折扣计算"""
    # 100 元打 8 折应该是 80 元
    result = calculate_discount(100, 20)  # 20% 折扣
    assert result == pytest.approx(80, rel=0.01)


def test_calculate_average_price():
    """测试平均价格计算"""
    items = [
        {'name': 'A', 'price': 10},
        {'name': 'B', 'price': 20},
        {'name': 'C', 'price': 30},
    ]
    result = calculate_average_price(items)
    assert result == pytest.approx(20, rel=0.01)


def test_calculate_average_price_empty():
    """测试空列表的平均价格"""
    result = calculate_average_price([])
    assert result == 0
