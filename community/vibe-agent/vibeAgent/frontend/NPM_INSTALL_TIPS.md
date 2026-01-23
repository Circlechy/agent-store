# npm install 安装说明

## 📦 正在安装的依赖

`npm install` 正在安装以下依赖包（共约 30+ 个包）：

### 主要依赖 (dependencies)
- `react` 和 `react-dom` - React 框架
- `antd` - Ant Design UI 组件库
- `@ant-design/icons` - 图标库
- `axios` - HTTP 客户端
- `react-router-dom` - 路由
- `zustand` - 状态管理
- `@monaco-editor/react` - 代码编辑器
- `mermaid` - 流程图库
- `reactflow` - 流程图组件
- `dayjs` - 日期处理

### 开发依赖 (devDependencies)
- `vite` - 构建工具
- `typescript` - TypeScript 编译器
- `@vitejs/plugin-react` - Vite React 插件
- `eslint` - 代码检查工具
- `prettier` - 代码格式化工具

## ⚠️ 为什么没有进度显示？

### 可能的原因

1. **npm 进度条被禁用**
   ```powershell
   # 启用进度显示
   npm config set progress=true
   ```

2. **安装过程正常，但显示延迟**
   - npm 需要下载所有依赖包
   - 首次安装可能需要几分钟时间
   - 网络速度影响下载时间

3. **卡在某个包上**
   - 可能某个包的下载很慢
   - 或者网络连接问题

## 🔧 解决方案

### 方案 1: 启用详细输出（推荐）

停止当前安装（按 `Ctrl + C`），然后使用：

```powershell
npm install --loglevel=info
```

或者使用更详细的输出：

```powershell
npm install --verbose
```

### 方案 2: 使用国内镜像加速（如果在国内）

```powershell
# 停止当前安装 (Ctrl + C)
# 设置淘宝镜像
npm config set registry https://registry.npmmirror.com

# 重新安装
npm install --loglevel=info
```

### 方案 3: 检查是否正在安装

打开任务管理器或使用命令查看：

```powershell
# 查看 npm 进程
Get-Process | Where-Object {$_.ProcessName -like "*node*" -or $_.ProcessName -like "*npm*"}
```

### 方案 4: 查看 npm 缓存

```powershell
# 查看缓存位置
npm config get cache

# 如果需要，清理缓存后重新安装
npm cache clean --force
npm install --loglevel=info
```

## ⏱️ 预计安装时间

- **快速网络（100Mbps+）**: 1-3 分钟
- **普通网络（10-50Mbps）**: 3-5 分钟
- **慢速网络（<10Mbps）**: 5-10 分钟或更长

## ✅ 验证安装是否完成

安装完成后，你应该看到：
- 显示安装的包数量
- 显示 `added X packages` 或类似消息
- 创建了 `node_modules` 目录
- 创建了 `package-lock.json` 文件

## 🚀 安装完成后

安装完成后，运行：

```powershell
npm run dev
```

或者使用启动脚本：

```powershell
.\start.bat
```

## 🔍 如果安装失败

### 常见错误

1. **网络超时**
   ```powershell
   npm install --timeout=60000
   ```

2. **权限问题**
   - 以管理员身份运行 PowerShell
   - 或使用 `npm install --legacy-peer-deps`

3. **依赖冲突**
   ```powershell
   npm install --force
   ```

## 💡 建议

首次安装建议使用：

```powershell
# 1. 设置国内镜像（如果在国内）
npm config set registry https://registry.npmmirror.com

# 2. 启用进度显示
npm config set progress=true

# 3. 使用详细信息安装
npm install --loglevel=info
```

这样可以看到详细的安装进度和日志。

