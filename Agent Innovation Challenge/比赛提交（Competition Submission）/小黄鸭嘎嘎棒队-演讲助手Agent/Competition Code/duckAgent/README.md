# DuckAgent - 问答智能体

基于 openJiuwen 框架构建的简单问答智能体，可以配置不同的 LLM API 进行问答交互。

## 功能特性

- 🚀 简单易用的问答交互界面
- 🔧 支持配置不同的 LLM API
- 📋 完整的工作流配置示例
- 🔄 异步执行，支持并发请求

## 目录结构

```
duckAgent/
├── duck_agent.py  # 主程序文件
└── README.md                 # 说明文档
```

## 环境要求

- Python 3.11 或更高版本
- openjiuwen SDK

## 安装依赖

```bash
# 安装 openjiuwen SDK
pip install openjiuwen
```

## 配置 LLM API

### 方式一：环境变量配置

在运行程序前设置环境变量：

```bash
# Linux/Mac
export API_BASE="your_api_base"
export API_KEY="your_api_key"
export MODEL_PROVIDER="your_provider"  # 如 openai、siliconflow 等
export MODEL_NAME="your_model_name"     # 如 gpt-4o-mini、qwen-turbo 等
export LLM_SSL_VERIFY="false"           # 可选，是否验证 SSL 证书

# Windows (PowerShell)
$env:API_BASE="your_api_base"
$env:API_KEY="your_api_key"
$env:MODEL_PROVIDER="your_provider"
$env:MODEL_NAME="your_model_name"
$env:LLM_SSL_VERIFY="false"
```

### 方式二：直接修改代码

在 `duck_agent.py` 文件中修改 `load_config()` 函数的默认值：

```python
def load_config():
    return {
        "API_BASE": "your_api_base",
        "API_KEY": "your_api_key",
        "MODEL_PROVIDER": "your_provider",
        "MODEL_NAME": "your_model_name",
        "LLM_SSL_VERIFY": "false",
    }
```

## 运行程序

```bash
cd duckAgent
python duck_agent.py
```

## 使用示例

```
==================================================
DuckAgent - 问答智能体
==================================================
创建工作流: duck_qa_agent v1.0
创建智能体: duck_qa_agent v1.0.0

请输入您的问题 (输入 'exit' 退出): 什么是人工智能？

思考中...

回答: 人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。这些任务包括学习、推理、解决问题、感知、理解自然语言、识别物体和声音、做出决策等。

请输入您的问题 (输入 'exit' 退出): exit

感谢使用 DuckAgent，再见！
```

## 自定义配置

### 修改系统提示词

在 `create_llm_component()` 函数中修改 `SYSTEM_PROMPT`：

```python
SYSTEM_PROMPT = "你是一个专业的技术顾问，能够回答关于计算机科学的问题。请保持回答准确、详细。"
```

### 修改用户提示词模板

在 `create_llm_component()` 函数中修改 `USER_PROMPT`：

```python
USER_PROMPT = "用户问题：{{query}}\n\n请给出专业、详细的回答，包含具体的例子。"
```

## 技术细节

- **工作流组件**：
  - `Start`：开始组件，接收用户输入
  - `LLMComponent`：大模型组件，处理问答逻辑
  - `End`：结束组件，返回结果

- **执行流程**：
  用户输入 → Start → LLMComponent → End → 输出回答

## 注意事项

1. 请确保您的 LLM API 配置正确，否则会导致连接失败
2. 某些 LLM API 可能需要设置特定的 `MODEL_PROVIDER` 和 `MODEL_NAME`
3. 长时间运行可能会产生较多的 API 调用费用，请合理控制
4. 如果遇到 SSL 验证问题，可以尝试设置 `LLM_SSL_VERIFY="false"`

## 常见问题

### Q: 为什么程序运行时提示 API 连接失败？
A: 请检查您的 API_BASE、API_KEY、MODEL_PROVIDER 和 MODEL_NAME 配置是否正确。

### Q: 如何修改回答的风格？
A: 可以通过修改系统提示词 `SYSTEM_PROMPT` 来调整回答风格。

### Q: 支持哪些 LLM 提供商？
A: 支持 openai、siliconflow 等常见的 LLM 提供商，具体取决于 openjiuwen 的 ModelFactory 实现。

## 许可证

本项目基于 Apache-2.0 许可证授权。
