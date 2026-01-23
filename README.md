# Agent Store

一个精选的 AI agent 实现集合，包含示例和模板，用于构建智能 agent。

## 概述

Agent Store 是一个开源仓库，提供多样化的 AI agent 实现集合。无论您是在寻找示例、模板还是构建自己的 agent 的起点，此仓库都提供跨不同领域和用例的各种 agent。

## 📁 项目结构

```
agent-store/
├── community/          # 活跃的 agent 实现
│   ├── deepcode/      # 代码分析和研究 agent
│   ├── finsight-agent/ # 金融洞察 agent
│   └── vibe-agent/    # 基于 Vibe 的 agent
├── archived/          # 非活跃的 agent（保留以供参考）
├── templates/         # Agent 模板和元数据架构
│   ├── coded-agents/  # 基于代码的 agent 模板
│   └── no-code-agents/# 无代码 agent 模板
├── AGENT_GUIDELINES.md # 创建 agent 的指南
├── CONTRIBUTING.md    # 贡献指南
└── README.md          # 本文件
```

### Community vs Archived

- **`community/`**：包含积极维护的 agent，功能正常且最新
- **`archived/`**：包含不再积极维护但保留以供参考的 agent

## 🚀 快速开始

### 探索 Agent

1. **浏览可用 Agent**：查看 `community/` 文件夹中的可用 agent
2. **阅读 Agent 文档**：每个 agent 都包含一个带有设置和使用说明的 `README.md`
3. **检查元数据**：查看 `metadata.json` 以获取 agent 信息、标签和类别

### 使用 Agent

1. **导航到 Agent 目录**：
   ```bash
   cd community/your-agent-name
   ```

2. **阅读 README**：遵循 agent 特定的设置说明
   ```bash
   cat README.md
   ```

3. **安装依赖项**：遵循 agent 的安装指南
   ```bash
   # Python agent 示例
   pip install -r requirements.txt
   ```

4. **配置**：设置环境变量和配置
   ```bash
   # 复制示例配置
   cp .env.example .env
   # 使用您的 API 密钥编辑 .env
   ```

5. **运行 Agent**：遵循 README 中的使用说明

## 📋 可用 Agent

### 活跃 Agent (community/)

| Agent | 描述 | 类别 | 标签 |
|-------|------|------|------|
| [deepcode](community/deepcode/) | 具有多 agent 功能的代码分析和研究 agent | 代码 | code, research, analysis |
| [finsight-agent](community/finsight-agent/) | 金融洞察和分析 agent | 金融 | finance, analysis, trading |
| [vibe-agent](community/vibe-agent/) | 基于 Vibe 的 agent 实现 | 通用 | automation, workflow |

*注意：查看每个 agent 的 `metadata.json` 以获取完整信息*

## 🛠️ 要求

要求因 agent 而异。常见要求包括：

- **Python 3.8+**（适用于基于 Python 的 agent）
- **Node.js**（适用于 JavaScript/TypeScript agent）
- **API 密钥**（因 agent 而异 - 请参阅各个 README）
- **依赖项**（请参阅每个 agent 的 `requirements.txt` 或 `package.json`）

## 📖 文档

- **[Agent 指南](AGENT_GUIDELINES.md)**：创建和提交 agent 的全面指南
- **[贡献指南](CONTRIBUTING.md)**：如何为该项目做出贡献
- **Agent README**：每个 agent 在其目录中包含详细文档

## 🤝 贡献

我们欢迎贡献！无论您想要：

- 添加新 agent
- 改进现有 agent
- 修复错误
- 增强文档

请阅读我们的[贡献指南](CONTRIBUTING.md)和[Agent 指南](AGENT_GUIDELINES.md)以开始。

### 快速贡献步骤

1. Fork 仓库
2. 为您的贡献创建分支
3. 遵循 [Agent 指南](AGENT_GUIDELINES.md)
4. 提交拉取请求

## 📝 Agent 要求

`community/` 文件夹中的所有 agent 必须：

1. ✅ 包含有效的 `metadata.json` 文件（请参阅 `templates/` 中的示例）
2. ✅ 包含全面的 `README.md` 文档
3. ✅ **永远不要包含 API 密钥、令牌或敏感信息**
4. ✅ 提供示例配置文件（`.env.example` 等）
5. ✅ 遵循安全最佳实践
6. ✅ 在 Apache 2.0 下许可（或已批准的替代方案）

请参阅 [Agent 指南](AGENT_GUIDELINES.md) 以获取完整要求。

## 🔒 安全

**重要**：此仓库不接受：

- ❌ API 密钥或访问令牌
- ❌ 私有凭据或密码
- ❌ 密钥或身份验证令牌
- ❌ 任何其他敏感信息

所有 agent 必须使用环境变量或配置文件（提供示例）来处理敏感数据。有关详细信息，请参阅 [Agent 指南 - 安全要求](AGENT_GUIDELINES.md#security-requirements)。

## 📄 许可证

本项目根据 Apache License 2.0 许可 - 有关详细信息，请参阅 [LICENSE](LICENSE) 文件。

各个 agent 可以指定自己的许可证，但必须与项目许可证兼容。

## 🙏 致谢

感谢所有与社区分享其 agent 实现的贡献者！

## 📧 联系方式

- **Issues**：[GitCode Issues](https://gitcode.com/openJiuwen/agent-store/issues)
- **Discussions**：[GitCode Discussions](https://gitcode.com/openJiuwen/agent-store/discussions)
- **安全**：对于安全问题，请直接联系维护者

## 🌟 Star 历史

如果您觉得这个项目有用，请考虑给它一个 star！⭐

---

**祝您构建 Agent 愉快！** 🚀
