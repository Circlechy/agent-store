---
name: workflow-generation-skill
description: 基于 openJiuwen 框架生成 Workflow 工作流代码。使用场景：需要预定义的多步骤任务流程、组件化编排、确定性执行流程的场景。生成包含 config.py、components.py、workflow_builder.py、main.py 等文件。
---

# Workflow 生成技能

## 概述

Workflow 模式是 openJiuwen 框架提供的预定义多步骤任务流程，通过组件的顺序执行来完成复杂任务。

## 核心特点

- **流程确定性**：步骤顺序和逻辑预先定义
- **组件化**：每个步骤是独立的组件（WorkflowComponent）
- **可复用**：组件可以在不同工作流中复用
- **易于调试**：流程清晰，便于定位问题

## 必需文件

1. **config.py** - 模型配置
2. **components.py** - 组件定义
3. **workflow_builder.py** - 工作流构建器
4. **main.py** - 入口文件

## 生成要求

### 1. config.py

根据 prompts 规则，config.py 必须包含：
- 环境变量配置（API_BASE, API_KEY, MODEL_NAME, MODEL_PROVIDER）
- SSL 验证设置：`os.environ["LLM_SSL_VERIFY"] = "False"`
- SSRF 保护设置：`os.environ["SSRF_PROTECT_ENABLED"] = "False"`
- `create_llm_client()` 函数（main.py 会使用）
- `create_model_config()` 函数（components.py 会使用）
- `create_workflow_config()` 函数（workflow_builder.py 会使用）
- Agent 配置常量（AGENT_ID, AGENT_VERSION, AGENT_DESCRIPTION）

**详细规则**：参考 `references/config-generation.md`

### 2. components.py

根据 prompts 规则，components.py 包含所有组件创建函数：
- Start 组件：固定格式
- LLMComponent：`response_format` 必须使用 `{"type": "json"}`
- QuestionerComponent：支持两种模式（智能提取模式、调查模式）
- IntentDetectionComponent、ToolComponent、CodeComponent、BranchComponent 等

**重要规则**（根据 prompts）：
- import 语句必须全部集中在文件开头
- 所有组件创建函数必须有完整的实现

**详细规则**：参考 `references/component-generation.md`

### 3. workflow_builder.py

根据 prompts 规则，workflow_builder.py 必须包含三个函数：
- `build_workflow()` - 组装和连接工作流组件
- `create_workflow_schema()` - 创建工作流 Schema
- `build_workflow_agent()` - 构建 WorkflowAgent 实例

**关键规则**（根据 prompts）：
- Start 组件的 inputs_schema 必须使用 `"${query}"`，不是 `"${start.query}"`
- IntentDetectionComponent 必须使用 `add_branch()`，禁止使用 `add_connection()`
- BranchComponent 必须实现 else 分支（使用 `"True"` 作为表达式）
- 所有组件必须先注册，再连接

**详细规则**：参考 `references/workflow-builder-generation.md`

### 4. main.py

根据 prompts 规则，main.py 必须包含：
- 环境变量设置：`os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = "300"`（必须在文件开头）
- `create_llm_client()` 创建 llm_client（用于人机交互处理）
- `run_test()` 函数：**必须包含人机交互处理逻辑**（当工作流中有提问器组件时）
- `main()` 函数：运行所有测试用例

**关键规则**（根据 prompts）：
- 使用 `build_workflow_agent()` 构建 Agent，不是 `build_workflow()`
- 使用 `workflow_agent.invoke()` 调用，不需要传入 runtime 参数
- 必须处理人机交互流程（使用 `InteractiveInput` 和 `llm_client`）

**详细规则**：参考 `references/main-generation.md`

## 关键约束

1. **必须使用 openJiuwen 的 Workflow 类**，不要自定义 Workflow 实现
2. **组件必须实现 ComponentExecutable 接口**
3. **使用 WorkflowConfig 和 WorkflowMetadata 配置工作流**
4. **使用 Start 和 End 组件作为入口和出口**

## 参考文档

详见 `references/` 目录下的文档。
