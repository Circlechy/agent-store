"""
特殊场景测试

测试用例覆盖 docs/03-测试用例设计.md 中 10.6 节的所有特殊场景用例
这些测试验证 Agent 在边界情况和异常场景中的处理能力
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


class TestHandleLargeFile:
    """测试处理大文件"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_large_file_with_offset_limit(self, mode_manager, temp_dir):
        """
        场景: 处理 1000+ 行文件
        预期: 使用 offset/limit 分段读取
        """
        read_tool = ReadFileTool(mode_manager)

        # 创建大文件
        large_file = os.path.join(temp_dir, "large_file.py")
        with open(large_file, 'w') as f:
            f.write('"""大文件"""\n\n')
            for i in range(1500):
                f.write(f'def function_{i}():\n')
                f.write(f'    """函数 {i}"""\n')
                f.write(f'    return {i}\n\n')

        # 1. 读取前 100 行
        read_result1 = await read_tool.ainvoke(ToolInput(data={
            "file_path": large_file,
            "limit": 100
        }))
        assert read_result1.success == True
        assert read_result1.data["line_count"] == 100

        # 2. 读取中间部分
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": large_file,
            "offset": 500,
            "limit": 100
        }))
        assert read_result2.success == True
        assert "function_12" in read_result2.data["content"]  # 大约在 500 行附近

        # 3. 读取最后部分
        read_result3 = await read_tool.ainvoke(ToolInput(data={
            "file_path": large_file,
            "offset": 5900,
            "limit": 100
        }))
        assert read_result3.success == True


class TestHandleBinaryFile:
    """测试处理二进制文件"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_binary_file(self, mode_manager, temp_dir):
        """
        场景: 遇到二进制文件
        预期: 识别并跳过或提示
        """
        read_tool = ReadFileTool(mode_manager)

        # 创建二进制文件
        binary_file = os.path.join(temp_dir, "binary_file.bin")
        with open(binary_file, 'wb') as f:
            f.write(bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD] * 100))

        # 尝试读取二进制文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": binary_file
        }))

        # 应该返回结果（可能是错误或警告）
        # 不应该崩溃
        assert read_result is not None


class TestHandleEncodingIssue:
    """测试处理编码问题"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_utf8_file(self, mode_manager, temp_dir):
        """
        场景: 处理 UTF-8 编码文件
        预期: 正确读取中文内容
        """
        read_tool = ReadFileTool(mode_manager)

        # 创建 UTF-8 文件
        utf8_file = os.path.join(temp_dir, "utf8_file.py")
        with open(utf8_file, 'w', encoding='utf-8') as f:
            f.write('''"""中文文档字符串"""

def 你好():
    """打招呼函数"""
    return "你好，世界！"

# 中文注释
变量 = "测试"
''')

        # 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": utf8_file
        }))

        assert read_result.success == True
        assert "中文文档字符串" in read_result.data["content"]
        assert "你好，世界！" in read_result.data["content"]


class TestHandlePermissionDenied:
    """测试处理权限被拒绝"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_permission_denied(self, mode_manager):
        """
        场景: 无权限文件
        预期: 优雅处理错误
        """
        read_tool = ReadFileTool(mode_manager)

        # 尝试读取系统文件（通常无权限）
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": "/etc/shadow"
        }))

        # 应该返回错误，不应该崩溃
        assert read_result.success == False
        assert read_result.error is not None


class TestHandleFileNotFound:
    """测试处理文件不存在"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_file_not_found(self, mode_manager):
        """
        场景: 文件不存在
        预期: 清晰错误信息
        """
        read_tool = ReadFileTool(mode_manager)

        # 尝试读取不存在的文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": "/nonexistent/path/to/file.py"
        }))

        assert read_result.success == False
        assert "不存在" in read_result.error


class TestRecoverFromError:
    """测试从错误中恢复"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_recover_from_error(self, mode_manager, temp_dir):
        """
        场景: 工具执行失败后恢复
        预期: 尝试替代方案或报告
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)

        # 1. 尝试读取不存在的文件 - 失败
        read_result1 = await read_tool.ainvoke(ToolInput(data={
            "file_path": os.path.join(temp_dir, "nonexistent.py")
        }))
        assert read_result1.success == False

        # 2. 创建文件 - 成功
        new_file = os.path.join(temp_dir, "new_file.py")
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": new_file,
            "content": "# New file\nprint('Hello')\n"
        }))
        assert write_result.success == True

        # 3. 读取新创建的文件 - 成功
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": new_file
        }))
        assert read_result2.success == True
        assert "Hello" in read_result2.data["content"]


class TestHandleEmptyFile:
    """测试处理空文件"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_empty_file(self, mode_manager, temp_dir):
        """
        场景: 处理空文件
        预期: 正确处理，不崩溃
        """
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 创建空文件
        empty_file = os.path.join(temp_dir, "empty.py")
        with open(empty_file, 'w') as f:
            pass  # 空文件

        # 1. 读取空文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": empty_file
        }))
        assert read_result.success == True
        assert read_result.data["line_count"] == 0

        # 2. 尝试编辑空文件（应该失败，因为找不到匹配）
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": empty_file,
            "old_string": "something",
            "new_string": "other"
        }))
        assert edit_result.success == False


class TestHandleSpecialCharacters:
    """测试处理特殊字符"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_special_characters_in_content(self, mode_manager, temp_dir):
        """
        场景: 文件内容包含特殊字符
        预期: 正确处理
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 创建包含特殊字符的文件
        special_file = os.path.join(temp_dir, "special.py")
        content = '''"""包含特殊字符的文件"""

# 正则表达式
pattern = r"\\d+\\.\\d+"

# 转义字符
escape_chars = "\\n\\t\\r"

# Unicode
emoji = "🎉🚀💻"

# 引号
quotes = 'He said "Hello"'
'''
        with open(special_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # 1. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": special_file
        }))
        assert read_result.success == True
        assert "emoji" in read_result.data["content"]

        # 2. 编辑包含特殊字符的内容
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": special_file,
            "old_string": 'emoji = "🎉🚀💻"',
            "new_string": 'emoji = "🎉🚀💻🎊"'
        }))
        assert edit_result.success == True


class TestHandleDangerousCommands:
    """测试处理危险命令"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_block_dangerous_commands(self, mode_manager):
        """
        场景: 尝试执行危险命令
        预期: 被阻止
        """
        bash_tool = BashTool(mode_manager)

        dangerous_commands = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs /dev/sda",
            ":(){:|:&};:",  # fork bomb
        ]

        for cmd in dangerous_commands:
            result = await bash_tool.ainvoke(ToolInput(data={
                "command": cmd,
                "timeout": 5
            }))
            assert result.success == False
            assert "阻止" in result.error


class TestHandleModeRestrictions:
    """测试模式限制"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_plan_mode_restrictions(self, temp_dir):
        """
        场景: PLAN 模式下尝试写入
        预期: 被阻止
        """
        plan_mode_manager = AgentModeManager(AgentMode.PLAN)
        write_tool = WriteFileTool(plan_mode_manager)

        result = await write_tool.ainvoke(ToolInput(data={
            "file_path": os.path.join(temp_dir, "test.py"),
            "content": "# Test"
        }))

        assert result.success == False
        assert "不可用" in result.error

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_review_mode_restrictions(self, temp_dir):
        """
        场景: REVIEW 模式下尝试编辑
        预期: 被阻止
        """
        review_mode_manager = AgentModeManager(AgentMode.REVIEW)
        edit_tool = EditFileTool(review_mode_manager)

        # 创建测试文件
        test_file = os.path.join(temp_dir, "test.py")
        with open(test_file, 'w') as f:
            f.write("# Test\n")

        result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": test_file,
            "old_string": "# Test",
            "new_string": "# Modified"
        }))

        assert result.success == False
        assert "不可用" in result.error


class TestHandleTimeout:
    """测试处理超时"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.mark.asyncio
    @pytest.mark.scenario_special
    async def test_handle_command_timeout(self, mode_manager):
        """
        场景: 命令执行超时
        预期: 超时后终止
        """
        bash_tool = BashTool(mode_manager)

        # 执行一个会超时的命令
        result = await bash_tool.ainvoke(ToolInput(data={
            "command": "sleep 10",
            "timeout": 1  # 1 秒超时
        }))

        # 应该超时
        assert result.success == False or "timeout" in str(result.data).lower() or "超时" in str(result.error)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "scenario_special"])
