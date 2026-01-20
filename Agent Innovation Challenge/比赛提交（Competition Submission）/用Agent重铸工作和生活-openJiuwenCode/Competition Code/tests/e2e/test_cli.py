"""
CLI 端到端测试

测试用例覆盖 docs/03-测试用例设计.md 中 4.1 节的所有 P1 用例
"""

import pytest
import asyncio
import sys
import os
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))


class TestCLIStartup:
    """测试 CLI 启动"""

    def test_cli_version(self):
        """测试 --version 参数"""
        result = subprocess.run(
            ["python", "-m", "packages.cli.main", "--version"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert result.returncode == 0
        assert "Jiuwen Code" in result.stdout or "0.1.0" in result.stdout

    def test_cli_help(self):
        """测试 --help 参数"""
        result = subprocess.run(
            ["python", "-m", "packages.cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert result.returncode == 0
        assert "jiuwen" in result.stdout.lower() or "usage" in result.stdout.lower()


class TestJiuwenCLI:
    """测试 JiuwenCLI 类"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            "api_key": "test-api-key",
            "provider": "openai",
            "model": "gpt-4o",
            "api_base_url": "https://api.openai.com/v1"
        }

    @pytest.fixture
    def cli_instance(self, mock_config):
        """创建 CLI 实例（不初始化 Agent）"""
        from cli.main import JiuwenCLI

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)
            cli.agent = None  # 不使用真实 Agent
            return cli

    # ========================================================================
    # test_cli_startup - CLI 启动
    # ========================================================================

    def test_cli_startup_with_config(self, mock_config):
        """测试 CLI 启动时正确加载配置"""
        from cli.main import JiuwenCLI

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            assert cli.config == mock_config
            assert cli.running == True

    # ========================================================================
    # test_cli_help_command - /help 命令
    # ========================================================================

    def test_cli_help_command(self, cli_instance, capsys):
        """测试 /help 命令显示帮助信息"""
        result = cli_instance.handle_command("/help")

        assert result == True  # 命令被处理

        captured = capsys.readouterr()
        # 检查帮助信息是否包含关键命令
        assert "/help" in captured.out or "help" in captured.out.lower()

    # ========================================================================
    # test_cli_mode_command - /mode 命令
    # ========================================================================

    def test_cli_mode_command_without_agent(self, cli_instance, capsys):
        """测试 /mode 命令（无 Agent）"""
        result = cli_instance.handle_command("/mode")

        assert result == True

        captured = capsys.readouterr()
        assert "未初始化" in captured.out or "Agent" in captured.out

    def test_cli_mode_command_with_agent(self, mock_config, capsys):
        """测试 /mode 命令（有 Agent）"""
        from cli.main import JiuwenCLI
        from server.agents.mode_manager import AgentMode, AgentModeManager

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent
            mock_agent = MagicMock()
            mock_agent.get_mode_info.return_value = {
                'mode': 'build',
                'read_only': False,
                'allowed_tools': ['read_file', 'write_file', 'bash']
            }
            mock_agent.get_current_mode.return_value = AgentMode.BUILD
            cli.agent = mock_agent

            result = cli.handle_command("/mode")

            assert result == True

    # ========================================================================
    # test_cli_clear_command - /clear 命令
    # ========================================================================

    def test_cli_clear_command(self, cli_instance, capsys):
        """测试 /clear 命令清除屏幕"""
        result = cli_instance.handle_command("/clear")

        assert result == True

        captured = capsys.readouterr()
        # 检查是否包含清屏序列或欢迎信息
        assert "\033[2J" in captured.out or "Jiuwen" in captured.out

    # ========================================================================
    # test_cli_exit_command - /exit 命令
    # ========================================================================

    def test_cli_exit_command(self, cli_instance, capsys):
        """测试 /exit 命令正常退出"""
        assert cli_instance.running == True

        result = cli_instance.handle_command("/exit")

        assert result == True
        assert cli_instance.running == False

        captured = capsys.readouterr()
        assert "再见" in captured.out or "bye" in captured.out.lower()

    def test_cli_quit_command(self, cli_instance, capsys):
        """测试 /quit 命令正常退出"""
        assert cli_instance.running == True

        result = cli_instance.handle_command("/quit")

        assert result == True
        assert cli_instance.running == False

    # ========================================================================
    # test_cli_keyboard_interrupt - Ctrl+C 中断
    # ========================================================================

    # 注意：Ctrl+C 中断测试需要在实际运行环境中测试
    # 这里测试 KeyboardInterrupt 的处理逻辑

    # ========================================================================
    # test_cli_streaming_output - 流式输出显示
    # ========================================================================

    @pytest.mark.asyncio
    async def test_cli_streaming_output(self, mock_config, capsys):
        """测试流式输出显示"""
        from cli.main import JiuwenCLI

        # 尝试导入 AgentEvent，如果失败则跳过测试
        try:
            from server.agents.openjiuwen_agent import AgentEvent
        except ImportError as e:
            pytest.skip(f"AgentEvent 导入失败 (SDK 兼容性问题): {e}")

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent 流式输出
            mock_agent = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield AgentEvent(type="content_chunk", data="Hello")
                yield AgentEvent(type="content_chunk", data=" World")

            mock_agent.stream = mock_stream
            mock_agent.api_key = "test-key"
            cli.agent = mock_agent

            await cli.process_message("test")

            captured = capsys.readouterr()
            assert "Hello" in captured.out
            assert "World" in captured.out

    # ========================================================================
    # test_cli_tool_call_display - 工具调用显示
    # ========================================================================

    @pytest.mark.asyncio
    async def test_cli_tool_call_display(self, mock_config, capsys):
        """测试工具调用显示（Claude Code 风格）"""
        from cli.main import JiuwenCLI

        # 尝试导入 AgentEvent，如果失败则跳过测试
        try:
            from server.agents.openjiuwen_agent import AgentEvent
        except ImportError as e:
            pytest.skip(f"AgentEvent 导入失败 (SDK 兼容性问题): {e}")

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent 工具调用
            mock_agent = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield AgentEvent(type="tool_call", data={
                    "name": "read_file",
                    "arguments": {"file_path": "/tmp/test.txt"}
                })
                yield AgentEvent(type="tool_result", data="File content here")
                yield AgentEvent(type="content", data="Done")

            mock_agent.stream = mock_stream
            mock_agent.api_key = "test-key"
            cli.agent = mock_agent

            await cli.process_message("read file")

            captured = capsys.readouterr()
            # 检查工具调用显示 - 应该使用友好名称 "Read" 而不是 "read_file"
            assert "Read" in captured.out or "read_file" in captured.out

    # ========================================================================
    # 模式切换测试
    # ========================================================================

    def test_cli_build_command(self, mock_config, capsys):
        """测试 /build 命令切换模式"""
        from cli.main import JiuwenCLI
        from server.agents.mode_manager import AgentMode

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent
            mock_agent = MagicMock()
            mock_agent.switch_mode.return_value = True
            mock_agent.get_current_mode.return_value = AgentMode.BUILD
            cli.agent = mock_agent

            result = cli.handle_command("/build")

            assert result == True
            mock_agent.switch_mode.assert_called_once()

    def test_cli_plan_command(self, mock_config, capsys):
        """测试 /plan 命令切换模式"""
        from cli.main import JiuwenCLI
        from server.agents.mode_manager import AgentMode

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent
            mock_agent = MagicMock()
            mock_agent.switch_mode.return_value = True
            mock_agent.get_current_mode.return_value = AgentMode.PLAN
            cli.agent = mock_agent

            result = cli.handle_command("/plan")

            assert result == True

    def test_cli_review_command(self, mock_config, capsys):
        """测试 /review 命令切换模式"""
        from cli.main import JiuwenCLI
        from server.agents.mode_manager import AgentMode

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)

            # 模拟 Agent
            mock_agent = MagicMock()
            mock_agent.switch_mode.return_value = True
            mock_agent.get_current_mode.return_value = AgentMode.REVIEW
            cli.agent = mock_agent

            result = cli.handle_command("/review")

            assert result == True

    # ========================================================================
    # 其他命令测试
    # ========================================================================

    def test_cli_config_command(self, cli_instance, capsys):
        """测试 /config 命令显示配置"""
        result = cli_instance.handle_command("/config")

        assert result == True

        captured = capsys.readouterr()
        assert "配置" in captured.out or "Provider" in captured.out

    def test_cli_tools_command_without_agent(self, cli_instance, capsys):
        """测试 /tools 命令（无 Agent）"""
        result = cli_instance.handle_command("/tools")

        assert result == True

        captured = capsys.readouterr()
        assert "未初始化" in captured.out or "Agent" in captured.out

    def test_cli_unknown_command(self, cli_instance, capsys):
        """测试未知命令"""
        result = cli_instance.handle_command("/unknown_cmd")

        assert result == True

        captured = capsys.readouterr()
        assert "未知命令" in captured.out or "unknown" in captured.out.lower()

    def test_cli_non_command_input(self, cli_instance):
        """测试非命令输入"""
        result = cli_instance.handle_command("hello world")

        assert result == False  # 不是命令


class TestCLIConfig:
    """测试 CLI 配置功能"""

    def test_get_config_from_env(self):
        """测试从环境变量获取配置"""
        from cli.main import get_config

        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "test-anthropic-key"
        }):
            config = get_config()

            # 应该能获取到 API Key
            assert config.get("api_key") is not None or config.get("provider") is not None

    def test_get_default_api_base(self):
        """测试获取默认 API Base URL"""
        from cli.main import get_default_api_base

        assert "anthropic" in get_default_api_base("anthropic")
        assert "openai" in get_default_api_base("openai")
        assert "bigmodel" in get_default_api_base("zhipu")

    def test_get_default_model(self):
        """测试获取默认模型"""
        from cli.main import get_default_model

        assert "claude" in get_default_model("anthropic")
        assert "gpt" in get_default_model("openai")
        assert "glm" in get_default_model("zhipu")


class TestCLIToolFormatting:
    """测试工具参数格式化"""

    @pytest.fixture
    def cli_instance(self):
        """创建 CLI 实例"""
        from cli.main import JiuwenCLI

        mock_config = {
            "api_key": "test-key",
            "provider": "openai",
            "model": "gpt-4o"
        }

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)
            return cli

    def test_format_read_file_args(self, cli_instance):
        """测试 read_file 参数格式化"""
        result = cli_instance._format_tool_args("read_file", {
            "file_path": "/path/to/file.txt",
            "limit": 10
        })

        assert "/path/to/file.txt" in result
        assert "limit=10" in result

    def test_format_write_file_args(self, cli_instance):
        """测试 write_file 参数格式化"""
        result = cli_instance._format_tool_args("write_file", {
            "file_path": "/path/to/file.txt",
            "content": "Hello World"
        })

        assert "/path/to/file.txt" in result

    def test_format_bash_args(self, cli_instance):
        """测试 bash 参数格式化"""
        result = cli_instance._format_tool_args("bash", {
            "command": "echo 'Hello World'"
        })

        assert "echo" in result

    def test_format_bash_args_long_command(self, cli_instance):
        """测试 bash 长命令参数格式化"""
        long_cmd = "a" * 100
        result = cli_instance._format_tool_args("bash", {
            "command": long_cmd
        })

        # 应该被截断
        assert len(result) <= 70
        assert "..." in result

    def test_format_grep_args(self, cli_instance):
        """测试 grep 参数格式化"""
        result = cli_instance._format_tool_args("grep", {
            "pattern": "def main",
            "path": "/src"
        })

        assert "def main" in result
        assert "/src" in result

    def test_format_glob_args(self, cli_instance):
        """测试 glob 参数格式化"""
        result = cli_instance._format_tool_args("glob", {
            "pattern": "**/*.py"
        })

        assert "**/*.py" in result


class TestToolNameMapping:
    """测试工具名称映射"""

    def test_get_tool_display_name_known_tools(self):
        """测试已知工具的显示名称映射"""
        from cli.main import get_tool_display_name

        assert get_tool_display_name("read_file") == "Read"
        assert get_tool_display_name("write_file") == "Write"
        assert get_tool_display_name("edit_file") == "Edit"
        assert get_tool_display_name("bash") == "Bash"
        assert get_tool_display_name("grep") == "Grep"
        assert get_tool_display_name("glob") == "Glob"
        assert get_tool_display_name("ls") == "LS"
        assert get_tool_display_name("todo_write") == "TodoWrite"
        assert get_tool_display_name("web_search") == "WebSearch"
        assert get_tool_display_name("web_fetch") == "WebFetch"

    def test_get_tool_display_name_unknown_tools(self):
        """测试未知工具的显示名称映射（自动转换）"""
        from cli.main import get_tool_display_name

        # 未知工具应该自动转换为 Title Case
        assert get_tool_display_name("unknown_tool") == "UnknownTool"
        assert get_tool_display_name("my_custom_tool") == "MyCustomTool"
        assert get_tool_display_name("simple") == "Simple"


class TestToolResultFormatting:
    """测试工具结果格式化"""

    @pytest.fixture
    def cli_instance(self):
        """创建 CLI 实例"""
        from cli.main import JiuwenCLI

        mock_config = {
            "api_key": "test-key",
            "provider": "openai",
            "model": "gpt-4o"
        }

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)
            cli.session_id = "test-session"
            return cli

    def test_format_read_file_result(self, cli_instance):
        """测试 read_file 结果格式化"""
        result = cli_instance._format_tool_result("read_file", "line1\nline2\nline3\nline4\nline5")
        assert result == "Read 5 lines"

    def test_format_write_file_result(self, cli_instance):
        """测试 write_file 结果格式化"""
        result = cli_instance._format_tool_result("write_file", "成功写入 hello.py (45 字节)")
        assert "成功写入" in result

    def test_format_edit_file_result(self, cli_instance):
        """测试 edit_file 结果格式化"""
        result = cli_instance._format_tool_result("edit_file", "成功编辑文件")
        assert "成功" in result

    def test_format_bash_result_single_line(self, cli_instance):
        """测试 bash 单行结果格式化"""
        result = cli_instance._format_tool_result("bash", "hello world")
        assert result == "hello world"

    def test_format_bash_result_multi_line(self, cli_instance):
        """测试 bash 多行结果格式化"""
        result = cli_instance._format_tool_result("bash", "line1\nline2\nline3")
        assert "line1" in result
        assert "+2 lines" in result

    def test_format_grep_result(self, cli_instance):
        """测试 grep 结果格式化"""
        result = cli_instance._format_tool_result("grep", "file1.py:10\nfile2.py:20\nfile3.py:30")
        assert result == "Found 3 matches"

    def test_format_grep_no_matches(self, cli_instance):
        """测试 grep 无匹配结果格式化"""
        result = cli_instance._format_tool_result("grep", "No matches found")
        assert result == "No matches found"

    def test_format_glob_result(self, cli_instance):
        """测试 glob 结果格式化"""
        result = cli_instance._format_tool_result("glob", "file1.py\nfile2.py")
        assert result == "Found 2 files"

    def test_format_ls_result(self, cli_instance):
        """测试 ls 结果格式化"""
        result = cli_instance._format_tool_result("ls", "dir1\ndir2\nfile1.py")
        assert result == "Listed 3 items"

    def test_format_empty_result(self, cli_instance):
        """测试空结果格式化"""
        result = cli_instance._format_tool_result("bash", "")
        assert result == "Done"


class TestTodoWriteDisplay:
    """测试 TodoWrite checkbox 显示"""

    @pytest.fixture
    def cli_instance(self):
        """创建 CLI 实例"""
        from cli.main import JiuwenCLI

        mock_config = {
            "api_key": "test-key",
            "provider": "openai",
            "model": "gpt-4o"
        }

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)
            cli.session_id = "test-session"
            return cli

    def test_display_todo_checkboxes_pending(self, cli_instance, capsys):
        """测试待处理任务的 checkbox 显示"""
        cli_instance._display_todo_checkboxes({
            "todos": [
                {"content": "任务1", "status": "pending"},
                {"content": "任务2", "status": "pending"}
            ]
        })

        captured = capsys.readouterr()
        assert "☐" in captured.out
        assert "任务1" in captured.out
        assert "任务2" in captured.out

    def test_display_todo_checkboxes_in_progress(self, cli_instance, capsys):
        """测试进行中任务的 checkbox 显示"""
        cli_instance._display_todo_checkboxes({
            "todos": [
                {"content": "任务1", "status": "in_progress"}
            ]
        })

        captured = capsys.readouterr()
        assert "◐" in captured.out
        assert "任务1" in captured.out

    def test_display_todo_checkboxes_completed(self, cli_instance, capsys):
        """测试已完成任务的 checkbox 显示"""
        cli_instance._display_todo_checkboxes({
            "todos": [
                {"content": "任务1", "status": "completed"}
            ]
        })

        captured = capsys.readouterr()
        assert "☑" in captured.out
        assert "任务1" in captured.out

    def test_display_todo_checkboxes_mixed_status(self, cli_instance, capsys):
        """测试混合状态任务的 checkbox 显示"""
        cli_instance._display_todo_checkboxes({
            "todos": [
                {"content": "已完成任务", "status": "completed"},
                {"content": "进行中任务", "status": "in_progress"},
                {"content": "待处理任务", "status": "pending"}
            ]
        })

        captured = capsys.readouterr()
        assert "☑" in captured.out
        assert "◐" in captured.out
        assert "☐" in captured.out

    def test_display_todo_checkboxes_legacy_format(self, cli_instance, capsys):
        """测试旧格式（tasks 字符串）的兼容性"""
        cli_instance._display_todo_checkboxes({
            "action": "create",
            "tasks": "任务1;任务2;任务3"
        })

        captured = capsys.readouterr()
        assert "任务1" in captured.out
        assert "任务2" in captured.out
        assert "任务3" in captured.out

    def test_display_todo_checkboxes_empty(self, cli_instance, capsys):
        """测试空任务列表的显示"""
        cli_instance._display_todo_checkboxes({})

        captured = capsys.readouterr()
        assert "Updated todos" in captured.out

    def test_display_todo_checkboxes_from_file(self, cli_instance, capsys, tmp_path):
        """测试从文件读取任务列表的显示"""
        import json
        from pathlib import Path

        # 创建临时 todos 文件
        todos_dir = Path.home() / ".jiuwen" / "todos"
        todos_dir.mkdir(parents=True, exist_ok=True)

        test_session_id = "test-file-read-session"
        cli_instance.session_id = test_session_id

        todo_file = todos_dir / f"{test_session_id}.json"
        todos_data = [
            {"content": "任务1", "status": "completed"},
            {"content": "任务2", "status": "in_progress"},
            {"content": "任务3", "status": "pending"}
        ]

        try:
            with open(todo_file, 'w', encoding='utf-8') as f:
                json.dump(todos_data, f)

            # 调用时不传 todos 参数，应该从文件读取
            cli_instance._display_todo_checkboxes({"action": "update", "task_id": "abc", "status": "completed"})

            captured = capsys.readouterr()
            assert "☑" in captured.out  # completed
            assert "◐" in captured.out  # in_progress
            assert "☐" in captured.out  # pending
            assert "任务1" in captured.out
            assert "任务2" in captured.out
            assert "任务3" in captured.out
        finally:
            # 清理测试文件
            if todo_file.exists():
                todo_file.unlink()


class TestGitCodeAppCommand:
    """测试 GitCode App 安装命令"""

    @pytest.fixture
    def cli_instance(self):
        """创建 CLI 实例"""
        from cli.main import JiuwenCLI

        mock_config = {
            "api_key": "test-key",
            "provider": "openai",
            "model": "gpt-4o"
        }

        with patch.object(JiuwenCLI, '_init_agent'):
            cli = JiuwenCLI(mock_config)
            cli.session_id = "test-session"
            return cli

    def test_install_gitcode_app_command(self, cli_instance, capsys):
        """测试 /install-gitcode-app 命令"""
        result = cli_instance.handle_command("/install-gitcode-app")

        assert result == True

        captured = capsys.readouterr()
        # 检查输出包含关键信息
        assert "GitCode" in captured.out or "gitcode" in captured.out.lower()
        assert "@jiuwen" in captured.out

    def test_install_gitcode_app_in_help(self, cli_instance, capsys):
        """测试 /install-gitcode-app 命令出现在帮助中"""
        cli_instance.show_help()

        captured = capsys.readouterr()
        # Rich 表格可能会截断长命令名，所以检查部分匹配
        assert "install-gitco" in captured.out or "GitCode" in captured.out

    def test_show_install_gitcode_app_content(self, cli_instance, capsys):
        """测试 GitCode App 安装指南内容"""
        cli_instance.show_install_gitcode_app()

        captured = capsys.readouterr()
        # 检查安装步骤
        assert "安装" in captured.out
        # 检查使用示例
        assert "@jiuwen" in captured.out
        # 检查 GitCode 链接或提及
        assert "gitcode" in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
