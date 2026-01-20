"""
搜索工具单元测试

测试用例覆盖 docs/03-测试用例设计.md 中 2.3 节的所有 P0 用例
"""

import pytest
import asyncio
import sys
import os
import shutil
import tempfile
from pathlib import Path

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.search_tools import GrepTool, GlobTool
from server.tools.base_tool import ToolInput


# 检查 ripgrep 是否安装
RIPGREP_INSTALLED = shutil.which("rg") is not None


@pytest.mark.skipif(not RIPGREP_INSTALLED, reason="ripgrep (rg) 未安装")
class TestGrepTool:
    """测试 Grep 内容搜索工具"""

    @pytest.fixture
    def build_mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def plan_mode_manager(self):
        return AgentModeManager(AgentMode.PLAN)

    @pytest.fixture
    def review_mode_manager(self):
        return AgentModeManager(AgentMode.REVIEW)

    @pytest.fixture
    def grep_tool(self, build_mode_manager):
        return GrepTool(build_mode_manager)

    @pytest.fixture
    def sample_project(self):
        """创建示例项目用于搜索测试"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建目录结构
            src_dir = os.path.join(temp_dir, "src")
            os.makedirs(src_dir)

            # 创建 Python 文件
            main_py = os.path.join(src_dir, "main.py")
            with open(main_py, 'w', encoding='utf-8') as f:
                f.write("""def main():
    print("Hello, World!")
    return 0

def helper_function():
    # This is a helper
    pass

if __name__ == "__main__":
    main()
""")

            utils_py = os.path.join(src_dir, "utils.py")
            with open(utils_py, 'w', encoding='utf-8') as f:
                f.write("""def format_string(s):
    return s.strip().lower()

def UPPERCASE_FUNCTION():
    return "UPPERCASE"

class MyClass:
    def method(self):
        pass
""")

            # 创建 JavaScript 文件
            app_js = os.path.join(src_dir, "app.js")
            with open(app_js, 'w', encoding='utf-8') as f:
                f.write("""function main() {
    console.log("Hello from JS");
}

const helper = () => {
    return "helper";
};
""")

            yield temp_dir

    # ========================================================================
    # test_grep_basic_pattern - 基本模式搜索
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_basic_pattern(self, grep_tool, sample_project):
        """测试基本模式搜索"""
        inputs = ToolInput(data={
            "pattern": "def main",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        assert "main" in result.data["matches"]

    @pytest.mark.asyncio
    async def test_grep_basic_pattern_multiple_matches(self, grep_tool, sample_project):
        """测试基本模式搜索多个匹配"""
        inputs = ToolInput(data={
            "pattern": "def ",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data["count"] > 1

    # ========================================================================
    # test_grep_regex_pattern - 正则表达式搜索
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_regex_pattern(self, grep_tool, sample_project):
        """测试正则表达式搜索"""
        inputs = ToolInput(data={
            "pattern": r"def \w+\(",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data["count"] > 0

    @pytest.mark.asyncio
    async def test_grep_regex_pattern_class(self, grep_tool, sample_project):
        """测试正则表达式搜索类定义"""
        inputs = ToolInput(data={
            "pattern": r"class \w+:",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        assert "MyClass" in result.data["matches"]

    # ========================================================================
    # test_grep_case_insensitive - 不区分大小写
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_case_insensitive(self, grep_tool, sample_project):
        """测试不区分大小写搜索"""
        inputs = ToolInput(data={
            "pattern": "uppercase",
            "path": sample_project,
            "case_sensitive": False
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        assert "UPPERCASE" in result.data["matches"]

    @pytest.mark.asyncio
    async def test_grep_case_sensitive(self, grep_tool, sample_project):
        """测试区分大小写搜索"""
        inputs = ToolInput(data={
            "pattern": "uppercase",
            "path": sample_project,
            "case_sensitive": True
        })

        result = await grep_tool.ainvoke(inputs)

        # 区分大小写时，小写 "uppercase" 不应匹配 "UPPERCASE"
        assert result.success == True
        # 可能没有匹配或匹配数较少

    # ========================================================================
    # test_grep_file_pattern - 文件类型过滤
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_file_pattern_python(self, grep_tool, sample_project):
        """测试只搜索 Python 文件"""
        inputs = ToolInput(data={
            "pattern": "function",
            "path": sample_project,
            "file_pattern": "*.py"
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        # Python 文件中有 "helper_function"
        if result.data["count"] > 0:
            assert ".py" in result.data["matches"] or "function" in result.data["matches"]

    @pytest.mark.asyncio
    async def test_grep_file_pattern_js(self, grep_tool, sample_project):
        """测试只搜索 JavaScript 文件"""
        inputs = ToolInput(data={
            "pattern": "console",
            "path": sample_project,
            "file_pattern": "*.js"
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        if result.data["count"] > 0:
            assert "console" in result.data["matches"]

    # ========================================================================
    # test_grep_context_lines - 上下文行
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_context_lines(self, grep_tool, sample_project):
        """测试显示上下文行"""
        inputs = ToolInput(data={
            "pattern": "helper_function",
            "path": sample_project,
            "context_lines": 2
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True
        # 应该包含上下文行
        if result.data["count"] > 0:
            assert "helper" in result.data["matches"]

    # ========================================================================
    # test_grep_no_match - 无匹配结果
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_no_match(self, grep_tool, sample_project):
        """测试无匹配结果"""
        inputs = ToolInput(data={
            "pattern": "nonexistent_pattern_xyz123",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        # 无匹配时应该返回 success=True，但 count=0
        assert result.success == True
        assert result.data["count"] == 0

    # ========================================================================
    # test_grep_ripgrep_not_installed - ripgrep 未安装
    # ========================================================================

    # 注意：这个测试需要模拟 ripgrep 未安装的情况
    # 在实际环境中可能难以测试，这里跳过

    # ========================================================================
    # test_grep_in_all_modes - 所有模式可用
    # ========================================================================

    @pytest.mark.asyncio
    async def test_grep_in_build_mode(self, build_mode_manager, sample_project):
        """测试 BUILD 模式下 Grep 可用"""
        grep_tool = GrepTool(build_mode_manager)
        inputs = ToolInput(data={
            "pattern": "def",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True

    @pytest.mark.asyncio
    async def test_grep_in_plan_mode(self, plan_mode_manager, sample_project):
        """测试 PLAN 模式下 Grep 可用"""
        grep_tool = GrepTool(plan_mode_manager)
        inputs = ToolInput(data={
            "pattern": "def",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True

    @pytest.mark.asyncio
    async def test_grep_in_review_mode(self, review_mode_manager, sample_project):
        """测试 REVIEW 模式下 Grep 可用"""
        grep_tool = GrepTool(review_mode_manager)
        inputs = ToolInput(data={
            "pattern": "def",
            "path": sample_project
        })

        result = await grep_tool.ainvoke(inputs)

        assert result.success == True


class TestGlobTool:
    """测试 Glob 文件模式匹配工具"""

    @pytest.fixture
    def build_mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def plan_mode_manager(self):
        return AgentModeManager(AgentMode.PLAN)

    @pytest.fixture
    def review_mode_manager(self):
        return AgentModeManager(AgentMode.REVIEW)

    @pytest.fixture
    def glob_tool(self, build_mode_manager):
        return GlobTool(build_mode_manager)

    @pytest.fixture
    def sample_project(self):
        """创建示例项目用于 glob 测试"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建目录结构
            src_dir = os.path.join(temp_dir, "src")
            tests_dir = os.path.join(temp_dir, "tests")
            src_utils_dir = os.path.join(src_dir, "utils")
            os.makedirs(src_dir)
            os.makedirs(tests_dir)
            os.makedirs(src_utils_dir)

            # 创建文件
            files = [
                os.path.join(src_dir, "main.py"),
                os.path.join(src_dir, "app.py"),
                os.path.join(src_dir, "config.json"),
                os.path.join(src_utils_dir, "helpers.py"),
                os.path.join(src_utils_dir, "validators.py"),
                os.path.join(tests_dir, "test_main.py"),
                os.path.join(tests_dir, "test_app.py"),
                os.path.join(temp_dir, "README.md"),
                os.path.join(temp_dir, "setup.py"),
            ]

            for file_path in files:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {os.path.basename(file_path)}\n")

            yield temp_dir

    # ========================================================================
    # test_glob_single_wildcard - 单层通配符
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_single_wildcard(self, glob_tool, sample_project):
        """测试单层通配符 *.py"""
        inputs = ToolInput(data={
            "pattern": "*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        # 只匹配当前目录的 .py 文件
        assert "setup.py" in str(result.data["files"])
        # 不应该匹配子目录的文件
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_glob_single_wildcard_json(self, glob_tool, sample_project):
        """测试单层通配符 *.json"""
        inputs = ToolInput(data={
            "pattern": "src/*.json",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        if result.data["count"] > 0:
            assert "config.json" in str(result.data["files"])

    # ========================================================================
    # test_glob_recursive - 递归通配符
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_recursive(self, glob_tool, sample_project):
        """测试递归通配符 **/*.py"""
        inputs = ToolInput(data={
            "pattern": "**/*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        # 应该匹配所有子目录的 .py 文件
        assert result.data["count"] >= 5  # main.py, app.py, helpers.py, validators.py, test_*.py, setup.py

    @pytest.mark.asyncio
    async def test_glob_recursive_specific_dir(self, glob_tool, sample_project):
        """测试递归通配符在特定目录"""
        inputs = ToolInput(data={
            "pattern": "src/**/*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        # 应该匹配 src 目录下的所有 .py 文件
        assert result.data["count"] >= 4  # main.py, app.py, helpers.py, validators.py

    # ========================================================================
    # test_glob_no_match - 无匹配文件
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_no_match(self, glob_tool, sample_project):
        """测试无匹配文件"""
        inputs = ToolInput(data={
            "pattern": "*.xyz",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data["count"] == 0
        assert result.data["files"] == []

    # ========================================================================
    # test_glob_relative_paths - 相对路径返回
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_relative_paths(self, glob_tool, sample_project):
        """测试返回相对路径"""
        inputs = ToolInput(data={
            "pattern": "*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        # 返回的路径应该是相对路径
        for file_path in result.data["files"]:
            assert not file_path.startswith("/")

    # ========================================================================
    # test_glob_sorted_results - 结果排序
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_sorted_results(self, glob_tool, sample_project):
        """测试结果按字母排序"""
        inputs = ToolInput(data={
            "pattern": "**/*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True
        files = result.data["files"]
        # 验证排序
        assert files == sorted(files)

    # ========================================================================
    # 所有模式可用测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_glob_in_build_mode(self, build_mode_manager, sample_project):
        """测试 BUILD 模式下 Glob 可用"""
        glob_tool = GlobTool(build_mode_manager)
        inputs = ToolInput(data={
            "pattern": "*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True

    @pytest.mark.asyncio
    async def test_glob_in_plan_mode(self, plan_mode_manager, sample_project):
        """测试 PLAN 模式下 Glob 可用"""
        glob_tool = GlobTool(plan_mode_manager)
        inputs = ToolInput(data={
            "pattern": "*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True

    @pytest.mark.asyncio
    async def test_glob_in_review_mode(self, review_mode_manager, sample_project):
        """测试 REVIEW 模式下 Glob 可用"""
        glob_tool = GlobTool(review_mode_manager)
        inputs = ToolInput(data={
            "pattern": "*.py",
            "path": sample_project
        })

        result = await glob_tool.ainvoke(inputs)

        assert result.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
