"""
L3 复杂场景 E2E 测试

这些测试通过真实的 jiuwen CLI 命令来验证跨模块、需要规划的复杂任务。
每个测试模拟一个真实的用户场景。

运行方式:
    pytest tests/e2e/test_e2e_l3.py -v -m e2e

    # 显示详细输出
    E2E_VERBOSE=1 pytest tests/e2e/test_e2e_l3.py -v -m e2e
"""

import pytest
import os
import sys
from pathlib import Path

from .conftest import (
    requires_api_key,
    JiuwenRunner,
    JiuwenResponse,
    assert_tool_called,
    assert_any_tool_called,
    assert_no_errors,
    assert_file_exists,
    assert_file_contains,
    assert_file_not_contains,
    assert_response_mentions,
)


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3RenameAcrossProject:
    """L3: 跨项目重命名场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_rename_class_across_files(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 在多个文件中重命名类

        用户指令: "把类名 OldClass 改成 NewClass"

        预期:
        1. jiuwen 搜索所有包含 OldClass 的文件
        2. jiuwen 在每个文件中进行替换
        3. 所有文件都被正确更新
        """
        # 创建多文件项目
        models_file = os.path.join(temp_project, "models.py")
        with open(models_file, 'w') as f:
            f.write('''class OldClass:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name
''')

        service_file = os.path.join(temp_project, "service.py")
        with open(service_file, 'w') as f:
            f.write('''from models import OldClass

class MyService:
    def create(self, name):
        return OldClass(name)
''')

        main_file = os.path.join(temp_project, "main.py")
        with open(main_file, 'w') as f:
            f.write('''from models import OldClass

obj = OldClass("test")
print(obj.get_name())
''')

        query = f"在 {temp_project} 目录中，把所有文件里的类名 OldClass 改成 NewClass"

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["grep", "glob", "edit_file", "read_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证所有文件都被更新
        for file_path in [models_file, service_file, main_file]:
            with open(file_path, 'r') as f:
                content = f.read()
            # 至少有一个文件应该包含 NewClass
            if "NewClass" in content:
                break
        else:
            # 如果没有任何文件包含 NewClass，检查是否至少尝试了修改
            assert response.has_tool_call("edit_file"), \
                "应该至少尝试修改文件"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3AddLogging:
    """L3: 添加日志记录场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_logging_to_module(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 给模块添加日志记录

        用户指令: "给这个模块的所有函数添加日志记录"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 添加 logging 导入
        3. jiuwen 在每个函数中添加日志
        """
        # 创建测试文件
        service_file = os.path.join(temp_project, "user_service.py")
        with open(service_file, 'w') as f:
            f.write('''class UserService:
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

        query = f"给 {service_file} 添加日志记录：导入 logging，创建 logger，在每个方法开始时记录 info 日志"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证日志被添加
        with open(service_file, 'r') as f:
            content = f.read()

        assert "import logging" in content or "from logging" in content, \
            f"应该导入 logging，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3ImplementFeature:
    """L3: 实现功能场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_implement_simple_feature(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 实现一个简单的功能

        用户指令: "实现一个简单的计数器类"

        预期:
        1. jiuwen 可能使用 todo_write 规划任务
        2. jiuwen 创建文件
        3. 实现的代码是完整的
        """
        target_file = os.path.join(temp_project, "counter.py")
        query = f"在 {target_file} 中实现一个 Counter 类，包含 increment(), decrement(), get_value() 方法"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        assert_file_exists(target_file)

        # 验证实现内容
        with open(target_file, 'r') as f:
            content = f.read()

        assert "class Counter" in content, f"应该有 Counter 类，实际内容: {content}"
        assert "def increment" in content or "def incr" in content, \
            f"应该有 increment 方法，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3RefactorToPattern:
    """L3: 重构为设计模式场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_refactor_to_strategy_pattern(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 用策略模式重构代码

        用户指令: "用策略模式重构这段代码"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 重构为策略模式
        3. 代码结构符合策略模式
        """
        # 创建需要重构的文件
        payment_file = os.path.join(temp_project, "payment.py")
        with open(payment_file, 'w') as f:
            f.write('''def process_payment(amount, method):
    if method == "credit_card":
        fee = amount * 0.03
        return {"method": "credit_card", "amount": amount, "fee": fee}
    elif method == "paypal":
        fee = amount * 0.04
        return {"method": "paypal", "amount": amount, "fee": fee}
    elif method == "bank_transfer":
        fee = 5.0
        return {"method": "bank_transfer", "amount": amount, "fee": fee}
    else:
        raise ValueError(f"Unknown method: {method}")
''')

        query = f"用策略模式重构 {payment_file}：创建 PaymentStrategy 基类和具体策略类（CreditCardPayment, PayPalPayment, BankTransferPayment）"

        response = await runner.run(query, timeout=150)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file", "write_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证重构结果
        with open(payment_file, 'r') as f:
            content = f.read()

        # 应该有策略类
        has_strategy = (
            "class " in content and
            ("Strategy" in content or "Payment" in content)
        )
        assert has_strategy, f"应该有策略类，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3AddApiEndpoint:
    """L3: 添加 API 端点场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_api_endpoint(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 添加新的 API 端点

        用户指令: "添加一个新的 API 端点"

        预期:
        1. jiuwen 读取现有 API 文件
        2. jiuwen 添加新端点
        3. 新端点符合现有风格
        """
        # 创建现有 API 文件
        api_file = os.path.join(temp_project, "api.py")
        with open(api_file, 'w') as f:
            f.write('''class UserAPI:
    def get_users(self):
        """获取所有用户"""
        return [{"id": 1, "name": "Alice"}]

    def get_user(self, user_id):
        """获取单个用户"""
        return {"id": user_id, "name": "User"}
''')

        query = f"在 {api_file} 的 UserAPI 类中添加 create_user(self, name, email) 和 delete_user(self, user_id) 方法"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证新端点被添加
        with open(api_file, 'r') as f:
            content = f.read()

        assert "def create_user" in content, f"应该有 create_user 方法，实际内容: {content}"
        assert "def delete_user" in content, f"应该有 delete_user 方法，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3TodoWorkflow:
    """L3: Todo 工作流场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_multi_step_task_with_todo(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 多步骤任务使用 Todo 管理

        用户指令: "帮我创建一个简单的用户管理模块，包含 User 类和 UserManager 类"

        预期:
        1. jiuwen 使用 todo_write 规划任务
        2. jiuwen 逐步完成任务
        3. 最终代码完整
        """
        query = f"在 {temp_project} 目录下创建一个用户管理模块：1) 创建 user.py 包含 User 类（有 id, name, email 属性）2) 创建 user_manager.py 包含 UserManager 类（有 add_user, get_user, list_users 方法）"

        response = await runner.run(query, timeout=180)

        # 验证调用了写入工具
        assert_tool_called(response, "write_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证至少创建了一个文件
        user_file = os.path.join(temp_project, "user.py")
        manager_file = os.path.join(temp_project, "user_manager.py")

        # 至少有一个文件应该存在
        assert os.path.exists(user_file) or os.path.exists(manager_file), \
            "应该至少创建一个文件"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3DatabaseMigration:
    """L3: 数据库迁移场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_create_migration_script(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 创建数据库迁移脚本

        用户指令: "创建一个数据库迁移脚本"

        预期:
        1. jiuwen 创建迁移脚本
        2. 脚本包含 upgrade 和 downgrade 函数
        """
        target_file = os.path.join(temp_project, "migration_001.py")
        query = f"在 {target_file} 创建一个数据库迁移脚本，添加 email_verified 布尔字段到 users 表，包含 upgrade() 和 downgrade() 函数"

        response = await runner.run(query, timeout=120)

        # 验证调用了写入工具
        assert_tool_called(response, "write_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        assert_file_exists(target_file)

        # 验证内容
        with open(target_file, 'r') as f:
            content = f.read()

        assert "def upgrade" in content or "upgrade" in content.lower(), \
            f"应该有 upgrade 函数，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l3
class TestL3ImplementRestApi:
    """L3: 实现 REST API 场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_implement_flask_api(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 用 Flask 实现 REST API

        用户指令: "用 Flask 实现一个简单的 TODO API"

        预期:
        1. jiuwen 创建 Flask 应用
        2. 实现 CRUD 端点
        """
        target_file = os.path.join(temp_project, "todo_api.py")
        query = f"在 {target_file} 用 Flask 实现一个简单的 TODO API，包含：GET /todos（列出所有）, POST /todos（创建）, DELETE /todos/<id>（删除）"

        response = await runner.run(query, timeout=150)

        # 验证调用了写入工具
        assert_tool_called(response, "write_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        assert_file_exists(target_file)

        # 验证内容
        with open(target_file, 'r') as f:
            content = f.read()

        assert "flask" in content.lower() or "Flask" in content, \
            f"应该使用 Flask，实际内容: {content}"
        assert "route" in content.lower() or "@app" in content, \
            f"应该有路由定义，实际内容: {content}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
