"""
pytest 配置和共享 fixtures

为所有测试提供通用的 fixtures 和配置
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path
from datetime import datetime

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool
from server.tools.search_tools import GrepTool, GlobTool
from server.tools.todo_tools import TodoWriteTool, TodoItem, TodoPersistenceManager


# ============================================================================
# 模式管理器 Fixtures
# ============================================================================

@pytest.fixture
def build_mode_manager():
    """创建 BUILD 模式管理器"""
    return AgentModeManager(AgentMode.BUILD)


@pytest.fixture
def plan_mode_manager():
    """创建 PLAN 模式管理器"""
    return AgentModeManager(AgentMode.PLAN)


@pytest.fixture
def review_mode_manager():
    """创建 REVIEW 模式管理器"""
    return AgentModeManager(AgentMode.REVIEW)


@pytest.fixture
def mode_manager():
    """创建默认模式管理器（BUILD 模式）"""
    return AgentModeManager(AgentMode.BUILD)


# ============================================================================
# 文件工具 Fixtures
# ============================================================================

@pytest.fixture
def read_tool(build_mode_manager):
    """创建 ReadFileTool"""
    return ReadFileTool(build_mode_manager)


@pytest.fixture
def write_tool(build_mode_manager):
    """创建 WriteFileTool"""
    return WriteFileTool(build_mode_manager)


@pytest.fixture
def edit_tool(build_mode_manager):
    """创建 EditFileTool"""
    return EditFileTool(build_mode_manager)


# ============================================================================
# Shell 工具 Fixtures
# ============================================================================

@pytest.fixture
def bash_tool(build_mode_manager):
    """创建 BashTool"""
    return BashTool(build_mode_manager)


@pytest.fixture
def bash_tool_plan_mode(plan_mode_manager):
    """创建 PLAN 模式下的 BashTool"""
    return BashTool(plan_mode_manager)


@pytest.fixture
def bash_tool_review_mode(review_mode_manager):
    """创建 REVIEW 模式下的 BashTool"""
    return BashTool(review_mode_manager)


# ============================================================================
# 搜索工具 Fixtures
# ============================================================================

@pytest.fixture
def grep_tool(build_mode_manager):
    """创建 GrepTool"""
    return GrepTool(build_mode_manager)


@pytest.fixture
def glob_tool(build_mode_manager):
    """创建 GlobTool"""
    return GlobTool(build_mode_manager)


# ============================================================================
# Todo 工具 Fixtures
# ============================================================================

@pytest.fixture
def temp_persistence():
    """创建临时持久化管理器"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        class TempPersistenceManager(TodoPersistenceManager):
            def __init__(self, session_id="test_session"):
                self.session_id = session_id
                self.todos_dir = temp_path / ".jiuwen" / "todos"
                self.todos_dir.mkdir(parents=True, exist_ok=True)
                self.file_path = self.todos_dir / f"{self.session_id}.json"

        yield TempPersistenceManager()


@pytest.fixture
def todo_tool(build_mode_manager, temp_persistence):
    """创建 TodoWriteTool"""
    tool = TodoWriteTool(build_mode_manager, "test_session")
    tool.persistence = temp_persistence
    return tool


# ============================================================================
# 临时文件 Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_file(temp_dir):
    """创建临时测试文件"""
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("Hello, World!\nLine 2\nLine 3\n")
    return file_path


@pytest.fixture
def temp_python_file(temp_dir):
    """创建临时 Python 文件"""
    file_path = os.path.join(temp_dir, "test_script.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("""def hello():
    print("Hello, World!")

def add(a, b):
    return a + b

if __name__ == "__main__":
    hello()
""")
    return file_path


@pytest.fixture
def sample_project(temp_dir):
    """创建示例项目结构"""
    # 创建目录结构
    src_dir = os.path.join(temp_dir, "src")
    tests_dir = os.path.join(temp_dir, "tests")
    os.makedirs(src_dir)
    os.makedirs(tests_dir)

    # 创建源文件
    main_py = os.path.join(src_dir, "main.py")
    with open(main_py, 'w', encoding='utf-8') as f:
        f.write("""def main():
    print("Main function")

if __name__ == "__main__":
    main()
""")

    utils_py = os.path.join(src_dir, "utils.py")
    with open(utils_py, 'w', encoding='utf-8') as f:
        f.write("""def helper():
    return "helper"

def format_string(s):
    return s.strip().lower()
""")

    # 创建测试文件
    test_main_py = os.path.join(tests_dir, "test_main.py")
    with open(test_main_py, 'w', encoding='utf-8') as f:
        f.write("""import pytest

def test_main():
    assert True
""")

    return temp_dir


# ============================================================================
# pytest 配置
# ============================================================================

def pytest_configure(config):
    """pytest 配置钩子"""
    # 添加自定义标记
    config.addinivalue_line("markers", "slow: 标记慢速测试")
    config.addinivalue_line("markers", "security: 标记安全测试")
    config.addinivalue_line("markers", "integration: 标记集成测试")


# ============================================================================
# 辅助函数
# ============================================================================

def create_tool_input(data: dict) -> ToolInput:
    """创建 ToolInput 对象"""
    return ToolInput(data=data)
