"""
Super Agent E2E 测试 - 演示复杂多步骤工作流（真实网站版）

运行方式:
    pytest tests/e2e/test_e2e_super_agent.py -v -m e2e -s

    # 使用 Python 3.11 venv
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_e2e_super_agent.py -v -m e2e -s

测试用例（全部访问真实网站）:
    1. Issue to PR - 访问 GitCode issue #77，分析并修复 openJiuwen SDK bug
    2. 简历筛选 - 访问 Boss 直聘，搜索并筛选 AI 工程师候选人
    3. 竞品分析 - 访问 Cursor、GitHub Copilot、Codeium 官网
"""

import pytest
import os

from .conftest import (
    requires_api_key,
    JiuwenRunner,
    assert_tool_called,
    assert_any_tool_called,
    assert_no_errors,
    assert_response_mentions,
)


# ============================================================================
# Fixture 1: Issue to PR 项目（真实 GitCode Issue）
# ============================================================================

@pytest.fixture
def issue_to_pr_project(temp_project):
    """创建 Issue to PR 测试项目（真实 GitCode Issue 版）

    项目结构:
        temp_project/
        └── output/                     # 输出目录

    真实 Issue:
        https://gitcode.com/openJiuwen/agent-core/issues/77
    """
    project_dir = temp_project

    # 创建输出目录
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    return {
        "project_dir": project_dir,
        "output_dir": output_dir,
        "issue_url": "https://gitcode.com/openJiuwen/agent-core/issues/77",
        "repo_url": "https://gitcode.com/openJiuwen/agent-core",
    }


# ============================================================================
# Fixture 2: 简历筛选项目（真实猎聘网）
# ============================================================================

@pytest.fixture
def resume_screening_project(temp_project):
    """创建职位筛选测试项目（HackerNews Jobs API 版）

    项目结构:
        temp_project/
        ├── requirements.md             # 职位要求
        └── output/                     # 输出目录

    数据源:
        HackerNews Jobs API - 对爬虫友好的真实职位数据
        - 职位列表: https://hacker-news.firebaseio.com/v0/jobstories.json
        - 职位详情: https://hacker-news.firebaseio.com/v0/item/{id}.json
    """
    project_dir = temp_project

    # 创建输出目录
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 创建 requirements.md - 职位要求
    requirements_file = os.path.join(project_dir, "requirements.md")
    with open(requirements_file, 'w', encoding='utf-8') as f:
        f.write("""# 软件工程师职位要求

## 必须条件
- 编程语言: Python, TypeScript, 或 Go 至少一种
- 后端开发经验: 2年以上
- 熟悉 Web 开发框架

## 加分项
- 有 AI/ML 相关经验
- 熟悉云服务 (AWS, GCP, Azure)
- 有创业公司经验
- YC 公司背景

## 工作职责
- 开发和维护后端服务
- 参与系统架构设计
- 代码审查和技术文档

## 搜索关键词
- Software Engineer
- Backend Engineer
- Full Stack Engineer
- Founding Engineer
""")

    return {
        "project_dir": project_dir,
        "requirements_file": requirements_file,
        "output_dir": output_dir,
        "job_api_url": "https://hacker-news.firebaseio.com/v0/jobstories.json",
        "job_detail_url_template": "https://hacker-news.firebaseio.com/v0/item/{id}.json",
        "job_site_name": "HackerNews Jobs",
        "search_keywords": ["Engineer", "Developer", "Backend", "Full Stack"],
    }


# ============================================================================
# Fixture 3: 竞品分析项目（真实网站版）
# ============================================================================

@pytest.fixture
def competitive_analysis_project(temp_project):
    """创建竞品分析测试项目（真实网站版）

    项目结构:
        temp_project/
        ├── competitors.md              # 竞品列表（真实 URL）
        └── output/                     # 输出目录

    竞品选择:
        - Cursor: AI IDE，热门产品
        - GitHub Copilot: 市场领导者
        - Codeium: 免费方案突出
    """
    project_dir = temp_project

    # 创建输出目录
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 创建 competitors.md - 竞品列表（真实 URL）
    competitors_file = os.path.join(project_dir, "competitors.md")
    with open(competitors_file, 'w', encoding='utf-8') as f:
        f.write("""# AI 编程助手竞品列表

## 竞品 1: Cursor
- 产品名称: Cursor
- 官网: https://cursor.com
- 定价页: https://cursor.com/pricing
- 简介: AI-first 代码编辑器，基于 VS Code

## 竞品 2: GitHub Copilot
- 产品名称: GitHub Copilot
- 官网: https://github.com/features/copilot
- 定价页: https://github.com/features/copilot/plans
- 简介: GitHub 官方 AI 编程助手

## 竞品 3: Codeium
- 产品名称: Codeium
- 官网: https://codeium.com
- 定价页: https://codeium.com/pricing
- 简介: 免费的 AI 代码补全工具

## 分析要求
请访问以上网站，提取以下信息：
1. 核心功能特性
2. 定价方案（免费版、个人版、团队版）
3. 与竞品的差异化优势
""")

    return {
        "project_dir": project_dir,
        "competitors_file": competitors_file,
        "output_dir": output_dir,
        "competitors": {
            "cursor": {
                "name": "Cursor",
                "url": "https://cursor.com",
                "pricing_url": "https://cursor.com/pricing",
            },
            "copilot": {
                "name": "GitHub Copilot",
                "url": "https://github.com/features/copilot",
                "pricing_url": "https://github.com/features/copilot/plans",
            },
            "codeium": {
                "name": "Codeium",
                "url": "https://codeium.com",
                "pricing_url": "https://codeium.com/pricing",
            },
        },
    }


# ============================================================================
# Test Case 1: Issue to PR 工作流（真实 GitCode Issue）
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.super_agent
@pytest.mark.network  # 需要网络访问
class TestSuperAgentIssueToPR:
    """Super Agent: Issue to PR 工作流（真实 GitCode Issue）

    场景: 开发者需要分析并修复 openJiuwen SDK 的真实 issue
    1. 访问 GitCode issue #77
    2. 理解问题描述和上下文
    3. 分析问题原因
    4. 提出修复方案或代码修改建议
    5. 生成分析报告
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_issue_to_pr_workflow(self, runner: JiuwenRunner, issue_to_pr_project: dict):
        """测试 Issue to PR 完整工作流 - 访问真实 GitCode Issue"""
        project = issue_to_pr_project
        output_dir = project["output_dir"]
        issue_url = project["issue_url"]

        # 构建查询
        query = f"""帮我分析修复 openJiuwen 社区的这个 issue: {issue_url}

请帮我完成以下任务：
1. 访问并读取 issue 的完整内容
2. 理解问题描述、复现步骤和错误信息
3. 分析问题的根本原因
4. 提出修复方案（代码修改建议）
5. 将分析报告保存到 {output_dir}/issue_analysis.md

报告应包含：
- Issue 摘要
- 问题原因分析
- 修复方案
- 建议的代码修改"""

        # 运行 jiuwen CLI（超时 300 秒，需要访问网站）
        response = await runner.run(query, timeout=300)

        # 验证工具调用 - 应该访问网站
        assert_any_tool_called(response, ["web_fetch", "browser_open", "bash"])
        assert_no_errors(response)

        # 验证响应包含 issue 相关的分析内容
        response_content = response.content.lower()
        has_analysis = (
            "issue" in response_content or
            "问题" in response.content or
            "分析" in response.content or
            "修复" in response.content or
            "建议" in response.content or
            "agent" in response_content or
            "error" in response_content or
            "77" in response.content
        )
        assert has_analysis, f"响应应该包含 issue 分析内容，实际响应: {response.content[:500]}"

        # 验证输出文件（如果生成了）
        output_file = os.path.join(output_dir, "issue_analysis.md")
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 100, f"分析报告应该有实质内容，实际长度: {len(content)}"


# ============================================================================
# Test Case 2: 职位筛选工作流（HackerNews Jobs API）
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.super_agent
@pytest.mark.network  # 需要网络访问
class TestSuperAgentJobScreening:
    """Super Agent: 职位筛选助手（HackerNews Jobs API）

    场景: 求职者需要从 HackerNews Jobs 筛选合适的职位
    1. 访问 HackerNews Jobs API 获取职位列表
    2. 获取每个职位的详细信息
    3. 根据职位要求筛选合适的职位
    4. 生成筛选报告
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_job_screening_workflow(self, runner: JiuwenRunner, resume_screening_project: dict):
        """测试职位筛选完整工作流 - 访问 HackerNews Jobs API"""
        project = resume_screening_project
        requirements_file = project["requirements_file"]
        output_dir = project["output_dir"]
        job_api_url = project["job_api_url"]
        job_detail_url_template = project["job_detail_url_template"]
        job_site_name = project["job_site_name"]

        # 构建查询 - 使用 HackerNews Jobs API
        query = f"""我需要从 {job_site_name} 筛选合适的职位。职位要求在 {requirements_file}。

请帮我：
1. 读取职位要求
2. 访问 HackerNews Jobs API 获取职位列表
   - 职位列表 API: {job_api_url}
   - 职位详情 API: {job_detail_url_template}
   - 使用 curl 或 web_fetch 工具访问 API
3. 获取前 10 个职位的详细信息
4. 分析每个职位，提取公司名称、职位标题、技术栈、薪资（如有）
5. 根据我的职位要求，筛选出最匹配的职位
6. 生成筛选报告（Markdown 格式），保存到 {output_dir}/screening_report.md

重要：必须从 {job_site_name} API 获取真实的职位数据。

报告应包含：
- 数据来源说明（{job_site_name}）
- 获取的职位总数
- 推荐的职位列表（包含公司、职位、技术栈、匹配度）
- 筛选建议"""

        # 运行 jiuwen CLI（超时 180 秒）
        response = await runner.run(query, timeout=180)

        # 验证工具调用 - 应该读取文件和访问 API
        assert_tool_called(response, "read_file")
        # 应该使用 curl 或 web_fetch 访问 API
        assert_any_tool_called(response, ["web_fetch", "WebFetch", "bash", "Bash"])
        assert_no_errors(response)

        # 验证输出文件必须存在
        output_file = os.path.join(output_dir, "screening_report.md")
        assert os.path.exists(output_file), f"筛选报告文件必须存在: {output_file}"

        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 验证报告有实质内容
        assert len(content) > 200, f"筛选报告应该有实质内容，实际长度: {len(content)}"

        # 验证报告包含真实的职位数据（从 HackerNews Jobs API 获取）
        import re

        # 检测 HackerNews Jobs 特有的内容
        # 1. YC 公司标识（很多 HN Jobs 是 YC 公司）
        has_yc_mention = "YC" in content or "Y Combinator" in content

        # 2. 职位标题格式（通常是 "Company (YC Sxx) Is Hiring" 或类似）
        job_title_pattern = re.compile(r'(Is Hiring|hiring|Hiring|Engineer|Developer|Founding)', re.IGNORECASE)
        has_job_titles = bool(job_title_pattern.search(content))

        # 3. 薪资格式（美元格式）
        salary_pattern = re.compile(r'\$\d+[kK]?|\d+K[-–]\d+K|\$\d+,?\d*')
        has_salary = bool(salary_pattern.search(content))

        # 4. 技术栈关键词
        tech_keywords = ["Python", "TypeScript", "JavaScript", "React", "Node", "AWS", "Go", "Rust", "PostgreSQL", "Redis"]
        has_tech_stack = any(tech in content for tech in tech_keywords)

        # 5. 公司名称（通常包含在职位标题中）
        # HN Jobs 的公司名通常是英文
        company_pattern = re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+\(YC\s+[SWF]\d+\))?')
        has_company_names = len(company_pattern.findall(content)) >= 2

        # 必须满足以下条件之一：
        # 1. 有 YC 提及 + 有职位标题
        # 2. 有职位标题 + 有技术栈
        # 3. 有薪资 + 有公司名称
        has_real_job_data = (
            (has_yc_mention and has_job_titles) or
            (has_job_titles and has_tech_stack) or
            (has_salary and has_company_names) or
            (has_tech_stack and has_company_names)
        )

        # 检查是否明确说明无法获取数据
        access_failed = (
            "无法访问" in content or
            "无法获取" in content or
            "API 错误" in content or
            "请求失败" in content or
            "模拟" in content or
            "示例数据" in content
        )

        if access_failed:
            pytest.fail(
                f"{job_site_name} API 访问失败，未能获取真实职位数据。\n"
                f"报告内容片段: {content[:500]}"
            )

        assert has_real_job_data, \
            f"报告必须包含从 {job_site_name} 获取的真实职位数据。\n" \
            f"检测结果: YC提及={has_yc_mention}, 职位标题={has_job_titles}, 薪资={has_salary}, 技术栈={has_tech_stack}, 公司名={has_company_names}\n" \
            f"报告内容: {content[:800]}"

        # 验证响应中提到了数据来源
        response_content = response.content.lower()
        mentions_data_source = (
            "hackernews" in response_content or
            "hacker news" in response_content or
            "hn" in response_content or
            "firebase" in response_content or
            "api" in response_content
        )
        assert mentions_data_source, f"响应应该提到数据来源（{job_site_name}），实际响应: {response.content[:500]}"


# ============================================================================
# Test Case 3: 竞品分析工作流（真实网站版）
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.super_agent
@pytest.mark.network  # 需要网络访问
class TestSuperAgentCompetitiveAnalysis:
    """Super Agent: 竞品分析报告（真实网站版）

    场景: 产品经理需要做竞品分析，Agent 需要：
    1. 读取竞品列表
    2. 访问真实网站获取信息
    3. 提取功能和定价信息
    4. 生成对比报告
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_competitive_analysis_workflow(self, runner: JiuwenRunner, competitive_analysis_project: dict):
        """测试竞品分析完整工作流 - 访问真实网站"""
        project = competitive_analysis_project
        competitors_file = project["competitors_file"]
        output_dir = project["output_dir"]

        # 构建查询
        query = f"""我需要做 AI 编程助手的竞品分析。竞品列表在 {competitors_file}。

请帮我：
1. 读取竞品列表，获取各产品的官网和定价页 URL
2. 访问每个竞品的网站，提取功能特性和定价信息
3. 生成对比报告（Markdown 格式），保存到 {output_dir}/analysis.md
4. 报告应包含：
   - 产品概述（各产品简介）
   - 功能对比表（代码补全、聊天、Agent 等核心功能）
   - 定价对比表（免费版、个人版、团队版价格）
   - 优劣势分析和建议

注意：请访问真实网站获取最新信息。"""

        # 运行 jiuwen CLI（超时 300 秒，需要访问多个网站）
        response = await runner.run(query, timeout=300)

        # 验证工具调用
        assert_tool_called(response, "read_file")
        assert_any_tool_called(response, ["web_fetch", "browser_open", "bash"])
        assert_no_errors(response)

        # 验证输出文件
        output_file = os.path.join(output_dir, "analysis.md")
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            content_lower = content.lower()
            # 验证包含所有竞品（至少应该包含一个）
            competitors_found = []
            if "cursor" in content_lower:
                competitors_found.append("Cursor")
            if "copilot" in content_lower:
                competitors_found.append("Copilot")
            if "codeium" in content_lower:
                competitors_found.append("Codeium")
            assert len(competitors_found) >= 1, \
                f"报告应包含至少一个竞品信息，实际内容: {content[:500]}"
        else:
            # 如果文件不存在，检查响应中是否有分析结果
            assert_response_mentions(response, ["Cursor", "Copilot", "Codeium", "功能", "定价"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
