"""
工具系统单元测试
"""

import pytest
import asyncio
import sys
from pathlib import Path

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool


class TestReadFileTool:
    """测试文件读取工具"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def read_tool(self, mode_manager):
        return ReadFileTool(mode_manager)

    @pytest.mark.asyncio
    async def test_read_file_success(self, read_tool):
        """测试成功读取文件"""
        inputs = ToolInput(data={
            "file_path": "README.md",
            "limit": 5
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data is not None
        assert "content" in result.data
        assert result.data["line_count"] == 5

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, read_tool):
        """测试读取不存在的文件"""
        inputs = ToolInput(data={
            "file_path": "/nonexistent/file.txt"
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_read_file_in_plan_mode(self, mode_manager):
        """测试 PLAN 模式下读取文件"""
        mode_manager.switch_mode(AgentMode.PLAN)
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": "README.md",
            "limit": 3
        })

        result = await read_tool.ainvoke(inputs)

        # PLAN 模式下读取文件应该成功
        assert result.success == True


class TestWriteFileTool:
    """测试文件写入工具"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def write_tool(self, mode_manager):
        return WriteFileTool(mode_manager)

    @pytest.mark.asyncio
    async def test_write_file_in_build_mode(self, write_tool):
        """测试 BUILD 模式下写文件"""
        inputs = ToolInput(data={
            "file_path": "/tmp/test_opencode.txt",
            "content": "Hello from openjiuwen-code!"
        })

        result = await write_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data["bytes_written"] > 0

    @pytest.mark.asyncio
    async def test_write_file_blocked_in_plan_mode(self, mode_manager):
        """测试 PLAN 模式下写文件被阻止"""
        mode_manager.switch_mode(AgentMode.PLAN)
        write_tool = WriteFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": "/tmp/test.txt",
            "content": "This should be blocked"
        })

        result = await write_tool.ainvoke(inputs)

        assert result.success == False
        assert "不可用" in result.error


class TestBashTool:
    """测试 Bash 工具"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def bash_tool(self, mode_manager):
        return BashTool(mode_manager)

    @pytest.mark.asyncio
    async def test_bash_safe_command(self, bash_tool):
        """测试执行安全命令"""
        inputs = ToolInput(data={
            "command": "echo 'Hello, World!'",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == True
        assert "Hello, World!" in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_bash_blacklisted_command(self, bash_tool):
        """测试黑名单命令被阻止"""
        inputs = ToolInput(data={
            "command": "rm -rf /",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    @pytest.mark.asyncio
    async def test_bash_destructive_in_plan_mode(self, mode_manager):
        """测试 PLAN 模式下破坏性命令被阻止"""
        mode_manager.switch_mode(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "rm file.txt",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    @pytest.mark.asyncio
    async def test_bash_readonly_in_plan_mode(self, mode_manager):
        """测试 PLAN 模式下只读命令允许"""
        mode_manager.switch_mode(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "ls -la /tmp",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
