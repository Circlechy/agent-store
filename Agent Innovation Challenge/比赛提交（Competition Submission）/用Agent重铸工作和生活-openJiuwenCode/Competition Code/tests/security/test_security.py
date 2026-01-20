"""
安全测试

测试用例覆盖 docs/03-测试用例设计.md 中第五节的所有 P0 用例
包括命令安全测试和模式权限安全测试
"""

import pytest
import asyncio
import sys
import os
import tempfile
from pathlib import Path

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool


class TestCommandSecurity:
    """测试命令安全 - 5.1 节"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def bash_tool(self, mode_manager):
        return BashTool(mode_manager)

    # ========================================================================
    # test_blacklist_rm_rf_root - 黑名单 rm -rf /
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_rm_rf_root(self, bash_tool):
        """测试黑名单命令 rm -rf /"""
        inputs = ToolInput(data={
            "command": "rm -rf /",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_blacklist_rm_rf_wildcard - 黑名单 rm -rf /*
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_rm_rf_wildcard(self, bash_tool):
        """测试黑名单命令 rm -rf /*"""
        inputs = ToolInput(data={
            "command": "rm -rf /*",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_blacklist_mkfs - 黑名单 mkfs
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_mkfs(self, bash_tool):
        """测试黑名单命令 mkfs"""
        inputs = ToolInput(data={
            "command": "mkfs /dev/sda1",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_blacklist_dd_zero - 黑名单 dd if=/dev/zero
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_dd_zero(self, bash_tool):
        """测试黑名单命令 dd if=/dev/zero"""
        inputs = ToolInput(data={
            "command": "dd if=/dev/zero of=/dev/sda",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_blacklist_fork_bomb - 黑名单 fork bomb
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_fork_bomb(self, bash_tool):
        """测试黑名单命令 fork bomb"""
        inputs = ToolInput(data={
            "command": ":(){:|:&};:",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_blacklist_chmod_777 - 黑名单 chmod -R 777 /
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_chmod_777(self, bash_tool):
        """测试黑名单命令 chmod -R 777 /"""
        inputs = ToolInput(data={
            "command": "chmod -R 777 /",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_restricted_path_etc - 受限路径 /etc
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_restricted_path_etc(self, bash_tool):
        """测试受限路径 /etc"""
        inputs = ToolInput(data={
            "command": "cat /etc/passwd",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "受限路径" in result.error or "禁止" in result.error

    # ========================================================================
    # test_restricted_path_usr_bin - 受限路径 /usr/bin
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_restricted_path_usr_bin(self, bash_tool):
        """测试受限路径 /usr/bin"""
        inputs = ToolInput(data={
            "command": "rm /usr/bin/python",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "受限路径" in result.error or "禁止" in result.error

    # ========================================================================
    # test_command_injection_semicolon - 命令注入 ;
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_command_injection_semicolon(self, bash_tool):
        """测试命令注入 - 分号"""
        # 这个测试验证即使有命令注入，危险命令仍然被阻止
        inputs = ToolInput(data={
            "command": "echo hello; rm -rf /",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # 应该被阻止，因为包含 rm -rf /
        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_command_injection_pipe - 命令注入 |
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_command_injection_pipe(self, bash_tool):
        """测试命令注入 - 管道"""
        inputs = ToolInput(data={
            "command": "cat /etc/passwd | grep root",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # 应该被阻止，因为涉及 /etc
        assert result.success == False

    # ========================================================================
    # test_path_traversal - 路径遍历 ../
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_path_traversal_etc(self, bash_tool):
        """测试路径遍历到 /etc"""
        inputs = ToolInput(data={
            "command": "cat ../../../../../../etc/passwd",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # 应该被阻止，因为涉及 /etc
        assert result.success == False

    # ========================================================================
    # 额外安全测试
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_shutdown(self, bash_tool):
        """测试黑名单命令 shutdown"""
        inputs = ToolInput(data={
            "command": "shutdown -h now",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_blacklist_reboot(self, bash_tool):
        """测试黑名单命令 reboot"""
        inputs = ToolInput(data={
            "command": "reboot",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_safe_command_allowed(self, bash_tool):
        """测试安全命令允许执行"""
        inputs = ToolInput(data={
            "command": "echo 'Hello, World!'",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == True
        assert "Hello, World!" in result.data["stdout"]

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_safe_ls_command(self, bash_tool):
        """测试安全的 ls 命令"""
        inputs = ToolInput(data={
            "command": "ls -la /tmp",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == True


class TestModeSecurity:
    """测试模式权限安全 - 5.2 节"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def temp_file(self, temp_dir):
        """创建临时测试文件"""
        file_path = os.path.join(temp_dir, "test_file.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Test content\n")
        return file_path

    # ========================================================================
    # test_plan_mode_cannot_write - PLAN 模式写入
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_plan_mode_cannot_write(self, temp_dir):
        """测试 PLAN 模式不能写入文件"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        write_tool = WriteFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": os.path.join(temp_dir, "new_file.txt"),
            "content": "Should not be written"
        })

        result = await write_tool.ainvoke(inputs)

        assert result.success == False
        assert "不可用" in result.error

    # ========================================================================
    # test_plan_mode_cannot_delete - PLAN 模式删除
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_plan_mode_cannot_delete(self, temp_file):
        """测试 PLAN 模式不能删除文件"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": f"rm {temp_file}",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        # 文件应该仍然存在
        assert os.path.exists(temp_file)

    # ========================================================================
    # test_plan_mode_cannot_git_commit - PLAN 模式 git commit
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_plan_mode_cannot_git_commit(self):
        """测试 PLAN 模式不能执行 git commit"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "git commit -m 'test'",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False

    # ========================================================================
    # test_review_mode_cannot_modify - REVIEW 模式修改
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_review_mode_cannot_modify(self, temp_file):
        """测试 REVIEW 模式不能修改文件"""
        mode_manager = AgentModeManager(AgentMode.REVIEW)
        edit_tool = EditFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file,
            "old_string": "Test",
            "new_string": "Modified"
        })

        result = await edit_tool.ainvoke(inputs)

        assert result.success == False
        assert "不可用" in result.error

    # ========================================================================
    # test_review_mode_cannot_git - REVIEW 模式 git
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_review_mode_cannot_git(self):
        """测试 REVIEW 模式不能执行 git 命令"""
        mode_manager = AgentModeManager(AgentMode.REVIEW)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "git status",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_review_mode_cannot_git_push(self):
        """测试 REVIEW 模式不能执行 git push"""
        mode_manager = AgentModeManager(AgentMode.REVIEW)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "git push origin main",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False

    # ========================================================================
    # test_mode_bypass_attempt - 模式绕过尝试
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_mode_bypass_attempt_via_bash(self, temp_dir):
        """测试通过 Bash 绕过模式限制"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        # 尝试通过 bash 写入文件
        file_path = os.path.join(temp_dir, "bypass_test.txt")
        inputs = ToolInput(data={
            "command": f"echo 'bypass content' > {file_path}",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # 应该被阻止（因为 > 是破坏性操作）
        assert result.success == False

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_mode_bypass_attempt_via_mv(self, temp_file):
        """测试通过 mv 绕过模式限制"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": f"mv {temp_file} {temp_file}.bak",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # 应该被阻止
        assert result.success == False
        # 原文件应该仍然存在
        assert os.path.exists(temp_file)

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_mode_bypass_attempt_via_cp(self, temp_file, temp_dir):
        """测试通过 cp 绕过模式限制"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        bash_tool = BashTool(mode_manager)

        dest_path = os.path.join(temp_dir, "copied_file.txt")
        inputs = ToolInput(data={
            "command": f"cp {temp_file} {dest_path}",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        # cp 在 PLAN 模式下应该被阻止
        assert result.success == False

    # ========================================================================
    # 额外模式安全测试
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_plan_mode_can_read(self, temp_file):
        """测试 PLAN 模式可以读取文件"""
        mode_manager = AgentModeManager(AgentMode.PLAN)
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == True
        assert "Test content" in result.data["content"]

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_review_mode_can_read(self, temp_file):
        """测试 REVIEW 模式可以读取文件"""
        mode_manager = AgentModeManager(AgentMode.REVIEW)
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == True
        assert "Test content" in result.data["content"]

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_build_mode_full_access(self, temp_dir):
        """测试 BUILD 模式有完全访问权限"""
        mode_manager = AgentModeManager(AgentMode.BUILD)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        file_path = os.path.join(temp_dir, "build_test.txt")

        # 写入
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Initial content"
        }))
        assert write_result.success == True

        # 编辑
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "old_string": "Initial",
            "new_string": "Modified"
        }))
        assert edit_result.success == True

        # Bash 命令
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"cat {file_path}",
            "timeout": 5
        }))
        assert bash_result.success == True

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_mode_switch_security(self, temp_dir):
        """测试模式切换后安全性正确更新"""
        mode_manager = AgentModeManager(AgentMode.BUILD)
        write_tool = WriteFileTool(mode_manager)

        file_path = os.path.join(temp_dir, "switch_test.txt")

        # BUILD 模式可以写入
        result1 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 1"
        }))
        assert result1.success == True

        # 切换到 PLAN 模式
        mode_manager.switch_mode(AgentMode.PLAN)

        # PLAN 模式不能写入
        result2 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 2"
        }))
        assert result2.success == False

        # 切换到 REVIEW 模式
        mode_manager.switch_mode(AgentMode.REVIEW)

        # REVIEW 模式也不能写入
        result3 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 3"
        }))
        assert result3.success == False

        # 切换回 BUILD 模式
        mode_manager.switch_mode(AgentMode.BUILD)

        # BUILD 模式又可以写入
        result4 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 4"
        }))
        assert result4.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])
