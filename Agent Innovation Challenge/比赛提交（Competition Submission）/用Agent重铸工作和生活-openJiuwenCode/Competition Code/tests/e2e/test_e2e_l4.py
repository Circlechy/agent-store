"""
L4 专家场景 E2E 测试

这些测试通过真实的 jiuwen CLI 命令来验证架构级、需要深度理解的复杂任务。
每个测试模拟一个真实的高级用户场景。

运行方式:
    pytest tests/e2e/test_e2e_l4.py -v -m e2e

    # 显示详细输出
    E2E_VERBOSE=1 pytest tests/e2e/test_e2e_l4.py -v -m e2e
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
@pytest.mark.scenario_l4
class TestL4ArchitectureRefactor:
    """L4: 架构重构场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_split_monolith_to_layers(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 把单体模块拆分成独立的服务层和数据层

        用户指令: "把这个单体模块拆分成 Repository 层和 Service 层"

        预期:
        1. Agent 分析现有代码
        2. Agent 创建 Repository 层（数据访问）
        3. Agent 创建 Service 层（业务逻辑）
        4. Agent 重构原有代码
        """
        # 创建单体模块
        monolith_file = os.path.join(temp_project, "user_manager.py")
        with open(monolith_file, 'w') as f:
            f.write('''class UserManager:
    """单体用户管理类 - 混合了数据访问和业务逻辑"""

    def __init__(self):
        self.db = {}

    def create_user(self, name, email):
        """创建用户"""
        user_id = len(self.db) + 1
        self.db[user_id] = {"id": user_id, "name": name, "email": email}
        return self.db[user_id]

    def get_user(self, user_id):
        """获取用户"""
        return self.db.get(user_id)

    def update_user(self, user_id, **kwargs):
        """更新用户"""
        if user_id in self.db:
            self.db[user_id].update(kwargs)
            return self.db[user_id]
        return None

    def delete_user(self, user_id):
        """删除用户"""
        if user_id in self.db:
            del self.db[user_id]
            return True
        return False

    def list_users(self):
        """列出所有用户"""
        return list(self.db.values())
''')

        query = f"""把 {monolith_file} 拆分成分层架构：
1. 创建 {temp_project}/repository.py - UserRepository 类，负责数据存储操作
2. 创建 {temp_project}/service.py - UserService 类，负责业务逻辑，依赖 UserRepository
3. UserService 应该通过构造函数注入 UserRepository"""

        response = await runner.run(query, timeout=240)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "write_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件创建
        repo_file = os.path.join(temp_project, "repository.py")
        service_file = os.path.join(temp_project, "service.py")

        # 至少创建了一个新文件
        files_created = os.path.exists(repo_file) or os.path.exists(service_file)
        assert files_created, "应该至少创建一个分层文件"

        # 如果 repository.py 存在，检查内容
        if os.path.exists(repo_file):
            with open(repo_file, 'r') as f:
                repo_content = f.read()
            assert "class" in repo_content, "repository.py 应该包含类定义"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l4
class TestL4PerformanceOptimization:
    """L4: 性能优化场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_optimize_algorithm(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 优化低效算法

        用户指令: "优化这个函数的性能，当前是 O(n²) 复杂度"

        预期:
        1. Agent 分析性能瓶颈
        2. Agent 使用更高效的算法
        """
        # 创建低效代码
        slow_file = os.path.join(temp_project, "duplicates.py")
        with open(slow_file, 'w') as f:
            f.write('''def find_duplicates(items):
    """找出列表中的重复元素 - O(n²) 实现"""
    duplicates = []
    for i, item in enumerate(items):
        for j, other in enumerate(items):
            if i != j and item == other and item not in duplicates:
                duplicates.append(item)
    return duplicates


def find_pairs_with_sum(numbers, target):
    """找出和为 target 的数对 - O(n²) 实现"""
    pairs = []
    for i, a in enumerate(numbers):
        for j, b in enumerate(numbers):
            if i < j and a + b == target:
                pairs.append((a, b))
    return pairs
''')

        query = f"优化 {slow_file} 中的 find_duplicates 函数，使用 set 或 Counter 将时间复杂度降低到 O(n)"

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证优化结果
        with open(slow_file, 'r') as f:
            content = f.read()

        # 应该使用更高效的数据结构
        has_optimization = (
            "set(" in content or
            "Counter" in content or
            "collections" in content or
            "{}" in content  # dict comprehension
        )
        assert has_optimization, f"应该使用高效数据结构，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l4
class TestL4SecurityAudit:
    """L4: 安全审计场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_fix_security_vulnerabilities(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 审计并修复安全漏洞

        用户指令: "审计这段代码的安全问题并修复"

        预期:
        1. Agent 识别 SQL 注入风险
        2. Agent 识别 XSS 风险
        3. Agent 修复所有问题
        """
        # 创建有安全漏洞的代码
        vuln_file = os.path.join(temp_project, "vulnerable.py")
        with open(vuln_file, 'w') as f:
            f.write('''import sqlite3

def get_user(username):
    """获取用户 - 有 SQL 注入漏洞"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # 危险：直接拼接用户输入
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()


def render_greeting(user_input):
    """渲染问候语 - 有 XSS 漏洞"""
    # 危险：直接插入用户输入到 HTML
    return f"<html><body>Hello, {user_input}!</body></html>"


def execute_command(cmd):
    """执行命令 - 有命令注入漏洞"""
    import os
    # 危险：直接执行用户输入
    os.system(f"echo {cmd}")
''')

        query = f"审计 {vuln_file} 的安全问题并修复：1) SQL 注入 - 使用参数化查询 2) XSS - 转义 HTML 3) 命令注入 - 使用 subprocess 并验证输入"

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证安全修复
        with open(vuln_file, 'r') as f:
            content = f.read()

        # 检查 SQL 注入修复
        has_sql_fix = (
            "?" in content or  # 参数化查询
            "execute(" in content and "," in content  # 带参数的 execute
        )

        # 检查 XSS 修复
        has_xss_fix = (
            "escape" in content.lower() or
            "html.escape" in content or
            "sanitize" in content.lower() or
            "cgi.escape" in content
        )

        # 至少修复了一个问题
        assert has_sql_fix or has_xss_fix, \
            f"应该修复安全漏洞，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l4
class TestL4ComprehensiveTestSuite:
    """L4: 完整测试套件场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_write_comprehensive_tests(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 编写完整的测试套件

        用户指令: "为这个模块编写完整的测试套件，覆盖所有边界情况"

        预期:
        1. Agent 分析所有方法
        2. Agent 识别边界情况
        3. Agent 编写全面测试
        """
        # 创建需要测试的模块
        calc_file = os.path.join(temp_project, "calculator.py")
        with open(calc_file, 'w') as f:
            f.write('''class Calculator:
    """计算器类"""

    def add(self, a, b):
        """加法"""
        return a + b

    def subtract(self, a, b):
        """减法"""
        return a - b

    def multiply(self, a, b):
        """乘法"""
        return a * b

    def divide(self, a, b):
        """除法"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def power(self, base, exp):
        """幂运算"""
        if exp < 0:
            return 1 / (base ** abs(exp))
        return base ** exp

    def factorial(self, n):
        """阶乘"""
        if n < 0:
            raise ValueError("Factorial not defined for negative numbers")
        if n == 0 or n == 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result
''')

        test_file = os.path.join(temp_project, "test_calculator.py")
        query = f"""为 {calc_file} 编写完整的测试套件到 {test_file}，包括：
1. 正常情况测试
2. 边界情况测试（0, 负数, 大数）
3. 异常情况测试（除零, 负数阶乘）
4. 使用 pytest 框架"""

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "write_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证测试文件存在
        assert_file_exists(test_file)

        # 验证测试内容
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有多个测试函数
        test_count = content.count("def test_")
        assert test_count >= 3, f"应该有至少 3 个测试函数，实际有 {test_count} 个"

        # 应该测试异常
        has_exception_test = (
            "pytest.raises" in content or
            "assertRaises" in content or
            "ValueError" in content
        )
        assert has_exception_test, "应该有异常测试"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l4
class TestL4LegacyCodeModernization:
    """L4: 遗留代码现代化场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_modernize_python2_code(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 把 Python 2 风格代码升级到 Python 3

        用户指令: "把这个 Python 2 风格的代码升级到 Python 3"

        预期:
        1. Agent 识别 Python 2 特性
        2. Agent 转换为 Python 3
        """
        # 创建 Python 2 风格代码
        legacy_file = os.path.join(temp_project, "legacy.py")
        with open(legacy_file, 'w') as f:
            f.write('''# -*- coding: utf-8 -*-
from __future__ import print_function, division

class OldStyleClass:
    """Python 2 风格的类"""

    def __init__(self):
        self.data = {}

    def get_data(self, key):
        if self.data.has_key(key):
            return self.data[key]
        return None

    def set_data(self, key, value):
        self.data[key] = value

    def get_keys(self):
        return self.data.keys()

    def get_items(self):
        return self.data.items()


def old_division(a, b):
    """旧式除法"""
    return a / b


def old_print():
    """旧式打印"""
    print "Hello, World!"


def old_exception():
    """旧式异常处理"""
    try:
        x = 1 / 0
    except ZeroDivisionError, e:
        print e
''')

        query = f"""把 {legacy_file} 升级到 Python 3：
1. 移除 __future__ 导入
2. 把 has_key() 改成 in 操作符
3. 修复 print 语句为函数调用
4. 修复异常语法 (except E, e -> except E as e)"""

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证现代化结果
        with open(legacy_file, 'r') as f:
            content = f.read()

        # 检查是否移除了 Python 2 特性
        modernized = (
            "has_key" not in content or  # 移除 has_key
            " in self.data" in content or  # 使用 in
            "as e" in content  # 现代异常语法
        )
        assert modernized, f"代码应该被现代化，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l4
class TestL4ImplementFromDesign:
    """L4: 根据设计文档实现场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_implement_event_bus(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 根据设计文档实现功能

        用户指令: "根据设计文档实现事件总线系统"

        预期:
        1. Agent 理解设计需求
        2. Agent 规划实现步骤
        3. Agent 逐步实现功能
        """
        target_file = os.path.join(temp_project, "event_bus.py")
        query = f"""在 {target_file} 中实现一个事件总线系统：

设计要求：
1. EventBus 类，支持订阅/发布模式
2. subscribe(event_type, handler) - 订阅事件
3. unsubscribe(event_type, handler) - 取消订阅
4. publish(event_type, data) - 发布事件
5. 支持同一事件类型多个处理器
6. 处理器按注册顺序调用"""

        response = await runner.run(query, timeout=240)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        assert_file_exists(target_file)

        # 验证实现内容
        with open(target_file, 'r') as f:
            content = f.read()

        # 检查核心功能
        assert "class EventBus" in content or "class Event" in content, \
            f"应该有 EventBus 类，实际内容: {content}"

        has_subscribe = "def subscribe" in content or "def on" in content
        has_publish = "def publish" in content or "def emit" in content

        assert has_subscribe, f"应该有订阅方法，实际内容: {content}"
        assert has_publish, f"应该有发布方法，实际内容: {content}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
