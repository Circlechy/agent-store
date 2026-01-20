import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, theme, FloatButton } from 'antd';
import { ArrowUpOutlined } from '@ant-design/icons';

const markdownContent = `
# 产品架构设计方案

## 1. 系统概览

本系统是一个基于语义检索的智能图片管理平台，采用前后端分离架构。前端基于 React 构建现代化 SPA 应用，后端基于 FastAPI 提供高性能 API 服务，结合 Qwen2-VL 多模态大模型和 Qdrant 向量数据库，实现以图搜图、语义搜索等核心功能。

## 2. 前端架构 (Frontend)

### 2.1 核心技术栈详解
- **React 18**: 利用并发渲染特性（Concurrent Rendering）和自动批处理（Automatic Batching），显著提升复杂交互下的页面响应速度。使用 Hooks（如 \`useMemo\`, \`useCallback\`）进行精细化的性能调优。
- **TypeScript**: 全项目采用严格模式（Strict Mode），通过静态类型检查确保组件 Props 和 API 响应数据的类型安全，大幅降低运行时错误。
- **Ant Design 5.x**: 基于 Design Token 的 CSS-in-JS 动态主题系统，实现了深色/浅色模式的毫秒级无缝切换，并提供了一套高质量的无障碍（Accessibility）组件。
- **Zustand**: 采用原子化状态管理方案，替代 Redux。支持状态持久化（Persist Middleware），确保用户刷新页面后 Session 和主题设置不丢失。
- **Vite**: 基于 ES Modules 的极速开发服务器，支持热模块替换（HMR），构建速度比 Webpack 快 10-100 倍。

### 2.2 核心模块
- **Layout**: 响应式侧边栏布局，支持深色模式切换。
- **Pages**:
  - \`HomePage\`: 搜索入口，展示随机提示词。
  - \`ChatPage\`: 智能对话界面，集成 AI Agent 交互。
  - \`GalleryPage\`: 图片瀑布流展示，支持无限滚动。
  - \`UploadPage\`: 图片上传，支持拖拽和批量上传。
- **Store**:
  - \`chatStore\`: 管理对话历史、会话状态。
  - \`themeStore\`: 管理主题模式（亮/暗）。

### 2.3 数据流设计
用户交互 -> 组件触发 Action -> Store 更新状态 / API 调用 -> 后端响应 -> Store 更新 -> UI 重新渲染。

## 3. 后端架构 (Backend)

### 3.1 核心服务技术详解
- **FastAPI**: 基于 Starlette 和 Pydantic 的高性能 Web 框架。完全支持异步编程（Async/Await），内置 OpenAPI（Swagger）文档自动生成，自动处理请求参数校验。
- **Qwen2-VL (多模态大模型)**: 
  - 核心能力：能够同时理解文本和图像输入的视觉语言模型。
  - 应用场景：用于生成图片的高维语义向量（Embedding），以及理解用户的复杂自然语言查询意图。
- **Qdrant (向量数据库)**:
  - 存储引擎：专为向量搜索优化的数据库，支持 HNSW（Hierarchical Navigable Small World）算法，实现亿级数据的毫秒级检索。
  - 混合检索：支持 Vector Search（语义相似度）与 Payload Filter（元数据过滤）的组合查询。
- **Pydantic**: 强大的数据验证库，确保进入系统的数据符合预定义的 Schema，自动处理类型转换和错误提示。
- **Uvicorn**: 基于 uvloop 的高性能 ASGI 服务器，作为 FastAPI 的生产级运行容器。

### 3.2 业务分层架构
- **Routers (API 层)**: 处理 HTTP 请求，参数校验 (\`app/routers\`).
- **Services (业务层)**: 核心业务逻辑封装 (\`app/services\`).
  - \`EmbeddingService\`: 调用本地模型生成向量。
  - \`VectorDBService\`: 封装 Qdrant 数据库操作。
  - \`StorageService\`: 管理本地文件存储。
  - \`SearchService\`: 整合搜索逻辑（文本/图片/混合）。
  - \`AgentService\`: 处理自然语言意图识别与对话。
- **Models (数据层)**: Pydantic 数据模型定义 (\`app/models\`).

### 3.2 核心组件交互
1.  **上传流程**: API -> StorageService (保存文件) -> EmbeddingService (生成向量) -> VectorDBService (存入 Qdrant).
2.  **搜索流程**: API -> EmbeddingService (Query 向量化) -> VectorDBService (相似度检索) -> StorageService (获取图片信息) -> 返回结果.

### 3.3 数据存储方案
- **结构化数据 & 向量数据**: Qdrant (存储 Image ID, Embedding, Tags, Metadata).
- **非结构化数据 (图片)**: 本地文件系统 (\`storage/images\`).

## 4. 关键技术亮点
- **多模态 Embedding**: 使用 Qwen2-VL-Embedding 模型，统一文本和图像的语义空间。
- **异步处理**: 图片上传与索引过程解耦，提升响应速度。
- **智能 Agent**: 基于意图识别的对话式交互，支持多轮对话。
`;

export const ArchitecturePage: React.FC = () => {
  const { token } = theme.useToken();

  return (
    <div style={{ 
      maxWidth: 1000, 
      margin: '0 auto', 
      padding: '24px 16px' 
    }}>
      <Card 
        bordered={false}
        style={{
          boxShadow: '0 8px 32px rgba(0,0,0,0.08)', 
          borderRadius: 16,
          background: token.colorBgContainer,
          // backdropFilter: 'blur(12px)', // 如果背景是半透明的
        }}
      >
        <div className="markdown-body" style={{ color: token.colorText }}>
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({node, ...props}) => <h1 style={{ color: token.colorPrimary, borderBottom: `1px solid ${token.colorBorderSecondary}`, paddingBottom: 16, marginBottom: 24 }} {...props} />,
              h2: ({node, ...props}) => <h2 style={{ color: token.colorTextHeading, marginTop: 32, marginBottom: 16 }} {...props} />,
              h3: ({node, ...props}) => <h3 style={{ color: token.colorTextHeading, marginTop: 24, marginBottom: 12 }} {...props} />,
              p: ({node, ...props}) => <p style={{ color: token.colorText, lineHeight: 1.8, marginBottom: 16 }} {...props} />,
              li: ({node, ...props}) => <li style={{ color: token.colorText, lineHeight: 1.8, marginBottom: 8 }} {...props} />,
              pre: ({node, ...props}) => (
                <pre style={{ 
                    background: token.colorFillAlter, 
                    padding: 16, 
                    borderRadius: 8, 
                    overflow: 'auto', 
                    marginBottom: 16,
                    border: `1px solid ${token.colorBorderSecondary}`
                }} {...props} />
              ),
              code: ({node, ...props}) => {
                // @ts-ignore
                const { inline } = props;
                if (inline) {
                   return (
                      <code 
                          style={{ 
                              background: token.colorFillAlter, 
                              padding: '2px 6px', 
                              borderRadius: 4, 
                              color: token.colorError, 
                              fontFamily: 'monospace',
                              fontSize: '0.9em'
                          }} 
                          {...props} 
                      />
                  )
                }
                return <code style={{ fontFamily: 'monospace', color: 'inherit' }} {...props} />;
              }
            }}
          >
            {markdownContent}
          </ReactMarkdown>
        </div>
      </Card>
      <FloatButton.BackTop />
    </div>
  );
};
