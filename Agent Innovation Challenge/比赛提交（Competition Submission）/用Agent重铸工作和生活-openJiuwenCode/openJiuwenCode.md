# OpenJiuwen Code - 智能编程助手 Agent

> 你的终端 AI 编程搭子，一句话完成 Issue 分析 → 代码修复 → PR 提交

---

## 1. Agent 应用场景

### 场景概述

OpenJiuwen Code 是一个基于 **openJiuwen agent-core SDK** 构建的终端 AI 编程助手。它采用 ReAct（Reasoning + Acting）模式，让你用自然语言指挥代码，复杂任务先规划再执行，步步可控。

### 典型用户场景

**🔧 一句话修 Bug**
> "帮我分析并修复这个 issue: https://gitcode.com/xxx/issues/77，并创建修复 PR"

Agent 自动：获取 Issue → 搜索代码 → 定位问题 → 修复代码 → 创建 PR

**📋 复杂任务规划**
> "把项目的 docs 目录部署到一个可公开访问的文档网站"

Agent 先出方案，你点头再动手，预授权命令无需反复确认

**🔍 批量 PR 审查**
> "审查 openJiuwen/agent-core 仓库所有待合入的 PR，给出审查意见"

自动遍历所有 PR，生成结构化审查报告

**🔬 并行竞品调研**
> "调研 AI 编程助手领域的主要竞品：Cursor、GitHub Copilot、Windsurf"

启动多个子 Agent 并行调研，上下文隔离，结果自动汇总

**📦 一键扩展能力**
> "/skills install example-skills@anthropics"

从社区 Marketplace 安装 Skills 插件，PDF 处理、Excel 操作、前端设计...

---

## 2. Agent 技术方案

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│              (CLI 终端 / IDE 插件 / MCP 协议)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     Agent 协调层                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │ 模式管理器   │  │ 意图识别    │  │ 上下文管理   │            │
│   │ BUILD/PLAN  │  │ 任务分类    │  │ 三层存储     │            │
│   │ /REVIEW     │  │ 优先级判断  │  │ 智能压缩     │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                  ReAct 推理执行层                                │
│   ┌──────────────────────────────────────────────────────┐     │
│   │  🧠 Reasoning: 分析任务 → 制定计划 → 选择工具         │     │
│   │  🎯 Acting: 执行工具 → 观察结果 → 迭代优化            │     │
│   └──────────────────────────────────────────────────────┘     │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │ 主 Agent    │  │ Sub Agent   │  │ Skills 系统 │            │
│   │ (Sonnet 4)  │  │ (Haiku 3.5) │  │ 可扩展插件  │            │
│   │ 复杂推理    │  │ 简单任务    │  │ 领域增强    │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      工具与服务层                                │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │文件操作 │ │代码搜索│ │Shell   │ │GitCode │ │Web搜索 │       │
│  │Read    │ │Grep    │ │Bash    │ │PR/Issue│ │WebFetch│       │
│  │Write   │ │Glob    │ │安全沙箱│ │Branch  │ │Research│       │
│  │Edit    │ │LS      │ │        │ │        │ │        │       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │子Agent │ │计划工具│ │用户交互│ │浏览器  │ │Todo    │       │
│  │Task    │ │Plan    │ │Ask     │ │Browser │ │TodoWrite│      │
│  │并行执行│ │Mode    │ │Question│ │自动化  │ │进度追踪│       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

### 核心技术组件

#### 2.1 三大工作模式 - 安全可控

```
┌─────────────────────────────────────────────────────────────┐
│                    三种工作模式                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔨 BUILD 模式 (默认)                                       │
│  ├── 放开手脚写代码，自动化一切                             │
│  ├── 完整工具访问权限                                       │
│  ├── 适用于：功能开发、Bug 修复、代码重构                   │
│  └── 危险操作需用户确认                                     │
│                                                             │
│  📋 PLAN 模式                                               │
│  ├── 大任务先出方案，你点头再动手                           │
│  ├── 只读权限，专注于分析和规划                             │
│  ├── 适用于：需求分析、架构设计、方案评估                   │
│  └── 支持预授权，审批后命令无需反复确认                     │
│                                                             │
│  🔍 REVIEW 模式                                             │
│  ├── 批量审 PR，漏洞 Bug 无处藏                             │
│  ├── 只读权限，专注审查                                     │
│  ├── 适用于：Code Review、安全审计、性能分析                │
│  └── 生成结构化审查报告                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**模式切换示例**：
```bash
/mode plan    # 切换到 PLAN 模式
/mode review  # 切换到 REVIEW 模式
/mode build   # 切换回 BUILD 模式
```

---

#### 2.2 子 Agent 并行 - 上下文隔离

```
┌─────────────────────────────────────────────────────────────┐
│                    子Agent 核心特性                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 上下文隔离 → 每个子Agent独立会话，互不污染              │
│  2. 并行执行   → 多任务同时进行，效率翻倍                   │
│  3. 结果聚合   → 主Agent汇总所有子Agent结果                 │
│  4. 成本优化   → 子Agent使用小模型，降低70%成本             │
│                                                             │
└─────────────────────────────────────────────────────────────┘

子Agent 工作原理：

┌──────────────────────────────────────────────┐
│              主 Agent (Sonnet 4)              │
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
    │          │          │
    └──────────┴──────────┘
               │ 结果返回
               ▼
        主Agent汇总输出
```

**并行执行效果**：
- ⏱️ 总耗时 ≈ 单个子Agent耗时（而非 N 倍）
- 💰 子Agent使用小模型，节省 70% Token 消耗

---

#### 2.3 Skills 插件系统 - 无限扩展

```
┌─────────────────────────────────────────────────────────────┐
│                    Skills 插件架构                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   三层 Skill 来源：                                         │
│                                                             │
│   ~/.jiuwen/skills/          # 全局 Skills（用户级）        │
│   <project>/.jiuwen/skills/  # 项目 Skills（项目级）        │
│   marketplace (远程)          # 社区 Skills（可安装）        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Skill 管理命令：                                          │
│                                                             │
│   /skills list                    # 查看已安装 Skills       │
│   /skills install <name>@<repo>   # 从 Marketplace 安装     │
│   /skills uninstall <name>        # 卸载 Skill              │
│   /skills add-marketplace <url>   # 添加自定义 Marketplace  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  📦 社区 Skills 示例：                                       │
│  • pdf - PDF 文档处理                                       │
│  • xlsx - Excel 表格操作                                    │
│  • pptx - PPT 演示文稿                                      │
│  • docx - Word 文档编辑                                     │
│  • frontend-design - 前端设计专家                           │
│  • mcp-builder - MCP 服务器构建                             │
│  • webapp-testing - Web 应用测试                            │
└─────────────────────────────────────────────────────────────┘
```

**自定义 Skill 示例**：
```markdown
# ~/.jiuwen/skills/code-review/SKILL.md

---
name: code-review
description: 当用户请求代码审查时激活
allowed-tools: read_file, grep, glob
---

## 代码审查专家

你是一位资深代码审查专家，专注于：
- 代码质量和可维护性
- 安全漏洞检测
- 性能优化建议
```

---

#### 2.4 GitCode 深度集成 - 全流程自动化

```
┌─────────────────────────────────────────────────────────────┐
│                    GitCode 工具集                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Issue 管理                                                 │
│  ├── gitcode_get_issue()      # 获取 Issue 详情            │
│  ├── gitcode_list_issues()    # 列出所有 Issue             │
│  └── gitcode_create_issue()   # 创建新 Issue               │
│                                                             │
│  PR 管理                                                    │
│  ├── gitcode_get_pr()         # 获取 PR 详情               │
│  ├── gitcode_list_prs()       # 列出所有 PR                │
│  ├── gitcode_create_pr()      # 创建新 PR                  │
│  └── gitcode_merge_pr()       # 合并 PR                    │
│                                                             │
│  分支管理                                                   │
│  ├── gitcode_list_branches()  # 列出分支                   │
│  └── gitcode_create_branch()  # 创建分支                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

#### 2.5 双模型路由 - 智能省钱

```
┌─────────────────────────────────────────────────────────────┐
│                    智能模型路由                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户请求 ──▶ 任务复杂度分析 ──┬──▶ 复杂任务 ──▶ 主模型   │
│                                 │     (40-50%)    Sonnet 4  │
│                                 │                           │
│                                 └──▶ 简单任务 ──▶ 小模型   │
│                                       (50-60%)    Haiku 3.5 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  💡 效果：相比单一模型方案，成本降低 70-80%                  │
└─────────────────────────────────────────────────────────────┘
```

| 任务类型 | 复杂度 | 使用模型 | 原因 |
|---------|--------|---------|------|
| 代码架构设计 | 高 | Sonnet 4 | 需要深度推理 |
| Bug 根因分析 | 高 | Sonnet 4 | 复杂逻辑推断 |
| 文件内容读取 | 低 | Haiku 3.5 | 简单信息提取 |
| 代码格式化 | 低 | Haiku 3.5 | 机械操作 |

---

#### 2.6 安全沙箱机制 - 生产级防护

```
┌─────────────────────────────────────────────────────────────┐
│                    多层安全防护                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🛡️ 第一层：命令黑名单                                      │
│  ├── Linux/macOS: rm -rf /, mkfs, dd if=/dev/zero          │
│  ├── Windows: format, del /s /q C:\, diskpart              │
│  └── 自动拦截危险命令                                       │
│                                                             │
│  🔒 第二层：路径限制                                        │
│  ├── Linux/macOS: /etc, /usr/bin, /boot                    │
│  ├── Windows: C:\Windows, C:\Program Files                 │
│  └── 防止误操作系统文件                                     │
│                                                             │
│  ⚠️ 第三层：用户确认                                        │
│  ├── 破坏性操作需要明确确认                                 │
│  └── 可配置确认级别                                         │
│                                                             │
│  📏 第四层：资源限制                                        │
│  ├── 单文件大小限制: 10MB                                   │
│  └── 命令执行超时: 可配置                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 功能演示

### 演示 1: BUILD 模式 - 一句话搞定开发

**输入**：
```
帮我分析并修复这个issue: https://gitcode.com/openJiuwen/agent-core/issues/77, 并创建一个修复的PR
```

**Agent 执行流程**：
```
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

---

### 演示 2: PLAN 模式 - 复杂任务规划

**输入**：
```
把 jiuwen-code 项目的 docs 目录部署到一个可公开访问的文档网站
```

**阶段 1: 进入 PLAN 模式并探索**
```
● enter_plan_mode()
  ⎿ 已进入 PLAN 模式

● glob(docs/**/*.md)
  ⎿ 找到文档文件...

● write_file(~/.jiuwen/plans/bright-calm-aurora.md)
  ⎿ 写入实现计划
```

**阶段 2: Plan 文件内容**
```markdown
# Implementation Plan

## Summary
使用 MkDocs + GitHub Pages 将项目文档部署为公开访问的静态网站

## Implementation Steps
1. 安装 mkdocs-material 依赖
2. 创建 mkdocs.yml 配置文件
3. 整理文档目录结构
4. 配置 GitHub Actions 自动部署
5. 推送并验证部署
```

**阶段 3: 请求审批（支持预授权）**
```
● exit_plan_mode(allowed_prompts=[
    {"tool": "Bash", "prompt": "install dependencies"},
    {"tool": "Bash", "prompt": "run mkdocs serve"},
    {"tool": "Bash", "prompt": "git operations"}
  ])

请审批此计划:
- 输入 'approve' 批准并切换到 BUILD 模式
```

**阶段 4: 用户审批后执行（预授权命令无需确认）**
```
[用户输入] approve

● bash(pip install mkdocs-material)  [预授权，无需确认]
● write_file(mkdocs.yml)
● bash(git add . && git commit && git push)  [预授权，无需确认]

✅ 部署完成！
   公开地址: https://snapek.github.io/openjiuwen-code
```

---

### 演示 3: REVIEW 模式 - 批量 PR 审查

**输入**：
```
/mode review
审查 openJiuwen/agent-core 仓库所有待合入的 PR，给出审查意见
```

**Agent 执行流程**：
```
● gitcode_list_prs(owner="openJiuwen", repo="agent-core", state="open")
  ⎿ 找到 3 个待审查 PR

● gitcode_get_pr(...) × 3
● web_fetch(...diff) × 3
```

**输出 - 审查汇总**：
```markdown
| PR | 标题 | 状态 | 建议 |
|----|------|------|------|
| #78 | fix: resolve KeyError | ✅ 可合入 | 建议补充测试 |
| #76 | feat: add retry mechanism | ⚠️ 需修改 | 添加配置和日志 |
| #75 | docs: update README | ✅ 可合入 | 无问题 |
```

---

### 演示 4: 子 Agent 并行 - 竞品调研

**输入**：
```
帮我调研 AI 编程助手领域的主要竞品：Cursor、GitHub Copilot、Windsurf，分析它们的核心功能、定价策略和技术特点，生成对比表格
```

**Agent 执行流程**：
```
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
│  [子Agent 1]  web_search → web_fetch → 分析中...           │
├─────────────────────────────────────────────────────────────┤
│  [子Agent 2]  web_search → web_fetch → 分析中...           │
├─────────────────────────────────────────────────────────────┤
│  [子Agent 3]  web_search → web_fetch → 分析中...           │
└─────────────────────────────────────────────────────────────┘

● 子Agent执行完成，汇总结果...
```

**输出 - 竞品对比表格**：
```markdown
| 功能 | Cursor | GitHub Copilot | Windsurf |
|------|--------|----------------|----------|
| 代码补全 | ✅ | ✅ | ✅ |
| 多文件编辑 | ✅ | ❌ | ✅ |
| 对话式编程 | ✅ | ✅ (Chat) | ✅ |
| 代码库理解 | ✅ | ⚠️ 有限 | ✅ |

📊 本报告由 3 个子Agent并行调研生成
⏱️ 总耗时: 45秒（单Agent串行需 2分钟+）
💰 成本: 子Agent使用小模型，节省 70% Token消耗
```

---

## 4. 核心优势总结

```
┌─────────────────────────────────────────────────────────────┐
│                    技术亮点快闪                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔨 三大模式        BUILD / PLAN / REVIEW，从想法到上线     │
│  🧩 Skill 插件      能力无限扩展，一键安装社区技能          │
│  🔗 GitCode 集成    Issue/PR/Branch 全流程自动化            │
│  👥 子Agent并行     上下文隔离，多任务同时执行              │
│  🌐 浏览器自动化    网页操作也能搞定                        │
│  💰 双模型路由      智能省钱，成本降 70%                    │
│  🌍 跨平台          Linux / macOS / Windows 通吃            │
│  🛡️ 安全沙箱        多层防护，生产级安全                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 与同类产品对比

| 特性 | OpenJiuwen Code | 传统 AI 编程助手 |
|------|-----------------|-----------------|
| **成本** | 降低 70-80% | 单一模型高成本 |
| **工作流** | BUILD/PLAN/REVIEW | 单一模式 |
| **扩展性** | Skills 插件系统 | 功能固定 |
| **并行能力** | 子Agent并行 | 串行执行 |
| **平台** | 跨平台 | 部分平台 |
| **安全性** | 多层防护 | 基础限制 |

---

## 5. 快速开始

### 安装

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/openjiuwen/code/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/openjiuwen/code/main/install.ps1 | iex

# 或手动安装
git clone https://gitcode.com/SnapeK/openjiuwen-code.git
cd openjiuwen-code
pip install -e .
```

### 配置

```bash
# 交互式配置（推荐）
jiuwen --config

# 或设置环境变量
export ANTHROPIC_API_KEY="sk-ant-xxx"
export GITCODE_ACCESS_TOKEN="xxx"
```

### 使用

```bash
# 启动 CLI
jiuwen

# 示例对话
> 帮我分析这个项目的架构
> 修复 src/utils.py 中的 bug
> /plan  # 切换到计划模式
> /review  # 切换到审查模式
> /skills list  # 查看可用 Skills
```

---

## 6. 技术栈

- **Agent 框架**: openJiuwen agent-core SDK
- **推理模式**: ReAct (Reasoning + Acting)
- **主模型**: Claude Sonnet 4 / GPT-4
- **辅助模型**: Claude Haiku 3.5 / GPT-3.5
- **CLI 框架**: prompt_toolkit + Rich
- **搜索引擎**: ripgrep (高性能代码搜索)
- **跨平台**: Python 3.11+

---

## 7. 项目信息

**项目地址**: https://gitcode.com/SnapeK/openjiuwen-code

**参赛信息**: openJiuwen Agent 编程大赛

---

> 🎉 **OpenJiuwen Code** - 让 AI 成为你的编程伙伴，而不只是工具。
