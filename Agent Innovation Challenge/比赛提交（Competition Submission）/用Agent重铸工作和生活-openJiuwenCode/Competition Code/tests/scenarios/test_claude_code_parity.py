"""
Claude Code 对标测试

测试用例覆盖 docs/03-测试用例设计.md 中 10.8 节的所有对标用例
这些测试直接模拟 Claude Code 的典型使用场景
"""

import pytest
import asyncio
import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool
from server.tools.search_tools import GrepTool, GlobTool


# 检查 ripgrep 是否安装
RIPGREP_INSTALLED = shutil.which("rg") is not None


class TestExploreCodebase:
    """测试探索代码库"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def sample_project(self):
        """创建示例项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建项目结构
            src_dir = os.path.join(temp_dir, "src")
            tests_dir = os.path.join(temp_dir, "tests")
            os.makedirs(src_dir)
            os.makedirs(tests_dir)

            # README
            readme = os.path.join(temp_dir, "README.md")
            with open(readme, 'w') as f:
                f.write('''# Sample Project

A sample Python project for testing.

## Features
- User management
- Order processing
- Payment handling
''')

            # main.py
            main_file = os.path.join(src_dir, "main.py")
            with open(main_file, 'w') as f:
                f.write('''"""主程序入口"""

from user import UserService
from order import OrderService


def main():
    """程序入口点"""
    user_service = UserService()
    order_service = OrderService()

    # 创建用户
    user = user_service.create_user("Alice", "alice@example.com")
    print(f"Created user: {user}")


if __name__ == "__main__":
    main()
''')

            # user.py
            user_file = os.path.join(src_dir, "user.py")
            with open(user_file, 'w') as f:
                f.write('''"""用户服务模块"""


class UserService:
    """用户服务"""

    def __init__(self):
        self.users = {}

    def create_user(self, name, email):
        """创建用户"""
        user_id = len(self.users) + 1
        self.users[user_id] = {"id": user_id, "name": name, "email": email}
        return self.users[user_id]

    def get_user(self, user_id):
        """获取用户"""
        return self.users.get(user_id)
''')

            # order.py
            order_file = os.path.join(src_dir, "order.py")
            with open(order_file, 'w') as f:
                f.write('''"""订单服务模块"""


class OrderService:
    """订单服务"""

    def __init__(self):
        self.orders = {}

    def create_order(self, user_id, items):
        """创建订单"""
        order_id = len(self.orders) + 1
        self.orders[order_id] = {
            "id": order_id,
            "user_id": user_id,
            "items": items
        }
        return self.orders[order_id]
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_explore_codebase(self, mode_manager, sample_project):
        """
        Claude Code 场景: "这个项目是做什么的？"
        预期: glob → 多次 read_file → 总结
        """
        glob_tool = GlobTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 1. 找到所有文件
        glob_result = await glob_tool.ainvoke(ToolInput(data={
            "pattern": "**/*",
            "path": sample_project
        }))
        assert glob_result.success == True

        # 2. 读取 README
        readme_path = os.path.join(sample_project, "README.md")
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": readme_path
        }))
        assert read_result.success == True
        assert "Sample Project" in read_result.data["content"]

        # 3. 读取主要源文件
        main_path = os.path.join(sample_project, "src", "main.py")
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": main_path
        }))
        assert read_result2.success == True
        assert "def main():" in read_result2.data["content"]


@pytest.mark.skipif(not RIPGREP_INSTALLED, reason="ripgrep (rg) 未安装")
class TestFindEntryPoint:
    """测试找到程序入口"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def sample_project(self):
        """创建示例项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建多个 Python 文件
            main_file = os.path.join(temp_dir, "main.py")
            with open(main_file, 'w') as f:
                f.write('''"""主程序"""

def main():
    print("Hello")


if __name__ == "__main__":
    main()
''')

            utils_file = os.path.join(temp_dir, "utils.py")
            with open(utils_file, 'w') as f:
                f.write('''"""工具函数"""

def helper():
    return "helper"
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_find_entry_point(self, mode_manager, sample_project):
        """
        Claude Code 场景: "程序的入口在哪里？"
        预期: grep "main" / "if __name__" → read_file
        """
        grep_tool = GrepTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 1. 搜索 if __name__ == "__main__"
        grep_result = await grep_tool.ainvoke(ToolInput(data={
            "pattern": '__name__.*==.*"__main__"',
            "path": sample_project
        }))
        assert grep_result.success == True
        assert grep_result.data["count"] >= 1

        # 2. 读取入口文件
        main_path = os.path.join(sample_project, "main.py")
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": main_path
        }))
        assert read_result.success == True
        assert 'if __name__ == "__main__":' in read_result.data["content"]


class TestLocateBugFromError:
    """测试从错误定位 Bug"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def buggy_project(self):
        """创建有 Bug 的项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建有 bug 的文件
            calc_file = os.path.join(temp_dir, "calculator.py")
            with open(calc_file, 'w') as f:
                f.write('''"""计算器模块"""

def divide(a, b):
    """除法 - 没有处理除零"""
    return a / b


def calculate(operation, a, b):
    """执行计算"""
    if operation == "divide":
        return divide(a, b)
    return None
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_locate_bug_from_error(self, mode_manager, buggy_project):
        """
        Claude Code 场景: "这个错误是什么原因？[粘贴错误]"
        预期: 分析错误 → grep → read_file → 定位
        """
        bash_tool = BashTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        calc_file = os.path.join(buggy_project, "calculator.py")

        # 1. 运行代码触发错误
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"python3 -c \"import sys; sys.path.insert(0, '{buggy_project}'); from calculator import divide; divide(10, 0)\"",
            "timeout": 10
        }))

        # 应该有 ZeroDivisionError
        assert bash_result.success == False
        error_output = bash_result.data.get("stderr", "") + bash_result.data.get("stdout", "")
        assert "ZeroDivisionError" in error_output or "division by zero" in error_output

        # 2. 读取源文件定位问题
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": calc_file
        }))
        assert read_result.success == True
        assert "def divide(a, b):" in read_result.data["content"]
        assert "return a / b" in read_result.data["content"]


class TestWriteDocumentation:
    """测试写文档"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_write_documentation(self, mode_manager, temp_dir):
        """
        Claude Code 场景: "给这个模块写文档"
        预期: read_file → 生成 markdown
        """
        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)

        # 创建源文件
        source_file = os.path.join(temp_dir, "user_service.py")
        with open(source_file, 'w') as f:
            f.write('''"""用户服务模块"""


class UserService:
    """用户服务类"""

    def __init__(self):
        self.users = {}

    def create_user(self, name: str, email: str) -> dict:
        """创建新用户"""
        user_id = len(self.users) + 1
        self.users[user_id] = {"id": user_id, "name": name, "email": email}
        return self.users[user_id]

    def get_user(self, user_id: int) -> dict:
        """获取用户信息"""
        return self.users.get(user_id)

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
''')

        # 1. 读取源文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": source_file
        }))
        assert read_result.success == True

        # 2. 生成文档
        doc_file = os.path.join(temp_dir, "USER_SERVICE.md")
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": doc_file,
            "content": '''# UserService 模块文档

## 概述

用户服务模块提供用户管理功能。

## 类: UserService

用户服务类，管理用户的创建、查询和删除。

### 方法

#### `create_user(name: str, email: str) -> dict`

创建新用户。

**参数:**
- `name`: 用户名
- `email`: 用户邮箱

**返回:** 包含用户信息的字典

#### `get_user(user_id: int) -> dict`

获取用户信息。

**参数:**
- `user_id`: 用户 ID

**返回:** 用户信息字典，如果不存在返回 None

#### `delete_user(user_id: int) -> bool`

删除用户。

**参数:**
- `user_id`: 用户 ID

**返回:** 删除成功返回 True，否则返回 False
'''
        }))
        assert write_result.success == True

        # 3. 验证文档已创建
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": doc_file
        }))
        assert read_result2.success == True
        assert "UserService" in read_result2.data["content"]
        assert "create_user" in read_result2.data["content"]


class TestSetupProject:
    """测试初始化项目"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_setup_project(self, mode_manager, temp_dir):
        """
        Claude Code 场景: "帮我初始化一个 Python 项目"
        预期: 创建目录结构、配置文件、README
        """
        write_tool = WriteFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        project_dir = os.path.join(temp_dir, "my_project")

        # 1. 创建目录结构
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"mkdir -p {project_dir}/src {project_dir}/tests",
            "timeout": 10
        }))
        assert bash_result.success == True

        # 2. 创建 README
        readme_file = os.path.join(project_dir, "README.md")
        write_result1 = await write_tool.ainvoke(ToolInput(data={
            "file_path": readme_file,
            "content": '''# My Project

A Python project.

## Installation

```bash
pip install -e .
```

## Usage

```python
from my_project import main
main()
```
'''
        }))
        assert write_result1.success == True

        # 3. 创建 setup.py
        setup_file = os.path.join(project_dir, "setup.py")
        write_result2 = await write_tool.ainvoke(ToolInput(data={
            "file_path": setup_file,
            "content": '''from setuptools import setup, find_packages

setup(
    name="my_project",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
)
'''
        }))
        assert write_result2.success == True

        # 4. 创建 __init__.py
        init_file = os.path.join(project_dir, "src", "__init__.py")
        write_result3 = await write_tool.ainvoke(ToolInput(data={
            "file_path": init_file,
            "content": '"""My Project package."""\n'
        }))
        assert write_result3.success == True

        # 5. 验证项目结构
        assert os.path.exists(os.path.join(project_dir, "README.md"))
        assert os.path.exists(os.path.join(project_dir, "setup.py"))
        assert os.path.exists(os.path.join(project_dir, "src", "__init__.py"))
        assert os.path.isdir(os.path.join(project_dir, "tests"))


class TestCodeReview:
    """测试代码审查"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_code_review(self, mode_manager, temp_dir):
        """
        Claude Code 场景: "review 一下这个代码"
        预期: 读取代码 → 分析 → 给出建议
        """
        read_tool = ReadFileTool(mode_manager)

        # 创建需要 review 的代码
        code_file = os.path.join(temp_dir, "code_to_review.py")
        with open(code_file, 'w') as f:
            f.write('''"""需要 review 的代码"""

def process(d):
    # 处理数据
    r = []
    for i in d:
        if i > 0:
            r.append(i * 2)
    return r


def calc(x, y):
    return x / y  # 没有处理除零


class mgr:
    def __init__(self):
        self.l = []

    def add(self, x):
        self.l.append(x)
''')

        # 读取代码进行 review
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": code_file
        }))

        assert read_result.success == True
        content = read_result.data["content"]

        # 验证代码中存在可以改进的地方
        assert "def process(d):" in content  # 命名不清晰
        assert "return x / y" in content  # 没有错误处理
        assert "class mgr:" in content  # 类名不符合规范


class TestUnderstandArchitecture:
    """测试理解项目架构"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def layered_project(self):
        """创建分层架构项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建分层目录
            for layer in ["models", "services", "controllers", "utils"]:
                layer_dir = os.path.join(temp_dir, layer)
                os.makedirs(layer_dir)

                init_file = os.path.join(layer_dir, "__init__.py")
                with open(init_file, 'w') as f:
                    f.write(f'"""{layer} 层"""\n')

            # models/user.py
            user_model = os.path.join(temp_dir, "models", "user.py")
            with open(user_model, 'w') as f:
                f.write('''"""用户模型"""

class User:
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email
''')

            # services/user_service.py
            user_service = os.path.join(temp_dir, "services", "user_service.py")
            with open(user_service, 'w') as f:
                f.write('''"""用户服务"""
from models.user import User


class UserService:
    def create_user(self, name, email):
        return User(1, name, email)
''')

            # controllers/user_controller.py
            user_controller = os.path.join(temp_dir, "controllers", "user_controller.py")
            with open(user_controller, 'w') as f:
                f.write('''"""用户控制器"""
from services.user_service import UserService


class UserController:
    def __init__(self):
        self.service = UserService()

    def create(self, data):
        return self.service.create_user(data["name"], data["email"])
''')

            yield temp_dir

    @pytest.mark.asyncio
    @pytest.mark.claude_code_parity
    async def test_understand_architecture(self, mode_manager, layered_project):
        """
        Claude Code 场景: "解释一下项目架构"
        预期: glob → read_file (多个) → 分析依赖
        """
        glob_tool = GlobTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 1. 找到所有 Python 文件
        glob_result = await glob_tool.ainvoke(ToolInput(data={
            "pattern": "**/*.py",
            "path": layered_project
        }))
        assert glob_result.success == True
        assert glob_result.data["count"] >= 6  # 4 个 __init__.py + 3 个模块

        # 2. 读取各层文件理解架构
        layers = ["models", "services", "controllers"]
        for layer in layers:
            init_file = os.path.join(layered_project, layer, "__init__.py")
            read_result = await read_tool.ainvoke(ToolInput(data={
                "file_path": init_file
            }))
            assert read_result.success == True

        # 3. 读取控制器理解依赖关系
        controller_file = os.path.join(layered_project, "controllers", "user_controller.py")
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": controller_file
        }))
        assert read_result.success == True
        assert "from services.user_service import" in read_result.data["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "claude_code_parity"])
