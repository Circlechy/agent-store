# LG2Jiuwen

> 版本：V2.1.0
> 更新日期：2026-02-10

## 1. 工具概述

LangGraph to openJiuwen Migration Tool - 是一款自动化迁移工具，用于将基于 LangGraph 框架开发的 Agent 代码迁移至 openJiuwen 框架。

**核心设计原则：规则优先，AI 兜底**
- 规则能处理的用规则（快速、确定、低成本）
- 规则无法处理的用 AI（语义理解、灵活）

**兼容性**：openJiuwen v0.1.4 / v0.1.5

## 2. 功能特性

### 2.1 核心功能

- 自动解析 LangGraph 源代码结构（状态、节点、边、工具等）
- 基于规则的代码转换（状态访问、LLM 调用、工具调用）
- 生成符合 openJiuwen 规范的多文件项目结构
- 自动提取源代码中的示例输入
- 支持单文件和多文件项目迁移
- 生成详细的迁移报告
- 智能依赖文件复制

### 2.2 V2.1.0 更新内容

#### 新特性
- **消息类型自动转换**：`AIMessage` → `AssistantMessage`，`HumanMessage` → `UserMessage`
- **工具参数智能转换**：LangGraph 字符串参数自动转换为 openJiuwen 字典参数
- **异步调用完整支持**：正确处理 `@tool` 装饰器返回的 `LocalFunction` 的 await 调用
- **LLM API 适配**：使用 openJiuwen v0.1.4+ 的 `model=` 参数格式

#### Bug 修复
- 修复路由函数中 `isinstance(msg, AIMessage)` 类型检查失败的问题
- 修复 `tool_map[key].invoke()` 未添加 await 导致的协程未执行问题
- 修复工具调用字符串参数导致的 `ValidationError` 问题
- 修复 `ChainCallRule` 错误匹配 subscript 模式的问题
- 修复 Start 组件 `inputs_schema` 为空的问题
- 修复重复 LLM 模型名变量定义的问题

### 2.3 典型场景

| 场景 | 说明 |
|------|------|
| 企业框架迁移 | 原有 LangGraph Agent 迁移至 openJiuwen 平台 |
| 多 Agent 批量迁移 | 命令行批量处理，提高迁移效率 |
| 生态工具转换 | 扩展 openJiuwen 生态工具的丰富性 |

## 3. 技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LG2Jiuwen 迁移工具                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  源代码 → AST → RuleExtractor → [AISemantic] → IR → CodeGenerator      │
│                     │                │           │           │          │
│                     ▼                ▼           ▼           ▼          │
│              ┌───────────┐    ┌───────────┐  ┌──────┐  ┌──────────┐    │
│              │ 转换规则   │    │ AI 处理   │  │ 中间 │  │ 代码生成 │    │
│              │ - 状态访问 │    │ (可选)    │  │ 表示 │  │ - 组件   │    │
│              │ - LLM调用  │    │           │  │      │  │ - 路由   │    │
│              │ - 工具调用 │    │           │  │      │  │ - 工作流 │    │
│              │ - 链式调用 │    │           │  │      │  │ - 工具   │    │
│              └───────────┘    └───────────┘  └──────┘  └──────────┘    │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                    openJiuwen Workflow 实现                              │
│                    CLI / Service API                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 项目结构

```
lg2jiuwen_tool/
├── __init__.py              # 模块入口
├── __main__.py              # 命令行入口
├── cli.py                   # CLI 实现
├── service.py               # 服务接口（主入口）
├── workflow/                # openJiuwen 工作流定义
│   ├── migration_workflow.py   # 主工作流
│   └── state.py                # 状态和数据模型
├── components/              # 工作流组件
│   ├── project_detector.py     # 项目检测（单/多文件）
│   ├── file_loader.py          # 文件加载
│   ├── ast_parser.py           # AST 解析
│   ├── rule_extractor.py       # 规则提取+转换（核心）
│   ├── pending_check.py        # 待处理检查
│   ├── ai_semantic.py          # AI 语义理解
│   ├── ir_builder.py           # IR 构建
│   ├── code_generator.py       # 代码生成（核心）
│   └── report.py               # 报告生成
├── rules/                   # 转换规则
│   ├── base.py                 # 规则基类
│   ├── state_rules.py          # 状态访问规则
│   ├── llm_rules.py            # LLM 调用规则
│   ├── tool_rules.py           # 工具调用规则
│   ├── chain_call_rules.py     # 链式调用规则
│   └── edge_rules.py           # 边/路由规则
└── ir/                      # 中间表示
    └── models.py               # IR 数据模型
```

### 3.3 核心模块

| 模块 | 目录/文件 | 职责 |
|------|----------|------|
| **Workflow** | `workflow/` | 定义迁移工作流和状态模型 |
| **Components** | `components/` | 各阶段处理组件 |
| **Rules** | `rules/` | 代码转换规则（状态、LLM、工具、链式调用） |
| **IR** | `ir/` | 中间表示数据模型 |
| **Service** | `service.py` | 对外服务接口 |

## 4. 迁移映射关系

### 4.1 结构映射

| LangGraph | openJiuwen |
|-----------|------------|
| `StateGraph` | `Workflow` |
| `TypedDict` State | `inputs_schema` 传递 |
| Node Function | `WorkflowComponent` |
| `add_edge()` | `add_connection()` |
| `add_conditional_edges()` | `add_conditional_connection()` + Router |
| `@tool` | `@tool()` + `Param` |
| `END` | `"end"` |
| `AIMessage` | `AssistantMessage` |
| `HumanMessage` | `UserMessage` |

### 4.2 代码转换映射

| LangGraph | openJiuwen |
|-----------|------------|
| `state["key"]` | `inputs["key"]` 或 `session.get_global_state("key")` |
| `state.get("key", default)` | `inputs.get("key", default)` |
| `state["key"] = val` | 收集到 `return {"key": val}` |
| `llm.invoke(msgs)` | `await self._llm.invoke(model=self.model_name, messages=msgs)` |
| `tool.invoke({"arg": val})` | `await tool.invoke(inputs={"arg": val})` |
| `tool_map[key].run(arg)` | `await invoke_tool(key, arg)` |
| `tool_map[key].invoke(arg)` | `await invoke_tool(key, arg)` |
| `return state` | `return {"key1": val1, ...}` |
| `return END` | `return "end"` |
| `isinstance(msg, AIMessage)` | `isinstance(msg, AssistantMessage)` |

### 4.3 路由函数转换

```python
# LangGraph
def should_continue(state):
    if state.get("is_end"):
        return END
    if state.get("loop_count", 0) >= 3:
        return END
    return "think"

# openJiuwen（自动生成）
def judge_router(session) -> str:
    # 上游组件输出 → 带节点前缀
    if session.get_global_state("judge.is_end"):
        return "end"
    # 全局状态 → 不带前缀
    if (session.get_global_state("loop_count") or 0) >= 3:
        return "end"
    return "think"
```

### 4.4 工具调用转换

```python
# LangGraph - 字符串参数
result = tool_map["Calculator"].invoke("100+200")

# openJiuwen - 自动转换为字典参数
result = await invoke_tool("Calculator", "100+200")
# invoke_tool 内部自动转换为 {"expression": "100+200"}
# 参数名从工具的 card.input_params 自动获取
```

### 4.5 消息类型转换

```python
# LangGraph
from langchain_core.messages import AIMessage
if isinstance(last_message, AIMessage):
    ...

# openJiuwen（自动生成）
from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
if isinstance(last_message, AssistantMessage):
    ...
```

## 5. 安装和使用

### 5.1 环境要求

- Python 3.9+
- openJiuwen >= 0.1.4

### 5.2 安装

```bash
# 克隆项目
git clone https://github.com/openjiuwen/lg2jiuwen.git

# 安装依赖
pip install -e .
```

### 5.3 命令行使用

```bash
# 迁移单个文件
python -m lg2jiuwen_tool my_agent.py -o ./output

# 迁移项目目录
python -m lg2jiuwen_tool ./my_project/ -o ./output

# 启用 AI 处理
python -m lg2jiuwen_tool my_agent.py -o ./output --use-ai

# 显示详细输出
python -m lg2jiuwen_tool my_agent.py -o ./output -v
```

### 5.4 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `source` | - | 源文件或目录路径 | (必需) |
| `--output` | `-o` | 输出目录 | `./output` |
| `--use-ai` | - | 启用 AI 处理 | `False` |
| `--no-report` | - | 不生成迁移报告 | `False` |
| `--no-comments` | - | 不保留原始注释 | `False` |
| `--verbose` | `-v` | 显示详细输出 | `False` |

### 5.5 编程接口

```python
from lg2jiuwen_tool import migrate_new, MigrationOptions

# 基本迁移
result = migrate_new(
    source_path="my_agent.py",
    output_dir="./output"
)

# 自定义选项
options = MigrationOptions(
    use_ai=True,
    preserve_comments=True,
    include_report=True
)
result = migrate_new("my_agent.py", "./output", options)

# 检查结果
if result.success:
    print("迁移成功！")
    print(f"规则处理: {result.rule_count} 项")
    print(f"AI 处理: {result.ai_count} 项")
    print("生成文件:", result.generated_files)
else:
    print("迁移失败:", result.errors)
```

## 6. 输出文件结构

迁移后生成的项目结构：

```
{agent_name}/
├── __init__.py           # 模块入口
├── config.py             # 配置（LLM、全局变量）
├── tools.py              # 工具函数 + invoke_tool 辅助函数
├── components/           # 组件目录
│   ├── __init__.py
│   └── {node}_comp.py    # 每个节点一个组件
├── routers.py            # 路由函数
├── workflow.py           # 工作流构建
└── main.py               # 主入口（含示例输入）
```

## 7. 支持的 LangGraph 特性

### 7.1 已支持

- [x] `StateGraph` 状态图定义
- [x] `TypedDict` 状态类
- [x] `add_node()` 节点添加（含单参数形式）
- [x] `add_edge()` 普通边
- [x] `add_conditional_edges()` 条件边
- [x] `set_entry_point()` 入口点
- [x] `@tool` 工具装饰器
- [x] `ChatOpenAI` 等 LLM 初始化
- [x] `tool_map[key].run()` / `tool_map[key].invoke()` 工具映射调用
- [x] 示例输入自动提取
- [x] 类实例作为节点函数
- [x] 跨文件函数引用解析
- [x] LangGraph 预构建组件（ToolNode 等）
- [x] `AIMessage` / `HumanMessage` 消息类型
- [x] `Configuration.from_runnable_config()` 配置模式

### 7.2 待支持

- [ ] 子图 (Subgraph)
- [ ] 并行节点
- [ ] Checkpointer 持久化
- [ ] 动态节点添加
- [ ] 流式输出 (Streaming)

## 8. 测试验证

### 8.1 多文件迁移 Agent（V1.0）

源目录 `example/langgraph/`，迁移后 `example/openjiuwen/`，生成多文件项目结构。

| Agent | 节点数 | 工具数 | 功能验证 | 状态 |
|-------|--------|--------|----------|------|
| LangGraphTinyAgent | 1 | 0 | 基础工作流执行、Configuration 兼容 | ✅ 通过 |
| react-agent | 2 | 0 | LLM 对话、消息类型转换 | ✅ 通过 |
| react_agent_V1.0 | 3 | 2 | ReAct 循环、Calculator/Weather 工具调用 | ✅ 通过 |

### 8.2 单文件迁移 Agent（V2.0）

源目录 `example/langgraph/`（单文件 LangGraph Agent），迁移后 `example/openjiuwen_V2.0/`，生成多文件项目结构。已通过全量 E2E 测试，迁移后直接运行成功。

| Agent | 领域 | 节点数 | 功能验证 | 耗时 | 状态 |
|-------|------|--------|----------|------|------|
| CookingAssistant | 烹饪助手 | 5 | 需求解析→菜品推荐→菜谱生成→烹饪技巧→格式化输出 | 141s | ✅ 通过 |
| FirstAidAssistant | 急救指导 | 5 | 伤情评估→紧急处理→详细指南→后续护理→格式化输出 | 81s | ✅ 通过 |
| InfoGap (Policy) | 政策解读 | 5 | 要点提取→政策解读→影响分析→机会挖掘→格式化输出 | 77s | ✅ 通过 |
| PostgraduateSchoolRec | 考研推荐 | 5 | 学生画像→院校匹配→对比分析→备考规划→格式化输出 | 123s | ✅ 通过 |
| RecRestaurant | 餐厅推荐 | 5 | 需求解析→餐厅推荐→详情获取→排名评分→格式化输出 | 125s | ✅ 通过 |
| Film-Rec | 电影推荐 | 5 | 偏好分析→候选推荐→信息丰富→排名评分→格式化输出 | 63s | ✅ 通过 |
| Idea | 创意生成 | 4 | 头脑风暴→创意评估→创意精炼→格式化输出 | 56s | ✅ 通过 |
| Short-Trip | 短途旅行 | 5 | 需求解析→目的地推荐→行程规划→预算方案→格式化输出 | 100s | ✅ 通过 |


## 9. 常见问题

### Q: 迁移后代码报错 `NameError`

检查变量是否在所有代码路径中都有定义。工具会自动初始化返回变量为 `None`，但复杂逻辑可能需要手动调整。

### Q: LLM 调用失败

确认：
1. API Key 和 API Base 配置正确（通过环境变量或 config.py）
2. 网络可访问 LLM 服务
3. 模型名称正确（使用 `MODEL_NAME` 环境变量）

### Q: 条件路由不生效

检查路由函数中的状态访问路径：
- 上游组件输出：`session.get_global_state("node.field")` 带前缀
- 全局状态：`session.get_global_state("field")` 不带前缀

### Q: 工具调用报错 `ValidationError`

openJiuwen 工具需要字典参数。迁移工具会自动处理：
- `invoke_tool` 辅助函数自动将字符串参数转换为字典
- 从工具的 `card.input_params` 获取正确的参数名

### Q: 消息类型不匹配 `Expected AIMessage but got AssistantMessage`

V2.1.0 已自动处理此问题：
- 将 `AIMessage` 替换为 `AssistantMessage`
- 将 `HumanMessage` 替换为 `UserMessage`
- 更新相应的 import 语句为 `from openjiuwen.core.foundation.llm.schema.message import ...`

### Q: 协程未执行 `coroutine was never awaited`

V2.1.0 已修复此问题：
- `tool_map[key].invoke()` 自动转换为 `await invoke_tool(key, arg)`
- 所有工具调用都正确添加 await

## 10. 相关链接

- [openJiuwen 文档](https://docs.openjiuwen.com)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [问题反馈](https://github.com/openjiuwen/lg2jiuwen/issues)
