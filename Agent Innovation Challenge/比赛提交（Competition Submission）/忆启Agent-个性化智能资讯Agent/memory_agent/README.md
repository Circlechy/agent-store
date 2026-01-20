# 个性化智能资讯Agent

## 【场景介绍】根据用户的个性化数据推送新闻和资讯

在信息爆炸的时代，每个人都面临着海量信息的困扰——每天产生的新闻和资讯远超个人阅读能力，如何从海量信息中快速筛选出真正对自己有价值的内容，已成为现代人的一大挑战。传统的新闻聚合平台虽然提供了基础的分类和推荐功能，但往往缺乏对个体用户深层次兴趣偏好的理解和记忆，导致推荐内容与用户实际需求存在偏差。

以一位关注AI技术发展的程序员为例，他希望获取最新的AI研究成果、编程工具更新和行业发展趋势，但不希望看到过多的娱乐八卦或体育新闻。传统的新闻推荐可能偶尔推送一些AI相关文章，但无法形成持续性的、基于用户长期兴趣的个性化服务。

本项目正是为解决这一"信息过载与个性化需求"矛盾而生：通过结合openJiuwen的MemoryEngine和WorkflowAgent，构建了一个具备长期记忆和即时反馈能力的个性化新闻简报生成系统。不同于传统的静态推荐算法，本系统能够持续学习和记忆用户的兴趣偏好，在用户反馈后自动更新用户画像，并基于这些记忆生成高度个性化的晨间简报，将"信息获取"从被动浏览升级为主动、智能、可定制的信息服务。

## 【方案介绍】基于长期记忆的个性化信息处理架构

### 【问题挑战：为什么传统方案在"个性化信息处理"上存在局限？】

在个性化新闻推荐中，最大的挑战不是"能不能获取新闻"，而是如何建立和维护一个准确、动态的用户兴趣模型，并在此基础上实现高质量的内容生成。

传统的推荐系统通常采用基于协同过滤或内容相似度的方法，这些方法存在明显的局限性：
1. **冷启动问题**：新用户没有历史行为数据，难以提供准确推荐
2. **记忆局限**：短期行为数据容易丢失重要偏好信息
3. **个性化深度不够**：只能处理表面特征，无法理解复杂的兴趣组合

### 【核心创新：利用MemoryEngine构建可持续的用户画像】

我们采用了基于openJiuwen MemoryEngine的记忆架构：将用户画像和偏好信息持久化存储，形成可扩展、可更新的长期记忆系统，让AI能够"记住"用户的个性化需求。

这种设计的核心优势在于**记忆与推理分离**：将稳定的用户偏好存储在MemoryEngine中，让大模型专注于内容分析和生成，既保证了记忆的持久性，又发挥了大模型的推理能力。

### 【方案设计｜四层个性化架构：用户画像 → 新闻获取 → 相关性打分 → 简报生成】

基于MemoryEngine和WorkflowAgent，我们实现了层次化的个性化处理流程：

**第一层：用户画像构建与管理**
系统通过MemoryEngine构建和维护用户画像，包括兴趣爱好、负面偏好、阅读习惯等多维度信息。
用户可以通过Web界面直观地编辑和更新自己的画像，系统会将这些信息持久化存储，形成长期记忆。

**第二层：智能新闻获取**
基于用户的长期画像，系统自动生成搜索关键词，从NewsData.io等API获取相关领域的最新新闻。
系统支持多语言新闻获取，并具备自动翻译功能，确保不同语言的优质内容都能被纳入考虑范围。

**第三层：个性化相关性打分**
获取新闻后，系统根据用户画像对每条新闻进行相关性打分，筛选出最符合用户兴趣的内容。
这一过程考虑了用户的正向偏好（如"关注AI技术"）和负向偏好（如"不看娱乐新闻"），实现精细化的内容筛选。

**第四层：个性化简报生成**
基于筛选后的高质量内容，系统生成结构化的晨间简报，格式为JSON数组，包含新闻类别、摘要和原始链接。
生成的简报既保持了信息的完整性，又符合用户的阅读偏好和风格要求。

### 【收益亮点】

- **长期记忆能力**：用户偏好被持久化存储，不会因会话结束而丢失，实现真正的个性化积累。
- **动态适应性**：系统能够根据用户反馈实时调整画像，不断优化推荐效果。
- **多模态支持**：支持多种新闻来源和语言，满足国际化需求。
- **可视化交互**：提供Streamlit Web界面，用户可以直观地管理画像、查看新闻和简报。
- **可扩展架构**：模块化设计便于集成更多数据源和服务功能。

## 功能特点

1. **长期记忆系统**：利用 MemoryEngine 构建 User Profile（用户画像），存储用户的长期兴趣和负面偏好
2. **数据相关性打分与清洗**：根据用户画像对原始数据进行相关性打分，筛选出最相关的信息
3. **个性化内容生成**：基于用户画像和筛选后的关键信息，生成结构化的晨间简报
4. **Web界面交互**：提供Streamlit Web界面，方便用户管理和查看个性化内容
5. **多语言支持**：支持多种语言新闻获取与翻译

## 环境准备

1. 确保已安装 Python 3.8+ 和 pip
2. 安装 openJiuwen SDK：
   ```bash
   pip install -U openjiuwen
   ```
3. 安装其他依赖：
   ```bash
   pip install flask streamlit pandas requests python-dotenv
   ```

## 配置设置

在 `.env` 文件或环境变量中设置以下参数：

```bash
# LLM API配置
API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key
MODEL_NAME=qwen-plus-latest
MODEL_PROVIDER=openai

# Embedding API配置
EMBED_API_BASE=https://api.siliconflow.cn/v1/embeddings
EMBED_MODEL_NAME=BAAI/bge-m3
EMBED_API_KEY=your_embed_api_key

# NewsData.io API配置
NEWSDATA_API_KEY=your_newsdada_api_key
```

## 运行步骤

1. 启动用户画像服务：
   ```bash
   python profile_service.py
   ```
   服务将在 `http://127.0.0.1:9000` 启动

2. 启动前端Web界面：
   ```bash
   streamlit run app.py
   ```
   Web界面将在 `http://localhost:8501` 启动

## 代码结构

### `memory_workflow_agent.py`
- 主要的 WorkflowAgent 实现文件
- 包含组件创建、工作流组装和测试逻辑
- 使用 MemoryEngine 管理用户画像
- 实现新闻获取与格式化功能
- 包含翻译功能和数据过滤功能

### `profile_service.py`
- Flask后端服务，提供用户画像管理API
- 提供 `/add_profile`、`/update_profile`、`/get_profile` 接口
- 提供 `/get_recent_news` 和 `/generate_news` 接口
- 集成 memory_workflow_agent 的功能

### `app.py`
- Streamlit前端界面
- 提供控制台视图和对话视图
- 实现用户画像编辑功能
- 实现新闻获取与展示功能
- 实现简报生成与展示功能
- 支持实时对话交互

## API 接口说明

### profile_service.py 提供的接口：

- `POST /add_profile`: 添加用户画像
  - 请求体: `{"user_id": "string", "message": "string"}`
  - 响应: `{"status": "success", "user_id": "string", "msg_id": "string"}`

- `POST /update_profile`: 更新用户画像
  - 请求体: `{"user_id": "string", "name": "string", "value": "string"}`
  - 响应: `{"status": "success", "user_id": "string"}`

- `GET /get_profile/<user_id>`: 获取用户画像
  - 响应: `{"user_id": "string", "profile": ["string"]}`

- `POST /get_recent_news/<user_id>`: 获取最新新闻
  - 请求体: `{"api_key": "string", "key_words": "string", "country": "string", "language": "string"}`
  - 响应: `{"user_id": "string", "raw_data": [...]}`

- `POST /generate_news/<user_id>`: 生成新闻简报
  - 请求体: `{"raw_data": [...]}`  
  - 响应: `{"user_id": "string", "news_list": "string"}`

## 组件说明

1. **用户画像更新工具**：调用外部 API 更新用户画像
2. **数据相关性打分组件**：根据用户画像对原始数据进行打分和筛选
3. **晨间简报生成组件**：基于筛选后的关键信息生成个性化简报
4. **新闻获取组件**：从 NewsData.io API 获取最新新闻

## 数据流程

1. 用户通过Web界面设置用户画像
2. 用户启动Agent获取新闻
3. 系统根据用户画像生成搜索关键词
4. 从新闻API获取相关新闻
5. 使用WorkflowAgent处理新闻数据，生成个性化简报
6. 在Web界面上展示简报内容
7. 用户可通过对话界面与系统交互
