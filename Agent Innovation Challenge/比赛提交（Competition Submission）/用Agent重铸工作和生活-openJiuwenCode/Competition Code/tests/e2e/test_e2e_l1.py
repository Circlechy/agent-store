"""
L1 简单场景 E2E 测试

这些测试通过真实的 jiuwen CLI 命令来验证简单的单文件任务。
每个测试模拟一个真实的用户场景。

运行方式:
    pytest tests/e2e/test_e2e_l1.py -v -m e2e

    # 显示详细输出
    E2E_VERBOSE=1 pytest tests/e2e/test_e2e_l1.py -v -m e2e
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
@pytest.mark.scenario_l1
class TestL1ReadFile:
    """L1: 读取文件场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_read_file_and_explain(self, runner: JiuwenRunner, sample_python_file: str):
        """
        场景: 用户请求读取并解释一个文件

        用户指令: "读取 sample.py 文件并告诉我它有什么函数"

        预期:
        1. jiuwen 调用 read_file 工具
        2. jiuwen 返回文件内容的解释
        """
        query = f"读取 {sample_python_file} 文件并告诉我它有什么函数"

        response = await runner.run(query, timeout=60)

        # 验证调用了 read_file
        assert_tool_called(response, "read_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证响应中提到了函数名
        assert_response_mentions(response, ["add", "subtract", "函数"])


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1AddDocstring:
    """L1: 添加文档字符串场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_docstring(self, runner: JiuwenRunner, no_docstring_file: str):
        """
        场景: 给函数添加 docstring

        用户指令: "给 calculate_average 函数添加 docstring"

        预期:
        1. jiuwen 调用 read_file 读取文件
        2. jiuwen 调用 edit_file 添加 docstring
        3. 文件中包含新的 docstring
        """
        query = f"给 {no_docstring_file} 中的 calculate_average 函数添加 docstring"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件被修改
        with open(no_docstring_file, 'r') as f:
            content = f.read()

        # 应该有 docstring（三引号）
        assert '"""' in content or "'''" in content, \
            f"文件应该包含 docstring，实际内容: {content[:300]}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1FixSyntaxError:
    """L1: 修复语法错误场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_fix_syntax_error(self, runner: JiuwenRunner, syntax_error_file: str):
        """
        场景: 修复语法错误

        用户指令: "修复这个文件的语法错误"

        预期:
        1. jiuwen 调用 read_file 读取文件
        2. jiuwen 调用 edit_file 修复错误
        3. 修复后的文件可以被 Python 解析
        """
        query = f"修复 {syntax_error_file} 的语法错误"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证语法正确 - 尝试编译
        import py_compile
        try:
            py_compile.compile(syntax_error_file, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"修复后的文件仍有语法错误: {e}")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1CreateFile:
    """L1: 创建新文件场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_create_hello_world(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 创建一个简单的 Python 文件

        用户指令: "创建一个 hello.py 文件，包含一个打印 Hello World 的函数"

        预期:
        1. jiuwen 调用 write_file 创建文件
        2. 文件存在且包含正确的代码
        """
        target_file = os.path.join(temp_project, "hello.py")
        query = f"在 {temp_project} 目录下创建一个 hello.py 文件，包含一个打印 Hello World 的函数"

        response = await runner.run(query, timeout=90)

        # 验证调用了 write_file
        assert_tool_called(response, "write_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        assert_file_exists(target_file)

        # 验证文件内容
        with open(target_file, 'r') as f:
            content = f.read()

        assert "def " in content, "文件应该包含函数定义"
        assert "hello" in content.lower() or "print" in content.lower(), \
            "文件应该包含 hello 或 print"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1RunCommand:
    """L1: 运行命令场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_run_python_version(self, runner: JiuwenRunner):
        """
        场景: 运行简单的 shell 命令

        用户指令: "运行 python3 --version 命令"

        预期:
        1. jiuwen 调用 bash 工具
        2. 返回 Python 版本信息
        """
        query = "运行 python3 --version 命令并告诉我结果"

        response = await runner.run(query, timeout=60)

        # 验证调用了 bash
        assert_tool_called(response, "bash")

        # 验证没有错误
        assert_no_errors(response)

        # 验证响应中包含版本信息
        assert_response_mentions(response, ["python", "3.", "版本"])


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1RenameVariable:
    """L1: 重命名变量场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_rename_variable(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 重命名变量

        用户指令: "把变量 x 重命名为 count"

        预期:
        1. jiuwen 调用 read_file 读取文件
        2. jiuwen 调用 edit_file 重命名变量
        3. 所有 x 都被替换为 count
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "counter.py")
        with open(test_file, 'w') as f:
            f.write('''def count_items(items):
    x = 0
    for item in items:
        x = x + 1
    return x
''')

        query = f"在 {test_file} 中把变量 x 重命名为 count"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证变量被重命名
        with open(test_file, 'r') as f:
            content = f.read()

        assert "count" in content, f"变量应该被重命名为 count，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1AddTypeHints:
    """L1: 添加类型注解场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_add_type_hints(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 给函数添加类型注解

        用户指令: "给这个函数添加类型注解"

        预期:
        1. jiuwen 调用 read_file 读取文件
        2. jiuwen 调用 edit_file 添加类型注解
        3. 函数签名包含类型注解
        """
        # 创建测试文件
        test_file = os.path.join(temp_project, "math_utils.py")
        with open(test_file, 'w') as f:
            f.write('''def add_numbers(a, b):
    return a + b

def multiply(x, y):
    return x * y
''')

        query = f"给 {test_file} 中的 add_numbers 函数添加类型注解（参数是 int，返回值也是 int）"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证类型注解被添加
        with open(test_file, 'r') as f:
            content = f.read()

        # 检查是否有类型注解
        assert "int" in content or ":" in content.split("def add_numbers")[1].split(")")[0], \
            f"函数应该有类型注解，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_l1
class TestL1FormatCode:
    """L1: 格式化代码场景"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_format_indentation(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 格式化代码缩进

        用户指令: "格式化这个文件的缩进"

        预期:
        1. jiuwen 读取文件
        2. jiuwen 修复缩进问题
        3. 代码可执行
        """
        # 创建有缩进问题的文件
        test_file = os.path.join(temp_project, "bad_indent.py")
        with open(test_file, 'w') as f:
            f.write('''def foo():
 x = 1
  y = 2
 return x + y
''')

        query = f"修复 {test_file} 的缩进问题，使用 4 个空格缩进"

        response = await runner.run(query, timeout=90)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证语法正确
        import py_compile
        try:
            py_compile.compile(test_file, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"格式化后的文件有语法错误: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
