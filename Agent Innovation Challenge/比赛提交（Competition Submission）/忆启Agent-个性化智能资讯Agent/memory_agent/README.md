# 记忆型 WorkflowAgent 示例

本示例基于 openJiuwen Core 构建了一个具备"长期记忆"与"即时反馈闭环"的 WorkflowAgent，用于生成个性化的晨间简报。

## 功能特点

1. **长期记忆系统**：利用 MemoryEngine 构建 User Profile（用户画像），存储用户的长期兴趣和负面偏好
2. **数据相关性打分与清洗**：根据用户画像对原始数据进行相关性打分，筛选出最相关的信息
3. **个性化内容生成**：基于用户画像和筛选后的关键信息，生成结构化的晨间简报
4. **反馈修正机制**：支持用户反馈（如"太长了"或"不要推这方向"），自动更新用户画像

## 工作流程

```
用户查询 → 意图识别 → （若有反馈则更新用户画像）→ 数据相关性打分 → 关键信息提取 → 晨间简报生成 → 结果返回
```

## 环境准备

1. 确保已安装 Python 3.8+ 和 pip
2. 安装 openJiuwen SDK：
   ```bash
   pip install -U openjiuwen
   ```
3. 安装其他依赖：
   ```bash
   pip install flask
   ```

## 配置设置

在 `memory_workflow_agent.py` 文件中设置 LLM API 的相关参数：

```python
API_BASE = os.getenv("API_BASE", "your api base")
API_KEY = os.getenv("API_KEY", "your api key")
MODEL_NAME = os.getenv("MODEL_NAME", "your model name")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "your model provider")
```

## 运行步骤

1. 启动用户画像服务：
   ```bash
   python profile_service.py
   ```
   服务将在 `http://localhost:9000` 启动

2. 运行记忆型 WorkflowAgent 示例：
   ```bash
   python memory_workflow_agent.py
   ```

## 代码结构

### `memory_workflow_agent.py`
- 主要的 WorkflowAgent 实现文件
- 包含组件创建、工作流组装和测试逻辑
- 使用 MemoryEngine 管理用户画像

### `profile_service.py`
- 简单的 Flask 服务，用于模拟用户画像更新 API
- 提供 `/update_profile` 和 `/get_profile` 接口

## 组件说明

1. **意图识别组件**：检测用户反馈意图（如"太长了"或"不要推这方向"）
2. **用户画像更新工具**：调用外部 API 更新用户画像
3. **数据相关性打分组件**：根据用户画像对原始数据进行打分和筛选
4. **晨间简报生成组件**：基于筛选后的关键信息生成个性化简报

## 测试数据

示例中使用了模拟的原始数据，包括科技新闻、娱乐八卦、环保新闻等，用于演示数据筛选和个性化生成功能。

## 扩展建议

1. 集成真实的新闻数据源（如 RSS 订阅或新闻 API）
2. 优化用户画像的存储和更新机制，支持更复杂的用户偏好
3. 添加更多的反馈类型和处理逻辑
4. 实现更丰富的简报格式和内容类型

## 注意事项

- 本示例使用了内存存储的 MemoryEngine，实际应用中建议使用持久化存储
- 确保 LLM API 的连接和权限设置正确
- 可根据实际需求调整数据筛选的阈值和简报生成的格式