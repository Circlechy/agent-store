"""
BashTool 安全限制单元测试

测试 PLAN 模式下的命令限制，特别是防止脚本执行绕过
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from packages.server.tools.openjiuwen_tools import BashTool
from packages.server.agents.mode_manager import AgentModeManager, AgentMode


class TestBashToolPlanModeRestrictions:
    """BashTool PLAN 模式限制测试"""

    @pytest.fixture
    def mode_manager(self):
        """创建模式管理器并切换到 PLAN 模式"""
        manager = AgentModeManager()
        manager.switch_mode(AgentMode.PLAN)
        return manager

    @pytest.fixture
    def bash_tool(self, mode_manager):
        """创建 BashTool"""
        return BashTool(mode_manager)

    @pytest.mark.asyncio
    async def test_blocks_mkdir(self, bash_tool):
        """测试阻止 mkdir 命令"""
        result = await bash_tool.ainvoke({"command": "mkdir test_dir"})
        assert "错误" in result
        assert "plan" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_rm(self, bash_tool):
        """测试阻止 rm 命令"""
        result = await bash_tool.ainvoke({"command": "rm test_file"})
        assert "错误" in result
        assert "plan" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_redirect(self, bash_tool):
        """测试阻止重定向"""
        result = await bash_tool.ainvoke({"command": "echo hello > test.txt"})
        assert "错误" in result
        assert "plan" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_python_c(self, bash_tool):
        """测试阻止 python3 -c 脚本执行"""
        result = await bash_tool.ainvoke({
            "command": "python3 -c \"print('hello')\""
        })
        assert "错误" in result
        assert "禁止执行脚本命令" in result

    @pytest.mark.asyncio
    async def test_blocks_python_heredoc(self, bash_tool):
        """测试阻止 python3 heredoc 脚本执行"""
        result = await bash_tool.ainvoke({
            "command": "python3 << 'EOF'\nprint('hello')\nEOF"
        })
        assert "错误" in result
        assert "禁止执行脚本命令" in result

    @pytest.mark.asyncio
    async def test_blocks_node_e(self, bash_tool):
        """测试阻止 node -e 脚本执行"""
        result = await bash_tool.ainvoke({
            "command": "node -e \"console.log('hello')\""
        })
        assert "错误" in result
        assert "禁止执行脚本命令" in result

    @pytest.mark.asyncio
    async def test_blocks_bash_c(self, bash_tool):
        """测试阻止 bash -c 脚本执行"""
        result = await bash_tool.ainvoke({
            "command": "bash -c 'echo hello'"
        })
        assert "错误" in result
        assert "禁止执行脚本命令" in result

    @pytest.mark.asyncio
    async def test_blocks_sh_c(self, bash_tool):
        """测试阻止 sh -c 脚本执行"""
        result = await bash_tool.ainvoke({
            "command": "sh -c 'echo hello'"
        })
        assert "错误" in result
        assert "禁止执行脚本命令" in result

    @pytest.mark.asyncio
    async def test_allows_read_commands(self, bash_tool):
        """测试允许只读命令"""
        result = await bash_tool.ainvoke({"command": "pwd"})
        assert "错误" not in result or "禁止" not in result

    @pytest.mark.asyncio
    async def test_allows_ls(self, bash_tool):
        """测试允许 ls 命令"""
        result = await bash_tool.ainvoke({"command": "ls"})
        assert "禁止" not in result


class TestBashToolBuildMode:
    """BashTool BUILD 模式测试"""

    @pytest.fixture
    def mode_manager(self):
        """创建模式管理器（默认 BUILD 模式）"""
        return AgentModeManager()

    @pytest.fixture
    def bash_tool(self, mode_manager):
        """创建 BashTool"""
        return BashTool(mode_manager)

    @pytest.mark.asyncio
    async def test_allows_mkdir_in_build_mode(self, bash_tool, tmp_path):
        """测试 BUILD 模式允许 mkdir"""
        result = await bash_tool.ainvoke({
            "command": f"mkdir {tmp_path}/test_dir"
        })
        # BUILD 模式下应该允许执行
        assert "禁止" not in result

    @pytest.mark.asyncio
    async def test_allows_python_c_in_build_mode(self, bash_tool):
        """测试 BUILD 模式允许 python3 -c"""
        result = await bash_tool.ainvoke({
            "command": "python3 -c \"print('hello')\""
        })
        # BUILD 模式下应该允许执行
        assert "禁止执行脚本命令" not in result


class TestBashToolBlacklist:
    """BashTool 黑名单命令测试"""

    @pytest.fixture
    def bash_tool(self):
        """创建 BashTool（无模式管理器）"""
        return BashTool()

    @pytest.mark.asyncio
    async def test_blocks_rm_rf_root(self, bash_tool):
        """测试阻止 rm -rf /"""
        result = await bash_tool.ainvoke({"command": "rm -rf /"})
        assert "错误" in result
        assert "安全限制" in result

    @pytest.mark.asyncio
    async def test_blocks_fork_bomb(self, bash_tool):
        """测试阻止 fork bomb"""
        result = await bash_tool.ainvoke({"command": ":(){ :|:& };:"})
        # fork bomb 可能被 shell 语法错误阻止，或被我们的黑名单阻止
        # 只要不成功执行就行
        assert "exit_code: 0" not in result or "错误" in result

    @pytest.mark.asyncio
    async def test_blocks_mkfs(self, bash_tool):
        """测试阻止 mkfs"""
        result = await bash_tool.ainvoke({"command": "mkfs.ext4 /dev/sda"})
        assert "错误" in result
        assert "安全限制" in result
