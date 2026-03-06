<h1 align="center" style="margin: 0 0 4px; padding:0; line-height:1.1; color: #8edb70ff;">
  ShadowWork「在忙呢」工作记录助手
</h1>

<p align="center" style="margin-top: 0;">
  <b> 💼 职场工作记录智能助手，低干扰融入工作流，自动完成工作记录、整理与复盘 </b>
</p>

<p align="center">
  <a href="#-项目简介">项目简介</a> •
  <a href="#-核心能力">核心能力</a> •
  <a href="#-使用方式">使用方式</a> •
  <a href="#-架构详解">架构详解</a> •
  <a href="#-快速上手">快速上手</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11.4-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/framework-OpenJiuwen-orange.svg" alt="OpenJiuwen">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License">
</p>

---

## 📖 项目简介

**项目地址**：https://gitcode.com/miaoran_li/ShadowWork

**ShadowWork（「在忙呢」工作记录助手）** 是一款专为职场人打造的低干扰工作记录智能Agent，基于 openJiuwen WorkflowAgent 工作流智能体模式开发，核心解决职场中**工作信息碎片化、记录繁琐、复盘无据可依**的核心痛点。

ShadowWork通过**后台静默运行 + 多模态输入 + 智能结构化整理**，自动保留工作过程、提取待办事项、生成复盘报告，让你专注核心工作产出，从此告别手动整理的低效。

---

## 🚀 核心能力

### 1. 低干扰工作记录
开启自动截图功能后，系统在后台按设定频率捕获屏幕状态，智能识别当前工作内容并生成结构化记录，无需刻意中断工作流程录入信息，彻底解决「忘记记录工作内容」的职场痛点。

### 2. 多模态信息整合
完美适配职场全场景信息形式，文字速记、文档上传、截图识别可自由组合使用，系统自动合并分析所有输入源，生成完整、统一的工作记录，告别信息散落在不同工具的管理难题。

### 3. 记录-待办一体化
从各类工作记录中**智能提取待办事项**，支持为待办设置截止日期、追踪推进进度，同时自动合并相似待办项，保持待办清单简洁、可操作，避免重复管理。

### 4. 智能复盘报告生成
无需手动拼凑碎片化信息，仅需选择时间范围，AI 自动调取该时段所有工作记录，分析任务完成情况与工作成果，生成结构化 Markdown 格式报告，可直接用于复盘、汇报，大幅提升工作效率。

---

## 🔧 使用方式

- **Web 可视化操作**：通过图形界面完成记录录入、待办管理、报告生成等全流程操作
- **多模态内容上传**：手动上传文本、图片、PDF/Word/MD 等文档，系统自动解析
- **自动截图记录**：后台静默运行，按设定频率自动截屏并分析工作内容
- **记录精细化管理**：查看、编辑、删除、整合任意时间段的工作记录
- **一键生成报告**：选择日期范围即可生成标准化复盘、周报或月报

---

## 🏗️ 架构详解

### 分层模块化架构
ShadowWork 采用分层模块化架构设计，基于 openJiuwen WorkflowAgent 与 Component 系统搭建，保障系统的稳定性、扩展性与可维护性，六层架构职责清晰、解耦设计：
```
## ShadowWork 架构

  📱 用户交互层
    ├── Web 界面
    └──命令行接口

  🤖 Agent 协调层
    ├── WorkSummaryAgent（统一接口）
    ├── WorkflowEngine（工作流引擎）
    └── WorkRecordManager（记录管理器）

  🔄 工作流编排层（基于 openJiuwen WorkflowAgent）
    ├── record_input_workflow（内容录入工作流）
    └── report_generation_workflow（报告生成工作流）

  🧩 组件层（基于 openJiuwen Component）
    ├── 提取器组件（Text/Document/Image Extractor）
    ├── 分析器组件（Work Understanding/Action Extraction）
    ├── 缓冲组件（Screenshot Buffer/Granularity Control）
    ├── 存储组件（Record Saver/Todo Storage）
    └── 格式化组件（Record/Report Formatter）

  🧠 LLM 推理层（基于 openJiuwen LLMComponent）
    ├── 工作内容理解
    ├── 行动提取
    └── 报告生成

  💾 存储层
    ├── 工作记录存储（按日期存储 JSON 文件）
    └── 待办事项存储（JSON 文件）
```

### ShadowWork 核心工作流
- 用户输入/系统截屏 → `record_input_workflow` 处理（多模态提取→内容理解→结构化存储）
- 复盘请求 → `report_generation_workflow` 处理（调取记录→分析汇总→格式化生成报告）
- 待办管理 → 从结构化记录中提取行动项→存储→支持增删改查/进度追踪


### 项目结构

```
ShadowWork/
├── backend/              # 后端核心模块
│   ├── agent/            # Agent定义
│   ├── components/       # 自定义组件
│   │   ├── extractors/   # 提取器组件
│   │   ├── analyzers/    # 分析器组件
│   │   ├── buffer/        # 缓冲组件
│   │   ├── storage/      # 存储组件
│   │   └── formatters/   # 格式化组件
│   ├── workflows/        # 工作流定义
│   ├── prompts/          # Prompt模板文件
│   └── utils/            # 工具模块
├── frontend/             # 前端Web界面
│   ├── static/           # 静态资源目录
│   └── uploads/          # 上传文件存储目录
├── analysis_results/    # 分析结果存储目录（默认）
│   ├── work_records/     # 工作记录存储目录
│   └── todos/            # 待办事项存储目录
└── docs/                 # 文档目录
    └── images/           # 示例图片
```
---
## 🚀 快速上手

### 环境要求
- Python 3.11.4
- openjiuwen v0.1.2
- 可访问大模型 API（或本地部署兼容模型）

### 1. Web界面使用

启动服务:
```bash
cd frontend && python server.py
```
启动服务后，访问 `http://localhost:5000` 即可使用 Web 界面：

- 输入内容、上传文件或使用截图功能
- 查看、编辑、删除记录
- 管理待办事项
- 生成工作报告

### 2. 命令行使用
> **注意**：运行前需在项目根目录创建 `.env` 文件并配置环境变量（API_KEY/API_BASE 等），`WorkSummaryAgent` 会自动加载该文件。

```python
import asyncio
from backend.work_summary_agent import WorkSummaryAgent

async def main():
    # 初始化Agent（会自动加载.env文件中的环境变量）
    agent = WorkSummaryAgent(image_processing_mode="multimodal")
    
    # 添加记录（默认使用当前日期）
    await agent.add_text_record("今天完成了项目需求分析...")
    await agent.add_document_record("work_report.pdf", additional_text="附加说明")
    await agent.add_image_record("screenshot.png")
    
    # 指定日期添加记录（日期格式：YYYY-MM-DD）
    await agent.add_text_record("完成了代码重构工作", date="2026-01-17")
    await agent.add_document_record("work_report.pdf", date="2026-01-17", additional_text="附加说明")
    await agent.add_image_record("screenshot.png", date="2026-01-17")
    await agent.capture_and_analyze(date="2026-01-17")  # 截图并保存到指定日期
    
    # 截图功能
    await agent.capture_and_analyze()  # 手动截图
    agent.start_auto_screenshot(interval=5)  # 自动截图
    agent.stop_auto_screenshot()
    
    # 记录管理
    agent.delete_work_record("2026-01-17", "2026-01-17T10:30:00Z")
    # 更新记录（content 为字典格式，包含 tasks, work_content, achievements 等字段）
    agent.update_work_record("2026-01-17", "2026-01-17T10:30:00Z", {
        "tasks": ["任务1", "任务2"],
        "work_content": "工作内容",
        "achievements": "成果",
        "problems": "问题",
        "next_steps": "下一步计划"
    })
    agent.clear_day_records("2026-01-17")  # 清空指定日期的所有记录
    await agent.consolidate_day_records("2026-01-17")  # 整合相似记录（使用LLM分析）
    
    # 获取记录和汇总
    records = agent.get_work_records("2026-01-17", "2026-01-19")
    summary = await agent.summarize_day_records("2026-01-17", use_llm=True)
    summary = await agent.summarize_date_range("2026-01-17", "2026-01-19")
    
    # 待办事项管理（通过 agent 直接操作）
    # 添加待办事项（支持字符串或字典格式）
    agent.add_todos(["完成项目文档", "准备会议材料"], source="manual")
    agent.add_todos([
        {
            "text": "代码审查",
            "deadline": "2026-01-20 18:00",
            "progress": "进行中"
        },
        {
            "text": "部署新版本",
            "deadline": "2026-01-21 12:00"
        }
    ], source="manual", source_date="2026-01-17")
    
    # 获取待办事项
    todos = agent.get_todos(include_completed=False)  # 只获取未完成的
    all_todos = agent.get_todos(include_completed=True)  # 获取所有待办事项（包括已完成的）
    
    # 更新待办事项（需要待办事项的ID）
    if todos:
        first_todo_id = todos[0].get("id")
        agent.update_todo(first_todo_id, text="更新后的待办事项", progress="已完成")
        agent.complete_todo(first_todo_id)  # 标记为完成
        # agent.delete_todo(first_todo_id)  # 删除待办事项
    
    # agent.clear_completed_todos()  # 清除所有已完成的待办事项

if __name__ == "__main__":
    asyncio.run(main())
```
