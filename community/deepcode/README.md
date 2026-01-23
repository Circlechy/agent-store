
### tolls的使用

#### 缺少的依赖：
 - anthropic
 - PyPDF2
 - mcp-agent
 - aiofiles

#### 核心Agent工具（MCP）：
 * bocha_search_server.py
     - 提供Bocha AI搜索功能，包括Web搜索和AI搜索
     - 输入：查询字符串、新鲜度参数、返回数量
     - 输出：搜索结果列表
     - 需要提供api key
 
 * code_implementation_server.py
     - 代码与文件核心操作
     - 输入：文件路径、代码字符串、Shell命令
     - 输出：文件内容、代码执行结果、搜索匹配项
 
 * code_reference_indexer.py
     - 代码库智能索引，搜索代码引用关系
     - 输入：索引文件路径、目标文件路径
     - 输出：相关代码片段、索引关系、实现思路
 
 * git_command.py
     - github仓库克隆和下载
     - 输入：github url或仓库标识符
     - 输出：本地存储路径
 
 * document_segmentation_server.py
     - 长文档智能处理
     - 输入：文档目录路径、查询类型、关键词
     - 输出：分割后的文本块、文档概览元数据
 
 * command_executor.py
     - 执行shell命令
     - 输入：shell命令，目标工作目录
     - 输出：命令执行结果
 
 * pdf_downloader.py
     - 从url下载pdf文件
     - 输入：url，本地存储路径，目标格式
     - 输出：下载后的文件实体、转换后的MD文本
 
#### 本地函数tools：
 * code_indexer.py
     - 索引构建逻辑，通过调用indexer.build_all_indexes()实现，并不会作为tools附加到LLM请求中
     - 输入：代码仓库路径
     - 输出：索引对象
 
 * pdf_utils.py
     - 读取pdf的标题、作者、页数等信息
     - 输入：pdf文件路径
     - 输出：pdf信息字典
 
 * pdf_converter.py
     - 将pdf文件转换为文本
     - 输入：pdf文件路径
     - 输出：生成的pdf文件
#### 第三方工具：
 * filesystem
     - 底层文件IO
     - 输入：文件路径、操作指令
     - 输出文件数据、目录列表
     - 需要node.js环境安装依赖
 
 * brave搜索服务器
     - 提供Brave搜索功能
     - 输入：查询字符串
     - 输出：搜索结果列表
     - 需要node.js环境安装依赖，设置api key
 
 * fetch服务器
     - 提供fetch功能
     - 输入：url
     - 输出：网页html/文本内容
     - 需要uv工具依赖

#### Windows环境运行需要额外的MCP服务器配置

使用Windows，需要在`mcp_agent.config.yaml`中手动配置MCP服务器:

```bash
# 1. 全局安装MCP服务器
npm i -g @modelcontextprotocol/server-brave-search
npm i -g @modelcontextprotocol/server-filesystem

# 2. 找到全局node_modules路径
npm -g root
```

然后更新`mcp_agent.config.yaml`，使用绝对路径:

```yaml
mcp:
  servers:
    brave:
      command: "node"
      args: ["C:/Program Files/nodejs/node_modules/@modelcontextprotocol/server-brave-search/dist/index.js"]
    filesystem:
      command: "node"
      args: ["C:/Program Files/nodejs/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js", "."]
```

> 将路径替换为步骤2中实际的全局node_modules路径。

#### 搜索服务器配置 (可选)

DeepCode支持多个搜索服务器进行Web搜索功能。可以在`mcp_agent.config.yaml`中配置您的首选选项:

```yaml
# 默认搜索服务器配置
# 选项: "brave" 或 "bocha-mcp"
default_search_server: "brave"
```

**可用选项:**
- **🔍 Brave搜索** (`"brave"`):
  - 具有高质量搜索结果的默认选项
  - 需要BRAVE_API_KEY配置
  - 推荐给大多数用户

- **🌐 Bocha-MCP** (`"bocha-mcp"`):
  - 替代搜索服务器选项
  - 需要BOCHA_API_KEY配置
  - 使用本地Python服务器实现

**在mcp_agent.config.yaml中的API密钥配置:**
```yaml
# 对于Brave搜索 (默认) - 第28行左右
brave:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  env:
    BRAVE_API_KEY: "your_brave_api_key_here"

# 对于Bocha-MCP (替代) - 第74行左右
bocha-mcp:
  command: "python"
  args: ["tools/bocha_search_server.py"]
  env:
    PYTHONPATH: "."
    BOCHA_API_KEY: "your_bocha_api_key_here"
```

> **💡 提示**: 两个搜索服务器都需要API密钥配置。

from [text](https://github.com/HKUDS/DeepCode)