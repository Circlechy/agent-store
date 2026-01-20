"""
L3 复杂场景测试

测试用例覆盖 docs/03-测试用例设计.md 中 10.4 节的所有 L3 用例
这些测试验证 Agent 在跨模块、需要规划的复杂任务中的能力
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
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios" / "l3_complex"

# 检查 ripgrep 是否安装
RIPGREP_INSTALLED = shutil.which("rg") is not None


class TestL3RenameAcrossProject:
    """测试跨项目重命名"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def multi_file_project(self):
        """创建多文件项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建多个使用 OldClass 的文件
            models_file = os.path.join(temp_dir, "models.py")
            with open(models_file, 'w') as f:
                f.write('''"""模型定义"""

class OldClass:
    """旧类名 - 需要重命名为 NewClass"""
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name
''')

            service_file = os.path.join(temp_dir, "service.py")
            with open(service_file, 'w') as f:
                f.write('''"""服务层"""
from models import OldClass


class MyService:
    def create_instance(self, name):
        return OldClass(name)

    def process(self, obj: OldClass):
        return obj.get_name()
''')

            main_file = os.path.join(temp_dir, "main.py")
            with open(main_file, 'w') as f:
                f.write('''"""主程序"""
from models import OldClass
from service import MyService


def main():
    obj = OldClass("test")
    service = MyService()
    result = service.process(obj)
    print(result)


if __name__ == "__main__":
    main()
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l3
    async def test_rename_across_project_workflow(self, mode_manager, multi_file_project):
        """
        场景: 把类名 OldClass 改成 NewClass
        预期: grep → glob → 多次 edit_file
        """
        glob_tool = GlobTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 1. 找到所有 Python 文件
        glob_result = await glob_tool.ainvoke(ToolInput(data={
            "pattern": "*.py",
            "path": multi_file_project
        }))
        assert glob_result.success == True
        assert glob_result.data["count"] == 3

        # 2. 重命名 models.py 中的类定义
        models_file = os.path.join(multi_file_project, "models.py")
        edit_result1 = await edit_tool.ainvoke(ToolInput(data={
            "file_path": models_file,
            "old_string": "OldClass",
            "new_string": "NewClass",
            "replace_all": True
        }))
        assert edit_result1.success == True

        # 3. 重命名 service.py 中的引用
        service_file = os.path.join(multi_file_project, "service.py")
        edit_result2 = await edit_tool.ainvoke(ToolInput(data={
            "file_path": service_file,
            "old_string": "OldClass",
            "new_string": "NewClass",
            "replace_all": True
        }))
        assert edit_result2.success == True

        # 4. 重命名 main.py 中的引用
        main_file = os.path.join(multi_file_project, "main.py")
        edit_result3 = await edit_tool.ainvoke(ToolInput(data={
            "file_path": main_file,
            "old_string": "OldClass",
            "new_string": "NewClass",
            "replace_all": True
        }))
        assert edit_result3.success == True

        # 5. 验证所有文件都已更新
        for file_name in ["models.py", "service.py", "main.py"]:
            file_path = os.path.join(multi_file_project, file_name)
            read_result = await read_tool.ainvoke(ToolInput(data={
                "file_path": file_path
            }))
            assert "OldClass" not in read_result.data["content"]
            assert "NewClass" in read_result.data["content"]


class TestL3AddLogging:
    """测试给模块添加日志记录"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l3
    async def test_add_logging_workflow(self, mode_manager, temp_dir):
        """
        场景: 给模块添加日志记录
        预期: read_file → edit_file (多处)
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建没有日志的模块
        target_file = os.path.join(temp_dir, "service.py")
        with open(target_file, 'w') as f:
            f.write('''"""服务模块 - 缺少日志"""

class UserService:
    def __init__(self):
        self.users = {}

    def create_user(self, user_id, name):
        self.users[user_id] = {"id": user_id, "name": name}
        return self.users[user_id]

    def get_user(self, user_id):
        return self.users.get(user_id)

    def delete_user(self, user_id):
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 添加日志导入和配置
        edit_result1 = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '"""服务模块 - 缺少日志"""',
            "new_string": '''"""服务模块 - 已添加日志"""
import logging

logger = logging.getLogger(__name__)'''
        }))
        assert edit_result1.success == True

        # 3. 添加日志到 create_user
        edit_result2 = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''    def create_user(self, user_id, name):
        self.users[user_id] = {"id": user_id, "name": name}
        return self.users[user_id]''',
            "new_string": '''    def create_user(self, user_id, name):
        logger.info(f"Creating user: {user_id}, {name}")
        self.users[user_id] = {"id": user_id, "name": name}
        logger.debug(f"User created: {self.users[user_id]}")
        return self.users[user_id]'''
        }))
        assert edit_result2.success == True

        # 4. 验证日志已添加
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "import logging" in read_result2.data["content"]
        assert "logger = logging.getLogger" in read_result2.data["content"]
        assert "logger.info" in read_result2.data["content"]

        # 5. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL3FixFailingTests:
    """测试修复失败的测试"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def failing_tests_project(self):
        """创建有失败测试的项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建有 bug 的代码
            math_file = os.path.join(temp_dir, "math_functions.py")
            with open(math_file, 'w') as f:
                f.write('''"""数学函数 - 有 bug"""

def add(a, b):
    """加法"""
    return a + b


def subtract(a, b):
    """减法 - 有 bug"""
    return a + b  # Bug: 应该是 a - b


def multiply(a, b):
    """乘法"""
    return a * b
''')

            # 创建测试文件
            test_file = os.path.join(temp_dir, "test_math.py")
            with open(test_file, 'w') as f:
                f.write('''"""数学函数测试"""
import pytest
from math_functions import add, subtract, multiply


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2  # 这个测试会失败


def test_multiply():
    assert multiply(4, 5) == 20
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l3
    async def test_fix_failing_tests_workflow(self, mode_manager, failing_tests_project):
        """
        场景: 修复失败的测试
        预期: bash (pytest) → read_file → edit_file
        """
        bash_tool = BashTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 1. 运行测试 - 预期失败
        bash_result1 = await bash_tool.ainvoke(ToolInput(data={
            "command": f"cd {failing_tests_project} && python3 -m pytest test_math.py -v",
            "timeout": 30
        }))
        # 测试应该失败
        assert "FAILED" in bash_result1.data.get("stdout", "") or bash_result1.success == False

        # 2. 读取源文件找到 bug
        math_file = os.path.join(failing_tests_project, "math_functions.py")
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": math_file
        }))
        assert read_result.success == True
        assert "return a + b  # Bug" in read_result.data["content"]

        # 3. 修复 bug
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": math_file,
            "old_string": "    return a + b  # Bug: 应该是 a - b",
            "new_string": "    return a - b  # 已修复"
        }))
        assert edit_result.success == True

        # 4. 再次运行测试 - 应该通过
        bash_result2 = await bash_tool.ainvoke(ToolInput(data={
            "command": f"cd {failing_tests_project} && python3 -m pytest test_math.py -v",
            "timeout": 30
        }))
        assert bash_result2.success == True
        assert "3 passed" in bash_result2.data["stdout"]


class TestL3AddApiEndpoint:
    """测试添加新的 API 端点"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l3
    async def test_add_api_endpoint_workflow(self, mode_manager, temp_dir):
        """
        场景: 添加一个新的 API 端点
        预期: glob → read_file → write_file/edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建现有的 API 文件
        api_file = os.path.join(temp_dir, "api.py")
        with open(api_file, 'w') as f:
            f.write('''"""API 端点"""

# 模拟的路由装饰器
def route(path):
    def decorator(func):
        func.route = path
        return func
    return decorator


class API:
    """API 类"""

    @route("/users")
    def get_users(self):
        """获取所有用户"""
        return [{"id": 1, "name": "Alice"}]

    @route("/users/<id>")
    def get_user(self, user_id):
        """获取单个用户"""
        return {"id": user_id, "name": "User"}
''')

        # 1. 读取现有 API
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": api_file
        }))
        assert read_result.success == True

        # 2. 添加新的端点
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": api_file,
            "old_string": '''    @route("/users/<id>")
    def get_user(self, user_id):
        """获取单个用户"""
        return {"id": user_id, "name": "User"}''',
            "new_string": '''    @route("/users/<id>")
    def get_user(self, user_id):
        """获取单个用户"""
        return {"id": user_id, "name": "User"}

    @route("/users", methods=["POST"])
    def create_user(self, data):
        """创建新用户"""
        return {"id": 2, "name": data.get("name", "New User")}

    @route("/users/<id>", methods=["DELETE"])
    def delete_user(self, user_id):
        """删除用户"""
        return {"deleted": True, "id": user_id}'''
        }))
        assert edit_result.success == True

        # 3. 验证新端点已添加
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": api_file
        }))
        assert "def create_user" in read_result2.data["content"]
        assert "def delete_user" in read_result2.data["content"]
        assert 'methods=["POST"]' in read_result2.data["content"]
        assert 'methods=["DELETE"]' in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {api_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL3RefactorToPattern:
    """测试用设计模式重构代码"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l3
    async def test_refactor_to_strategy_pattern(self, mode_manager, temp_dir):
        """
        场景: 用策略模式重构代码
        预期: read_file → 多次 edit/write
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建需要重构的代码（使用 if-else 的支付处理）
        payment_file = os.path.join(temp_dir, "payment.py")
        with open(payment_file, 'w') as f:
            f.write('''"""支付处理 - 使用 if-else，需要重构为策略模式"""

def process_payment(amount, method):
    """处理支付"""
    if method == "credit_card":
        # 信用卡支付逻辑
        fee = amount * 0.03
        return {"method": "credit_card", "amount": amount, "fee": fee}
    elif method == "paypal":
        # PayPal 支付逻辑
        fee = amount * 0.04
        return {"method": "paypal", "amount": amount, "fee": fee}
    elif method == "bank_transfer":
        # 银行转账逻辑
        fee = 5.0
        return {"method": "bank_transfer", "amount": amount, "fee": fee}
    else:
        raise ValueError(f"Unknown payment method: {method}")
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": payment_file
        }))
        assert read_result.success == True

        # 2. 重构为策略模式
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": payment_file,
            "content": '''"""支付处理 - 使用策略模式重构"""
from abc import ABC, abstractmethod


class PaymentStrategy(ABC):
    """支付策略基类"""

    @abstractmethod
    def calculate_fee(self, amount: float) -> float:
        pass

    @abstractmethod
    def get_method_name(self) -> str:
        pass

    def process(self, amount: float) -> dict:
        fee = self.calculate_fee(amount)
        return {
            "method": self.get_method_name(),
            "amount": amount,
            "fee": fee
        }


class CreditCardPayment(PaymentStrategy):
    """信用卡支付策略"""

    def calculate_fee(self, amount: float) -> float:
        return amount * 0.03

    def get_method_name(self) -> str:
        return "credit_card"


class PayPalPayment(PaymentStrategy):
    """PayPal 支付策略"""

    def calculate_fee(self, amount: float) -> float:
        return amount * 0.04

    def get_method_name(self) -> str:
        return "paypal"


class BankTransferPayment(PaymentStrategy):
    """银行转账支付策略"""

    def calculate_fee(self, amount: float) -> float:
        return 5.0

    def get_method_name(self) -> str:
        return "bank_transfer"


# 策略注册表
PAYMENT_STRATEGIES = {
    "credit_card": CreditCardPayment,
    "paypal": PayPalPayment,
    "bank_transfer": BankTransferPayment,
}


def process_payment(amount: float, method: str) -> dict:
    """处理支付 - 使用策略模式"""
    if method not in PAYMENT_STRATEGIES:
        raise ValueError(f"Unknown payment method: {method}")

    strategy = PAYMENT_STRATEGIES[method]()
    return strategy.process(amount)
'''
        }))
        assert write_result.success == True

        # 3. 验证重构
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": payment_file
        }))
        assert "class PaymentStrategy(ABC):" in read_result2.data["content"]
        assert "class CreditCardPayment(PaymentStrategy):" in read_result2.data["content"]
        assert "PAYMENT_STRATEGIES" in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {payment_file}",
            "timeout": 10
        }))
        assert bash_result.success == True

        # 5. 验证功能正常
        bash_result2 = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -c \"import sys; sys.path.insert(0, '{temp_dir}'); from payment import process_payment; print(process_payment(100, 'credit_card'))\"",
            "timeout": 10
        }))
        assert bash_result2.success == True
        assert "credit_card" in bash_result2.data["stdout"]
        assert "3.0" in bash_result2.data["stdout"]  # 3% fee


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "scenario_l3"])
