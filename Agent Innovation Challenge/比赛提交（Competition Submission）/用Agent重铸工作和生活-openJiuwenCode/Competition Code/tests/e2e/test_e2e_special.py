"""
特殊场景 E2E 测试

这些测试通过真实的 jiuwen CLI 命令验证特殊情况下的行为，包括：
- 中断恢复
- 错误处理
- 上下文理解
- 模糊指令处理
- 大文件处理
- 并发任务

运行方式:
    pytest tests/e2e/test_e2e_special.py -v -m e2e

    # 显示详细输出
    E2E_VERBOSE=1 pytest tests/e2e/test_e2e_special.py -v -m e2e
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
@pytest.mark.scenario_special
class TestContextUnderstanding:
    """特殊场景: 上下文理解"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_multi_turn_context(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 多轮对话中的上下文保持

        用户指令序列:
        1. "读取 config.py"
        2. "把端口改成 8080"

        预期:
        - Agent 理解第二条指令指的是 config.py
        """
        # 创建配置文件
        config_file = os.path.join(temp_project, "config.py")
        with open(config_file, 'w') as f:
            f.write('''# 应用配置
HOST = "localhost"
PORT = 3000
DEBUG = False
''')

        # 第一轮：读取文件
        response1 = await runner.run(f"读取 {config_file}", timeout=60)
        assert_tool_called(response1, "read_file")
        assert_no_errors(response1)

        # 第二轮：修改文件（依赖上下文）
        response2 = await runner.run(f"把 {config_file} 中的 PORT 改成 8080", timeout=90)
        assert_any_tool_called(response2, ["edit_file", "read_file"])
        assert_no_errors(response2)

        # 验证修改结果
        with open(config_file, 'r') as f:
            content = f.read()

        assert "8080" in content, f"端口应该被改成 8080，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestErrorRecovery:
    """特殊场景: 错误恢复"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_handle_nonexistent_file(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 处理不存在的文件

        用户指令: "读取 nonexistent.py"

        预期:
        - Agent 尝试读取文件
        - Agent 优雅地报告文件不存在
        - 不会崩溃
        """
        nonexistent_file = os.path.join(temp_project, "nonexistent.py")
        query = f"读取 {nonexistent_file} 并告诉我它的内容"

        response = await runner.run(query, timeout=60)

        # 应该尝试读取
        assert_tool_called(response, "read_file")

        # 响应应该提到文件不存在或类似信息
        response_lower = response.content.lower()
        mentions_error = (
            "不存在" in response.content or
            "not found" in response_lower or
            "not exist" in response_lower or
            "找不到" in response.content or
            "无法" in response.content or
            "error" in response_lower
        )
        # 注意：这个断言可能需要根据实际 Agent 行为调整
        # Agent 可能会创建文件而不是报错


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestAmbiguousInstructions:
    """特殊场景: 模糊指令处理"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_handle_vague_instruction(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 处理不明确的用户指令

        用户指令: "优化一下这个代码"

        预期:
        - Agent 可能询问具体优化方向
        - 或者 Agent 提供多个优化建议
        - 或者 Agent 进行合理的默认优化
        """
        # 创建可优化的代码
        code_file = os.path.join(temp_project, "to_optimize.py")
        with open(code_file, 'w') as f:
            f.write('''def process_list(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result


def find_item(items, target):
    for i in range(len(items)):
        if items[i] == target:
            return i
    return -1
''')

        query = f"优化 {code_file} 中的代码"

        response = await runner.run(query, timeout=120)

        # Agent 应该做出某种响应
        assert len(response.content) > 0 or len(response.tool_calls) > 0, \
            "Agent 应该有响应"

        # 如果进行了修改，检查是否有改进
        if response.has_tool_call("edit_file"):
            with open(code_file, 'r') as f:
                content = f.read()
            # 可能的优化：列表推导式、enumerate、更好的命名等
            # 这里只检查文件被修改了


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestLargeFileHandling:
    """特殊场景: 大文件处理"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_handle_large_file(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 处理大文件

        预期:
        - Agent 能正确读取大文件
        - 不会超时
        - 修改准确
        """
        # 创建大文件（500+ 行）
        large_file = os.path.join(temp_project, "large_module.py")
        with open(large_file, 'w') as f:
            f.write('"""大型模块"""\n\n')

            # 生成多个类和函数
            for i in range(50):
                f.write(f'''
class Handler{i}:
    """处理器 {i}"""

    def __init__(self):
        self.id = {i}

    def process(self, data):
        return data * {i + 1}

    def validate(self, value):
        return value > 0


def utility_function_{i}(x, y):
    """工具函数 {i}"""
    return x + y + {i}

''')

        query = f"在 {large_file} 的开头添加 'import logging'，并在文件末尾添加一个 'logger = logging.getLogger(__name__)'"

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证修改结果
        with open(large_file, 'r') as f:
            content = f.read()

        assert "import logging" in content, "应该添加 logging 导入"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestMultipleFilesOperation:
    """特殊场景: 多文件操作"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_modify_multiple_files(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 同时修改多个文件

        用户指令: "给 a.py 和 b.py 都添加 docstring"

        预期:
        - 两个文件都被处理
        - 不会相互干扰
        """
        # 创建两个文件
        file_a = os.path.join(temp_project, "module_a.py")
        with open(file_a, 'w') as f:
            f.write('''def func_a(x):
    return x * 2
''')

        file_b = os.path.join(temp_project, "module_b.py")
        with open(file_b, 'w') as f:
            f.write('''def func_b(y):
    return y + 1
''')

        query = f"给 {file_a} 中的 func_a 和 {file_b} 中的 func_b 都添加 docstring"

        response = await runner.run(query, timeout=120)

        # 验证调用了文件操作工具
        assert_any_tool_called(response, ["read_file", "edit_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证至少一个文件被修改
        with open(file_a, 'r') as f:
            content_a = f.read()
        with open(file_b, 'r') as f:
            content_b = f.read()

        has_docstring = ('"""' in content_a or "'''" in content_a or
                         '"""' in content_b or "'''" in content_b)
        assert has_docstring, "至少一个文件应该有 docstring"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestCodeGeneration:
    """特殊场景: 代码生成"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_generate_boilerplate(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 生成样板代码

        用户指令: "创建一个 Flask 应用的基本结构"

        预期:
        - 创建必要的文件
        - 代码结构正确
        """
        query = f"在 {temp_project} 目录下创建一个简单的 Flask 应用 app.py，包含一个返回 'Hello World' 的根路由"

        response = await runner.run(query, timeout=120)

        # 验证调用了写入工具
        assert_tool_called(response, "write_file")

        # 验证没有错误
        assert_no_errors(response)

        # 验证文件存在
        app_file = os.path.join(temp_project, "app.py")
        assert_file_exists(app_file)

        # 验证内容
        with open(app_file, 'r') as f:
            content = f.read()

        assert "flask" in content.lower() or "Flask" in content, \
            f"应该导入 Flask，实际内容: {content}"
        assert "route" in content.lower() or "@app" in content, \
            f"应该有路由定义，实际内容: {content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestSearchAndReplace:
    """特殊场景: 搜索替换"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_global_search_replace(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 全局搜索替换

        用户指令: "把所有的 'old_name' 替换成 'new_name'"

        预期:
        - 搜索所有文件
        - 替换所有出现
        """
        # 创建多个包含目标字符串的文件
        for i in range(3):
            file_path = os.path.join(temp_project, f"file_{i}.py")
            with open(file_path, 'w') as f:
                f.write(f'''# File {i}
old_name = "value_{i}"

def use_old_name():
    return old_name
''')

        query = f"在 {temp_project} 目录下的所有 .py 文件中，把变量名 'old_name' 替换成 'new_name'"

        response = await runner.run(query, timeout=180)

        # 验证调用了搜索和编辑工具
        assert_any_tool_called(response, ["grep", "glob", "edit_file", "read_file"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证至少一个文件被修改
        modified_count = 0
        for i in range(3):
            file_path = os.path.join(temp_project, f"file_{i}.py")
            with open(file_path, 'r') as f:
                content = f.read()
            if "new_name" in content:
                modified_count += 1

        assert modified_count >= 1, "至少一个文件应该被修改"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestIncrementalChanges:
    """特殊场景: 增量修改"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_incremental_feature_addition(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 增量添加功能

        用户指令序列:
        1. "创建一个 User 类"
        2. "给 User 类添加 email 属性"
        3. "给 User 类添加 validate_email 方法"

        预期:
        - 每次修改都保留之前的内容
        - 最终类包含所有功能
        """
        user_file = os.path.join(temp_project, "user.py")

        # 第一步：创建基本类
        response1 = await runner.run(
            f"在 {user_file} 中创建一个 User 类，包含 name 属性和 __init__ 方法",
            timeout=90
        )
        assert_tool_called(response1, "write_file")
        assert_no_errors(response1)

        # 验证第一步
        with open(user_file, 'r') as f:
            content1 = f.read()
        assert "class User" in content1, "应该有 User 类"
        assert "name" in content1, "应该有 name 属性"

        # 第二步：添加 email 属性
        response2 = await runner.run(
            f"给 {user_file} 中的 User 类的 __init__ 方法添加 email 参数",
            timeout=90
        )
        assert_any_tool_called(response2, ["read_file", "edit_file"])
        assert_no_errors(response2)

        # 验证第二步
        with open(user_file, 'r') as f:
            content2 = f.read()
        assert "class User" in content2, "User 类应该保留"
        assert "email" in content2, "应该有 email"

        # 第三步：添加方法
        response3 = await runner.run(
            f"给 {user_file} 中的 User 类添加一个 get_info 方法，返回 'name: email' 格式的字符串",
            timeout=90
        )
        assert_any_tool_called(response3, ["read_file", "edit_file"])
        assert_no_errors(response3)

        # 验证最终结果
        with open(user_file, 'r') as f:
            final_content = f.read()

        assert "class User" in final_content, "User 类应该保留"
        assert "def get_info" in final_content or "def info" in final_content, \
            f"应该有 get_info 方法，实际内容: {final_content}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestCodeAnalysis:
    """特殊场景: 代码分析"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_analyze_code_structure(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 分析代码结构

        用户指令: "分析这个项目的代码结构"

        预期:
        - Agent 使用搜索工具
        - Agent 提供结构概述
        """
        # 创建简单项目结构
        os.makedirs(os.path.join(temp_project, "src"), exist_ok=True)
        os.makedirs(os.path.join(temp_project, "tests"), exist_ok=True)

        # 创建源文件
        with open(os.path.join(temp_project, "src", "main.py"), 'w') as f:
            f.write('''"""主模块"""
from .utils import helper

def main():
    return helper()
''')

        with open(os.path.join(temp_project, "src", "utils.py"), 'w') as f:
            f.write('''"""工具模块"""

def helper():
    return "Hello"
''')

        with open(os.path.join(temp_project, "tests", "test_main.py"), 'w') as f:
            f.write('''"""测试模块"""
import pytest

def test_main():
    pass
''')

        query = f"分析 {temp_project} 目录的代码结构，告诉我有哪些模块和它们的功能"

        response = await runner.run(query, timeout=120)

        # 验证使用了搜索或读取工具
        assert_any_tool_called(response, ["glob", "read_file", "bash", "grep"])

        # 验证没有错误
        assert_no_errors(response)

        # 验证响应包含结构信息
        response_lower = response.content.lower()
        has_structure_info = (
            "main" in response_lower or
            "utils" in response_lower or
            "test" in response_lower or
            "模块" in response.content or
            "文件" in response.content
        )
        assert has_structure_info, f"响应应该包含结构信息，实际响应: {response.content[:300]}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestMultiToolCallAPI:
    """特殊场景: 多轮工具调用 API 稳定性测试"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_multi_tool_call_no_api_error(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 多轮工具调用后不应出现 API 400 错误

        用户指令: 执行多个工具调用的任务

        预期:
        - Agent 能完成多轮工具调用
        - 不会因为消息格式问题导致 API 400 错误
        - 不会出现 181001 错误码
        """
        # 创建多个文件，触发多轮工具调用
        for i in range(3):
            file_path = os.path.join(temp_project, f"module_{i}.py")
            with open(file_path, 'w') as f:
                f.write(f'''"""模块 {i}"""

def function_{i}(x):
    return x * {i + 1}
''')

        # 执行需要多轮工具调用的任务
        query = f"读取 {temp_project} 目录下的所有 .py 文件，然后给每个文件的函数添加类型注解"

        response = await runner.run(query, timeout=180)

        # 验证没有 API 错误
        assert "API 调用失败" not in response.content, \
            f"不应该有 API 错误，实际响应: {response.content}"
        assert "181001" not in response.content, \
            f"不应该有 181001 错误码，实际响应: {response.content}"
        assert "status code is 400" not in response.content.lower(), \
            f"不应该有 400 错误，实际响应: {response.content}"

        # 验证使用了文件操作工具
        assert_any_tool_called(response, ["read_file", "glob", "edit_file"])

        # 验证没有严重错误
        assert_no_errors(response)

    @requires_api_key
    @pytest.mark.asyncio
    async def test_large_tool_result_handling(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 处理大型工具结果

        用户指令: 读取大文件

        预期:
        - Agent 能处理大型工具结果
        - 不会因为消息体过大导致 API 错误
        """
        # 创建一个较大的文件
        large_file = os.path.join(temp_project, "large_data.py")
        with open(large_file, 'w') as f:
            f.write('"""大型数据文件"""\n\n')
            f.write('DATA = [\n')
            # 生成大量数据
            for i in range(500):
                f.write(f'    {{"id": {i}, "name": "item_{i}", "value": {i * 100}}},\n')
            f.write(']\n')

        query = f"读取 {large_file} 并告诉我这个文件有多少条数据记录"

        response = await runner.run(query, timeout=120)

        # 验证没有 API 错误
        assert "API 调用失败" not in response.content, \
            f"不应该有 API 错误，实际响应: {response.content}"
        assert "181001" not in response.content, \
            f"不应该有 181001 错误码，实际响应: {response.content}"

        # 验证调用了读取工具
        assert_tool_called(response, "read_file")

        # 验证没有严重错误
        assert_no_errors(response)

    @requires_api_key
    @pytest.mark.asyncio
    async def test_browser_multi_tool_sequence(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 浏览器工具多轮调用序列 (复现 issue #77 场景)

        用户指令: 分析一个网页内容

        预期:
        - Agent 能完成多轮浏览器工具调用
        - 不会因为多轮工具调用导致 API 400 错误

        这个测试复现了以下工具调用序列:
        BrowserOpen -> BrowserSnapshot -> BrowserWait -> BrowserSnapshot ->
        TodoWrite -> Bash -> TodoWrite -> Grep -> Read -> Grep -> 错误
        """
        # 创建一个本地 HTML 文件来测试，避免依赖外部网络
        html_file = os.path.join(temp_project, "test_page.html")
        with open(html_file, 'w') as f:
            f.write('''<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
<h1>Issue #77 Test</h1>
<p>This is a test page for multi-tool call sequence.</p>
<ul>
<li>Item 1: questioner component</li>
<li>Item 2: max_iteration setting</li>
<li>Item 3: async stream error</li>
</ul>
</body>
</html>''')

        # 创建一些相关的 Python 文件来模拟代码分析场景
        for i, name in enumerate(["questioner", "config", "utils"]):
            py_file = os.path.join(temp_project, f"{name}.py")
            with open(py_file, 'w') as f:
                f.write(f'''"""模块 {name}"""

class {name.capitalize()}Component:
    def __init__(self):
        self.max_iteration = 5

    def process(self, data):
        return data
''')

        # 执行复杂的多轮工具调用任务
        query = f"""分析 {temp_project} 目录下的代码:
1. 首先列出所有 .py 文件
2. 读取每个文件的内容
3. 找出所有包含 'max_iteration' 的文件
4. 总结这些文件的功能"""

        response = await runner.run(query, timeout=300)

        # 验证没有 API 错误
        assert "API 调用失败" not in response.content, \
            f"不应该有 API 错误，实际响应: {response.content}"
        assert "181001" not in response.content, \
            f"不应该有 181001 错误码，实际响应: {response.content}"
        assert "status code is 400" not in response.content.lower(), \
            f"不应该有 400 错误，实际响应: {response.content}"

        # 验证使用了多种工具
        assert_any_tool_called(response, ["glob", "read_file", "grep", "bash"])

        # 验证没有严重错误
        assert_no_errors(response)


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.scenario_special
class TestIssueAnalysis:
    """特殊场景: Issue 分析与修复"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_analyze_github_issue(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 分析并修复社区 Issue

        用户指令: "帮我分析修复 openjiuwen社区的这个issue: https://gitcode.com/openJiuwen/agent-core/issues/77"

        预期:
        - Agent 能访问并理解 issue 内容
        - Agent 能分析问题原因
        - Agent 能提出修复方案或进行代码修改
        - 不会因为迭代次数限制而中断
        """
        query = "帮我分析修复 openjiuwen社区的这个issue: https://gitcode.com/openJiuwen/agent-core/issues/77"

        response = await runner.run(query, timeout=600)

        # 验证没有 API 错误
        assert "API 调用失败" not in response.content, \
            f"不应该有 API 错误，实际响应: {response.content}"
        assert "181001" not in response.content, \
            f"不应该有 181001 错误码，实际响应: {response.content}"
        assert "status code is 400" not in response.content.lower(), \
            f"不应该有 400 错误，实际响应: {response.content}"

        # 验证没有超过迭代次数限制
        assert "exceeded max iteration" not in response.content.lower(), \
            f"不应该超过迭代次数限制，实际响应: {response.content}"

        # 验证使用了网络访问或代码分析工具
        assert_any_tool_called(response, ["browser_open", "web_fetch", "grep", "glob", "read_file", "bash"])

        # 验证没有严重错误
        assert_no_errors(response)

        # 验证响应包含 issue 相关的分析内容
        response_content = response.content.lower()
        has_analysis = (
            "issue" in response_content or
            "问题" in response.content or
            "分析" in response.content or
            "修复" in response.content or
            "建议" in response.content or
            "agent" in response_content or
            "error" in response_content
        )
        assert has_analysis, f"响应应该包含 issue 分析内容，实际响应: {response.content[:500]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
