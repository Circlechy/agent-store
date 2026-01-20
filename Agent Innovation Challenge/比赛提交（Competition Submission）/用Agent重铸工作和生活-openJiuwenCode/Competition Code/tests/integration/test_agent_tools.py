"""
Agent + 工具集成测试

测试用例覆盖 docs/03-测试用例设计.md 中 3.1 节的所有 P0 用例
"""

import pytest
import asyncio
import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# 添加 packages 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from server.agents.mode_manager import AgentMode, AgentModeManager
from server.tools.base_tool import ReadFileTool, WriteFileTool, EditFileTool, ToolInput
from server.tools.shell_tools import BashTool
from server.tools.search_tools import GrepTool, GlobTool
from server.tools.todo_tools import TodoWriteTool, TodoPersistenceManager


# 检查 ripgrep 是否安装
RIPGREP_INSTALLED = shutil.which("rg") is not None


class TestAgentToolsIntegration:
    """测试 Agent + 工具集成"""

    @pytest.fixture
    def mode_manager(self):
        return AgentModeManager(AgentMode.BUILD)

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def temp_file(self, temp_dir):
        """创建临时测试文件"""
        file_path = os.path.join(temp_dir, "test_file.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Hello, World!\nLine 2\nLine 3\n")
        return file_path

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

    # ========================================================================
    # test_agent_read_file_tool_call - Agent 调用 read_file
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_read_file_tool_call(self, mode_manager, temp_file):
        """测试 Agent 调用 read_file 工具"""
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == True
        assert "Hello, World!" in result.data["content"]
        assert result.data["line_count"] == 3

    @pytest.mark.asyncio
    async def test_agent_read_file_with_offset_and_limit(self, mode_manager, temp_file):
        """测试 Agent 调用 read_file 带偏移和限制"""
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file,
            "offset": 2,
            "limit": 1
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == True
        assert "Line 2" in result.data["content"]
        assert result.data["line_count"] == 1

    # ========================================================================
    # test_agent_write_file_tool_call - Agent 调用 write_file
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_write_file_tool_call(self, mode_manager, temp_dir):
        """测试 Agent 调用 write_file 工具"""
        write_tool = WriteFileTool(mode_manager)

        file_path = os.path.join(temp_dir, "new_file.txt")
        inputs = ToolInput(data={
            "file_path": file_path,
            "content": "New content created by agent"
        })

        result = await write_tool.ainvoke(inputs)

        assert result.success == True
        assert result.data["bytes_written"] > 0

        # 验证文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == "New content created by agent"

    @pytest.mark.asyncio
    async def test_agent_write_file_creates_parent_dirs(self, mode_manager, temp_dir):
        """测试 Agent 调用 write_file 自动创建父目录"""
        write_tool = WriteFileTool(mode_manager)

        file_path = os.path.join(temp_dir, "subdir", "nested", "file.txt")
        inputs = ToolInput(data={
            "file_path": file_path,
            "content": "Nested file content"
        })

        result = await write_tool.ainvoke(inputs)

        assert result.success == True
        assert os.path.exists(file_path)

    # ========================================================================
    # test_agent_multi_tool_sequence - 多工具顺序调用
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_multi_tool_sequence(self, mode_manager, temp_dir):
        """测试多工具顺序调用: read → edit → write 流程"""
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)

        # 1. 创建初始文件
        file_path = os.path.join(temp_dir, "sequence_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Original content\nLine 2\n")

        # 2. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True
        assert "Original content" in read_result.data["content"]

        # 3. 编辑文件
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "old_string": "Original content",
            "new_string": "Modified content"
        }))
        assert edit_result.success == True
        assert edit_result.data["replacements"] == 1

        # 4. 再次读取验证
        read_result2 = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result2.success == True
        assert "Modified content" in read_result2.data["content"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not RIPGREP_INSTALLED, reason="ripgrep (rg) 未安装")
    async def test_agent_search_and_edit_sequence(self, mode_manager, temp_dir):
        """测试搜索并编辑流程: grep → read → edit"""
        grep_tool = GrepTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)

        # 创建测试文件
        file_path = os.path.join(temp_dir, "search_edit.py")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("""def old_function():
    pass

def another_function():
    old_function()
""")

        # 1. 搜索 old_function
        grep_result = await grep_tool.ainvoke(ToolInput(data={
            "pattern": "old_function",
            "path": temp_dir
        }))
        assert grep_result.success == True
        assert grep_result.data["count"] > 0

        # 2. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True

        # 3. 编辑文件（替换所有）
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "old_string": "old_function",
            "new_string": "new_function",
            "replace_all": True
        }))
        assert edit_result.success == True
        assert edit_result.data["replacements"] == 2

    # ========================================================================
    # test_agent_tool_error_handling - 工具执行错误
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_tool_error_handling_file_not_found(self, mode_manager):
        """测试工具执行错误 - 文件不存在"""
        read_tool = ReadFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": "/nonexistent/path/file.txt"
        })

        result = await read_tool.ainvoke(inputs)

        assert result.success == False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_agent_tool_error_handling_edit_not_found(self, mode_manager, temp_file):
        """测试工具执行错误 - 编辑字符串不存在"""
        edit_tool = EditFileTool(mode_manager)

        inputs = ToolInput(data={
            "file_path": temp_file,
            "old_string": "nonexistent string xyz",
            "new_string": "replacement"
        })

        result = await edit_tool.ainvoke(inputs)

        assert result.success == False
        assert "未找到" in result.error

    @pytest.mark.asyncio
    async def test_agent_tool_error_handling_bash_blacklist(self, mode_manager):
        """测试工具执行错误 - Bash 黑名单命令"""
        bash_tool = BashTool(mode_manager)

        inputs = ToolInput(data={
            "command": "rm -rf /",
            "timeout": 5
        })

        result = await bash_tool.ainvoke(inputs)

        assert result.success == False
        assert "阻止" in result.error

    # ========================================================================
    # test_agent_mode_switch_refresh_tools - 模式切换刷新工具
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_mode_switch_refresh_tools(self, temp_dir):
        """测试模式切换后工具权限正确更新"""
        mode_manager = AgentModeManager(AgentMode.BUILD)
        write_tool = WriteFileTool(mode_manager)

        file_path = os.path.join(temp_dir, "mode_test.txt")

        # BUILD 模式下可以写入
        result1 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "BUILD mode content"
        }))
        assert result1.success == True

        # 切换到 PLAN 模式
        mode_manager.switch_mode(AgentMode.PLAN)

        # PLAN 模式下不能写入
        result2 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "PLAN mode content"
        }))
        assert result2.success == False
        assert "不可用" in result2.error

        # 切换回 BUILD 模式
        mode_manager.switch_mode(AgentMode.BUILD)

        # BUILD 模式下又可以写入
        result3 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "BUILD mode again"
        }))
        assert result3.success == True

    @pytest.mark.asyncio
    async def test_agent_mode_switch_bash_permissions(self, temp_dir):
        """测试模式切换后 Bash 权限正确更新"""
        mode_manager = AgentModeManager(AgentMode.BUILD)
        bash_tool = BashTool(mode_manager)

        # BUILD 模式下可以执行 rm 命令
        file_path = os.path.join(temp_dir, "to_delete.txt")
        with open(file_path, 'w') as f:
            f.write("test")

        # 切换到 PLAN 模式
        mode_manager.switch_mode(AgentMode.PLAN)

        # PLAN 模式下 rm 命令被阻止
        result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"rm {file_path}",
            "timeout": 5
        }))
        assert result.success == False

    # ========================================================================
    # test_agent_todo_workflow - Todo 工作流
    # ========================================================================

    @pytest.mark.asyncio
    async def test_agent_todo_workflow(self, mode_manager, temp_persistence):
        """测试 Todo 工作流: 创建 → 更新 → 完成"""
        todo_tool = TodoWriteTool(mode_manager, "test_session")
        todo_tool.persistence = temp_persistence

        # 1. 创建任务
        create_result = await todo_tool.ainvoke({
            "action": "create",
            "tasks": "任务一;任务二;任务三"
        })
        assert "成功创建 3 个任务" in create_result

        # 2. 获取任务列表
        list_result = await todo_tool.ainvoke({"action": "list"})
        assert "任务列表" in list_result
        assert "任务一" in list_result

        # 3. 获取第一个任务 ID
        todos = todo_tool.persistence.load_todos()
        first_task_id = todos[0].id[:8]

        # 4. 完成第一个任务
        update_result = await todo_tool.ainvoke({
            "action": "update",
            "task_id": first_task_id,
            "status": "completed"
        })
        assert "状态更新" in update_result

        # 5. 验证状态
        updated_todos = todo_tool.persistence.load_todos()
        assert updated_todos[0].status == "completed"

        # 6. 开始第二个任务
        second_task_id = todos[1].id[:8]
        await todo_tool.ainvoke({
            "action": "update",
            "task_id": second_task_id,
            "status": "in_progress"
        })

        # 7. 验证只有一个 in_progress
        final_todos = todo_tool.persistence.load_todos()
        in_progress_count = sum(1 for t in final_todos if t.status == "in_progress")
        assert in_progress_count == 1

    @pytest.mark.asyncio
    async def test_agent_todo_with_file_operations(self, mode_manager, temp_dir, temp_persistence):
        """测试 Todo 与文件操作结合的工作流"""
        todo_tool = TodoWriteTool(mode_manager, "test_session")
        todo_tool.persistence = temp_persistence
        write_tool = WriteFileTool(mode_manager)
        read_tool = ReadFileTool(mode_manager)

        # 1. 创建任务
        await todo_tool.ainvoke({
            "action": "create",
            "tasks": "创建文件;读取文件;验证内容"
        })

        # 2. 执行第一个任务 - 创建文件
        file_path = os.path.join(temp_dir, "workflow_test.txt")
        await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Workflow test content"
        }))

        # 3. 完成第一个任务
        todos = todo_tool.persistence.load_todos()
        await todo_tool.ainvoke({
            "action": "update",
            "task_id": todos[0].id[:8],
            "status": "completed"
        })

        # 4. 开始第二个任务 - 读取文件
        await todo_tool.ainvoke({
            "action": "update",
            "task_id": todos[1].id[:8],
            "status": "in_progress"
        })

        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True
        assert "Workflow test content" in read_result.data["content"]

        # 5. 完成第二个任务
        await todo_tool.ainvoke({
            "action": "update",
            "task_id": todos[1].id[:8],
            "status": "completed"
        })

        # 6. 验证任务状态
        final_todos = todo_tool.persistence.load_todos()
        completed_count = sum(1 for t in final_todos if t.status == "completed")
        assert completed_count == 2


class TestModeAwareIntegration:
    """测试模式感知集成"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    # ========================================================================
    # test_build_mode_full_workflow - BUILD 模式完整流程
    # ========================================================================

    @pytest.mark.asyncio
    async def test_build_mode_full_workflow(self, temp_dir):
        """测试 BUILD 模式完整流程 - 读写编辑都可用"""
        mode_manager = AgentModeManager(AgentMode.BUILD)

        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        edit_tool = EditFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        file_path = os.path.join(temp_dir, "build_test.txt")

        # 1. 写入文件
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Initial content"
        }))
        assert write_result.success == True

        # 2. 读取文件
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True

        # 3. 编辑文件
        edit_result = await edit_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "old_string": "Initial",
            "new_string": "Modified"
        }))
        assert edit_result.success == True

        # 4. 执行 Bash 命令
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": f"cat {file_path}",
            "timeout": 5
        }))
        assert bash_result.success == True
        assert "Modified content" in bash_result.data["stdout"]

    # ========================================================================
    # test_plan_mode_readonly_workflow - PLAN 模式只读流程
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.skipif(not RIPGREP_INSTALLED, reason="ripgrep (rg) 未安装")
    async def test_plan_mode_readonly_workflow(self, temp_dir):
        """测试 PLAN 模式只读流程 - 只能读取和搜索"""
        mode_manager = AgentModeManager(AgentMode.PLAN)

        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        grep_tool = GrepTool(mode_manager)
        glob_tool = GlobTool(mode_manager)

        # 创建测试文件
        file_path = os.path.join(temp_dir, "plan_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Test content for plan mode")

        # 1. 读取文件 - 应该成功
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True

        # 2. 写入文件 - 应该失败
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": os.path.join(temp_dir, "new_file.txt"),
            "content": "Should not be written"
        }))
        assert write_result.success == False
        assert "不可用" in write_result.error

        # 3. Grep 搜索 - 应该成功
        grep_result = await grep_tool.ainvoke(ToolInput(data={
            "pattern": "Test",
            "path": temp_dir
        }))
        assert grep_result.success == True

        # 4. Glob 搜索 - 应该成功
        glob_result = await glob_tool.ainvoke(ToolInput(data={
            "pattern": "*.txt",
            "path": temp_dir
        }))
        assert glob_result.success == True

    # ========================================================================
    # test_review_mode_analysis_workflow - REVIEW 模式分析流程
    # ========================================================================

    @pytest.mark.asyncio
    async def test_review_mode_analysis_workflow(self, temp_dir):
        """测试 REVIEW 模式分析流程 - 只读"""
        mode_manager = AgentModeManager(AgentMode.REVIEW)

        read_tool = ReadFileTool(mode_manager)
        write_tool = WriteFileTool(mode_manager)
        bash_tool = BashTool(mode_manager)

        # 创建测试文件
        file_path = os.path.join(temp_dir, "review_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Code to review")

        # 1. 读取文件 - 应该成功
        read_result = await read_tool.ainvoke(ToolInput(data={
            "file_path": file_path
        }))
        assert read_result.success == True

        # 2. 写入文件 - 应该失败
        write_result = await write_tool.ainvoke(ToolInput(data={
            "file_path": os.path.join(temp_dir, "new_file.txt"),
            "content": "Should not be written"
        }))
        assert write_result.success == False

        # 3. Git 命令 - 应该被阻止
        bash_result = await bash_tool.ainvoke(ToolInput(data={
            "command": "git status",
            "timeout": 5
        }))
        assert bash_result.success == False

    # ========================================================================
    # test_mode_switch_during_task - 任务中切换模式
    # ========================================================================

    @pytest.mark.asyncio
    async def test_mode_switch_during_task(self, temp_dir):
        """测试任务中切换模式 - 工具权限即时更新"""
        mode_manager = AgentModeManager(AgentMode.BUILD)
        write_tool = WriteFileTool(mode_manager)

        file_path = os.path.join(temp_dir, "switch_test.txt")

        # BUILD 模式下写入
        result1 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 1"
        }))
        assert result1.success == True

        # 切换到 PLAN 模式
        mode_manager.switch_mode(AgentMode.PLAN)

        # 立即尝试写入 - 应该失败
        result2 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 2"
        }))
        assert result2.success == False

        # 切换到 REVIEW 模式
        mode_manager.switch_mode(AgentMode.REVIEW)

        # 仍然不能写入
        result3 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 3"
        }))
        assert result3.success == False

        # 切换回 BUILD 模式
        mode_manager.switch_mode(AgentMode.BUILD)

        # 又可以写入了
        result4 = await write_tool.ainvoke(ToolInput(data={
            "file_path": file_path,
            "content": "Content 4"
        }))
        assert result4.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
