"""
L2 中等场景测试

测试用例覆盖 docs/03-测试用例设计.md 中 10.3 节的所有 L2 用例
这些测试验证 Agent 在多文件、多工具协作任务中的能力
"""

import pytest
import asyncio
import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool
from server.tools.search_tools import GrepTool, GlobTool


# 获取 fixtures 路径
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios" / "l2_medium"

# 检查 ripgrep 是否安装
RIPGREP_INSTALLED = shutil.which("rg") is not None


class TestL2FindAndFixBug:
    """测试找到并修复 Bug"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def buggy_project(self):
        """创建有 Bug 的计算器项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制 buggy_calculator 项目
            src_dir = FIXTURES_DIR / "buggy_calculator"
            if src_dir.exists():
                for file in src_dir.iterdir():
                    shutil.copy(file, temp_dir)
            else:
                # 如果 fixture 不存在，创建测试文件
                calc_file = os.path.join(temp_dir, "calculator.py")
                with open(calc_file, 'w') as f:
                    f.write('''"""有 Bug 的计算器模块"""

def calculate_total(items, tax_rate=0.1):
    """计算总价（含税）- Bug: 税率计算错误"""
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    # Bug: 这里应该是乘法，不是加法
    total = subtotal + tax_rate
    return total


def calculate_discount(price, discount_percent):
    """计算折扣后价格 - Bug: 折扣百分比处理错误"""
    # Bug: discount_percent 应该除以 100
    return price * (1 - discount_percent)


def calculate_average_price(items):
    """计算平均价格 - Bug: 空列表会导致除零错误"""
    total = sum(item['price'] for item in items)
    # Bug: 没有检查空列表
    return total / len(items)
''')

                test_file = os.path.join(temp_dir, "test_calculator.py")
                with open(test_file, 'w') as f:
                    f.write('''"""计算器测试"""
import pytest
from calculator import calculate_total, calculate_discount, calculate_average_price


def test_calculate_total():
    items = [
        {'name': 'Apple', 'price': 1.0, 'quantity': 3},
        {'name': 'Banana', 'price': 0.5, 'quantity': 6},
    ]
    result = calculate_total(items, tax_rate=0.1)
    assert result == pytest.approx(6.6, rel=0.01)


def test_calculate_discount():
    result = calculate_discount(100, 20)
    assert result == pytest.approx(80, rel=0.01)


def test_calculate_average_price():
    items = [
        {'name': 'A', 'price': 10},
        {'name': 'B', 'price': 20},
        {'name': 'C', 'price': 30},
    ]
    result = calculate_average_price(items)
    assert result == pytest.approx(20, rel=0.01)


def test_calculate_average_price_empty():
    result = calculate_average_price([])
    assert result == 0
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_find_and_fix_bug_workflow(self, mode_manager, buggy_project):
        """
        场景: 找到并修复 calculate_total 的 bug
        预期: grep → read_file → edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        calc_file = os.path.join(buggy_project, "calculator.py")

        # 1. 读取文件定位 bug
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": calc_file
        }))
        assert read_result.success == True
        assert "calculate_total" in read_result.data["content"]

        # 2. 修复 bug - 将加法改为乘法
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": calc_file,
            "old_string": "total = subtotal + tax_rate",
            "new_string": "total = subtotal * (1 + tax_rate)"
        }))
        assert edit_result.success == True

        # 3. 验证修复
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": calc_file
        }))
        assert "total = subtotal * (1 + tax_rate)" in read_result2.data["content"]


class TestL2AddErrorHandling:
    """测试添加错误处理"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_add_error_handling_workflow(self, mode_manager, temp_dir):
        """
        场景: 给函数添加错误处理
        预期: read_file → edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建缺少错误处理的文件
        target_file = os.path.join(temp_dir, "no_error_handling.py")
        with open(target_file, 'w') as f:
            f.write('''"""缺少错误处理的代码"""

def divide_values(a, b):
    """除法运算"""
    return a / b


def get_list_item(items, index):
    """获取列表元素"""
    return items[index]
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 添加错误处理
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''def divide_values(a, b):
    """除法运算"""
    return a / b''',
            "new_string": '''def divide_values(a, b):
    """除法运算"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b'''
        }))
        assert edit_result.success == True

        # 3. 验证错误处理
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert 'raise ValueError("Cannot divide by zero")' in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL2RefactorFunction:
    """测试重构函数"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_refactor_function_workflow(self, mode_manager, temp_dir):
        """
        场景: 重构函数，拆分成更小的函数
        预期: read_file → edit_file (多次)
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建需要重构的文件
        target_file = os.path.join(temp_dir, "long_function.py")
        with open(target_file, 'w') as f:
            f.write('''"""需要重构的长函数"""

def process_order(order):
    """处理订单 - 这个函数太长了"""
    # 验证订单
    if not order.get('items'):
        return {'error': 'No items'}
    if not order.get('customer_id'):
        return {'error': 'No customer'}

    # 计算总价
    subtotal = sum(item['price'] * item['quantity'] for item in order['items'])
    tax = subtotal * 0.1
    total = subtotal + tax

    # 生成订单号
    import uuid
    order_id = str(uuid.uuid4())[:8]

    return {
        'order_id': order_id,
        'subtotal': subtotal,
        'tax': tax,
        'total': total
    }
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 重构 - 提取验证函数
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''"""需要重构的长函数"""

def process_order(order):''',
            "new_string": '''"""重构后的订单处理模块"""

def validate_order(order):
    """验证订单"""
    if not order.get('items'):
        return {'error': 'No items'}
    if not order.get('customer_id'):
        return {'error': 'No customer'}
    return None


def calculate_order_total(items, tax_rate=0.1):
    """计算订单总价"""
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    tax = subtotal * tax_rate
    return subtotal, tax, subtotal + tax


def generate_order_id():
    """生成订单号"""
    import uuid
    return str(uuid.uuid4())[:8]


def process_order(order):'''
        }))
        assert edit_result.success == True

        # 3. 验证重构
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "def validate_order(order):" in read_result2.data["content"]
        assert "def calculate_order_total(items" in read_result2.data["content"]
        assert "def generate_order_id():" in read_result2.data["content"]


class TestL2AddUnitTest:
    """测试为函数写单元测试"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_add_unit_test_workflow(self, mode_manager, temp_dir):
        """
        场景: 为函数写单元测试
        预期: read_file → write_file
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建源文件
        source_file = os.path.join(temp_dir, "math_utils.py")
        with open(source_file, 'w') as f:
            f.write('''"""数学工具函数"""

def factorial(n):
    """计算阶乘"""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def fibonacci(n):
    """计算斐波那契数列第 n 项"""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
''')

        # 1. 读取源文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": source_file
        }))
        assert read_result.success == True

        # 2. 创建测试文件
        test_file = os.path.join(temp_dir, "test_math_utils.py")
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": test_file,
            "content": '''"""数学工具函数测试"""
import pytest
from math_utils import factorial, fibonacci


class TestFactorial:
    """阶乘函数测试"""

    def test_factorial_zero(self):
        assert factorial(0) == 1

    def test_factorial_one(self):
        assert factorial(1) == 1

    def test_factorial_five(self):
        assert factorial(5) == 120

    def test_factorial_negative(self):
        with pytest.raises(ValueError):
            factorial(-1)


class TestFibonacci:
    """斐波那契函数测试"""

    def test_fibonacci_zero(self):
        assert fibonacci(0) == 0

    def test_fibonacci_one(self):
        assert fibonacci(1) == 1

    def test_fibonacci_ten(self):
        assert fibonacci(10) == 55

    def test_fibonacci_negative(self):
        with pytest.raises(ValueError):
            fibonacci(-1)
'''
        }))
        assert write_result.success == True

        # 3. 运行测试
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"cd {temp_dir} && python3 -m pytest test_math_utils.py -v",
            "timeout": 30
        }))
        assert bash_result.success == True
        assert "passed" in bash_result.data["stdout"]


@pytest.mark.skipif(not RIPGREP_INSTALLED, reason="ripgrep (rg) 未安装")
class TestL2FindAllUsages:
    """测试找到函数的所有调用位置"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def multi_file_project(self):
        """创建多文件项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建多个文件
            utils_file = os.path.join(temp_dir, "utils.py")
            with open(utils_file, 'w') as f:
                f.write('''"""工具函数"""

def helper_function():
    """辅助函数"""
    return "helper"
''')

            main_file = os.path.join(temp_dir, "main.py")
            with open(main_file, 'w') as f:
                f.write('''"""主模块"""
from utils import helper_function

def main():
    result = helper_function()
    print(result)
''')

            service_file = os.path.join(temp_dir, "service.py")
            with open(service_file, 'w') as f:
                f.write('''"""服务模块"""
from utils import helper_function

class MyService:
    def process(self):
        return helper_function()
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_find_all_usages_workflow(self, mode_manager, multi_file_project):
        """
        场景: 找到 helper_function 的所有调用位置
        预期: grep → glob → read_file
        """
        grep_tool = GrepTool(mode_manager)
        glob_tool = GlobTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 1. 搜索 helper_function
        grep_result = await grep_tool.ainvoke(ToolInput(data={
            "pattern": "helper_function",
            "path": multi_file_project
        }))
        assert grep_result.success == True
        assert grep_result.data["count"] >= 3  # 定义 + 2 个调用

        # 2. 找到所有 Python 文件
        glob_result = await glob_tool.ainvoke(ToolInput(data={
            "pattern": "*.py",
            "path": multi_file_project
        }))
        assert glob_result.success == True
        assert glob_result.data["count"] == 3


class TestL2ConvertSyncToAsync:
    """测试把同步函数改成异步"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_convert_sync_to_async_workflow(self, mode_manager, temp_dir):
        """
        场景: 把同步函数改成异步
        预期: read_file → edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建同步代码
        target_file = os.path.join(temp_dir, "sync_code.py")
        with open(target_file, 'w') as f:
            f.write('''"""同步代码"""

def fetch_data(url):
    """获取数据"""
    import time
    time.sleep(0.1)  # 模拟 IO
    return {"url": url, "data": "result"}


def process_data(data):
    """处理数据"""
    return {"processed": True, **data}
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 转换为异步
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''"""同步代码"""

def fetch_data(url):
    """获取数据"""
    import time
    time.sleep(0.1)  # 模拟 IO
    return {"url": url, "data": "result"}


def process_data(data):
    """处理数据"""
    return {"processed": True, **data}''',
            "new_string": '''"""异步代码"""
import asyncio


async def fetch_data(url):
    """获取数据"""
    await asyncio.sleep(0.1)  # 模拟异步 IO
    return {"url": url, "data": "result"}


async def process_data(data):
    """处理数据"""
    return {"processed": True, **data}'''
        }))
        assert edit_result.success == True

        # 3. 验证转换
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "async def fetch_data" in read_result2.data["content"]
        assert "await asyncio.sleep" in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL2ExtractConfig:
    """测试把硬编码的值提取到配置文件"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l2
    async def test_extract_config_workflow(self, mode_manager, temp_dir):
        """
        场景: 把硬编码的值提取到配置文件
        预期: read_file → write_file (config) → edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 创建硬编码配置的文件
        app_file = os.path.join(temp_dir, "app.py")
        with open(app_file, 'w') as f:
            f.write('''"""硬编码配置的应用"""

def connect_database():
    host = "localhost"
    port = 5432
    database = "myapp"
    return f"postgresql://{host}:{port}/{database}"
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": app_file
        }))
        assert read_result.success == True

        # 2. 创建配置文件
        config_file = os.path.join(temp_dir, "config.py")
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": config_file,
            "content": '''"""配置文件"""

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "myapp"
'''
        }))
        assert write_result.success == True

        # 3. 修改应用文件使用配置
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": app_file,
            "old_string": '''"""硬编码配置的应用"""

def connect_database():
    host = "localhost"
    port = 5432
    database = "myapp"
    return f"postgresql://{host}:{port}/{database}"''',
            "new_string": '''"""使用配置文件的应用"""
from config import DATABASE_HOST, DATABASE_PORT, DATABASE_NAME


def connect_database():
    return f"postgresql://{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"'''
        }))
        assert edit_result.success == True

        # 4. 验证修改
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": app_file
        }))
        assert "from config import" in read_result2.data["content"]
        assert "DATABASE_HOST" in read_result2.data["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "scenario_l2"])
