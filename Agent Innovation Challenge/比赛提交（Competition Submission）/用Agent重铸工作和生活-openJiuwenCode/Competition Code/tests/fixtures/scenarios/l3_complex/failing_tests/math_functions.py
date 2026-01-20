"""失败的测试 - 需要修复"""

import pytest


def add(a, b):
    """加法"""
    return a + b


def subtract(a, b):
    """减法 - 有 bug"""
    return a + b  # Bug: 应该是 a - b


def multiply(a, b):
    """乘法"""
    return a * b


def divide(a, b):
    """除法 - 缺少除零检查"""
    return a / b


class TestMath:
    """数学函数测试"""

    def test_add(self):
        assert add(2, 3) == 5

    def test_subtract(self):
        # 这个测试会失败，因为 subtract 有 bug
        assert subtract(5, 3) == 2

    def test_multiply(self):
        assert multiply(4, 5) == 20

    def test_divide(self):
        assert divide(10, 2) == 5

    def test_divide_by_zero(self):
        # 这个测试会失败，因为没有处理除零
        with pytest.raises(ZeroDivisionError):
            divide(10, 0)
