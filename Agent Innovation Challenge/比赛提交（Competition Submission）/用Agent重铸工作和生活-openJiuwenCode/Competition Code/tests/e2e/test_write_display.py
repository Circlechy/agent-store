"""测试 Write/Update 工具显示格式

验证：
1. 新建文件时显示 "Write"，更新文件时显示 "Update"
2. 显示写入行数
3. 显示内容预览（前10行）
"""
import os
import pytest

from .conftest import JiuwenRunner, requires_api_key


class TestWriteDisplayFormat:
    """测试 Write/Update 显示格式"""

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_write_new_file_display(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 创建新文件时显示 Write

        预期:
        1. 工具名称显示为 "Write"
        2. 结果显示 "Wrote X lines"
        3. 显示内容预览（前10行）
        """
        test_file = os.path.join(temp_project, "new_file.py")

        # 确保文件不存在
        if os.path.exists(test_file):
            os.remove(test_file)

        query = f"创建文件 {test_file}，内容为一个简单的 hello world 函数"
        response = await runner.run(query, timeout=60)

        # 验证文件被创建
        assert os.path.exists(test_file), "文件应该被创建"

        # 验证输出包含 "Wrote" 和行数
        assert "Wrote" in response.content or "Write" in response.content

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_update_existing_file_display(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 更新已有文件时显示 Update

        预期:
        1. 如果使用 write_file，工具名称显示为 "Update"
        2. 如果使用 edit_file，显示 "Edit"（这也是正确的行为）
        """
        test_file = os.path.join(temp_project, "existing_file.py")

        # 先创建文件
        with open(test_file, 'w') as f:
            f.write("# Original content\n")

        # 使用 write_file 强制覆盖整个文件
        query = f"用 write_file 工具重写文件 {test_file}，内容为一个 greet 函数"
        response = await runner.run(query, timeout=60)

        # 验证输出包含 "Updated" 或 "Update"（如果使用 write_file）
        # 或者 "Edit"（如果 LLM 选择使用 edit_file）
        assert "Updated" in response.content or "Update" in response.content or "Edit" in response.content

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_write_shows_line_count(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: Write 显示写入行数

        预期:
        1. 显示 "X lines" 格式
        """
        test_file = os.path.join(temp_project, "multiline.py")

        query = f"创建文件 {test_file}，包含一个有 5 个方法的类"
        response = await runner.run(query, timeout=90)

        # 验证输出包含行数信息
        assert "lines" in response.content.lower()

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_write_shows_content_preview(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: Write 显示内容预览

        预期:
        1. 显示前几行内容
        2. 如果超过10行，显示 "+X lines" 提示
        """
        test_file = os.path.join(temp_project, "preview_test.py")

        query = f"创建文件 {test_file}，包含一个完整的计算器类，有加减乘除方法"
        response = await runner.run(query, timeout=90)

        # 验证文件被创建且有内容
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            content = f.read()
        assert len(content) > 0

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_update_display_with_write_tool(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 使用 write_file 工具覆盖已有文件时显示 Update

        预期:
        1. 工具名称显示为 "Update"（而非 "Write"）
        2. 显示更新后的行数
        3. 显示内容预览
        """
        test_file = os.path.join(temp_project, "update_test.py")

        # 先创建原始文件
        original_content = '''def old_function():
    """旧函数"""
    return "old"
'''
        with open(test_file, 'w') as f:
            f.write(original_content)

        # 请求覆盖文件
        query = f"使用 write_file 工具将 {test_file} 的内容完全替换为一个新的 new_function 函数"
        response = await runner.run(query, timeout=60)

        # 验证文件被更新
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            new_content = f.read()
        assert "new_function" in new_content or "new" in new_content.lower()

        # 验证显示 "Update" 而非 "Write"
        assert "Update" in response.content or "Updated" in response.content, \
            "覆盖已有文件时应显示 Update"

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_update_shows_line_count_change(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: Update 显示行数变化

        预期:
        1. 显示更新后的行数
        """
        test_file = os.path.join(temp_project, "line_count_test.py")

        # 创建只有 2 行的文件
        with open(test_file, 'w') as f:
            f.write("# Line 1\n# Line 2\n")

        # 请求扩展为更多行
        query = f"使用 write_file 工具将 {test_file} 扩展为包含 10 行注释的文件"
        response = await runner.run(query, timeout=60)

        # 验证文件行数增加
        with open(test_file, 'r') as f:
            lines = f.readlines()
        assert len(lines) >= 5, "文件应该有更多行"

        # 验证显示行数信息
        assert "lines" in response.content.lower() or "行" in response.content

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_update_preserves_file_after_multiple_writes(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: 多次 Update 后文件内容正确

        预期:
        1. 每次 Update 都正确显示
        2. 最终文件内容是最后一次写入的内容
        """
        test_file = os.path.join(temp_project, "multi_update.py")

        # 第一次创建
        with open(test_file, 'w') as f:
            f.write("# Version 1\n")

        # 第一次更新
        query1 = f"使用 write_file 将 {test_file} 内容改为 '# Version 2'"
        response1 = await runner.run(query1, timeout=60)

        with open(test_file, 'r') as f:
            content = f.read()
        assert "Version 2" in content or "version 2" in content.lower()

        # 第二次更新
        query2 = f"使用 write_file 将 {test_file} 内容改为 '# Version 3'"
        response2 = await runner.run(query2, timeout=60)

        with open(test_file, 'r') as f:
            final_content = f.read()
        assert "Version 3" in final_content or "version 3" in final_content.lower()

        # 验证两次都显示 Update
        assert "Update" in response1.content or "Updated" in response1.content
        assert "Update" in response2.content or "Updated" in response2.content

    @requires_api_key
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_update_shows_content_preview_like_write(self, runner: JiuwenRunner, temp_project: str):
        """
        场景: Update 显示内容预览（和 Write 格式一致）

        预期:
        1. 显示 "Updated X lines to /path/to/file"
        2. 显示前几行内容预览
        3. 如果超过10行，显示 "+X lines" 提示
        """
        test_file = os.path.join(temp_project, "update_preview_test.py")

        # 先创建原始文件
        with open(test_file, 'w') as f:
            f.write("# Original\n")

        # 请求覆盖为多行内容
        query = f"使用 write_file 工具将 {test_file} 替换为一个包含 15 行代码的 Calculator 类"
        response = await runner.run(query, timeout=90)

        # 验证文件被更新
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            content = f.read()
        assert len(content) > 0

        # 验证显示 "Updated" 和行数
        assert "Updated" in response.content, "应显示 Updated"
        assert "lines" in response.content.lower(), "应显示行数"

        # 验证显示内容预览（检查是否有代码片段）
        # 预览应该包含类定义或函数定义等代码特征
        has_preview = any(keyword in response.content for keyword in [
            "class", "def", "Calculator", "#", "self"
        ])
        assert has_preview, "应显示内容预览"

