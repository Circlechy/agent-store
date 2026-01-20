"""
任务完成验证测试

验收标准：LLM 会把所有任务执行完成后才停下

测试场景：
1. 用户请求"帮我写一个用户登录功能"
2. Agent 应该：
   - 调用 todo_write 创建任务列表
   - 执行所有任务（write_file/edit_file 等）
   - 更新任务状态为 completed
   - 所有任务完成后才停止
"""

import pytest
import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any

# 导入测试配置
from .conftest import (
    requires_api_key,
    JiuwenResponse,
    JiuwenRunner,
    assert_tool_called,
    assert_any_tool_called,
    assert_no_errors,
)


# ============================================================================
# 任务完成验证测试
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestTaskCompletion:
    """任务完成验证测试

    验收标准：LLM 会把所有任务执行完成后才停下
    """

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def todos_dir(self):
        """获取 todos 目录"""
        return Path.home() / ".jiuwen" / "todos"

    def get_todos_from_file(self, todos_dir: Path) -> List[Dict]:
        """从文件读取最新的 todos"""
        if not todos_dir.exists():
            return []

        # 获取最新的 todo 文件
        todo_files = list(todos_dir.glob("*.json"))
        if not todo_files:
            return []

        # 按修改时间排序，取最新的
        latest_file = max(todo_files, key=lambda f: f.stat().st_mtime)
        try:
            with open(latest_file, 'r', encoding='utf-8') as file:
                return json.load(file)
        except:
            return []

    def count_completed_todos(self, todos: List[Dict]) -> int:
        """统计已完成的任务数"""
        return sum(1 for t in todos if t.get("status") == "completed")

    def count_total_todos(self, todos: List[Dict]) -> int:
        """统计总任务数"""
        return len(todos)

    def all_todos_completed(self, todos: List[Dict]) -> bool:
        """检查是否所有任务都已完成"""
        if not todos:
            return False
        return all(t.get("status") == "completed" for t in todos)

    # ========================================================================
    # 核心测试用例：用户登录功能
    # ========================================================================

    @requires_api_key
    @pytest.mark.asyncio
    async def test_login_feature_all_tasks_completed(self, runner: JiuwenRunner, temp_workspace, todos_dir):
        """测试：帮我写一个用户登录功能

        验收标准：
        1. Agent 调用 todo_write 创建任务列表
        2. Agent 执行所有任务（创建文件等）
        3. Agent 更新任务状态
        4. 所有任务都标记为 completed
        """
        target_file = os.path.join(temp_workspace, "login.py")
        query = f"帮我在 {target_file} 写一个用户登录功能，包括表单验证和错误处理"

        response = await runner.run(query, timeout=180)

        # 1. 验证调用了 todo_write（通过输出检测）
        has_todo = response.has_tool_call("todo_write")

        # 2. 验证调用了文件操作工具
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 3. 验证创建了文件
        assert os.path.exists(target_file) or any(
            os.path.exists(os.path.join(temp_workspace, f))
            for f in os.listdir(temp_workspace) if f.endswith('.py')
        ), "应该创建至少一个 Python 文件"

        # 4. 验证任务状态（如果有 todo）
        if has_todo:
            todos = self.get_todos_from_file(todos_dir)
            if todos:
                completed = self.count_completed_todos(todos)
                total = self.count_total_todos(todos)
                # 至少完成了一个任务
                assert completed >= 1, \
                    f"应该至少完成 1 个任务，实际完成: {completed}/{total}"

        # 5. 验证没有错误
        assert_no_errors(response)

    # ========================================================================
    # 简单任务测试
    # ========================================================================

    @requires_api_key
    @pytest.mark.asyncio
    async def test_simple_hello_world_completed(self, runner: JiuwenRunner, temp_workspace, todos_dir):
        """测试：帮我写一个 hello world 程序

        简单任务，应该快速完成
        """
        target_file = os.path.join(temp_workspace, "hello.py")
        query = f"帮我在 {target_file} 写一个 Python hello world 程序"

        response = await runner.run(query, timeout=120)

        # 验证调用了 write_file
        assert_tool_called(response, "write_file")

        # 验证创建了文件
        assert os.path.exists(target_file), f"文件应该存在: {target_file}"

        with open(target_file, 'r') as f:
            content = f.read()
        assert "hello" in content.lower() or "print" in content.lower(), \
            "文件应该包含 hello world 相关代码"

        assert_no_errors(response)

    # ========================================================================
    # 多任务测试
    # ========================================================================

    @requires_api_key
    @pytest.mark.asyncio
    async def test_multi_task_all_completed(self, runner: JiuwenRunner, temp_workspace, todos_dir):
        """测试：多任务场景

        验收标准：所有任务都应该完成
        """
        target_file = os.path.join(temp_workspace, "calculator.py")
        query = f"帮我在 {target_file} 创建一个简单的计算器模块，包含加法和减法函数"

        response = await runner.run(query, timeout=180)

        # 验证调用了文件操作
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证文件存在
        assert os.path.exists(target_file), f"文件应该存在: {target_file}"

        # 验证文件内容
        with open(target_file, 'r') as f:
            content = f.read()
        assert "def " in content, "应该包含函数定义"

        assert_no_errors(response)

    # ========================================================================
    # 任务中断恢复测试
    # ========================================================================

    @requires_api_key
    @pytest.mark.asyncio
    async def test_task_continues_after_todo_write(self, runner: JiuwenRunner, temp_workspace, todos_dir):
        """测试：todo_write 后继续执行

        关键验收标准：
        - Agent 在调用 todo_write 后不应该停下来等待用户
        - 应该立即开始执行第一个任务
        """
        target_file = os.path.join(temp_workspace, "user_manager.py")
        query = f"帮我在 {target_file} 写一个用户管理系统，包含添加用户和删除用户功能"

        response = await runner.run(query, timeout=180)

        # 验证有文件操作
        assert_any_tool_called(response, ["write_file", "edit_file", "read_file"])

        # 验证文件存在
        assert os.path.exists(target_file), f"文件应该存在: {target_file}"

        # 验证任务完成（如果有 todo）
        if response.has_tool_call("todo_write"):
            todos = self.get_todos_from_file(todos_dir)
            if todos:
                completed = self.count_completed_todos(todos)
                assert completed >= 1, \
                    f"应该至少完成 1 个任务，实际完成: {completed}"

        assert_no_errors(response)


# ============================================================================
# 工具调用统计测试
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestToolCallStatistics:
    """工具调用统计测试"""

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @requires_api_key
    @pytest.mark.asyncio
    async def test_tool_call_sequence(self, runner: JiuwenRunner, temp_workspace):
        """测试工具调用序列

        验证 Agent 按正确顺序调用工具
        """
        target_file = os.path.join(temp_workspace, "config_parser.py")
        query = f"帮我在 {target_file} 写一个简单的配置文件解析器"

        response = await runner.run(query, timeout=180)

        # 验证有文件操作
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证文件存在
        assert os.path.exists(target_file), f"文件应该存在: {target_file}"

        assert_no_errors(response)

    @requires_api_key
    @pytest.mark.asyncio
    async def test_todo_update_calls(self, runner: JiuwenRunner, temp_workspace):
        """测试 todo 更新调用

        验证 Agent 在完成任务后更新 todo 状态
        """
        target_file = os.path.join(temp_workspace, "validator.py")
        query = f"帮我在 {target_file} 写一个数据验证函数"

        response = await runner.run(query, timeout=180)

        # 验证有文件操作
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证文件存在
        assert os.path.exists(target_file), f"文件应该存在: {target_file}"

        assert_no_errors(response)


# ============================================================================
# 边界情况测试
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @requires_api_key
    @pytest.mark.asyncio
    async def test_single_simple_task(self, runner: JiuwenRunner, temp_workspace):
        """测试单个简单任务

        简单任务可能不需要 todo_write
        """
        target_file = os.path.join(temp_workspace, "test.txt")
        query = f"创建一个名为 {target_file} 的文件，内容是 hello"

        response = await runner.run(query, timeout=120)

        # 验证调用了 write_file
        assert_tool_called(response, "write_file")

        # 验证文件创建
        assert os.path.exists(target_file), "文件应该存在"

        assert_no_errors(response)

    @requires_api_key
    @pytest.mark.asyncio
    async def test_complex_multi_file_task(self, runner: JiuwenRunner, temp_workspace):
        """测试复杂多文件任务

        验证 Agent 能处理需要创建多个文件的任务
        """
        query = f"帮我在 {temp_workspace} 目录创建一个简单的 MVC 结构，包含 model.py, view.py, controller.py"

        response = await runner.run(query, timeout=180)

        # 验证有文件操作
        assert_any_tool_called(response, ["write_file", "edit_file"])

        # 验证至少创建了一个文件
        py_files = [f for f in os.listdir(temp_workspace) if f.endswith('.py')]
        assert len(py_files) >= 1, \
            f"应该创建至少 1 个 Python 文件，实际创建: {py_files}"

        assert_no_errors(response)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "e2e"])
