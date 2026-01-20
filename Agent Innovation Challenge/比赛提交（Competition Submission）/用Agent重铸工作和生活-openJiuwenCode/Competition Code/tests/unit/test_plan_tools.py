"""
Plan 工具单元测试
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from packages.server.tools.plan_tools import (
    PlanFileManager,
    PlanSession,
    EnterPlanModeTool,
    ExitPlanModeTool,
    create_plan_tools,
    ADJECTIVES,
    NOUNS
)
from packages.server.agents.mode_manager import AgentModeManager, AgentMode


class TestPlanSession:
    """PlanSession 数据模型测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        session = PlanSession(
            session_id="test_session",
            plan_file_path="/tmp/test.md",
            created_at="2024-01-01T00:00:00",
            status="planning",
            allowed_prompts=[{"tool": "Bash", "prompt": "run tests"}]
        )

        result = session.to_dict()

        assert result["session_id"] == "test_session"
        assert result["plan_file_path"] == "/tmp/test.md"
        assert result["status"] == "planning"
        assert len(result["allowed_prompts"]) == 1

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "session_id": "test_session",
            "plan_file_path": "/tmp/test.md",
            "created_at": "2024-01-01T00:00:00",
            "status": "approved",
            "allowed_prompts": []
        }

        session = PlanSession.from_dict(data)

        assert session.session_id == "test_session"
        assert session.status == "approved"


class TestPlanFileManager:
    """PlanFileManager 测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    @pytest.fixture
    def manager(self, temp_home):
        """创建 PlanFileManager 实例"""
        with patch.object(Path, 'home', return_value=temp_home):
            return PlanFileManager(session_id="test_session")

    def test_init_creates_plans_dir(self, temp_home):
        """测试初始化时创建 plans 目录"""
        with patch.object(Path, 'home', return_value=temp_home):
            manager = PlanFileManager(session_id="test")
            assert manager.plans_dir.exists()

    def test_generate_plan_filename(self, manager):
        """测试生成 plan 文件名"""
        filename = manager._generate_plan_filename()

        # 格式: adjective-adjective-noun.md
        parts = filename.replace(".md", "").split("-")
        assert len(parts) == 3
        assert parts[0] in ADJECTIVES
        assert parts[1] in ADJECTIVES
        assert parts[2] in NOUNS

    def test_create_plan_file(self, manager, temp_home):
        """测试创建 plan 文件"""
        with patch.object(Path, 'home', return_value=temp_home):
            file_path = manager.create_plan_file()

            assert file_path.exists()
            assert file_path.suffix == ".md"

            # 检查模板内容
            content = file_path.read_text()
            assert "# Implementation Plan" in content
            assert "## Summary" in content

    def test_get_current_plan_file(self, manager, temp_home):
        """测试获取当前 plan 文件"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建文件前应该返回 None
            assert manager.get_current_plan_file() is None

            # 创建文件后应该返回路径
            created_path = manager.create_plan_file()
            current_path = manager.get_current_plan_file()

            assert current_path == created_path

    def test_read_plan_file(self, manager, temp_home):
        """测试读取 plan 文件"""
        with patch.object(Path, 'home', return_value=temp_home):
            file_path = manager.create_plan_file()
            content = manager.read_plan_file(file_path)

            assert "# Implementation Plan" in content

    def test_update_plan_file(self, manager, temp_home):
        """测试更新 plan 文件"""
        with patch.object(Path, 'home', return_value=temp_home):
            file_path = manager.create_plan_file()

            new_content = "# My Custom Plan\n\nThis is my plan."
            result = manager.update_plan_file(new_content, file_path)

            assert result is True
            assert file_path.read_text() == new_content

    def test_update_session_status(self, manager, temp_home):
        """测试更新会话状态"""
        with patch.object(Path, 'home', return_value=temp_home):
            manager.create_plan_file()

            allowed_prompts = [{"tool": "Bash", "prompt": "run tests"}]
            manager.update_session_status("approved", allowed_prompts)

            session = manager.get_session()
            assert session.status == "approved"
            assert session.allowed_prompts == allowed_prompts


class TestEnterPlanModeTool:
    """EnterPlanModeTool 测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    @pytest.fixture
    def mode_manager(self):
        """创建模式管理器"""
        return AgentModeManager(initial_mode=AgentMode.BUILD)

    @pytest.fixture
    def tool(self, mode_manager, temp_home):
        """创建 EnterPlanModeTool 实例"""
        with patch.object(Path, 'home', return_value=temp_home):
            return EnterPlanModeTool(
                mode_manager=mode_manager,
                session_id="test_session"
            )

    def test_tool_name(self, tool):
        """测试工具名称"""
        assert tool.name == "enter_plan_mode"

    def test_tool_has_no_params(self, tool):
        """测试工具无参数"""
        assert len(tool.params) == 0

    @pytest.mark.asyncio
    async def test_enter_plan_mode_from_build(self, tool, mode_manager, temp_home):
        """测试从 BUILD 模式进入 PLAN 模式"""
        with patch.object(Path, 'home', return_value=temp_home):
            result = await tool.ainvoke({})

            assert "已进入 PLAN 模式" in result
            assert "Plan 文件已创建" in result
            assert mode_manager.get_current_mode() == AgentMode.PLAN

    @pytest.mark.asyncio
    async def test_enter_plan_mode_already_in_plan(self, tool, mode_manager, temp_home):
        """测试已经在 PLAN 模式时的行为"""
        with patch.object(Path, 'home', return_value=temp_home):
            mode_manager.switch_mode(AgentMode.PLAN)

            result = await tool.ainvoke({})

            assert "已经处于 PLAN 模式" in result


class TestExitPlanModeTool:
    """ExitPlanModeTool 测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    @pytest.fixture
    def mode_manager(self):
        """创建模式管理器"""
        return AgentModeManager(initial_mode=AgentMode.PLAN)

    @pytest.fixture
    def plan_file_manager(self, temp_home):
        """创建 PlanFileManager"""
        with patch.object(Path, 'home', return_value=temp_home):
            return PlanFileManager(session_id="test_session")

    @pytest.fixture
    def tool(self, mode_manager, plan_file_manager, temp_home):
        """创建 ExitPlanModeTool 实例"""
        with patch.object(Path, 'home', return_value=temp_home):
            return ExitPlanModeTool(
                mode_manager=mode_manager,
                session_id="test_session",
                plan_file_manager=plan_file_manager
            )

    def test_tool_name(self, tool):
        """测试工具名称"""
        assert tool.name == "exit_plan_mode"

    def test_tool_has_allowed_prompts_param(self, tool):
        """测试工具有 allowed_prompts 参数"""
        param_names = [p.name for p in tool.params]
        assert "allowed_prompts" in param_names

    @pytest.mark.asyncio
    async def test_exit_not_in_plan_mode(self, tool, mode_manager, temp_home):
        """测试不在 PLAN 模式时退出"""
        with patch.object(Path, 'home', return_value=temp_home):
            mode_manager.switch_mode(AgentMode.BUILD)

            result = await tool.ainvoke({})

            assert "错误" in result
            assert "不在 PLAN 模式" in result

    @pytest.mark.asyncio
    async def test_exit_no_plan_file(self, tool, temp_home):
        """测试没有 plan 文件时退出"""
        with patch.object(Path, 'home', return_value=temp_home):
            result = await tool.ainvoke({})

            assert "错误" in result
            assert "未找到 plan 文件" in result

    @pytest.mark.asyncio
    async def test_exit_empty_plan_file(self, tool, plan_file_manager, temp_home):
        """测试 plan 文件为空时退出"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建 plan 文件（使用模板）
            plan_file_manager.create_plan_file()

            result = await tool.ainvoke({})

            assert "错误" in result
            assert "未修改" in result

    @pytest.mark.asyncio
    async def test_exit_with_valid_plan(self, tool, plan_file_manager, temp_home):
        """测试有有效 plan 时退出"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建并修改 plan 文件
            file_path = plan_file_manager.create_plan_file()
            plan_file_manager.update_plan_file(
                "# My Plan\n\nThis is a real implementation plan.",
                file_path
            )

            result = await tool.ainvoke({})

            assert "Plan 审批请求" in result
            assert "My Plan" in result

    @pytest.mark.asyncio
    async def test_exit_with_allowed_prompts(self, tool, plan_file_manager, temp_home):
        """测试带预授权退出"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建并修改 plan 文件
            file_path = plan_file_manager.create_plan_file()
            plan_file_manager.update_plan_file(
                "# My Plan\n\nThis is a real implementation plan.",
                file_path
            )

            allowed_prompts = json.dumps([
                {"tool": "Bash", "prompt": "run tests"},
                {"tool": "Bash", "prompt": "build project"}
            ])

            result = await tool.ainvoke({"allowed_prompts": allowed_prompts})

            assert "预申请的命令权限" in result
            assert "run tests" in result
            assert "build project" in result


class TestCreatePlanTools:
    """create_plan_tools 工厂函数测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    def test_creates_both_tools(self, temp_home):
        """测试创建两个工具"""
        with patch.object(Path, 'home', return_value=temp_home):
            mode_manager = AgentModeManager()
            tools = create_plan_tools(mode_manager, "test_session")

            assert len(tools) == 2
            tool_names = [t.name for t in tools]
            assert "enter_plan_mode" in tool_names
            assert "exit_plan_mode" in tool_names

    def test_tools_share_plan_file_manager(self, temp_home):
        """测试两个工具共享同一个 PlanFileManager"""
        with patch.object(Path, 'home', return_value=temp_home):
            mode_manager = AgentModeManager()
            tools = create_plan_tools(mode_manager, "test_session")

            enter_tool = next(t for t in tools if t.name == "enter_plan_mode")
            exit_tool = next(t for t in tools if t.name == "exit_plan_mode")

            # 它们应该共享同一个 plan_file_manager
            assert enter_tool.plan_file_manager is exit_tool.plan_file_manager


class TestExitPlanModeApprovalMarker:
    """ExitPlanMode 审批等待标记测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    @pytest.fixture
    def mode_manager(self):
        """创建模式管理器"""
        manager = AgentModeManager()
        manager.switch_mode(AgentMode.PLAN)
        return manager

    @pytest.fixture
    def plan_file_manager(self, temp_home):
        """创建 plan 文件管理器"""
        with patch.object(Path, 'home', return_value=temp_home):
            return PlanFileManager("test_session")

    @pytest.fixture
    def tool(self, mode_manager, plan_file_manager):
        """创建 ExitPlanMode 工具"""
        return ExitPlanModeTool(mode_manager, "test_session", plan_file_manager)

    @pytest.mark.asyncio
    async def test_exit_contains_awaiting_approval_marker(self, tool, plan_file_manager, temp_home):
        """测试退出时包含 AWAITING_USER_APPROVAL 标记"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建并修改 plan 文件
            file_path = plan_file_manager.create_plan_file()
            plan_file_manager.update_plan_file(
                "# My Plan\n\nThis is a real implementation plan.",
                file_path
            )

            result = await tool.ainvoke({})

            # 验证包含审批等待标记
            assert "<AWAITING_USER_APPROVAL>" in result
            assert "</AWAITING_USER_APPROVAL>" in result
            assert "等待用户审批" in result

    @pytest.mark.asyncio
    async def test_exit_contains_stop_instruction(self, tool, plan_file_manager, temp_home):
        """测试退出时包含停止执行指令"""
        with patch.object(Path, 'home', return_value=temp_home):
            # 创建并修改 plan 文件
            file_path = plan_file_manager.create_plan_file()
            plan_file_manager.update_plan_file(
                "# My Plan\n\nThis is a real implementation plan.",
                file_path
            )

            result = await tool.ainvoke({})

            # 验证包含停止执行指令
            assert "必须停止执行" in result or "请勿继续执行" in result


class TestPlanApprovalWorkflow:
    """Plan 审批工作流测试"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """创建临时 home 目录"""
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)
        yield tmp_path
        if old_home:
            os.environ["HOME"] = old_home

    @pytest.fixture
    def plan_file_manager(self, temp_home):
        """创建 plan 文件管理器"""
        with patch.object(Path, 'home', return_value=temp_home):
            return PlanFileManager("test_session")

    def test_is_pending_approval_false_initially(self, plan_file_manager, temp_home):
        """测试初始状态不是待审批"""
        with patch.object(Path, 'home', return_value=temp_home):
            assert plan_file_manager.is_pending_approval() is False

    def test_is_pending_approval_false_after_create(self, plan_file_manager, temp_home):
        """测试创建 plan 后状态是 planning，不是待审批"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            assert plan_file_manager.is_pending_approval() is False

    def test_is_pending_approval_true_after_update_status(self, plan_file_manager, temp_home):
        """测试更新状态为 pending_approval 后是待审批"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            plan_file_manager.update_session_status("pending_approval")
            assert plan_file_manager.is_pending_approval() is True

    def test_approve_plan_success(self, plan_file_manager, temp_home):
        """测试成功批准 plan"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            plan_file_manager.update_session_status("pending_approval")

            result = plan_file_manager.approve_plan()

            assert result is True
            session = plan_file_manager.get_session()
            assert session.status == "approved"

    def test_approve_plan_fails_when_not_pending(self, plan_file_manager, temp_home):
        """测试非待审批状态时批准失败"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            # 状态是 planning，不是 pending_approval

            result = plan_file_manager.approve_plan()

            assert result is False

    def test_reject_plan_success(self, plan_file_manager, temp_home):
        """测试成功拒绝 plan"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            plan_file_manager.update_session_status("pending_approval")

            result = plan_file_manager.reject_plan()

            assert result is True
            session = plan_file_manager.get_session()
            assert session.status == "rejected"

    def test_reject_plan_fails_when_not_pending(self, plan_file_manager, temp_home):
        """测试非待审批状态时拒绝失败"""
        with patch.object(Path, 'home', return_value=temp_home):
            plan_file_manager.create_plan_file()
            # 状态是 planning，不是 pending_approval

            result = plan_file_manager.reject_plan()

            assert result is False

    def test_approve_plan_applies_permissions(self, plan_file_manager, temp_home):
        """测试批准 plan 时应用预授权权限"""
        from packages.server.tools.plan_tools import get_permission_manager, reset_permission_manager

        with patch.object(Path, 'home', return_value=temp_home):
            # 重置权限管理器
            reset_permission_manager()

            plan_file_manager.create_plan_file()
            allowed_prompts = [{"tool": "Bash", "prompt": "run tests"}]
            plan_file_manager.update_session_status("pending_approval", allowed_prompts)

            plan_file_manager.approve_plan()

            # 验证权限已应用
            pm = get_permission_manager()
            assert pm.is_command_preauthorized("pytest tests/")

            # 清理
            reset_permission_manager()
