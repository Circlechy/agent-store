"""
TodoWrite 工具完整单元测试

测试用例覆盖 docs/03-测试用例设计.md 中 2.5 节的所有 P0 用例
"""

import pytest
import asyncio
import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.todo_tools import TodoWriteTool, TodoItem, TodoPersistenceManager


class TestTodoPersistenceManager:
    """测试 Todo 持久化管理器"""

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

    def test_save_and_load_todos(self, temp_persistence):
        """测试保存和加载 todos"""
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

        assert temp_persistence.save_todos(todos) == True

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

        assert temp_persistence.clear_todos() == True
        assert temp_persistence.load_todos() == []

    def test_persistence_file_path(self, temp_persistence):
        """测试持久化文件路径"""
        assert "test_session.json" in str(temp_persistence.file_path)
        assert ".jiuwen/todos" in str(temp_persistence.file_path)


class TestTodoWriteTool:
    """测试 TodoWrite 工具"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def plan_mode_manager(self):
        return AgentModeManager(AgentMode.PLAN)

    @pytest.fixture
    def review_mode_manager(self):
        return AgentModeManager(AgentMode.REVIEW)

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

    # ========================================================================
    # test_todo_create_simple - 简化格式创建
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_create_simple(self, todo_tool):
        """测试简化格式创建任务（用分号分隔）"""
        inputs = {
            "action": "create",
            "tasks": "创建登录表单;实现表单验证;添加错误处理"
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 3 个任务" in result
        assert "创建登录表单" in result
        assert "实现表单验证" in result
        assert "添加错误处理" in result

    @pytest.mark.asyncio
    async def test_todo_create_simple_newline(self, todo_tool):
        """测试简化格式创建任务（用换行分隔）"""
        inputs = {
            "action": "create",
            "tasks": "任务一\n任务二\n任务三"
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 3 个任务" in result

    @pytest.mark.asyncio
    async def test_todo_create_simple_chinese_separator(self, todo_tool):
        """测试简化格式创建任务（用中文分号分隔）"""
        inputs = {
            "action": "create",
            "tasks": "任务一；任务二；任务三"
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 3 个任务" in result

    @pytest.mark.asyncio
    async def test_todo_create_simple_single_task(self, todo_tool):
        """测试简化格式创建单个任务"""
        inputs = {
            "action": "create",
            "tasks": "单个任务"
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 1 个任务" in result
        assert "单个任务" in result

    # ========================================================================
    # test_todo_create_full_format - 完整格式创建
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_create_full_format(self, todo_tool):
        """测试完整格式创建任务（用 todos 数组）"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "in_progress"
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
    async def test_todo_create_full_format_json_string(self, todo_tool):
        """测试完整格式创建任务（JSON 字符串）"""
        inputs = {
            "action": "create",
            "todos": json.dumps([
                {
                    "content": "任务1",
                    "activeForm": "正在执行任务1",
                    "status": "pending"
                }
            ])
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 1 个任务" in result

    # ========================================================================
    # test_todo_first_task_in_progress - 首个任务状态
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_first_task_in_progress(self, todo_tool):
        """测试简化格式创建时首个任务自动设为 in_progress"""
        inputs = {
            "action": "create",
            "tasks": "任务一;任务二;任务三"
        }

        await todo_tool.ainvoke(inputs)

        todos = todo_tool.persistence.load_todos()
        assert len(todos) == 3
        assert todos[0].status == "in_progress"
        assert todos[1].status == "pending"
        assert todos[2].status == "pending"

    # ========================================================================
    # test_todo_only_one_in_progress - 单一进行中任务
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_only_one_in_progress(self, todo_tool):
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

    # ========================================================================
    # test_todo_update_status - 更新任务状态
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_update_status(self, todo_tool):
        """测试更新任务状态"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "todos": [
                {
                    "content": "编写代码",
                    "activeForm": "正在编写代码",
                    "status": "pending"
                }
            ]
        })

        # 获取任务 ID
        todos = todo_tool.persistence.load_todos()
        todo_id = todos[0].id

        # 更新任务
        result = await todo_tool.ainvoke({
            "action": "update",
            "todos": [
                {
                    "id": todo_id,
                    "status": "in_progress"
                }
            ]
        })

        assert "成功更新 1 个任务" in result

        # 验证更新
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_todo_update_status_simplified(self, todo_tool):
        """测试简化格式更新任务状态"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 获取任务 ID
        todos = todo_tool.persistence.load_todos()
        task_id = todos[0].id[:8]  # 前8位

        # 使用简化格式更新
        result = await todo_tool.ainvoke({
            "action": "update",
            "task_id": task_id,
            "status": "completed"
        })

        assert "状态更新" in result

        # 验证更新
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "completed"

    # ========================================================================
    # test_todo_update_by_prefix - 前缀 ID 更新
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_update_by_prefix(self, todo_tool):
        """测试支持 8 位前缀匹配更新"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 获取任务 ID 前8位
        todos = todo_tool.persistence.load_todos()
        prefix = todos[0].id[:8]

        # 使用前缀更新
        result = await todo_tool.ainvoke({
            "action": "update",
            "task_id": prefix,
            "status": "completed"
        })

        assert "状态更新" in result

        # 验证更新
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "completed"

    # ========================================================================
    # test_todo_list - 列出任务
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_list(self, todo_tool):
        """测试列出任务（按状态分组显示）"""
        # 创建任务
        await todo_tool.ainvoke({
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
        })

        # 列出任务
        result = await todo_tool.ainvoke({"action": "list"})

        assert "任务列表" in result
        assert "编写代码" in result
        assert "运行测试" in result
        assert "进行中" in result
        assert "待处理" in result
        assert "已完成" in result

    @pytest.mark.asyncio
    async def test_todo_list_empty(self, todo_tool):
        """测试列出空任务列表"""
        result = await todo_tool.ainvoke({"action": "list"})

        assert "当前没有任务" in result

    # ========================================================================
    # test_todo_clear - 清除任务
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_clear(self, todo_tool):
        """测试清除所有任务"""
        # 创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 清除任务
        result = await todo_tool.ainvoke({"action": "clear"})

        assert "成功清除" in result

        # 验证清除
        todos = todo_tool.persistence.load_todos()
        assert todos == []

    # ========================================================================
    # test_todo_persistence - 持久化
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_persistence(self, todo_tool):
        """测试任务持久化到文件"""
        # 创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "持久化测试任务"
        })

        # 验证文件存在
        assert todo_tool.persistence.file_path.exists()

        # 验证文件内容
        with open(todo_tool.persistence.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["content"] == "持久化测试任务"

    # ========================================================================
    # test_todo_invalid_action - 无效操作
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_invalid_action(self, todo_tool):
        """测试无效的 action"""
        result = await todo_tool.ainvoke({"action": "invalid_action"})

        assert "错误" in result
        assert "invalid_action" in result

    # ========================================================================
    # test_todo_missing_params - 缺少参数
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_missing_params_create(self, todo_tool):
        """测试创建任务缺少参数"""
        result = await todo_tool.ainvoke({"action": "create"})

        assert "错误" in result or "tasks" in result or "todos" in result

    @pytest.mark.asyncio
    async def test_todo_missing_params_update(self, todo_tool):
        """测试更新任务缺少参数"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 尝试更新但缺少参数
        result = await todo_tool.ainvoke({"action": "update"})

        assert "错误" in result

    @pytest.mark.asyncio
    async def test_todo_missing_action(self, todo_tool):
        """测试缺少 action 参数"""
        result = await todo_tool.ainvoke({})

        assert "错误" in result
        assert "action" in result

    # ========================================================================
    # test_todo_in_all_modes - 所有模式可用
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_in_build_mode(self, mode_manager, temp_persistence):
        """测试 BUILD 模式下 TodoWrite 可用"""
        tool = TodoWriteTool(mode_manager, "test_session")
        tool.persistence = temp_persistence

        result = await tool.ainvoke({
            "action": "create",
            "tasks": "BUILD 模式任务"
        })

        assert "成功创建" in result

    @pytest.mark.asyncio
    async def test_todo_in_plan_mode(self, plan_mode_manager, temp_persistence):
        """测试 PLAN 模式下 TodoWrite 可用"""
        tool = TodoWriteTool(plan_mode_manager, "test_session")
        tool.persistence = temp_persistence

        result = await tool.ainvoke({
            "action": "create",
            "tasks": "PLAN 模式任务"
        })

        assert "成功创建" in result

    @pytest.mark.asyncio
    async def test_todo_in_review_mode(self, review_mode_manager, temp_persistence):
        """测试 REVIEW 模式下 TodoWrite 可用"""
        tool = TodoWriteTool(review_mode_manager, "test_session")
        tool.persistence = temp_persistence

        result = await tool.ainvoke({
            "action": "create",
            "tasks": "REVIEW 模式任务"
        })

        assert "成功创建" in result

    # ========================================================================
    # 额外测试用例
    # ========================================================================

    @pytest.mark.asyncio
    async def test_todo_create_missing_content(self, todo_tool):
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
    async def test_todo_create_missing_activeForm(self, todo_tool):
        """测试缺少 activeForm 字段"""
        inputs = {
            "action": "create",
            "todos": [
                {
                    "content": "任务",
                    "status": "pending"
                }
            ]
        }

        result = await todo_tool.ainvoke(inputs)

        assert "错误" in result
        assert "activeForm" in result

    @pytest.mark.asyncio
    async def test_todo_create_invalid_status(self, todo_tool):
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
    async def test_todo_update_not_found(self, todo_tool):
        """测试更新不存在的任务"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 尝试更新不存在的任务
        result = await todo_tool.ainvoke({
            "action": "update",
            "task_id": "nonexist",
            "status": "completed"
        })

        assert "错误" in result
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_todo_update_invalid_status(self, todo_tool):
        """测试更新为无效状态"""
        # 先创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "测试任务"
        })

        # 获取任务 ID
        todos = todo_tool.persistence.load_todos()
        task_id = todos[0].id[:8]

        # 尝试更新为无效状态
        result = await todo_tool.ainvoke({
            "action": "update",
            "task_id": task_id,
            "status": "invalid"
        })

        assert "错误" in result

    @pytest.mark.asyncio
    async def test_todo_update_switches_in_progress(self, todo_tool):
        """测试更新为 in_progress 时自动切换其他任务状态"""
        # 创建多个任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "任务一;任务二;任务三"
        })

        # 获取第二个任务的 ID
        todos = todo_tool.persistence.load_todos()
        second_task_id = todos[1].id[:8]

        # 将第二个任务设为 in_progress
        await todo_tool.ainvoke({
            "action": "update",
            "task_id": second_task_id,
            "status": "in_progress"
        })

        # 验证状态
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "pending"  # 原来的 in_progress 变为 pending
        assert updated_todos[1].status == "in_progress"  # 新的 in_progress
        assert updated_todos[2].status == "pending"

    @pytest.mark.asyncio
    async def test_todo_create_with_numbered_list(self, todo_tool):
        """测试创建带序号的任务列表"""
        inputs = {
            "action": "create",
            "tasks": "1. 第一个任务;2. 第二个任务;3. 第三个任务"
        }

        result = await todo_tool.ainvoke(inputs)

        assert "成功创建 3 个任务" in result

        # 验证序号被正确移除
        todos = todo_tool.persistence.load_todos()
        assert todos[0].content == "第一个任务"
        assert todos[1].content == "第二个任务"
        assert todos[2].content == "第三个任务"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
