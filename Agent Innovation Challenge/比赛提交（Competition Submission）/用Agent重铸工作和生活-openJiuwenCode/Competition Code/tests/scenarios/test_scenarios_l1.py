"""
L1 简单场景测试

测试用例覆盖 docs/03-测试用例设计.md 中 10.2 节的所有 L1 用例
这些测试验证 Agent 在简单单文件任务中的能力
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


# 获取 fixtures 路径
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios" / "l1_simple"


class TestL1ExplainFunction:
    """测试解释函数功能"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_explain_function_read_file(self, mode_manager, temp_dir):
        """
        场景: 用户请求解释一个函数
        预期: Agent 能正确读取文件内容

        这是 L1 测试的基础 - 验证读取能力
        """
        read_tool = ReadFileTool(mode_manager)

        # 复制测试文件到临时目录
        source_file = FIXTURES_DIR / "no_docstring.py"
        target_file = os.path.join(temp_dir, "no_docstring.py")
        shutil.copy(source_file, target_file)

        # 读取文件
        result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))

        assert result.success == True
        assert "def calculate_average" in result.data["content"]
        assert "def find_max" in result.data["content"]


class TestL1AddDocstring:
    """测试添加文档字符串"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_add_docstring_workflow(self, mode_manager, temp_dir):
        """
        场景: 给函数添加 docstring
        预期: read_file → edit_file 流程
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 复制测试文件
        source_file = FIXTURES_DIR / "no_docstring.py"
        target_file = os.path.join(temp_dir, "no_docstring.py")
        shutil.copy(source_file, target_file)

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 添加 docstring
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)''',
            "new_string": '''def calculate_average(numbers):
    """计算数字列表的平均值。

    Args:
        numbers: 数字列表

    Returns:
        平均值，如果列表为空则返回 0
    """
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)'''
        }))

        assert edit_result.success == True

        # 3. 验证 docstring 已添加
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert '"""计算数字列表的平均值' in read_result2.data["content"]
        assert "Args:" in read_result2.data["content"]
        assert "Returns:" in read_result2.data["content"]


class TestL1FixSyntaxError:
    """测试修复语法错误"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_fix_syntax_error_workflow(self, mode_manager, temp_dir):
        """
        场景: 修复语法错误
        预期: read_file → edit_file 修复错误
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建有语法错误的文件
        target_file = os.path.join(temp_dir, "syntax_error.py")
        with open(target_file, 'w') as f:
            f.write('''"""有语法错误的文件"""

def calculate_sum(a, b)  # 缺少冒号
    return a + b
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True
        assert "def calculate_sum(a, b)" in read_result.data["content"]

        # 2. 修复语法错误 - 添加冒号
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": "def calculate_sum(a, b)  # 缺少冒号",
            "new_string": "def calculate_sum(a, b):  # 已修复"
        }))
        assert edit_result.success == True

        # 3. 验证语法正确 - 尝试编译
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL1RenameVariable:
    """测试变量重命名"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_rename_variable_workflow(self, mode_manager, temp_dir):
        """
        场景: 把变量 x 重命名为 count
        预期: read_file → edit_file (replace_all)
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 复制测试文件
        source_file = FIXTURES_DIR / "bad_naming.py"
        target_file = os.path.join(temp_dir, "bad_naming.py")
        shutil.copy(source_file, target_file)

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 重命名变量 t 为 weighted_average
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": "    t = x * 0.5 + y * 0.3 + z * 0.2\n    return t",
            "new_string": "    weighted_average = x * 0.5 + y * 0.3 + z * 0.2\n    return weighted_average"
        }))
        assert edit_result.success == True

        # 3. 验证重命名
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "weighted_average" in read_result2.data["content"]
        assert "return weighted_average" in read_result2.data["content"]


class TestL1AddTypeHints:
    """测试添加类型注解"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_add_type_hints_workflow(self, mode_manager, temp_dir):
        """
        场景: 给函数添加类型注解
        预期: read_file → edit_file
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 复制测试文件
        source_file = FIXTURES_DIR / "no_type_hints.py"
        target_file = os.path.join(temp_dir, "no_type_hints.py")
        shutil.copy(source_file, target_file)

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True

        # 2. 添加类型注解
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": "def add_numbers(a, b):\n    return a + b",
            "new_string": "def add_numbers(a: int, b: int) -> int:\n    return a + b"
        }))
        assert edit_result.success == True

        # 3. 验证类型注解
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "def add_numbers(a: int, b: int) -> int:" in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True


class TestL1RunAndExplainError:
    """测试运行脚本并解释错误"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_run_and_explain_error_workflow(self, mode_manager, temp_dir):
        """
        场景: 运行脚本并解释错误
        预期: bash → 分析输出
        """
        bash_tool = BashTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 复制测试文件
        source_file = FIXTURES_DIR / "error_script.py"
        target_file = os.path.join(temp_dir, "error_script.py")
        shutil.copy(source_file, target_file)

        # 1. 运行脚本 - 预期会失败
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 {target_file}",
            "timeout": 10
        }))

        # 脚本应该失败（除零错误）
        assert bash_result.success == False
        assert "ZeroDivisionError" in bash_result.data.get("stderr", "") or \
               "ZeroDivisionError" in bash_result.data.get("stdout", "") or \
               "division by zero" in str(bash_result.data)

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_run_successful_script(self, mode_manager, temp_dir):
        """
        场景: 运行成功的脚本
        预期: bash 执行成功
        """
        bash_tool = BashTool(mode_manager)

        # 创建一个会成功的脚本
        target_file = os.path.join(temp_dir, "success_script.py")
        with open(target_file, 'w') as f:
            f.write('''
def divide_numbers(a, b):
    if b == 0:
        return "Cannot divide by zero"
    return a / b

if __name__ == "__main__":
    result = divide_numbers(10, 2)
    print(f"Result: {result}")
''')

        # 运行脚本
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 {target_file}",
            "timeout": 10
        }))

        assert bash_result.success == True
        assert "Result: 5.0" in bash_result.data["stdout"]


class TestL1CompleteWorkflow:
    """测试完整的 L1 工作流"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_l1
    async def test_complete_l1_workflow(self, mode_manager, temp_dir):
        """
        完整 L1 工作流: 读取 → 理解 → 修改 → 验证

        模拟用户请求: "给这个函数添加 docstring 和类型注解"
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建测试文件
        target_file = os.path.join(temp_dir, "simple_function.py")
        with open(target_file, 'w') as f:
            f.write('''def greet(name):
    return f"Hello, {name}!"
''')

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert read_result.success == True
        assert "def greet(name):" in read_result.data["content"]

        # 2. 添加 docstring 和类型注解
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": target_file,
            "old_string": '''def greet(name):
    return f"Hello, {name}!"''',
            "new_string": '''def greet(name: str) -> str:
    """生成问候语。

    Args:
        name: 要问候的人的名字

    Returns:
        问候语字符串
    """
    return f"Hello, {name}!"'''
        }))
        assert edit_result.success == True

        # 3. 验证修改
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": target_file
        }))
        assert "def greet(name: str) -> str:" in read_result2.data["content"]
        assert '"""生成问候语' in read_result2.data["content"]

        # 4. 验证语法正确
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -m py_compile {target_file}",
            "timeout": 10
        }))
        assert bash_result.success == True

        # 5. 验证功能正常
        bash_result2 = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -c \"import sys; sys.path.insert(0, '{temp_dir}'); from simple_function import greet; print(greet('World'))\"",
            "timeout": 10
        }))
        assert bash_result2.success == True
        assert "Hello, World!" in bash_result2.data["stdout"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "scenario_l1"])
