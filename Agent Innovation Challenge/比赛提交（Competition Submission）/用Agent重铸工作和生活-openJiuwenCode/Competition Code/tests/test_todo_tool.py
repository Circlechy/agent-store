"""
TodoWrite 工具单元测试
"""

import pytest
import asyncio
import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.todo_tools import TodoWriteTool, TodoItem, TodoPersistenceManager


class TestTodoPersistenceManager:
    """测试 Todo 持久化管理器"""

    @pytest.fixture
    def temp_persistence(self):
        """创建临时持久化管理器"""
        # 使用临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 创建临时持久化管理器
            class TempPersistenceManager(TodoPersistenceManager):
                def __init__(self, session_id="test_session"):
                    self.session_id = session_id
                    self.todos_dir = temp_path / ".jiuwen" / "todos"
                    self.todos_dir.mkdir(parents=True, exist_ok=True)
                    self.file_path = self.todos_dir / f"{self.session_id}.json"

            yield TempPersistenceManager()

    def test_save_and_load_todos(self, temp_persistence):
        """测试保存和加载 todos"""
        # 创建测试数据
        todos = [
            TodoItem(
                id="1",
                content="编写代码",
                activeForm="正在编写代码",
                status="pending",
                createdAt=datetime.now().isoformat(),
                updatedAt=datetime.now().isoformat()
            ),
            TodoItem(
                id="2",
                content="运行测试",
                activeForm="正在运行测试",
                status="in_progress",
                createdAt=datetime.now().isoformat(),
                updatedAt=datetime.now().isoformat()
            ),
        ]

        # 保存
        assert temp_persistence.save_todos(todos) == True

        # 加载
        loaded_todos = temp_persistence.load_todos()
        assert len(loaded_todos) == 2
        assert loaded_todos[0].content == "编写代码"
        assert loaded_todos[1].status == "in_progress"

    def test_load_empty_todos(self, temp_persistence):
        """测试加载空的 todos"""
        todos = temp_persistence.load_todos()
        assert todos == []

    def test_clear_todos(self, temp_persistence):
        """测试清除 todos"""
        # 创建并保存 todos
        todos = [
            TodoItem(
                id="1",
                content="测试",
                activeForm="正在测试",
                status="pending",
                createdAt=datetime.now().isoformat(),
                updatedAt=datetime.now().isoformat()
            )
        ]
        temp_persistence.save_todos(todos)

        # 清除
        assert temp_persistence.clear_todos() == True
        assert temp_persistence.load_todos() == []


class TestTodoWriteTool:
    """测试 TodoWrite 工具"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_persistence(self):
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
    def todo_tool(self, mode_manager, temp_persistence):
        """创建 TodoWrite 工具"""
        tool = TodoWriteTool(mode_manager, "test_session")
        tool.persistence = temp_persistence
        return tool

    @pytest.mark.asyncio
    async def test_create_todos(self, todo_tool):
        """测试创建任务列表"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                },
                {
                    "content": "运行测试",
                    "activeForm": "正在运行测试",
                    "status": "pending"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 2 个任务" in result

    @pytest.mark.asyncio
    async def test_create_todos_with_in_progress(self, todo_tool):
        """测试创建包含 in_progress 任务的列表"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "in_progress"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 1 个任务" in result

    @pytest.mark.asyncio
    async def test_create_todos_multiple_in_progress_fails(self, todo_tool):
        """测试不能创建多个 in_progress 任务"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "任务1",
                    "activeForm": "正在执行任务1",
                    "status": "in_progress"
                },
                {
                    "content": "任务2",
                    "activeForm": "正在执行任务2",
                    "status": "in_progress"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "只能有一个" in result

    @pytest.mark.asyncio
    async def test_create_todos_missing_content(self, todo_tool):
        """测试缺少 content 字段"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "activeForm": "正在工作",
                    "status": "pending"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_create_todos_invalid_status(self, todo_tool):
        """测试无效的状态值"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "任务",
                    "activeForm": "正在执行",
                    "status": "invalid_status"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_update_todos(self, todo_tool):
        """测试更新任务"""
        # 先创建任务
        create_inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                }
            ]
        }
        await todo_tool.ainvoke(create_inputs)

        # 获取任务 ID
        todos = todo_tool.persistence.load_todos()
        todo_id = todos[0].id

        # 更新任务
        update_inputs = {
            "action": "update",
            "todos": [
                {
                    "id": todo_id,
                    "status": "in_progress"
                }
            ]
        }

        result = await todo_tool.ainvoke(update_inputs)

        assert "成功更新 1 个任务" in result

        # 验证更新
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_update_todos_not_found(self, todo_tool):
        """测试更新不存在的任务"""
        # 先创建任务
        create_inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                }
            ]
        }
        await todo_tool.ainvoke(create_inputs)

        # 尝试更新不存在的任务
        inputs = {
            "action": "update",
            "todos": [
                {
                    "id": "nonexistent_id",
                    "status": "completed"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_update_todos_missing_id(self, todo_tool):
        """测试更新任务缺少 ID"""
        # 先创建任务
        create_inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                }
            ]
        }
        await todo_tool.ainvoke(create_inputs)

        # 尝试更新缺少 ID 的任务
        inputs = {
            "action": "update",
            "todos": [
                {
                    "status": "completed"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "id" in result

    @pytest.mark.asyncio
    async def test_list_todos(self, todo_tool):
        """测试列出任务"""
        # 创建任务
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                },
                {
                    "content": "运行测试",
                    "activeForm": "正在运行测试",
                    "status": "in_progress"
                },
                {
                    "content": "写文档",
                    "activeForm": "正在写文档",
                    "status": "completed"
                }
            ]
        }
        await todo_tool.ainvoke(inputs)

        # 列出任务
        result = await todo_tool.ainvoke({"action": "list"})

        assert "任务列表" in result
        assert "编写代码" in result
        assert "运行测试" in result
        assert "进行中" in result
        assert "待处理" in result
        assert "已完成" in result

    @pytest.mark.asyncio
    async def test_list_empty_todos(self, todo_tool):
        """测试列出空任务列表"""
        result = await todo_tool.ainvoke({"action": "list"})

        assert "当前没有任务" in result

    @pytest.mark.asyncio
    async def test_clear_todos(self, todo_tool):
        """测试清除任务"""
        # 创建任务
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "测试",
                    "activeForm": "正在测试",
                    "status": "pending"
                }
            ]
        }
        await todo_tool.ainvoke(inputs)

        # 清除任务
        result = await todo_tool.ainvoke({"action": "clear"})

        assert "成功清除" in result

        # 验证清除
        todos = todo_tool.persistence.load_todos()
        assert todos == []

    @pytest.mark.asyncio
    async def test_invalid_action(self, todo_tool):
        """测试无效的 action"""
        result = await todo_tool.ainvoke({"action": "invalid_action"})

        assert "错误" in result
        assert "invalid_action" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
