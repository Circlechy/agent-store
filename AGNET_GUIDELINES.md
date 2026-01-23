# Agent 指南

本文档概述了为 Agent Store 项目创建和贡献 agent 的指南和要求。

## 概述

Agent Store 是一个 AI agent 实现集合，可用作示例、模板或构建自定义 agent 的起点。`community` 文件夹中的所有 agent 必须遵循这些指南，以确保一致性、安全性和可维护性。

## 必需文件

### 1. Metadata.json

**`community` 文件夹中的每个 agent 项目必须在 agent 目录的根目录包含一个 `metadata.json` 文件**。此文件提供有关 agent 的基本信息，用于发现、分类和文档化。

#### 模板结构

您可以根据 agent 类型使用任一模板：

- **代码型 Agent**：`templates/coded-agents/metadata.json`
- **无代码 Agent**：`templates/no-code-agents/metadata.json`

#### 元数据架构

```json
{
  "schema_version": "1.0.0",
  "id": "your-agent-id",
  "version": "1.0.0",
  "updated_at": "2024-01-25T09:15:00Z",
  "description": "您的 agent 功能的简要描述",
  "author": {
    "name": "您的姓名",
    "email": "your.email@example.com",
    "github": "https://github.com/yourusername"
  },
  "licence": "Apache 2.0",
  "tags": ["tag1", "tag2"],
  "category": "category-name"
}
```

#### 字段说明

- **schema_version**：元数据架构的版本（当前为 "1.0.0"）
- **id**：agent 的唯一标识符（使用小写，空格用连字符，例如 "my-awesome-agent"）
- **version**：agent 的语义版本（例如 "1.0.0"、"2.1.3"）
- **updated_at**：最后更新的 ISO 8601 时间戳（例如 "2024-01-25T09:15:00Z"）
- **description**：agent 用途和功能的清晰、简洁描述
- **author**：包含作者信息的对象
  - **name**：您的全名或显示名称
  - **email**：联系邮箱（可选但推荐）
  - **github**：您的 GitHub 个人资料 URL
- **licence**：许可证类型（通常为 "Apache 2.0" 以匹配项目）
- **tags**：用于分类和搜索的相关标签数组
- **category**：主要类别（例如 "financial"、"code"、"research"、"automation"）

### 2. README.md

每个 agent 应包含一个全面的 README.md 文件，涵盖：

- **概述**：agent 的功能
- **特性**：核心功能
- **安装**：设置说明
- **配置**：如何配置 agent
- **使用**：示例和使用模式
- **依赖项**：所需的包和工具
- **API 密钥**：设置 API 密钥的说明（不暴露密钥）
- **示例**：代码示例或用例
- **贡献**：其他人如何为这个特定 agent 做出贡献

## 安全要求

### ⚠️ 重要：禁止敏感信息

**在您的 agent 提交中永远不要包含以下内容：**

- ❌ API 密钥
- ❌ 私有令牌
- ❌ 密码
- ❌ 密钥
- ❌ 身份验证凭据
- ❌ 个人访问令牌
- ❌ 包含凭据的数据库连接字符串
- ❌ OAuth 客户端密钥
- ❌ 任何其他敏感或私有信息

### 配置最佳实践

1. **使用环境变量**：将敏感配置存储在环境变量中
   ```python
   # ✅ 正确
   api_key = os.getenv("MY_API_KEY")
   
   # ❌ 错误
   api_key = "sk-1234567890abcdef"
   ```

2. **提供示例配置文件**：包含 `.env.example` 或 `config.example.yaml` 文件
   ```bash
   # .env.example
   MY_API_KEY=your_api_key_here
   DATABASE_URL=your_database_url_here
   ```

3. **使用 `.gitignore`**：确保排除敏感文件
   ```
   .env
   *.secrets.yaml
   config.local.*
   ```

4. **记录所需密钥**：在 README 中清楚列出所需的 API 密钥以及获取位置

## 项目结构

### 推荐的目录结构

```
your-agent-name/
├── metadata.json          # 必需：Agent 元数据
├── README.md              # 必需：Agent 文档
├── .gitignore             # 推荐：排除敏感文件
├── requirements.txt       # Python 依赖项（如适用）
├── pyproject.toml         # Python 项目配置（如适用）
├── package.json           # Node.js 依赖项（如适用）
├── .env.example           # 示例环境变量
├── config.example.yaml    # 示例配置（如适用）
├── src/                   # 源代码
│   ├── agents/            # Agent 实现
│   ├── tools/             # 工具和实用程序
│   └── utils/             # 辅助函数
├── tests/                 # 测试文件
└── docs/                  # 其他文档（可选）
```

## 代码质量标准

### 1. 代码风格

- 遵循特定语言的风格指南（Python 的 PEP 8、JavaScript 的 ESLint 等）
- 使用有意义的变量和函数名
- 为复杂逻辑添加注释
- 保持函数专注和模块化

### 2. 文档

- 为所有公共函数和类包含文档字符串
- 记录复杂算法和业务逻辑
- 在代码注释中提供使用示例（如适用）

### 3. 错误处理

- 实现适当的错误处理
- 提供有意义的错误消息
- 适当记录错误（不暴露敏感信息）

### 4. 测试

- 为核心功能包含单元测试
- 测试错误情况和边界条件
- 在 README 中记录如何运行测试

## 许可证要求

所有 agent 应在 **Apache 2.0** 下许可，以匹配项目许可证。如果您需要使用不同的许可证，请先与维护者讨论。

## 版本控制

- 使用[语义版本控制](https://semver.org/)（主版本号.次版本号.修订号）
- 发布新版本时更新 `metadata.json` 中的 `version` 字段
- 进行更改时更新 `updated_at` 时间戳

## 类别和标签

选择适当的类别和标签以帮助用户发现您的 agent：

### 常见类别
- `financial` - 金融分析、交易、投资
- `code` - 代码生成、分析、重构
- `research` - 研究辅助、信息收集
- `automation` - 任务自动化、工作流管理
- `data` - 数据分析、处理、可视化
- `communication` - 聊天、电子邮件、消息
- `productivity` - 任务管理、调度
- `education` - 学习、辅导、教育内容

### 标签指南
- 使用小写
- 多词标签使用连字符
- 具体但不过于细化
- 包含 3-7 个相关标签

## 提交清单

在提交 agent 之前，请确保：

- [ ] `metadata.json` 文件存在且有效
- [ ] `README.md` 全面且清晰
- [ ] 代码中没有 API 密钥、令牌或敏感信息
- [ ] 提供了 `.env.example` 或类似的配置文件
- [ ] `.gitignore` 排除了敏感文件
- [ ] 代码遵循风格指南
- [ ] 包含测试（如适用）
- [ ] 许可证为 Apache 2.0（或已批准的替代方案）
- [ ] 所有依赖项都已记录
- [ ] agent 功能正常且经过测试

## 获取帮助

如果您对这些指南有疑问：

1. 查看 `community` 文件夹中的现有 agent 作为示例
2. 查看 `templates` 文件夹中的模板
3. 在 GitHub 上提出问题以获取澄清
4. 联系维护者

## Agent 生命周期

### 活跃 Agent (community/)
- `community` 文件夹中的 agent 是积极维护的
- 应该功能正常且最新
- 鼓励定期更新

### 已归档 Agent (archived/)
- 不再积极维护的 agent 将移至 `archived/`
- 已归档的 agent 保留以供参考，但可能无法正常工作
- 用户仍可以访问已归档的 agent，但应期望有限的支持

---

**记住**：目标是创建高质量、安全且文档完善的 agent，供他人学习和使用。如有疑问，请优先考虑安全性和清晰度。
