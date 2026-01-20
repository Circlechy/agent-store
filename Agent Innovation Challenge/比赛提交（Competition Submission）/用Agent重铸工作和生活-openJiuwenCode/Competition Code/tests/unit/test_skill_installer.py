"""
Skill 安装器单元测试
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from packages.server.skills.installer import (
    SkillInstaller,
    InstalledPlugin,
    MarketplaceInfo,
    parse_plugin_spec,
    DEFAULT_MARKETPLACES,
)


# ==================== parse_plugin_spec 测试 ====================

class TestParsePluginSpec:
    """parse_plugin_spec 测试"""

    def test_valid_spec(self):
        """测试有效的 plugin@marketplace 格式"""
        plugin, marketplace = parse_plugin_spec("example-skills@anthropics")
        assert plugin == "example-skills"
        assert marketplace == "anthropics"

    def test_spec_with_multiple_at(self):
        """测试包含多个 @ 的格式"""
        plugin, marketplace = parse_plugin_spec("my@plugin@marketplace")
        assert plugin == "my@plugin"
        assert marketplace == "marketplace"

    def test_invalid_spec_no_at(self):
        """测试无效格式（无 @）"""
        with pytest.raises(ValueError, match="无效格式"):
            parse_plugin_spec("example-skills")

    def test_invalid_spec_empty_plugin(self):
        """测试无效格式（空 plugin）"""
        with pytest.raises(ValueError, match="不能为空"):
            parse_plugin_spec("@marketplace")

    def test_invalid_spec_empty_marketplace(self):
        """测试无效格式（空 marketplace）"""
        with pytest.raises(ValueError, match="不能为空"):
            parse_plugin_spec("plugin@")


# ==================== MarketplaceInfo 测试 ====================

class TestMarketplaceInfo:
    """MarketplaceInfo 测试"""

    def test_to_dict(self):
        """测试序列化"""
        mp = MarketplaceInfo(
            name="test-mp",
            url="https://github.com/test/skills.git",
            install_location=Path("/tmp/test"),
            last_updated=datetime(2026, 1, 19, 10, 0, 0),
        )
        data = mp.to_dict()
        assert data["url"] == "https://github.com/test/skills.git"
        assert data["install_location"] == "/tmp/test"
        assert "2026-01-19" in data["last_updated"]

    def test_from_dict(self):
        """测试反序列化"""
        data = {
            "url": "https://github.com/test/skills.git",
            "install_location": "/tmp/test",
            "last_updated": "2026-01-19T10:00:00",
        }
        mp = MarketplaceInfo.from_dict("test-mp", data)
        assert mp.name == "test-mp"
        assert mp.url == "https://github.com/test/skills.git"
        assert mp.install_location == Path("/tmp/test")
        assert mp.last_updated.year == 2026


# ==================== InstalledPlugin 测试 ====================

class TestInstalledPlugin:
    """InstalledPlugin 测试"""

    def test_spec_property(self):
        """测试 spec 属性"""
        plugin = InstalledPlugin(
            plugin_name="example-skills",
            marketplace="anthropics",
            install_path=Path("/tmp/cache"),
            version="1.0.0",
            installed_at=datetime.now(),
            skills=["skill1", "skill2"],
        )
        assert plugin.spec == "example-skills@anthropics"

    def test_to_dict(self):
        """测试序列化"""
        plugin = InstalledPlugin(
            plugin_name="example-skills",
            marketplace="anthropics",
            install_path=Path("/tmp/cache"),
            version="1.0.0",
            installed_at=datetime(2026, 1, 19, 10, 0, 0),
            git_commit="abc123",
            skills=["skill1", "skill2"],
        )
        data = plugin.to_dict()
        assert data["install_path"] == "/tmp/cache"
        assert data["version"] == "1.0.0"
        assert data["git_commit"] == "abc123"
        assert data["skills"] == ["skill1", "skill2"]

    def test_from_dict(self):
        """测试反序列化"""
        data = {
            "install_path": "/tmp/cache",
            "version": "1.0.0",
            "installed_at": "2026-01-19T10:00:00",
            "git_commit": "abc123",
            "skills": ["skill1", "skill2"],
        }
        plugin = InstalledPlugin.from_dict("example-skills@anthropics", data)
        assert plugin.plugin_name == "example-skills"
        assert plugin.marketplace == "anthropics"
        assert plugin.version == "1.0.0"
        assert plugin.skills == ["skill1", "skill2"]


# ==================== SkillInstaller 测试 ====================

class TestSkillInstaller:
    """SkillInstaller 测试"""

    @pytest.fixture
    def installer(self, tmp_path):
        """创建测试用的安装器"""
        return SkillInstaller(base_dir=tmp_path)

    def test_init_creates_dirs(self, tmp_path):
        """测试初始化创建目录"""
        installer = SkillInstaller(base_dir=tmp_path)
        assert installer.cache_dir.exists()
        assert installer.marketplaces_dir.exists()

    def test_default_marketplaces(self, installer):
        """测试默认 marketplace"""
        marketplaces = installer._load_known_marketplaces()
        assert "anthropics" in marketplaces

    def test_save_and_load_installed_plugins(self, installer, tmp_path):
        """测试保存和加载已安装插件"""
        plugin = InstalledPlugin(
            plugin_name="test-plugin",
            marketplace="test-mp",
            install_path=tmp_path / "cache" / "test",
            version="1.0.0",
            installed_at=datetime.now(),
            skills=["skill1"],
        )

        # 保存
        installer._save_installed_plugins({plugin.spec: plugin})

        # 加载
        loaded = installer._load_installed_plugins()
        assert plugin.spec in loaded
        assert loaded[plugin.spec].plugin_name == "test-plugin"

    def test_list_installed_empty(self, installer):
        """测试列出已安装插件（空）"""
        plugins = installer.list_installed()
        assert plugins == []

    def test_add_marketplace(self, installer):
        """测试添加自定义 marketplace"""
        mp = installer.add_marketplace(
            "custom-mp",
            "https://github.com/custom/skills.git"
        )
        assert mp.name == "custom-mp"
        assert mp.url == "https://github.com/custom/skills.git"

        # 验证已保存
        marketplaces = installer._load_known_marketplaces()
        assert "custom-mp" in marketplaces

    def test_list_marketplaces(self, installer):
        """测试列出 marketplace"""
        marketplaces = installer.list_marketplaces()
        # 至少有默认的 marketplace
        assert len(marketplaces) >= 1
        names = [mp.name for mp in marketplaces]
        assert "anthropics" in names

    @patch("subprocess.run")
    def test_clone_marketplace(self, mock_run, installer):
        """测试克隆 marketplace"""
        mock_run.return_value = MagicMock(returncode=0)

        mp = MarketplaceInfo(
            name="test-mp",
            url="https://github.com/test/skills.git",
            install_location=installer.marketplaces_dir / "test-mp",
        )

        result = installer._clone_marketplace(mp)
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_clone_marketplace_already_exists(self, mock_run, installer):
        """测试克隆已存在的 marketplace"""
        mp = MarketplaceInfo(
            name="test-mp",
            url="https://github.com/test/skills.git",
            install_location=installer.marketplaces_dir / "test-mp",
        )
        mp.install_location.mkdir(parents=True)

        result = installer._clone_marketplace(mp)
        assert result is True
        mock_run.assert_not_called()

    def test_find_plugin_in_marketplace_direct_structure(self, installer, tmp_path):
        """测试在 marketplace 中查找插件（直接目录结构）"""
        # 创建 marketplace 目录结构
        mp_path = tmp_path / "marketplace"
        plugin_path = mp_path / "test-plugin"
        plugin_path.mkdir(parents=True)

        # 创建 skill
        skill_dir = plugin_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test")

        found = installer._find_plugin_in_marketplace(mp_path, "test-plugin")
        assert found == plugin_path

    def test_find_plugin_in_marketplace_skills_subdir(self, installer, tmp_path):
        """测试在 marketplace 中查找插件（skills 子目录）"""
        # 创建 marketplace 目录结构
        mp_path = tmp_path / "marketplace"
        plugin_path = mp_path / "skills" / "test-plugin"
        plugin_path.mkdir(parents=True)

        found = installer._find_plugin_in_marketplace(mp_path, "test-plugin")
        assert found == plugin_path

    def test_find_plugin_not_found(self, installer, tmp_path):
        """测试查找不存在的插件"""
        mp_path = tmp_path / "marketplace"
        mp_path.mkdir()

        found = installer._find_plugin_in_marketplace(mp_path, "nonexistent")
        assert found is None

    def test_copy_plugin_skills_structure1(self, installer, tmp_path):
        """测试复制插件 skills（结构1：plugin/skills/<skill>/SKILL.md）"""
        # 创建源目录
        plugin_path = tmp_path / "plugin"
        skills_dir = plugin_path / "skills"
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir(parents=True)
        (skill1_dir / "SKILL.md").write_text("---\nname: skill1\n---\n# Skill 1")

        skill2_dir = skills_dir / "skill2"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("---\nname: skill2\n---\n# Skill 2")

        # 复制
        dest_path = tmp_path / "dest"
        skills = installer._copy_plugin_skills(plugin_path, dest_path)

        assert set(skills) == {"skill1", "skill2"}
        assert (dest_path / "skill1" / "SKILL.md").exists()
        assert (dest_path / "skill2" / "SKILL.md").exists()

    def test_copy_plugin_skills_structure2(self, installer, tmp_path):
        """测试复制插件 skills（结构2：plugin/<skill>/SKILL.md）"""
        # 创建源目录
        plugin_path = tmp_path / "plugin"
        skill1_dir = plugin_path / "skill1"
        skill1_dir.mkdir(parents=True)
        (skill1_dir / "SKILL.md").write_text("---\nname: skill1\n---\n# Skill 1")

        # 复制
        dest_path = tmp_path / "dest"
        skills = installer._copy_plugin_skills(plugin_path, dest_path)

        assert skills == ["skill1"]
        assert (dest_path / "skill1" / "SKILL.md").exists()

    def test_copy_plugin_skills_structure3(self, installer, tmp_path):
        """测试复制插件 skills（结构3：plugin/SKILL.md）"""
        # 创建源目录
        plugin_path = tmp_path / "single-skill"
        plugin_path.mkdir()
        (plugin_path / "SKILL.md").write_text("---\nname: single-skill\n---\n# Single")

        # 复制
        dest_path = tmp_path / "dest"
        skills = installer._copy_plugin_skills(plugin_path, dest_path)

        assert skills == ["single-skill"]
        assert (dest_path / "single-skill" / "SKILL.md").exists()

    @patch("subprocess.run")
    def test_install_plugin_success(self, mock_run, installer, tmp_path):
        """测试安装插件成功"""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc12345")

        # 创建模拟的 marketplace
        mp_path = installer.marketplaces_dir / "test-mp"
        plugin_path = mp_path / "test-plugin"
        skill_dir = plugin_path / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test")

        # 添加 marketplace
        installer.add_marketplace("test-mp", "https://github.com/test/skills.git")

        # 安装
        plugin = installer.install("test-plugin@test-mp")

        assert plugin.plugin_name == "test-plugin"
        assert plugin.marketplace == "test-mp"
        assert "test-skill" in plugin.skills

        # 验证缓存
        cache_path = installer.cache_dir / "test-mp" / "test-plugin"
        assert cache_path.exists()
        assert (cache_path / "test-skill" / "SKILL.md").exists()

    def test_install_plugin_already_installed(self, installer, tmp_path):
        """测试安装已安装的插件"""
        # 创建已安装记录
        plugin = InstalledPlugin(
            plugin_name="test-plugin",
            marketplace="test-mp",
            install_path=tmp_path / "cache",
            version="1.0.0",
            installed_at=datetime.now(),
            skills=["skill1"],
        )
        installer._save_installed_plugins({plugin.spec: plugin})

        # 尝试安装
        with pytest.raises(ValueError, match="已安装"):
            installer.install("test-plugin@test-mp")

    def test_uninstall_plugin_success(self, installer, tmp_path):
        """测试卸载插件成功"""
        # 创建已安装记录和缓存
        cache_path = installer.cache_dir / "test-mp" / "test-plugin"
        cache_path.mkdir(parents=True)
        (cache_path / "test-skill").mkdir()

        plugin = InstalledPlugin(
            plugin_name="test-plugin",
            marketplace="test-mp",
            install_path=cache_path,
            version="1.0.0",
            installed_at=datetime.now(),
            skills=["test-skill"],
        )
        installer._save_installed_plugins({plugin.spec: plugin})

        # 卸载
        result = installer.uninstall("test-plugin@test-mp")

        assert result is True
        assert not cache_path.exists()

        # 验证记录已删除
        installed = installer._load_installed_plugins()
        assert "test-plugin@test-mp" not in installed

    def test_uninstall_plugin_not_installed(self, installer):
        """测试卸载未安装的插件"""
        with pytest.raises(ValueError, match="未安装"):
            installer.uninstall("nonexistent@test-mp")


# ==================== 集成测试 ====================

class TestSkillInstallerIntegration:
    """SkillInstaller 集成测试"""

    @pytest.fixture
    def full_setup(self, tmp_path):
        """创建完整的测试环境"""
        # 创建安装器
        installer = SkillInstaller(base_dir=tmp_path)

        # 创建模拟的 marketplace
        mp_path = installer.marketplaces_dir / "test-marketplace"
        mp_path.mkdir(parents=True)

        # 创建 plugin 目录结构
        plugin_path = mp_path / "example-plugin"
        plugin_path.mkdir()

        # 创建多个 skills
        for i in range(3):
            skill_dir = plugin_path / f"skill-{i}"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""---
name: skill-{i}
description: Test skill {i}
allowed-tools: Bash,Read
---

# Skill {i}

This is test skill {i}.
""")

        # 添加 marketplace
        installer.add_marketplace(
            "test-marketplace",
            "https://github.com/test/marketplace.git"
        )

        return installer

    @patch("subprocess.run")
    def test_full_install_uninstall_cycle(self, mock_run, full_setup):
        """测试完整的安装-卸载周期"""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc12345")
        installer = full_setup

        # 安装
        plugin = installer.install("example-plugin@test-marketplace")
        assert plugin.plugin_name == "example-plugin"
        assert len(plugin.skills) == 3

        # 验证已安装
        installed = installer.list_installed()
        assert len(installed) == 1
        assert installed[0].spec == "example-plugin@test-marketplace"

        # 卸载
        installer.uninstall("example-plugin@test-marketplace")

        # 验证已卸载
        installed = installer.list_installed()
        assert len(installed) == 0
