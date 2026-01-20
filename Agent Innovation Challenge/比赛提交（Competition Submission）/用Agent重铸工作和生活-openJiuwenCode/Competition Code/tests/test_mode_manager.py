"""
Agent 模式管理器单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager


class TestAgentModeManager:
    """测试 Agent 模式管理器"""

    def test_initial_mode(self):
        """测试初始模式"""
        manager = AgentModeManager()
        assert manager.get_current_mode() == AgentMode.BUILD

    def test_switch_mode(self):
        """测试模式切换"""
        manager = AgentModeManager()

        # 切换到 PLAN 模式
        assert manager.switch_mode(AgentMode.PLAN) == True
        assert manager.get_current_mode() == AgentMode.PLAN

        # 再次切换到相同模式（应该返回 False）
        assert manager.switch_mode(AgentMode.PLAN) == False

        # 切换到 REVIEW 模式
        assert manager.switch_mode(AgentMode.REVIEW) == True
        assert manager.get_current_mode() == AgentMode.REVIEW

    def test_build_mode_permissions(self):
        """测试 BUILD 模式权限"""
        manager = AgentModeManager(AgentMode.BUILD)

        # BUILD 模式下所有工具都应该可用
        assert manager.is_tool_allowed("read_file") == True
        assert manager.is_tool_allowed("write_file") == True
        assert manager.is_tool_allowed("edit_file") == True
        assert manager.is_tool_allowed("bash") == True

        # BUILD 模式下没有阻止的命令
        assert manager.is_command_blocked("ls") == False
        assert manager.is_command_blocked("rm file.txt") == False

    def test_plan_mode_permissions(self):
        """测试 PLAN 模式权限"""
        manager = AgentModeManager(AgentMode.PLAN)

        # PLAN 模式下写入工具不可用
        assert manager.is_tool_allowed("read_file") == True
        assert manager.is_tool_allowed("write_file") == False
        assert manager.is_tool_allowed("edit_file") == False

        # PLAN 模式下破坏性命令被阻止
        assert manager.is_command_blocked("rm file.txt") == True
        assert manager.is_command_blocked("mv a b") == True
        assert manager.is_command_blocked("ls") == False

    def test_review_mode_permissions(self):
        """测试 REVIEW 模式权限"""
        manager = AgentModeManager(AgentMode.REVIEW)

        # REVIEW 模式下只读工具可用
        assert manager.is_tool_allowed("read_file") == True
        assert manager.is_tool_allowed("write_file") == False

        # REVIEW 模式下 git 命令也被阻止
        assert manager.is_command_blocked("git status") == True
        assert manager.is_command_blocked("ls") == False

    def test_mode_prompt_suffix(self):
        """测试模式特定提示词"""
        manager = AgentModeManager()

        # BUILD 模式提示词
        manager.switch_mode(AgentMode.BUILD)
        prompt = manager.get_mode_prompt_suffix()
        assert "BUILD 模式" in prompt
        assert "完全的开发权限" in prompt

        # PLAN 模式提示词
        manager.switch_mode(AgentMode.PLAN)
        prompt = manager.get_mode_prompt_suffix()
        assert "PLAN 模式" in prompt
        assert "只读模式" in prompt

        # REVIEW 模式提示词
        manager.switch_mode(AgentMode.REVIEW)
        prompt = manager.get_mode_prompt_suffix()
        assert "REVIEW 模式" in prompt
        assert "代码审查" in prompt

    def test_get_mode_info(self):
        """测试获取模式信息"""
        manager = AgentModeManager(AgentMode.PLAN)
        info = manager.get_mode_info()

        assert info["mode"] == "plan"
        assert info["read_only"] == True
        assert "read_file" in info["allowed_tools"]
        assert "write_file" not in info["allowed_tools"]
        assert len(info["blocked_commands"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
