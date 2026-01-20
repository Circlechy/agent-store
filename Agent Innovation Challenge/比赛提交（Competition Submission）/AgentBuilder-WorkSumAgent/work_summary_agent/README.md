# 工作总结管理系统

一个基于 openJiuwen 框架的智能工作总结系统，支持文字、文档、图片等多种输入方式，自动分析和整理工作内容。

## 项目结构

```
work_summary_agent/
├── backend/              # 后端核心模块
│   ├── __init__.py
│   ├── agent/            # Agent定义
│   │   ├── work_summary_workflow_agent.py  # WorkflowAgent包装器
│   │   └── custom_workflow_controller.py   # 自定义WorkflowController
│   ├── components/       # 自定义组件
│   │   ├── extractors/   # 提取器组件
│   │   │   ├── text_extractor.py          # 文本提取器
│   │   │   ├── document_extractor.py       # 文档提取器
│   │   │   ├── image_extractor.py         # 图片提取器（OCR/多模态）
│   │   │   └── text_merger.py             # 文本合并器（合并多种输入）
│   │   ├── analyzers/    # 分析器组件
│   │   │   └── content_analyzer_comp.py   # 内容分析器（基于LLM）
│   │   ├── storage/      # 存储组件
│   │   │   ├── record_saver.py            # 记录保存组件
│   │   │   └── record_query.py           # 记录查询组件
│   │   └── formatters/   # 格式化组件
│   │       ├── record_formatter.py        # 记录格式化组件
│   │       └── report_formatter.py        # 报告格式化组件
│   ├── workflows/        # 工作流定义
│   │   ├── record_input_workflow.py      # 内容录入工作流
│   │   └── report_generation_workflow.py # 报告生成工作流
│   ├── prompts/          # Prompt模板文件
│   │   ├── content_analyzer/             # 内容分析相关prompt
│   │   ├── report_generation/            # 报告生成相关prompt
│   │   ├── consolidation/                # 记录整合相关prompt
│   │   ├── multimodal/                   # 多模态模型相关prompt
│   │   └── prompt_loader.py              # Prompt加载工具
│   ├── work_summary_agent_adapter.py     # 适配器（向后兼容）
│   ├── input_processor.py                # 输入处理工具类
│   ├── screen_capture.py                 # 屏幕截图模块
│   └── TESTING.md                        # 测试文档
├── frontend/             # 前端Web界面
│   ├── index.html        # 前端页面
│   ├── server.py         # Flask后端服务器
│   ├── README.md         # 前端使用说明
│   ├── uploads/          # 上传文件存储目录
│   │   └── screenshots/  # 截图文件目录
│   └── logs/             # 前端日志目录
├── tests/                # 测试文件
│   ├── test_real_usage.py
│   ├── test_screenshot.py
│   ├── test_documents/   # 测试文档目录
│   └── test_images/      # 测试图片目录
├── work_records/         # 工作记录存储目录（按日期存储JSON文件）
├── logs/                 # 日志目录
├── README.md            # 本文件
└── requirements.txt      # Python依赖
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录（`work_summary_agent/`）创建 `.env` 文件：

```env
API_KEY=your_api_key
API_BASE=your_api_base  # 可选，默认为 https://api.modelarts-maas.com/openai/v1
MODEL_NAME=your_model_name  # 可选，默认为 deepseek-v3.2-exp
MULTIMODAL_MODEL=your_multimodal_model  # 可选，多模态视觉模型（用于图片理解），默认为 qwen3-vl-plus
LLM_SSL_VERIFY=false  # 可选，SSL验证设置
```

### 3. 启动服务

```bash
cd frontend && python server.py
```

访问 `http://localhost:5000`

## 功能特性

- **多种输入方式**：
  - 文字输入：直接输入工作内容
  - 文档上传：支持 PDF、Word、TXT、MD、JSON 等格式
  - 图片上传：支持 OCR 文字识别和多模态内容理解
  - 混合输入：支持同时输入文字、文档、图片，自动合并分析
- **智能内容分析**：基于 LLM 自动提取任务、工作内容、成果、问题、下一步计划
- **智能记录整合**：
  - 自动检测并合并相似记录（基于时间窗口和内容相似度）
  - 支持手动整合指定日期的记录（使用 LLM 分析）
- **记录管理**：
  - 增删改查操作
  - 按日期存储（JSON格式）
  - 支持单日和日期范围汇总
- **截图功能**：
  - 手动截图并自动分析
  - 自动定时截图（可配置间隔）
  - 截图队列处理，避免阻塞
- **报告生成**：基于 LLM 智能汇总，生成结构化工作总结报告

## 架构设计

本项目基于 **openjiuwen** 的 **WorkflowAgent** 架构，使用工作流编排实现模块化设计：

### 核心组件

1. **WorkSummaryWorkflowAgent**: WorkflowAgent 包装器，管理多个工作流
2. **record_input_workflow**: 内容录入工作流（处理文本/文档/图片输入）
3. **report_generation_workflow**: 报告生成工作流（生成工作总结报告）

### 工作流组件

- **提取器组件**: 
  - `TextExtractor`: 文本内容提取
  - `DocumentExtractor`: 文档内容提取（支持PDF/Word/TXT/MD/JSON）
  - `ImageExtractor`: 图片内容提取（支持OCR和多模态识别）
  - `TextMerger`: 文本合并器（合并多种输入源，支持混合输入）
- **分析器组件**: 
  - `ContentAnalyzer`: 内容分析器（基于LLM，提取任务、工作内容、成果、问题、下一步计划）
- **存储组件**: 
  - `RecordSaver`: 记录保存组件（支持自动合并相似记录）
  - `RecordQuery`: 记录查询组件（按日期范围查询）
- **格式化组件**: 
  - `RecordFormatter`: 记录格式化组件（格式化记录供LLM分析）
  - `ReportFormatter`: 报告格式化组件（格式化汇总报告）

### 向后兼容

通过 `WorkSummaryAgentAdapter` 保持与旧 API 的完全兼容，前端无需修改。

## 使用方式

### 命令行使用

```python
from backend.work_summary_agent_adapter import WorkSummaryAgentAdapter

agent = WorkSummaryAgentAdapter(image_processing_mode="multimodal")

# 添加记录
await agent.add_text_record("今天完成了项目需求分析...")
await agent.add_document_record("work_report.pdf", additional_text="附加说明")
await agent.add_image_record("screenshot.png")

# 截图功能
await agent.capture_and_analyze()  # 手动截图
agent.start_auto_screenshot(interval=5)  # 自动截图
agent.stop_auto_screenshot()

# 记录管理
agent.delete_work_record("2026-01-17", "2026-01-17T10:30:00Z")
agent.update_work_record("2026-01-17", "2026-01-17T10:30:00Z", {...})
agent.clear_day_records("2026-01-17")  # 清空指定日期的所有记录
await agent.consolidate_day_records("2026-01-17")  # 整合相似记录（使用LLM分析）

# 获取记录和汇总
records = agent.get_work_records("2026-01-17", "2026-01-19")
summary = await agent.summarize_day_records("2026-01-17", use_llm=True)
summary = await agent.summarize_date_range("2026-01-17", "2026-01-19")
```

### Web界面使用

1. 启动服务器：`cd frontend && python server.py`
2. 访问 `http://localhost:5000`
3. 输入内容、上传文件或使用截图功能
4. 查看、编辑、删除记录，生成报告

## 依赖

### 必需依赖

- `openjiuwen>=0.1.0` - 核心框架
- `flask>=2.3.0` - Web框架
- `flask-cors>=4.0.0` - 跨域支持
- `werkzeug>=2.3.0` - WSGI工具库
- `python-dotenv>=1.0.0` - 环境变量管理

### 可选依赖（按需安装）

- `paddlepaddle>=2.5.0` + `paddleocr>=2.7.0` - OCR功能（图片文字识别）
- `openai>=1.0.0` - 多模态模型支持（图片理解）
- `mss>=9.0.0` - 屏幕截图功能（跨平台）
- `Pillow>=10.0.0` - 图像处理

> 注意：如果不使用OCR功能，可以不安装 `paddlepaddle` 和 `paddleocr`；如果不使用多模态功能，可以不安装 `openai`；如果不使用截图功能，可以不安装 `mss`。

## 许可证

本项目基于 openJiuwen 框架开发。
