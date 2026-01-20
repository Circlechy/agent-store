"""
Skill 系统单元测试
"""

import pytest
import tempfile
from pathlib import Path

from packages.server.skills.models import Skill, SkillMetadata, SkillSource
from packages.server.skills.loader import SkillLoader
from packages.server.skills.matcher import SkillMatcher
from packages.server.skills.executor import SkillExecutor, SkillExecutionContext, TOOL_NAME_MAP
from packages.server.skills.manager import SkillManager


# ==================== SkillMetadata 测试 ====================

class TestSkillMetadata:
    """SkillMetadata 测试"""

    def test_from_yaml_basic(self):
        """测试基本 YAML 解析"""
        yaml_str = """
name: test-skill
description: A test skill
allowed-tools: Bash,Read,Write
"""
        metadata = SkillMetadata.from_yaml(yaml_str)
        assert metadata.name == "test-skill"
        assert metadata.description == "A test skill"
        assert metadata.allowed_tools == {"bash", "read", "write"}

    def test_from_yaml_list_tools(self):
        """测试列表格式的 allowed-tools"""
        yaml_str = """
name: test-skill
description: A test skill
allowed-tools:
  - Bash
  - Read
  - Write
"""
        metadata = SkillMetadata.from_yaml(yaml_str)
        assert metadata.allowed_tools == {"bash", "read", "write"}

    def test_from_yaml_empty_tools(self):
        """测试空的 allowed-tools"""
        yaml_str = """
name: test-skill
description: A test skill
"""
        metadata = SkillMetadata.from_yaml(yaml_str)
        assert metadata.allowed_tools == set()

    def test_from_yaml_with_optional_fields(self):
        """测试可选字段"""
        yaml_str = """
name: test-skill
description: A test skill
version: 2.0.0
author: Test Author
tags:
  - test
  - example
"""
        metadata = SkillMetadata.from_yaml(yaml_str)
        assert metadata.version == "2.0.0"
        assert metadata.author == "Test Author"
        assert metadata.tags == ["test", "example"]


# ==================== Skill 测试 ====================

class TestSkill:
    """Skill 测试"""

    def test_from_file(self, tmp_path):
        """测试从文件加载 Skill"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill for testing
allowed-tools: Bash,Read
---

# Test Skill

This is a test skill.

## Usage

Use this skill for testing.
""")
        skill = Skill.from_file(skill_file, SkillSource.LOCAL)
        assert skill.name == "test-skill"
        assert skill.description == "A test skill for testing"
        assert skill.allowed_tools == {"bash", "read"}
        assert "# Test Skill" in skill.content
        assert skill.source == SkillSource.LOCAL

    def test_from_file_no_frontmatter(self, tmp_path):
        """测试无 frontmatter 的文件"""
        skill_dir = tmp_path / "simple-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""# Simple Skill

Just some content without frontmatter.
""")
        skill = Skill.from_file(skill_file, SkillSource.PROJECT)
        assert skill.name == "simple-skill"  # 使用目录名
        assert skill.description == ""
        assert skill.allowed_tools == set()

    def test_to_prompt_injection(self, tmp_path):
        """测试提示词注入生成"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill
allowed-tools: Bash,Read
---

# Test Content
""")
        skill = Skill.from_file(skill_file, SkillSource.LOCAL)
        prompt = skill.to_prompt_injection()
        assert "test-skill" in prompt
        assert "# Test Content" in prompt
        assert "bash" in prompt.lower() or "read" in prompt.lower()


# ==================== SkillLoader 测试 ====================

class TestSkillLoader:
    """SkillLoader 测试"""

    def test_load_local_skills(self, tmp_path, monkeypatch):
        """测试加载本地 skills"""
        # 创建临时的 ~/.jiuwen/skills 目录
        local_skills_dir = tmp_path / ".jiuwen" / "skills"
        local_skills_dir.mkdir(parents=True)

        # 创建测试 skill
        skill_dir = local_skills_dir / "local-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: local-skill
description: A local skill
---
# Local Skill
""")

        # Mock home 目录
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        loader = SkillLoader(project_root=tmp_path / "project")
        skills = loader.load_all()

        assert "local-skill" in skills
        assert skills["local-skill"].source == SkillSource.LOCAL

    def test_load_project_skills(self, tmp_path, monkeypatch):
        """测试加载项目 skills"""
        # 创建项目 skills 目录
        project_root = tmp_path / "project"
        project_skills_dir = project_root / ".jiuwen" / "skills"
        project_skills_dir.mkdir(parents=True)

        # 创建测试 skill
        skill_dir = project_skills_dir / "project-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: project-skill
description: A project skill
---
# Project Skill
""")

        # Mock home 目录（空的）
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        loader = SkillLoader(project_root=project_root)
        skills = loader.load_all()

        assert "project-skill" in skills
        assert skills["project-skill"].source == SkillSource.PROJECT

    def test_project_skills_override_local(self, tmp_path, monkeypatch):
        """测试项目 skills 覆盖本地 skills"""
        # 创建本地 skill
        local_skills_dir = tmp_path / ".jiuwen" / "skills"
        local_skills_dir.mkdir(parents=True)
        local_skill_dir = local_skills_dir / "same-name"
        local_skill_dir.mkdir()
        (local_skill_dir / "SKILL.md").write_text("""---
name: same-name
description: Local version
---
# Local
""")

        # 创建项目 skill（同名）
        project_root = tmp_path / "project"
        project_skills_dir = project_root / ".jiuwen" / "skills"
        project_skills_dir.mkdir(parents=True)
        project_skill_dir = project_skills_dir / "same-name"
        project_skill_dir.mkdir()
        (project_skill_dir / "SKILL.md").write_text("""---
name: same-name
description: Project version
---
# Project
""")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        loader = SkillLoader(project_root=project_root)
        skills = loader.load_all()

        assert "same-name" in skills
        assert skills["same-name"].source == SkillSource.PROJECT
        assert skills["same-name"].description == "Project version"


# ==================== SkillMatcher 测试 ====================

class TestSkillMatcher:
    """SkillMatcher 测试"""

    @pytest.fixture
    def loader_with_skills(self, tmp_path, monkeypatch):
        """创建带有测试 skills 的 loader"""
        local_skills_dir = tmp_path / ".jiuwen" / "skills"
        local_skills_dir.mkdir(parents=True)

        # 创建 youtube-transcript skill
        skill1_dir = local_skills_dir / "youtube-transcript"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
name: youtube-transcript
description: Download YouTube video transcripts when user provides a YouTube URL
allowed-tools: Bash,Read,Write
---
# YouTube Transcript
""")

        # 创建 article-extractor skill
        skill2_dir = local_skills_dir / "article-extractor"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
name: article-extractor
description: Extract clean article content from URLs
allowed-tools: Bash,Write
---
# Article Extractor
""")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        loader = SkillLoader(project_root=tmp_path / "project")
        loader.load_all()
        return loader

    def test_match_explicit_skill_command(self, loader_with_skills):
        """测试显式 /skill 命令匹配"""
        matcher = SkillMatcher(loader_with_skills)
        result = matcher.match_explicit("/skill youtube-transcript")
        assert result is not None
        skill, args = result
        assert skill.name == "youtube-transcript"
        assert args == ""

    def test_match_explicit_skill_command_with_args(self, loader_with_skills):
        """测试带参数的 /skill 命令"""
        matcher = SkillMatcher(loader_with_skills)
        result = matcher.match_explicit("/skill youtube-transcript https://youtube.com/watch?v=xxx")
        assert result is not None
        skill, args = result
        assert skill.name == "youtube-transcript"
        assert "youtube.com" in args

    def test_match_explicit_slash_skill_name(self, loader_with_skills):
        """测试 /<skill-name> 格式"""
        matcher = SkillMatcher(loader_with_skills)
        result = matcher.match_explicit("/youtube-transcript")
        assert result is not None
        skill, args = result
        assert skill.name == "youtube-transcript"

    def test_match_explicit_unknown_skill(self, loader_with_skills):
        """测试未知 skill"""
        matcher = SkillMatcher(loader_with_skills)
        result = matcher.match_explicit("/skill unknown-skill")
        assert result is None

    def test_match_declarative(self, loader_with_skills):
        """测试声明式匹配"""
        matcher = SkillMatcher(loader_with_skills)
        skill = matcher.match_declarative("download transcript from youtube video")
        assert skill is not None
        assert skill.name == "youtube-transcript"


# ==================== SkillExecutor 测试 ====================

class TestSkillExecutor:
    """SkillExecutor 测试"""

    @pytest.fixture
    def sample_skill(self, tmp_path):
        """创建示例 skill"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill
allowed-tools: Bash,Read
---
# Test Skill
""")
        return Skill.from_file(skill_file, SkillSource.LOCAL)

    def test_activate_skill(self, sample_skill):
        """测试激活 skill"""
        executor = SkillExecutor()
        assert not executor.is_skill_active

        context = executor.activate_skill(sample_skill)
        assert executor.is_skill_active
        assert executor.current_skill == sample_skill
        assert context.skill == sample_skill

    def test_deactivate_skill(self, sample_skill):
        """测试停用 skill"""
        executor = SkillExecutor()
        executor.activate_skill(sample_skill)
        assert executor.is_skill_active

        executor.deactivate_skill()
        assert not executor.is_skill_active
        assert executor.current_skill is None

    def test_is_tool_allowed(self, sample_skill):
        """测试工具权限检查"""
        executor = SkillExecutor()
        executor.activate_skill(sample_skill)

        # 允许的工具
        assert executor.is_tool_allowed("bash")
        assert executor.is_tool_allowed("Bash")  # 大小写不敏感
        assert executor.is_tool_allowed("read")
        assert executor.is_tool_allowed("read_file")  # 别名

        # 不允许的工具
        assert not executor.is_tool_allowed("write")
        assert not executor.is_tool_allowed("edit")

    def test_is_tool_allowed_no_skill(self):
        """测试无激活 skill 时的工具权限"""
        executor = SkillExecutor()
        # 没有激活的 skill，所有工具都允许
        assert executor.is_tool_allowed("bash")
        assert executor.is_tool_allowed("write")
        assert executor.is_tool_allowed("anything")

    def test_filter_tools(self, sample_skill):
        """测试工具过滤"""
        executor = SkillExecutor()
        executor.activate_skill(sample_skill)

        # 模拟工具列表
        class MockTool:
            def __init__(self, name):
                self.name = name

        tools = [
            MockTool("bash"),
            MockTool("read_file"),
            MockTool("write_file"),
            MockTool("edit_file"),
        ]

        filtered = executor.filter_tools(tools)
        filtered_names = [t.name for t in filtered]

        assert "bash" in filtered_names
        assert "read_file" in filtered_names
        assert "write_file" not in filtered_names
        assert "edit_file" not in filtered_names


# ==================== SkillManager 测试 ====================

class TestSkillManager:
    """SkillManager 测试"""

    def test_integration(self, tmp_path, monkeypatch):
        """测试 SkillManager 集成"""
        # 创建测试 skill
        local_skills_dir = tmp_path / ".jiuwen" / "skills"
        local_skills_dir.mkdir(parents=True)
        skill_dir = local_skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
allowed-tools: Bash,Read
---
# Test Skill
""")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SkillManager(project_root=tmp_path / "project")
        manager.load_skills()

        # 测试列出 skills
        skills = manager.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "test-skill"

        # 测试获取 skill
        skill = manager.get_skill("test-skill")
        assert skill is not None
        assert skill.name == "test-skill"

        # 测试激活 skill
        context = manager.activate_skill(skill)
        assert manager.is_skill_active
        assert manager.current_skill == skill

        # 测试工具权限
        assert manager.is_tool_allowed("bash")
        assert not manager.is_tool_allowed("write")

        # 测试停用 skill
        manager.deactivate_skill()
        assert not manager.is_skill_active


# ==================== 工具名称映射测试 ====================

class TestToolNameMap:
    """工具名称映射测试"""

    def test_tool_name_map_coverage(self):
        """测试工具名称映射覆盖常见名称"""
        # Claude Code 风格的名称应该都能映射
        assert "bash" in TOOL_NAME_MAP
        assert "read" in TOOL_NAME_MAP
        assert "write" in TOOL_NAME_MAP
        assert "edit" in TOOL_NAME_MAP
        assert "grep" in TOOL_NAME_MAP
        assert "glob" in TOOL_NAME_MAP

    def test_tool_name_map_aliases(self):
        """测试工具名称别名"""
        assert TOOL_NAME_MAP["read"] == "read_file"
        assert TOOL_NAME_MAP["read_file"] == "read_file"
        assert TOOL_NAME_MAP["write"] == "write_file"
        assert TOOL_NAME_MAP["edit"] == "edit_file"
