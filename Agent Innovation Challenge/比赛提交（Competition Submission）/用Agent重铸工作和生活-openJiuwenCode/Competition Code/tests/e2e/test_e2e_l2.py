"""
L2 中等场景 E2E 测试

这些测试通过真实的 jiuwen CLI 命令来验证多文件、多工具协作的任务。
每个测试模拟一个真实的用户场景。

运行方式:
    pytest tests/e2e/test_e2e_l2.py -v -m e2e

    # 显示详细输出
    E2E_VERBOSE=1 pytest tests/e2e/test_e2e_l2.py -v -m e2e
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
@pytest.mark.scenario_l2
class TestL2FindAndFixBug:
    """L2: 找到并修复 Bug 场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_find_and_fix_bug(self, runner: JiuwenRunner, buggy_calculator: str):
        """
        场景: 用户报告一个 bug，要求 jiuwen 找到并修复

        用户指令: "calculate_total 函数返回的结果不对，帮我找到并修复这个 bug"

        预期:
        1. jiuwen 搜索或读取相关文件
        2. jiuwen 分析代码找到 bug
        3. jiuwen 使用 edit_file 修复 bug
        4. 修复后测试通过
        """
        calc_file = os.path.join(buggy_calculator, "calculator.py")
        query = f"在 {buggy_calculator} 目录中，calculate_total 函数返回的结果不对（应该是 subtotal * (1 + tax_rate) 而不是 subtotal + tax_rate），帮我找到并修复这个 bug"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "grep", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证 bug 被修复 - 检查文件内容
        with open(calc_file, 'r') as f:
            content = f.read()

        # 应该包含正确的计算逻辑
        assert "subtotal + tax_rate" not in content or "* (1 + tax_rate)" in content or "* 1." in content, \
            f"Bug 应该被修复，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2AddErrorHandling:
    """L2: 添加错误处理场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_error_handling(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 给函数添加错误处理

        用户指令: "给这个除法函数添加除零错误处理"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 添加 try-except 或条件检查
        3. 函数能正确处理除零情况
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "math_ops.py")
        with open(test_file, 'w') as f:
            f.write('''def divide(a, b):
    return a / b
''')

        query = f"给 {test_file} 中的 divide 函数添加除零错误处理，当 b 为 0 时抛出 ValueError"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证错误处理被添加
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有错误处理逻辑
        has_error_handling = (
            "if b == 0" in content or
            "if b == 0:" in content or
            "ValueError" in content or
            "ZeroDivisionError" in content or
            "try:" in content
        )
        assert has_error_handling, f"应该有错误处理逻辑，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2WriteUnitTest:
    """L2: 编写单元测试场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_write_unit_test(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 为函数编写单元测试

        用户指令: "为这个函数写单元测试"

        预期:
        1. jiuwen 读取源文件
        2. jiuwen 创建测试文件
        3. 测试文件包含有效的测试用例
        """
        # 创建源文件
        source_file = os.path.join(temp_project, "string_utils.py")
        with open(source_file, 'w') as f:
            f.write('''def reverse_string(s):
    """反转字符串"""
    return s[::-1]

def is_palindrome(s):
    """检查是否是回文"""
    return s == s[::-1]
''')

        test_file = os.path.join(temp_project, "test_string_utils.py")
        query = f"为 {source_file} 中的函数编写单元测试，保存到 {test_file}"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "write_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证测试文件存在
        assert_file_exists(test_file)

        # 验证测试文件内容
        with open(test_file, 'r') as f:
            content = f.read()

        assert "def test_" in content or "class Test" in content, \
            f"测试文件应该包含测试函数，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2RefactorFunction:
    """L2: 重构函数场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_refactor_long_function(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 重构一个过长的函数

        用户指令: "把这个函数拆分成更小的函数"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 编辑文件，提取子函数
        3. 代码结构更清晰
        """
        # 创建需要重构的文件
        test_file = os.path.join(temp_project, "processor.py")
        with open(test_file, 'w') as f:
            f.write('''def process_data(data):
    # 验证数据
    if not data:
        return None
    if not isinstance(data, dict):
        return None

    # 提取字段
    name = data.get('name', '')
    age = data.get('age', 0)
    email = data.get('email', '')

    # 格式化输出
    result = f"Name: {name}, Age: {age}, Email: {email}"
    return result
''')

        query = f"把 {test_file} 中的 process_data 函数拆分成更小的函数：validate_data, extract_fields, format_output"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file", "write_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证重构结果
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有多个函数定义
        func_count = content.count("def ")
        assert func_count >= 2, f"应该有多个函数定义，实际只有 {func_count} 个"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2SearchAndModify:
    """L2: 搜索并修改场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_search_and_modify(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 搜索特定模式并修改

        用户指令: "找到所有使用 print 的地方，改成使用 logging"

        预期:
        1. jiuwen 使用 grep 搜索
        2. jiuwen 读取相关文件
        3. jiuwen 编辑文件替换 print
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "app.py")
        with open(test_file, 'w') as f:
            f.write('''def main():
    print("Starting application")
    result = process()
    print(f"Result: {result}")
    print("Done")

def process():
    print("Processing...")
    return 42
''')

        query = f"在 {test_file} 中，把所有的 print 语句改成使用 logging.info（需要先导入 logging）"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "grep", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证修改结果
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有 logging 导入或使用
        has_logging = (
            "import logging" in content or
            "from logging" in content or
            "logging.info" in content or
            "logging.debug" in content
        )
        assert has_logging, \
            f"应该导入或使用 logging，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2ExtractConfig:
    """L2: 提取配置场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_extract_config(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 把硬编码的值提取到配置文件

        用户指令: "把硬编码的配置提取到单独的配置文件"

        预期:
        1. jiuwen 读取源文件
        2. jiuwen 创建配置文件
        3. jiuwen 修改源文件引用配置
        """
        # 创建有硬编码配置的文件
        app_file = os.path.join(temp_project, "app.py")
        with open(app_file, 'w') as f:
            f.write('''def connect_db():
    host = "localhost"
    port = 5432
    database = "myapp"
    return f"postgresql://{host}:{port}/{database}"
''')

        config_file = os.path.join(temp_project, "config.py")
        query = f"把 {app_file} 中的数据库配置（host, port, database）提取到 {config_file}，然后修改 app.py 使用配置文件中的值"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "write_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证配置文件存在
        assert_file_exists(config_file)

        # 验证配置文件内容
        with open(config_file, 'r') as f:
            config_content = f.read()

        assert "localhost" in config_content or "5432" in config_content, \
            f"配置文件应该包含配置值，实际内容: {config_content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2AddInputValidation:
    """L2: 添加输入验证场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_input_validation(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 给函数添加参数验证

        用户指令: "给 create_user 函数添加参数验证"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 添加验证逻辑
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "user.py")
        with open(test_file, 'w') as f:
            f.write('''def create_user(name, email, age):
    return {"name": name, "email": email, "age": age}
''')

        query = f"给 {test_file} 中的 create_user 函数添加参数验证：name 不能为空，email 必须包含 @，age 必须是正整数"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证验证逻辑被添加
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有验证逻辑
        has_validation = (
            "if not name" in content or
            "if name" in content or
            "@" in content or
            "raise" in content or
            "ValueError" in content
        )
        assert has_validation, f"应该有验证逻辑，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l2
class TestL2AddCaching:
    """L2: 添加缓存场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_caching(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 给函数添加缓存

        用户指令: "给 expensive_calculation 函数添加缓存"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 添加缓存装饰器
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "calc.py")
        with open(test_file, 'w') as f:
            f.write('''def expensive_calculation(n):
    result = 0
    for i in range(n):
        result += i ** 2
    return result
''')

        query = f"给 {test_file} 中的 expensive_calculation 函数添加 lru_cache 缓存"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证缓存被添加
        with open(test_file, 'r') as f:
            content = f.read()

        # 应该有缓存相关代码
        has_cache = (
            "lru_cache" in content or
            "cache" in content.lower() or
            "functools" in content
        )
        assert has_cache, f"应该有缓存代码，实际内容: {content}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
