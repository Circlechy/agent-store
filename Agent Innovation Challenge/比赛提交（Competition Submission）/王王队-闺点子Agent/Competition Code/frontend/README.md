# Frontend (Vue 3 + Naive UI)

## 技术栈
- Vue 3 + Composition API
- Vite 6 (ESM 构建)
- Naive UI 组件库

## 安装与启动

```bash
cd frontend
npm install
npm run dev
```

## 目录结构

- `src/views/ChatView.vue`：主聊天页面
- `src/components/`：消息、输入、调试面板、加载动画等 UI 组件
- `src/composables/`：SSE 管理、聊天历史、调试日志
- `src/utils/`：配置、输入验证、API 封装、格式化工具

## 配置

- `src/config/app.config.js`：API 地址、SSE 重连信息、验证规则
- `configs/config.yaml` 中的 `frontend.api_base_url` 用于替换默认 API 端点
