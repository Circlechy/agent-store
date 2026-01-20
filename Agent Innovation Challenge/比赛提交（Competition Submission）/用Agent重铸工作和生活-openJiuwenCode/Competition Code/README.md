# OpenJiuwen Code

> 你的终端 AI 编程搭子 - 说一句话，自动完成 Issue 分析 → 代码修复 → PR 提交

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/)
[![Tests](https://img.shields.io/badge/tests-169%20passed-brightgreen.svg)](tests/)

## 项目简介

**OpenJiuwen Code** 是一个让你用自然语言指挥代码的终端 AI 助手，基于开源的 [openJiuwen agent-core SDK](https://gitcode.com/openJiuwen/agent-core) 构建。

```
三大模式，从想法到上线全搞定

BUILD 模式  → 放开手脚写代码，自动化一切
PLAN 模式   → 大任务先出方案，你点头再动手
REVIEW 模式 → 批量审 PR，漏洞 Bug 无处藏
```

### 核心能力

| 能力 | 说明 |
|------|------|
| **Skill 插件系统** | 能力无限扩展，一键安装社区技能 |
| **GitCode 深度集成** | Issue/PR/Branch 全流程自动化 |
| **子Agent并行** | 上下文隔离，多任务同时执行 |
| **浏览器自动化** | 网页操作也能搞定 |
| **双模型路由** | 智能省钱，成本降 70% |
| **跨平台** | Linux / macOS / Windows 通吃 |
| **169 个测试** | 100% 通过，稳如老狗 |

## 快速开始

### 一键安装（推荐）

**Linux / macOS**

```bash
curl -fsSL https://gitcode.com/SnapeK/openjiuwen-code/raw/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://gitcode.com/SnapeK/openjiuwen-code/raw/main/install.ps1 | iex
```

### 从源码安装

<details>
<summary>Linux / macOS</summary>

```bash
# 克隆项目（包含 agent-core SDK submodule）
git clone --recurse-submodules https://gitcode.com/SnapeK/openjiuwen-code.git
cd openjiuwen-code

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行
./jiuwen
```

</details>

<details>
<summary>Windows</summary>

```powershell
# 克隆项目
git clone --recurse-submodules https://gitcode.com/SnapeK/openjiuwen-code.git
cd openjiuwen-code

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行（如果颜色显示异常，加 --no-color）
python -m packages.cli.main
```

</details>

### 配置 API Key

```bash
# 方式 1：环境变量（推荐）
export ANTHROPIC_API_KEY="your-api-key"    # Anthropic Claude
export OPENAI_API_KEY="your-api-key"       # OpenAI
export ZHIPU_API_KEY="your-api-key"        # 智谱 AI

# 方式 2：交互式配置
jiuwen --config
```

### 系统要求

- **Python**: 3.10+
- **操作系统**: Linux / macOS / Windows 10+
- **终端**: 支持 ANSI 颜色（Windows 推荐使用 Windows Terminal）

## 核心工具集

| 工具 | 功能 | 说明 |
|------|------|------|
| **ReadFile** | 读取文件 | 支持行号范围、大文件分页 |
| **WriteFile** | 写入文件 | 完全覆盖模式 |
| **EditFile** | 智能编辑 | 字符串替换，保留格式 |
| **Bash** | Shell 执行 | 带安全检查、超时控制 |
| **Grep** | 内容搜索 | 基于 ripgrep，支持正则 |
| **Glob** | 文件匹配 | 支持 `**/*` 递归模式 |
| **LS** | 目录列表 | 列出目录内容 |
| **TodoWrite** | 任务管理 | 持久化任务列表 |
| **WebFetch** | 网页抓取 | 获取网页内容 |
| **WebSearch** | 网络搜索 | 搜索引擎集成 |
| **GitCode API** | 代码托管 | Issue/PR/Branch 操作 |
| **SpawnSubAgent** | 子Agent | 并行任务，上下文隔离 |
| **EnterPlanMode** | 规划模式 | 复杂任务先规划后执行 |
| **BrowserAutomation** | 浏览器自动化 | 网页交互操作 |

## 内置子Agent

子Agent 是独立运行的轻量级 Agent，拥有独立上下文，可并行执行任务。主Agent 可以派发多个子Agent 同时工作，最后汇总结果。

| 子Agent | 用途 | 特点 |
|---------|------|------|
| **Explore** | 代码库探索 | 快速搜索文件、代码关键词、理解项目结构 |
| **Plan** | 方案规划 | 设计实现计划、识别关键文件、权衡架构方案 |
| **Researcher** | 信息调研 | 网络搜索、竞品分析、技术调研 |
| **CodeReviewer** | 代码审查 | 审查代码质量、安全漏洞、最佳实践 |
| **Debugger** | 问题诊断 | 复杂问题诊断、根因分析、系统化排查 |
| **Refactoring** | 代码重构 | 安全代码转换、设计模式应用、结构优化 |

### 子Agent 核心特性

```
┌──────────────────────────────────────────────┐
│              主 Agent (Sonnet)               │
│  - 任务分解与派发                             │
│  - 结果汇总与报告生成                         │
└──────────────┬───────────────────────────────┘
               │ spawn_sub_agents()
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│子Agent1│ │子Agent2│ │子Agent3│
│(Haiku) │ │(Haiku) │ │(Haiku) │
│独立上下文│ │独立上下文│ │独立上下文│
└────────┘ └────────┘ └────────┘
```

- **上下文隔离**: 每个子Agent独立会话，互不污染
- **并行执行**: 多任务同时进行，效率翻倍
- **结果聚合**: 主Agent汇总所有子Agent结果
- **成本优化**: 子Agent使用小模型，降低 70% 成本

## 核心用例

### 用例 1: BUILD 模式 - 一句话搞定开发

> 说句话，Issue 到 PR 全自动

```
[BUILD] ❯ 帮我分析并修复这个issue: https://gitcode.com/openJiuwen/agent-core/issues/77, 并创建一个修复的PR

● web_fetch(https://gitcode.com/openJiuwen/agent-core/issues/77)
  ⎿ Issue #77: ReActAgent 在流式输出时偶发 KeyError

● grep("KeyError", **/*.py)
  ⎿ 找到 3 处相关代码

● read_file(agent-core/openjiuwen/core/agent/react.py)
  ⎿ 成功读取 (450 行)

● 思考中...
  发现问题：第 234 行缺少 key 存在性检查

● edit_file(agent-core/openjiuwen/core/agent/react.py)
  ⎿ 修改成功

● bash(git checkout -b fix/issue-77-keyerror)
● bash(git add . && git commit -m "fix: add key check for streaming output")

● gitcode_create_pr(...)
  ⎿ PR #78 创建成功: https://gitcode.com/openJiuwen/agent-core/pulls/78
```

### 用例 2: PLAN 模式 - 复杂任务先规划再执行

> 大任务先出方案，你点头再动手

```
[BUILD] ❯ 把项目的 docs 目录部署到一个可公开访问的文档网站

● enter_plan_mode()
  ⎿ 已进入 PLAN 模式
  ⎿ Plan 文件: ~/.jiuwen/plans/bright-calm-aurora.md

[PLAN 模式]

● glob(docs/**/*.md)
  ⎿ 找到 5 个文档文件

● write_file(~/.jiuwen/plans/bright-calm-aurora.md)
  ⎿ 写入实现计划

## Plan 审批请求

请审批此计划:
- 输入 'approve' 批准并切换到 BUILD 模式
- 输入 'reject' 继续规划

### 预申请的命令权限:
- [Bash] install dependencies
- [Bash] run mkdocs serve
- [Bash] git operations

[用户输入] approve

● 已切换到 BUILD 模式，开始执行计划...

● bash(pip install mkdocs-material)  [预授权，无需确认]
  ⎿ Successfully installed mkdocs-material-9.5.0

● write_file(mkdocs.yml)
● write_file(.github/workflows/docs.yml)

✅ 部署完成！
   公开地址: https://snapek.github.io/openjiuwen-code
```

### 用例 3: REVIEW 模式 - 批量 PR 审查

> 自动审查所有待合入 PR

```
[BUILD] ❯ /mode review

[REVIEW] ❯ 审查 openJiuwen/agent-core 仓库所有待合入的 PR，给出审查意见

● gitcode_list_prs(owner="openJiuwen", repo="agent-core", state="open")
  ⎿ 找到 3 个待审查 PR

● gitcode_get_pr(...) × 3
● web_fetch(...diff) × 3

## 审查汇总

| PR | 标题 | 状态 | 建议 |
|----|------|------|------|
| #78 | fix: resolve KeyError | ✅ 可合入 | 建议补充测试 |
| #76 | feat: add retry mechanism | ⚠️ 需修改 | 添加配置和日志 |
| #75 | docs: update README | ✅ 可合入 | 无问题 |
```

### 用例 4: 子Agent并行 - 竞品调研

> 多个子Agent并行调研，互不干扰

```
[BUILD] ❯ 帮我调研 AI 编程助手领域的主要竞品：Cursor、GitHub Copilot、Windsurf

● 思考中...
  分析任务：需要调研 3 个竞品，每个竞品调研相互独立
  决策：启动 3 个并行子Agent

● spawn_sub_agents([
    {name: "cursor-researcher", task: "调研 Cursor 编辑器"},
    {name: "copilot-researcher", task: "调研 GitHub Copilot"},
    {name: "windsurf-researcher", task: "调研 Windsurf"}
  ])
  ⎿ 启动 3 个子Agent，并行执行中...

┌─────────────────────────────────────────────────────────────┐
│  [子Agent 1: cursor-researcher]                             │
│  ● web_search("Cursor AI editor features pricing")          │
├─────────────────────────────────────────────────────────────┤
│  [子Agent 2: copilot-researcher]                            │
│  ● web_search("GitHub Copilot features pricing")            │
├─────────────────────────────────────────────────────────────┤
│  [子Agent 3: windsurf-researcher]                           │
│  ● web_search("Windsurf AI IDE features")                   │
└─────────────────────────────────────────────────────────────┘

⏱️ 并行执行，总耗时 ≈ 单个子Agent耗时（而非 3 倍）

## AI 编程助手竞品调研报告

| 产品 | 免费版 | 付费版 | 特色功能 |
|------|--------|--------|----------|
| Cursor | 2周试用 | $20/月 | Composer多文件编辑 |
| GitHub Copilot | ❌ | $10/月 | 深度GitHub集成 |
| Windsurf | ✅ 无限制 | $15/月 | Cascade流式编辑 |

📊 本报告由 3 个子Agent并行调研生成
💰 成本: 子Agent使用小模型，节省 70% Token消耗
```

### 用例 5: Skill 系统 - 可扩展能力

```bash
# 查看已安装 Skills
[BUILD] ❯ /skills list

📦 本地 Skills (~/.jiuwen/skills/)
  - code-review: 代码审查专家
  - git-commit: 智能提交助手

📦 项目 Skills (.jiuwen/skills/)
  - project-guide: 项目开发指南

# 安装社区插件
[BUILD] ❯ /skills install example-skills@anthropics
  ⎿ 克隆 marketplace: https://github.com/anthropics/skills.git
  ⎿ 安装完成！新增 12 个 skills

# 使用 Skill
[BUILD] ❯ /pdf 分析 report.pdf 并提取关键数据
● 激活 Skill: pdf
● read_file(report.pdf)
  ⎿ 解析 PDF (32 页)

## 报告分析结果
- 用户增长: 150% YoY
- 月活用户: 2.3M
```

## 命令参考

```bash
/mode build|plan|review    # 切换模式
/skills list               # 列出所有可用 skills
/skills install <plugin>@<marketplace>  # 安装插件
/help                      # 显示帮助
/clear                     # 清除对话历史
/exit                      # 退出程序
```

## 技术架构

### 核心设计

| 设计 | 说明 |
|------|------|
| **双模型路由** | 主模型 (Sonnet) 40-50%，小模型 (Haiku) 50-60%，成本降 70% |
| **子Agent隔离** | 每个子Agent独立会话，互不污染，结果聚合到主Agent |
| **三层工具架构** | 低层(Read/Write/Bash) → 中层(Edit/Grep/Glob) → 高层(Task/TodoWrite) |
| **模式权限控制** | BUILD 全权限，PLAN 只读+预授权，REVIEW 专注审查 |

### 工具权限矩阵

| 工具 | BUILD | PLAN | REVIEW |
|------|-------|------|--------|
| Read/Grep/Glob | ✅ | ✅ | ✅ |
| Write/Edit | ✅ | ❌ | ❌ |
| Bash | ✅ | ⚠️ 只读 | ❌ |
| TodoWrite | ✅ | ✅ | ✅ |
| GitCode API | ✅ | ✅ | ✅ |

## 项目结构

```
openjiuwen-code/
├── packages/
│   ├── server/                 # Agent 服务器
│   │   ├── agents/             # Agent 实现 (JiuwenCodeAgent, ModeManager)
│   │   ├── tools/              # 工具集 (8 个核心工具)
│   │   └── skills/             # Skills 系统 (loader/matcher/executor/installer)
│   └── cli/                    # TUI 客户端 (Rich 美化)
├── agent-core/                 # openJiuwen SDK (git submodule)
├── tests/                      # 测试套件 (169 个测试)
└── docs/                       # 设计文档
```

## 安全机制

- 命令黑名单（`rm -rf /`, `mkfs`, `format C:` 等）
- 路径限制（`/etc`, `/usr/bin`, `C:\Windows` 等）
- PLAN 模式禁止破坏性命令
- 超时控制（默认 30 秒）
- 跨平台安全检查（自动适配 Linux/macOS/Windows）

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 查看测试覆盖率
pytest --cov=packages/server --cov-report=html
```

**测试统计**: 169 个测试，100% 通过

## 文档

- [架构设计](docs/01-架构设计.md) - 整体架构和设计理念
- [详细技术设计](docs/02-详细技术设计.md) - 各模块的详细实现
- [SDK 修改记录](SDK_CHANGES.md) - 对 openJiuwen SDK 的修改

## 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [openJiuwen agent-core](https://gitcode.com/openJiuwen/agent-core) - 强大的 Agent 开发框架
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) - 设计灵感来源

---

**项目地址**: https://gitcode.com/SnapeK/openjiuwen-code

**openJiuwen Agent 编程大赛参赛作品**
