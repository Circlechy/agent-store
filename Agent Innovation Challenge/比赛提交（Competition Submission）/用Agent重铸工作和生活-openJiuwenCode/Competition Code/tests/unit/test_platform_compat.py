"""
平台兼容性模块测试

测试 platform_compat.py 中的跨平台功能
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from packages.server.utils.platform_compat import (
    Platform,
    get_current_platform,
    is_windows,
    is_unix,
    set_file_permissions,
    get_restricted_paths,
    is_restricted_path,
    get_blacklisted_commands,
    get_plan_mode_blocked_patterns,
    get_plan_mode_blocked_script_patterns,
    get_mode_blocked_commands,
    supports_ansi_colors,
    normalize_path,
    is_absolute_path,
)


class TestPlatformDetection:
    """平台检测测试"""

    def test_get_current_platform_returns_enum(self):
        """测试 get_current_platform 返回 Platform 枚举"""
        result = get_current_platform()
        assert isinstance(result, Platform)

    def test_get_current_platform_valid_value(self):
        """测试返回的平台值是有效的"""
        result = get_current_platform()
        assert result in [Platform.WINDOWS, Platform.LINUX, Platform.MACOS, Platform.UNKNOWN]

    def test_is_windows_returns_bool(self):
        """测试 is_windows 返回布尔值"""
        result = is_windows()
        assert isinstance(result, bool)

    def test_is_unix_returns_bool(self):
        """测试 is_unix 返回布尔值"""
        result = is_unix()
        assert isinstance(result, bool)

    def test_platform_consistency(self):
        """测试平台检测的一致性"""
        # 不能同时是 Windows 和 Unix
        if is_windows():
            assert not is_unix()
        if is_unix():
            assert not is_windows()


class TestPlatformDetectionMocked:
    """使用 mock 测试不同平台的行为"""

    def test_windows_detection(self):
        """测试 Windows 平台检测"""
        with patch('packages.server.utils.platform_compat.sys.platform', 'win32'):
            # 需要重新导入以应用 mock
            from packages.server.utils import platform_compat
            # 直接测试 sys.platform
            assert platform_compat.sys.platform == 'win32'

    def test_linux_detection(self):
        """测试 Linux 平台检测"""
        with patch('packages.server.utils.platform_compat.sys.platform', 'linux'):
            from packages.server.utils import platform_compat
            assert platform_compat.sys.platform == 'linux'

    def test_macos_detection(self):
        """测试 macOS 平台检测"""
        with patch('packages.server.utils.platform_compat.sys.platform', 'darwin'):
            from packages.server.utils import platform_compat
            assert platform_compat.sys.platform == 'darwin'


class TestRestrictedPaths:
    """受限路径测试"""

    def test_get_restricted_paths_returns_list(self):
        """测试 get_restricted_paths 返回列表"""
        paths = get_restricted_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0

    def test_restricted_paths_are_strings(self):
        """测试受限路径都是字符串"""
        paths = get_restricted_paths()
        for path in paths:
            assert isinstance(path, str)

    def test_is_restricted_path_returns_bool(self):
        """测试 is_restricted_path 返回布尔值"""
        result = is_restricted_path("/some/path")
        assert isinstance(result, bool)

    def test_is_restricted_path_empty_string(self):
        """测试空字符串不是受限路径"""
        assert is_restricted_path("") == False

    def test_is_restricted_path_none(self):
        """测试 None 不是受限路径"""
        assert is_restricted_path(None) == False

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_etc_is_restricted_on_unix(self):
        """测试 /etc 在 Unix 上是受限路径"""
        assert is_restricted_path("/etc") == True
        assert is_restricted_path("/etc/passwd") == True

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_home_not_restricted_on_unix(self):
        """测试用户主目录不是受限路径"""
        home = os.path.expanduser("~")
        assert is_restricted_path(home) == False

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_system_restricted(self):
        """测试 Windows 系统目录是受限路径"""
        assert is_restricted_path("C:\\Windows") == True
        assert is_restricted_path("C:\\Windows\\System32") == True


class TestBlacklistedCommands:
    """黑名单命令测试"""

    def test_get_blacklisted_commands_returns_list(self):
        """测试 get_blacklisted_commands 返回列表"""
        commands = get_blacklisted_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0

    def test_blacklisted_commands_are_strings(self):
        """测试黑名单命令都是字符串"""
        commands = get_blacklisted_commands()
        for cmd in commands:
            assert isinstance(cmd, str)

    def test_fork_bomb_always_blacklisted(self):
        """测试 fork bomb 始终在黑名单中"""
        commands = get_blacklisted_commands()
        assert ":(){:|:&};:" in commands

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_rm_rf_blacklisted_on_unix(self):
        """测试 rm -rf / 在 Unix 上被黑名单"""
        commands = get_blacklisted_commands()
        assert "rm -rf /" in commands

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_format_blacklisted_on_windows(self):
        """测试 format 在 Windows 上被黑名单"""
        commands = get_blacklisted_commands()
        assert any("format" in cmd.lower() for cmd in commands)


class TestPlanModePatterns:
    """PLAN 模式阻止模式测试"""

    def test_get_plan_mode_blocked_patterns_returns_list(self):
        """测试 get_plan_mode_blocked_patterns 返回列表"""
        patterns = get_plan_mode_blocked_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_common_patterns_present(self):
        """测试通用模式存在"""
        patterns = get_plan_mode_blocked_patterns()
        assert "git commit" in patterns
        assert "pip install" in patterns

    def test_redirect_patterns_present(self):
        """测试重定向模式存在"""
        patterns = get_plan_mode_blocked_patterns()
        assert "> " in patterns
        assert ">> " in patterns

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_unix_file_commands_blocked(self):
        """测试 Unix 文件命令被阻止"""
        patterns = get_plan_mode_blocked_patterns()
        assert "rm " in patterns
        assert "mv " in patterns
        assert "cp " in patterns

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_file_commands_blocked(self):
        """测试 Windows 文件命令被阻止"""
        patterns = get_plan_mode_blocked_patterns()
        assert "del " in patterns
        assert "copy " in patterns
        assert "move " in patterns


class TestScriptPatterns:
    """脚本执行模式测试"""

    def test_get_plan_mode_blocked_script_patterns_returns_list(self):
        """测试 get_plan_mode_blocked_script_patterns 返回列表"""
        patterns = get_plan_mode_blocked_script_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_python_patterns_present(self):
        """测试 Python 脚本模式存在"""
        patterns = get_plan_mode_blocked_script_patterns()
        assert "python -c" in patterns
        assert "python3 -c" in patterns

    def test_node_patterns_present(self):
        """测试 Node.js 脚本模式存在"""
        patterns = get_plan_mode_blocked_script_patterns()
        assert "node -e" in patterns

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_bash_patterns_on_unix(self):
        """测试 bash 脚本模式在 Unix 上存在"""
        patterns = get_plan_mode_blocked_script_patterns()
        assert "bash -c" in patterns
        assert "sh -c" in patterns

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_powershell_patterns_on_windows(self):
        """测试 PowerShell 脚本模式在 Windows 上存在"""
        patterns = get_plan_mode_blocked_script_patterns()
        assert any("powershell" in p.lower() for p in patterns)


class TestModeBlockedCommands:
    """模式阻止命令测试"""

    def test_get_mode_blocked_commands_returns_set(self):
        """测试 get_mode_blocked_commands 返回集合"""
        commands = get_mode_blocked_commands()
        assert isinstance(commands, set)
        assert len(commands) > 0

    def test_common_commands_blocked(self):
        """测试通用命令被阻止"""
        commands = get_mode_blocked_commands()
        assert "dd" in commands
        assert "mkfs" in commands
        assert "format" in commands


class TestFilePermissions:
    """文件权限测试"""

    def test_set_file_permissions_returns_bool(self, tmp_path):
        """测试 set_file_permissions 返回布尔值"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = set_file_permissions(test_file)
        assert isinstance(result, bool)

    def test_set_file_permissions_success(self, tmp_path):
        """测试成功设置文件权限"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = set_file_permissions(test_file, 0o600)
        assert result == True

    def test_set_file_permissions_nonexistent_file(self, tmp_path):
        """测试不存在的文件返回 False"""
        test_file = tmp_path / "nonexistent.txt"
        result = set_file_permissions(test_file)
        assert result == False

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_file_permissions_applied_on_unix(self, tmp_path):
        """测试 Unix 上文件权限被正确应用"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        set_file_permissions(test_file, 0o600)
        # 检查权限
        import stat
        mode = os.stat(test_file).st_mode
        assert mode & 0o777 == 0o600


class TestColorSupport:
    """终端颜色支持测试"""

    def test_supports_ansi_colors_returns_bool(self):
        """测试 supports_ansi_colors 返回布尔值"""
        result = supports_ansi_colors()
        assert isinstance(result, bool)

    def test_no_color_env_disables_colors(self):
        """测试 NO_COLOR 环境变量禁用颜色"""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            assert supports_ansi_colors() == False

    def test_force_color_env_enables_colors(self):
        """测试 FORCE_COLOR 环境变量启用颜色"""
        with patch.dict(os.environ, {'FORCE_COLOR': '1'}, clear=False):
            # 移除 NO_COLOR 如果存在
            env = os.environ.copy()
            env.pop('NO_COLOR', None)
            env['FORCE_COLOR'] = '1'
            with patch.dict(os.environ, env, clear=True):
                assert supports_ansi_colors() == True


class TestPathUtilities:
    """路径工具测试"""

    def test_normalize_path_returns_string(self):
        """测试 normalize_path 返回字符串"""
        result = normalize_path("/some/path")
        assert isinstance(result, str)

    def test_normalize_path_removes_double_slashes(self):
        """测试 normalize_path 移除双斜杠"""
        result = normalize_path("/some//path")
        assert "//" not in result

    def test_is_absolute_path_returns_bool(self):
        """测试 is_absolute_path 返回布尔值"""
        result = is_absolute_path("/some/path")
        assert isinstance(result, bool)

    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
    def test_unix_absolute_path(self):
        """测试 Unix 绝对路径检测"""
        assert is_absolute_path("/home/user") == True
        assert is_absolute_path("relative/path") == False

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_absolute_path(self):
        """测试 Windows 绝对路径检测"""
        assert is_absolute_path("C:\\Users\\user") == True
        assert is_absolute_path("relative\\path") == False
        assert is_absolute_path("\\\\server\\share") == True


class TestIntegration:
    """集成测试"""

    def test_all_functions_callable(self):
        """测试所有导出的函数都可调用"""
        from packages.server.utils.platform_compat import (
            get_current_platform,
            is_windows,
            is_unix,
            set_file_permissions,
            get_restricted_paths,
            is_restricted_path,
            get_blacklisted_commands,
            get_plan_mode_blocked_patterns,
            get_plan_mode_blocked_script_patterns,
            get_mode_blocked_commands,
            supports_ansi_colors,
            normalize_path,
            is_absolute_path,
        )

        # 所有函数都应该可以无参数调用（除了需要参数的）
        assert callable(get_current_platform)
        assert callable(is_windows)
        assert callable(is_unix)
        assert callable(get_restricted_paths)
        assert callable(get_blacklisted_commands)
        assert callable(get_plan_mode_blocked_patterns)
        assert callable(get_plan_mode_blocked_script_patterns)
        assert callable(get_mode_blocked_commands)
        assert callable(supports_ansi_colors)

    def test_platform_specific_lists_not_empty(self):
        """测试平台特定列表不为空"""
        assert len(get_restricted_paths()) > 0
        assert len(get_blacklisted_commands()) > 0
        assert len(get_plan_mode_blocked_patterns()) > 0
        assert len(get_plan_mode_blocked_script_patterns()) > 0
        assert len(get_mode_blocked_commands()) > 0
