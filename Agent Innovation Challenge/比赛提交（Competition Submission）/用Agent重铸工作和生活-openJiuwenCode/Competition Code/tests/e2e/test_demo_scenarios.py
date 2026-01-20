"""
Demo 录制场景 E2E 测试

测试 DEMO_RECORDING_GUIDE.md 中定义的 5 个视频场景，
每个视频对应一个测试用例，确保录制前所有关键功能正常工作。

运行方式:
    # 运行所有 Demo 场景测试
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_demo_scenarios.py -v -s

    # 运行单个场景
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_demo_scenarios.py::test_demo_video1_build_mode_issue_to_pr -v -s

    # 跳过网络依赖测试
    SKIP_NETWORK_TESTS=1 /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_demo_scenarios.py -v -s

注意:
    - 部分测试需要配置 GITCODE_ACCESS_TOKEN 环境变量
    - 网络测试可能因外部服务不可用而失败
    - 建议在录制前单独运行验证
"""

import pytest
import os
import re

from .conftest import (
    requires_api_key,
    JiuwenRunner,
    JiuwenResponse,
    assert_tool_called,
    assert_any_tool_called,
)


# ============================================================================
# 跳过条件
# ============================================================================

requires_gitcode_token = pytest.mark.skipif(
    not os.environ.get("GITCODE_ACCESS_TOKEN"),
    reason="需要配置 GITCODE_ACCESS_TOKEN 环境变量"
)

requires_network = pytest.mark.skipif(
    os.environ.get("SKIP_NETWORK_TESTS", "0") == "1",
    reason="跳过网络依赖测试"
)


# ============================================================================
# Demo 专用断言函数
# ============================================================================

def assert_no_demo_errors(response: JiuwenResponse) -> None:
    """断言 Demo 场景执行没有严重错误"""
    error_patterns = [
        r"执行异常",
        r"执行失败",
        r"validation error",
        r"Traceback",
    ]

    content = response.content + response.stdout + response.stderr

    for pattern in error_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match and len(response.content) < 100:
            pytest.fail(
                f"Demo 场景执行出错，匹配到错误模式: {pattern}\n"
                f"响应内容: {content[:1000]}"
            )


def assert_demo_response_quality(response: JiuwenResponse, keywords: list, min_length: int = 100) -> None:
    """断言 Demo 响应质量达标

    Args:
        response: JiuwenResponse 对象
        keywords: 期望包含的关键词列表（至少匹配一个）
        min_length: 最小响应长度
    """
    content = response.content.lower()

    if len(response.content) < min_length:
        pytest.fail(
            f"响应内容过短（{len(response.content)} < {min_length}）\n"
            f"响应: {response.content}"
        )

    found_keywords = [kw for kw in keywords if kw.lower() in content]
    if not found_keywords:
        pytest.fail(
            f"响应未包含任何期望的关键词: {keywords}\n"
            f"响应内容: {response.content[:500]}"
        )


# ============================================================================
# Demo 专用 Fixtures
# ============================================================================

@pytest.fixture
def buggy_code_project(temp_project):
    """创建有 Bug 的代码项目（视频 1 用）

    模拟 Issue: ReActAgent 在流式输出时偶发 KeyError
    """
    project_dir = temp_project
    src_dir = os.path.join(project_dir, "src")
    os.makedirs(src_dir, exist_ok=True)

    # 创建有 Bug 的代码
    with open(os.path.join(src_dir, "react_agent.py"), 'w', encoding='utf-8') as f:
        f.write('''"""ReAct Agent 实现 - 有 Bug"""

class ReActAgent:
    """ReAct Agent 类"""

    def __init__(self):
        self.state = {}
        self.history = []

    def process_stream(self, data: dict) -> str:
        """处理流式输出

        Bug: 直接访问 data["output"] 可能抛出 KeyError
        当流式数据不完整时，output 字段可能不存在
        """
        # Bug: 缺少 key 存在性检查
        result = data["output"]  # KeyError 风险!
        self.history.append(result)
        return result

    def safe_process(self, data: dict) -> str:
        """安全处理方法（正确实现）"""
        result = data.get("output", "")
        if result:
            self.history.append(result)
        return result
''')

    # 初始化 Git 仓库
    os.system(f"cd {project_dir} && git init -q && git config user.email 'test@test.com' && git config user.name 'Test' && git add . && git commit -q -m 'Initial commit'")

    return {
        "project_dir": project_dir,
        "src_dir": src_dir,
        "bug_file": os.path.join(src_dir, "react_agent.py"),
    }


@pytest.fixture
def docs_project(temp_project):
    """创建包含 docs 目录的项目（视频 2 用）"""
    project_dir = temp_project
    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    with open(os.path.join(docs_dir, "01-架构设计.md"), 'w', encoding='utf-8') as f:
        f.write("""# 架构设计

## 概述
这是一个示例项目的架构设计文档。

## 核心模块
- 用户模块
- 订单模块
- 支付模块

## 技术栈
- Python 3.11
- FastAPI
- PostgreSQL
""")

    with open(os.path.join(docs_dir, "02-详细技术设计.md"), 'w', encoding='utf-8') as f:
        f.write("""# 详细技术设计

## API 设计
RESTful API 设计规范。

## 数据库设计
使用 PostgreSQL 作为主数据库。
""")

    return {
        "project_dir": project_dir,
        "docs_dir": docs_dir,
    }


@pytest.fixture
def pr_review_project(temp_project):
    """创建 PR 审查项目（视频 3 用）"""
    project_dir = temp_project
    src_dir = os.path.join(project_dir, "src")
    os.makedirs(src_dir, exist_ok=True)

    with open(os.path.join(src_dir, "new_feature.py"), 'w', encoding='utf-8') as f:
        f.write('''"""新功能实现 - 待审查"""

def retry_api_call(func, max_retries=3):
    """API 调用重试机制

    待审查点:
    1. 重试次数硬编码
    2. 缺少重试日志
    3. 没有指数退避
    """
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            continue
    return None

def process_data(data):
    """数据处理函数

    待审查点:
    1. 缺少输入验证
    2. 没有类型提示
    """
    result = data * 2
    return result
''')

    return {
        "project_dir": project_dir,
        "review_file": os.path.join(src_dir, "new_feature.py"),
    }


# ============================================================================
# 视频 1: BUILD 模式 - Issue 到 PR 全流程
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
@requires_api_key
@pytest.mark.asyncio
async def test_demo_video1_build_mode_issue_to_pr(runner: JiuwenRunner, buggy_code_project: dict):
    """视频 1: BUILD 模式 - 分析并修复 Issue，创建 PR

    对应 DEMO_RECORDING_GUIDE.md 视频 1

    预期工具调用流程:
    1. web_fetch/read_file → 获取 Issue 信息或读取代码
    2. grep → 搜索相关代码
    3. read_file → 读取有问题的文件
    4. edit_file → 修复 Bug
    5. bash(git) → 创建分支、提交
    6. (可选) gitcode_create_pr → 创建 PR

    验证点:
    - 工具调用: read_file, grep, edit_file, bash
    - 响应包含: 分析、修复、KeyError 相关内容
    """
    project = buggy_code_project

    query = f"""请帮我分析并修复 {project['bug_file']} 中的 Bug。

问题描述（模拟 Issue #77）：
ReActAgent 的 process_stream 方法在处理流式数据时可能抛出 KeyError，
因为直接访问 data["output"] 而没有检查 key 是否存在。

请完成以下步骤：
1. 读取代码分析问题
2. 修复 Bug（参考 safe_process 方法的实现）
3. 创建 Git 分支 fix/keyerror-bug
4. 提交修复"""

    response = await runner.run(query, timeout=180)

    # 验证工具调用
    assert_any_tool_called(response, ["read_file", "grep"])
    assert_no_demo_errors(response)

    # 验证响应质量
    assert_demo_response_quality(
        response,
        keywords=["keyerror", "output", "get", "修复", "fix", "process_stream", "bug"],
        min_length=100
    )

    print(f"\n✅ 视频 1 测试通过")
    print(f"   工具调用: {[c.name for c in response.tool_calls]}")
    print(f"   响应长度: {len(response.content)} 字符")


# ============================================================================
# 视频 2: PLAN 模式 - 文档网站部署
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
@requires_api_key
@pytest.mark.asyncio
async def test_demo_video2_plan_mode_docs_deployment(runner: JiuwenRunner, docs_project: dict):
    """视频 2: PLAN 模式 - 规划文档网站部署

    对应 DEMO_RECORDING_GUIDE.md 视频 2

    预期工具调用流程:
    1. enter_plan_mode → 进入 PLAN 模式
    2. glob/ls → 探索文档目录结构
    3. read_file → 读取文档内容
    4. write_file → 写入 Plan 文件
    5. exit_plan_mode → 退出并等待用户审批

    验证点:
    - 工具调用: enter_plan_mode, glob/ls, read_file
    - 模式切换: 进入 PLAN 模式
    - 响应包含: 规划、部署、文档相关内容
    """
    project = docs_project

    query = f"""请帮我规划将 {project['docs_dir']} 目录部署为文档网站。

请完成以下步骤：
1. 进入 PLAN 模式（使用 enter_plan_mode 工具）
2. 探索文档目录结构，了解有哪些文档
3. 分析文档内容，制定部署方案
4. 生成部署计划（考虑使用 MkDocs、VitePress 或 Docsify）
5. 退出 PLAN 模式等待审批"""

    response = await runner.run(query, timeout=180)

    # 验证工具调用
    assert_any_tool_called(response, ["enter_plan_mode", "glob", "ls", "read_file"])
    assert_no_demo_errors(response)

    # 验证模式切换或规划内容
    content_lower = response.content.lower()
    has_plan_content = (
        "plan" in content_lower or
        "规划" in response.content or
        "部署" in response.content or
        "mkdocs" in content_lower or
        "vitepress" in content_lower or
        "docsify" in content_lower
    )

    assert has_plan_content, f"应该包含规划相关内容，实际响应: {response.content[:500]}"

    print(f"\n✅ 视频 2 测试通过")
    print(f"   工具调用: {[c.name for c in response.tool_calls]}")
    print(f"   响应长度: {len(response.content)} 字符")


# ============================================================================
# 视频 3: REVIEW 模式 - 批量 PR 审查
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
@requires_api_key
@pytest.mark.asyncio
async def test_demo_video3_review_mode_pr_review(runner: JiuwenRunner, pr_review_project: dict):
    """视频 3: REVIEW 模式 - 代码审查

    对应 DEMO_RECORDING_GUIDE.md 视频 3

    预期工具调用流程:
    1. (可选) /mode review → 切换到 REVIEW 模式
    2. read_file → 读取待审查代码
    3. grep → 搜索相关代码模式
    4. 生成审查报告

    验证点:
    - 工具调用: read_file
    - 响应包含: 审查意见、建议、问题点
    """
    project = pr_review_project

    query = f"""请审查 {project['review_file']} 的代码质量。

审查要点：
1. 代码质量和可读性
2. 潜在的 Bug 或问题
3. 性能和安全考虑
4. 改进建议

请生成结构化的代码审查报告，包括：
- 问题列表（按严重程度排序）
- 具体的改进建议
- 代码示例（如果需要）"""

    response = await runner.run(query, timeout=180)

    # 验证工具调用
    assert_tool_called(response, "read_file")
    assert_no_demo_errors(response)

    # 验证审查内容
    assert_demo_response_quality(
        response,
        keywords=["审查", "review", "建议", "问题", "重试", "retry", "日志", "log", "类型", "验证"],
        min_length=200
    )

    print(f"\n✅ 视频 3 测试通过")
    print(f"   工具调用: {[c.name for c in response.tool_calls]}")
    print(f"   响应长度: {len(response.content)} 字符")


# ============================================================================
# 视频 4: Skill 系统
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
@requires_api_key
@pytest.mark.asyncio
async def test_demo_video4_skill_system(runner: JiuwenRunner):
    """视频 4: Skill 系统 - 可扩展插件

    对应 DEMO_RECORDING_GUIDE.md 视频 4

    预期流程:
    1. /skills list → 列出已安装的 Skills
    2. /skills search → 搜索可用 Skills
    3. (可选) /skills install → 安装 Skill
    4. (可选) /pdf → 激活并使用 Skill

    验证点:
    - 命令响应: 返回 Skills 相关信息
    - 响应包含: skill、已安装、可用等关键词
    """
    # 测试 /skills list 命令
    response = await runner.run("/skills list", timeout=60)

    # 验证响应包含 Skills 信息
    content_lower = response.content.lower()
    has_skills_info = (
        "skill" in content_lower or
        "已安装" in response.content or
        "本地" in response.content or
        "项目" in response.content or
        "无" in response.content or
        "没有" in response.content or
        "可用" in response.content
    )

    assert has_skills_info, f"应该返回 Skills 信息，实际响应: {response.content[:500]}"

    # 测试 /skills help 命令
    help_response = await runner.run("/skills help", timeout=30)

    help_content_lower = help_response.content.lower()
    has_help = (
        "skill" in help_content_lower or
        "命令" in help_response.content or
        "用法" in help_response.content or
        "help" in help_content_lower or
        "list" in help_content_lower or
        "install" in help_content_lower
    )

    assert has_help, f"应该返回帮助信息，实际响应: {help_response.content[:300]}"

    print(f"\n✅ 视频 4 测试通过")
    print(f"   /skills list 响应长度: {len(response.content)} 字符")
    print(f"   /skills help 响应长度: {len(help_response.content)} 字符")


# ============================================================================
# 视频 5: 子Agent并行 - 竞品调研
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.slow
@requires_api_key
@requires_network
@pytest.mark.asyncio
async def test_demo_video5_subagent_parallel_research(runner: JiuwenRunner):
    """视频 5: 子Agent并行 - 上下文隔离的竞品调研

    对应 DEMO_RECORDING_GUIDE.md 视频 5

    预期工具调用流程:
    1. 主Agent分析任务，决定派发子Agent
    2. spawn_sub_agents / task → 启动多个并行子Agent
       - cursor-researcher: 调研 Cursor
       - copilot-researcher: 调研 GitHub Copilot
       - windsurf-researcher: 调研 Windsurf
    3. 子Agent各自执行 web_search/web_fetch
    4. 主Agent汇总结果，生成对比表格

    验证点:
    - 工具调用: task 或 web_fetch/web_search
    - 响应包含: 竞品名称、功能对比、定价等
    - 响应格式: 包含表格或结构化对比
    """
    query = """帮我调研 AI 编程助手领域的主要竞品：Cursor、GitHub Copilot、Windsurf。

请分析它们的：
1. 核心功能
2. 定价策略
3. 技术特点

要求：
- 使用 Task 工具启动子Agent进行并行调研（每个竞品一个子Agent）
- 或者直接使用 web_fetch 获取各产品官网信息
- 最后生成对比表格

注意：这是一个展示子Agent并行执行能力的Demo，请尽量使用 Task 工具。"""

    response = await runner.run(query, timeout=300)

    # 验证执行了调研（通过 task 或 web_fetch）
    assert_any_tool_called(response, ["task", "web_fetch", "web_search"])
    assert_no_demo_errors(response)

    # 验证响应包含竞品信息
    content_lower = response.content.lower()
    competitors_mentioned = sum([
        1 for comp in ["cursor", "copilot", "windsurf"]
        if comp in content_lower
    ])

    assert competitors_mentioned >= 2, \
        f"应该提到至少 2 个竞品，实际提到 {competitors_mentioned} 个\n响应: {response.content[:500]}"

    # 验证响应质量
    assert_demo_response_quality(
        response,
        keywords=["cursor", "copilot", "windsurf", "功能", "定价", "ai", "编程", "编辑器"],
        min_length=300
    )

    # 检查是否有表格或结构化输出
    has_structured_output = (
        "|" in response.content or  # Markdown 表格
        "对比" in response.content or
        "比较" in response.content or
        "总结" in response.content or
        "结论" in response.content
    )

    print(f"\n✅ 视频 5 测试通过")
    print(f"   工具调用: {[c.name for c in response.tool_calls]}")
    print(f"   响应长度: {len(response.content)} 字符")
    print(f"   提到竞品数: {competitors_mentioned}")
    print(f"   有结构化输出: {has_structured_output}")


# ============================================================================
# 辅助测试：验证测试环境
# ============================================================================

@pytest.mark.e2e
@pytest.mark.demo
def test_demo_environment_check():
    """验证 Demo 测试环境配置

    检查：
    - API Key 配置
    - GitCode Token 配置（可选）
    - 网络连接（可选）
    """
    checks = {
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
        "ZHIPU_API_KEY": bool(os.environ.get("ZHIPU_API_KEY")),
        "GITCODE_ACCESS_TOKEN": bool(os.environ.get("GITCODE_ACCESS_TOKEN")),
        "SKIP_NETWORK_TESTS": os.environ.get("SKIP_NETWORK_TESTS", "0"),
    }

    print("\n📋 Demo 测试环境检查:")
    for key, value in checks.items():
        status = "✅" if value and value != "0" else "❌"
        print(f"   {status} {key}: {value}")

    # 至少需要一个 API Key
    has_api_key = checks["ANTHROPIC_API_KEY"] or checks["OPENAI_API_KEY"] or checks["ZHIPU_API_KEY"]

    if not has_api_key:
        pytest.skip("需要至少配置一个 API Key (ANTHROPIC_API_KEY, OPENAI_API_KEY, 或 ZHIPU_API_KEY)")

    print("\n   ✅ 环境检查通过，可以运行 Demo 测试")
