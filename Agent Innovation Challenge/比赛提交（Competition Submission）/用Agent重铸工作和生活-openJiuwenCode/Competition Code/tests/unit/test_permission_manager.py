"""
PermissionManager 单元测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from packages.server.tools.plan_tools import (
    PermissionManager,
    get_permission_manager,
    reset_permission_manager,
)


class TestPermissionManager:
    """PermissionManager 测试"""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """每个测试前重置全局管理器"""
        reset_permission_manager()
        yield
        reset_permission_manager()

    def test_add_allowed_prompts(self):
        """测试添加预授权"""
        manager = PermissionManager()
        prompts = [
            {"tool": "Bash", "prompt": "run tests"},
            {"tool": "Bash", "prompt": "build the project"}
        ]
        manager.add_allowed_prompts(prompts)

        assert len(manager.get_allowed_prompts()) == 2

    def test_clear_allowed_prompts(self):
        """测试清除预授权"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "run tests"}])
        manager.clear_allowed_prompts()

        assert len(manager.get_allowed_prompts()) == 0

    def test_is_command_preauthorized_pytest(self):
        """测试 pytest 命令预授权"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "run tests"}])

        assert manager.is_command_preauthorized("pytest tests/")
        assert manager.is_command_preauthorized("python -m pytest")
        assert manager.is_command_preauthorized("npm test")

    def test_is_command_preauthorized_install(self):
        """测试安装命令预授权"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "install dependencies"}])

        assert manager.is_command_preauthorized("pip install requests")
        assert manager.is_command_preauthorized("npm install lodash")
        assert manager.is_command_preauthorized("yarn add express")

    def test_is_command_preauthorized_build(self):
        """测试构建命令预授权"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "build the project"}])

        assert manager.is_command_preauthorized("npm run build")
        assert manager.is_command_preauthorized("make")
        assert manager.is_command_preauthorized("cargo build")

    def test_is_command_not_preauthorized(self):
        """测试未预授权的命令"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "run tests"}])

        # 这些命令不应该被预授权
        assert not manager.is_command_preauthorized("rm -rf /")
        assert not manager.is_command_preauthorized("git push")
        assert not manager.is_command_preauthorized("echo hello")

    def test_is_command_preauthorized_direct_match(self):
        """测试直接匹配"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "git status"}])

        assert manager.is_command_preauthorized("git status")
        assert manager.is_command_preauthorized("git status --short")

    def test_only_bash_tool_preauthorized(self):
        """测试只有 Bash 工具的预授权生效"""
        manager = PermissionManager()
        manager.add_allowed_prompts([
            {"tool": "Other", "prompt": "run tests"},
            {"tool": "Bash", "prompt": "build the project"}
        ])

        # Other 工具的预授权不应该生效
        assert not manager.is_command_preauthorized("pytest")
        # Bash 工具的预授权应该生效
        assert manager.is_command_preauthorized("npm run build")

    def test_get_matching_prompt(self):
        """测试获取匹配的预授权提示词"""
        manager = PermissionManager()
        manager.add_allowed_prompts([
            {"tool": "Bash", "prompt": "run tests"},
            {"tool": "Bash", "prompt": "build the project"}
        ])

        assert manager.get_matching_prompt("pytest") == "run tests"
        assert manager.get_matching_prompt("npm run build") == "build the project"
        assert manager.get_matching_prompt("rm -rf /") is None

    def test_add_custom_pattern(self):
        """测试添加自定义模式"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "deploy"}])
        manager.add_custom_pattern("deploy", ["kubectl apply", "docker push"])

        assert manager.is_command_preauthorized("kubectl apply -f deployment.yaml")
        assert manager.is_command_preauthorized("docker push myimage:latest")

    def test_global_permission_manager(self):
        """测试全局权限管理器"""
        manager1 = get_permission_manager()
        manager2 = get_permission_manager()

        # 应该是同一个实例
        assert manager1 is manager2

        # 添加预授权
        manager1.add_allowed_prompts([{"tool": "Bash", "prompt": "run tests"}])

        # 另一个引用也应该能看到
        assert manager2.is_command_preauthorized("pytest")

    def test_case_insensitive_matching(self):
        """测试大小写不敏感匹配"""
        manager = PermissionManager()
        manager.add_allowed_prompts([{"tool": "Bash", "prompt": "run tests"}])

        assert manager.is_command_preauthorized("PYTEST")
        assert manager.is_command_preauthorized("PyTest tests/")
        assert manager.is_command_preauthorized("NPM TEST")
