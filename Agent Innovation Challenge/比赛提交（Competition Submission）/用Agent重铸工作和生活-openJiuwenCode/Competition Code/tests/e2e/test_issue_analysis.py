"""
Issue 分析和 PR 创建测试

测试 Agent 处理 GitCode issue 分析和 PR 创建的能力。
主要用于调试 API 429 错误等问题。

运行方式:
    # 使用 Python 3.11 venv
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_issue_analysis.py -v -m e2e -s
"""

import pytest
import os

from .conftest import (
    requires_api_key,
    JiuwenRunner,
    assert_any_tool_called,
)


# ============================================================================
# Test Case: Issue 分析和 PR 创建
# ============================================================================

@pytest.mark.e2e
@pytest.mark.workflow
class TestIssueAnalysisWorkflow:
    """测试 Issue 分析和 PR 创建工作流"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_analyze_gitcode_issue_and_create_pr(self, runner: JiuwenRunner, temp_project: str):
        """测试分析 GitCode issue 并创建 PR 的工作流

        这个测试用例用于调试 API 429 错误等问题。
        """
        query = "请帮我分析并修复openjiuwen社区的issue: https://gitcode.com/openJiuwen/agent-core/issues/77, 并创建Pull Request"

        print(f"\n{'='*60}")
        print(f"测试查询: {query}")
        print(f"{'='*60}\n")

        # 使用较长的超时时间，因为这个任务涉及网络请求
        response = await runner.run(query, timeout=180)

        print(f"\n{'='*60}")
        print("测试结果:")
        print(f"{'='*60}")
        print(f"Exit code: {response.exit_code}")
        print(f"Duration: {response.duration:.2f}s")
        print(f"Errors: {response.errors}")
        print(f"\n--- stdout ---")
        print(response.stdout)
        print(f"\n--- stderr ---")
        print(response.stderr)
        print(f"\n--- content ---")
        print(response.content)
        print(f"{'='*60}\n")

        # 检查是否有 429 错误
        full_output = response.stdout + response.stderr + response.content
        if "429" in full_output:
            print("\n[!] 检测到 429 错误!")
            # 提取 429 相关的错误信息
            for line in full_output.split('\n'):
                if '429' in line or 'rate' in line.lower() or 'limit' in line.lower():
                    print(f"  -> {line}")

        # 检查是否有其他 API 错误
        api_error_keywords = ['error', 'exception', 'failed', 'timeout', 'rate limit', 'quota']
        for keyword in api_error_keywords:
            if keyword.lower() in full_output.lower():
                print(f"\n[!] 检测到关键词 '{keyword}'")
                for line in full_output.split('\n'):
                    if keyword.lower() in line.lower():
                        print(f"  -> {line}")

        # 这个测试主要用于调试，不做严格断言
        # 只要能运行并返回结果就算通过
        assert response.content or response.stdout, "应该有输出内容"


@pytest.mark.e2e
@pytest.mark.workflow
class TestApiErrorHandling:
    """测试 API 错误处理"""

    @requires_api_key
    @pytest.mark.asyncio
    async def test_api_rate_limit_error_details(self, runner: JiuwenRunner, temp_project: str):
        """测试 API 速率限制错误的详细信息

        发送一个需要多次 API 调用的复杂请求，观察是否触发 429 错误。
        """
        # 一个复杂的请求，可能触发多次 API 调用
        query = """请帮我完成以下任务：
1. 访问 https://gitcode.com/openJiuwen/agent-core/issues/77 获取 issue 详情
2. 分析 issue 中描述的问题
3. 在本地代码库中搜索相关代码
4. 提出修复方案
5. 创建 Pull Request"""

        print(f"\n{'='*60}")
        print(f"测试查询: {query}")
        print(f"{'='*60}\n")

        response = await runner.run(query, timeout=300)

        print(f"\n{'='*60}")
        print("测试结果:")
        print(f"{'='*60}")
        print(f"Exit code: {response.exit_code}")
        print(f"Duration: {response.duration:.2f}s")
        print(f"Errors count: {len(response.errors)}")

        # 详细打印所有错误
        if response.errors:
            print("\n--- Errors ---")
            for i, err in enumerate(response.errors):
                print(f"Error {i+1}: {err}")

        # 检查输出中的错误信息
        full_output = response.stdout + response.stderr + response.content

        # 查找 HTTP 状态码错误
        import re
        http_errors = re.findall(r'(\d{3})\s*(error|Error|ERROR)?', full_output)
        if http_errors:
            print("\n--- HTTP 状态码 ---")
            for code, _ in http_errors:
                if code.startswith(('4', '5')):
                    print(f"  HTTP {code}")

        # 查找 API 相关错误
        api_patterns = [
            r'rate.?limit',
            r'429',
            r'too.?many.?requests',
            r'quota',
            r'exceeded',
            r'anthropic.*error',
            r'openai.*error',
            r'api.*error',
        ]

        print("\n--- API 错误检测 ---")
        for pattern in api_patterns:
            matches = re.findall(f'.*{pattern}.*', full_output, re.IGNORECASE)
            if matches:
                print(f"Pattern '{pattern}':")
                for match in matches[:5]:  # 只显示前5个匹配
                    print(f"  -> {match.strip()[:200]}")

        print(f"\n--- 完整输出 (前 2000 字符) ---")
        print(full_output[:2000])
        print(f"{'='*60}\n")

        # 不做严格断言，主要用于调试
        assert True, "测试完成，请查看输出日志"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])
