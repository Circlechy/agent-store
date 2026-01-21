# 前端项目安装指南

## 📋 项目说明

本项目是一个基于 React + TypeScript + Vite 的前端项目。

## 🚫 Git 忽略的文件

以下文件/文件夹**不会**上传到 Git 仓库（已配置在 `.gitignore` 中）：

- ✅ `node_modules/` - 依赖包文件夹（体积大，通过 `npm install` 自动生成）
- ✅ `dist/` - 构建产物文件夹（通过 `npm run build` 生成）
- ✅ `.env*` - 环境变量文件（可能包含敏感配置）
- ✅ `*.log` - 日志文件
- ✅ `.DS_Store`, `Thumbs.db` - 系统生成的文件
- ✅ `.vscode/`, `.idea/` - IDE 配置文件（个人配置）

**会被上传到 Git 的文件：**
- ✅ `package.json` - 依赖声明（**必须**）
- ✅ `package-lock.json` - 依赖版本锁定（**建议提交**，保证团队依赖一致性）
- ✅ 所有源代码文件（`src/` 目录）
- ✅ 配置文件（`vite.config.ts`, `tsconfig.json` 等）
- ✅ `.gitignore` - Git 忽略规则文件

## 📦 安装步骤

### 前置要求

确保已安装以下软件：

1. **Node.js** (版本 18 或更高)
   ```powershell
   node --version
   ```

2. **npm** (随 Node.js 一起安装)
   ```powershell
   npm --version
   ```

**如果未安装 Node.js：**
- 下载地址：https://nodejs.org/
- 安装后重启终端

### 安装依赖

首次克隆项目后，需要安装依赖：

```powershell
# 进入前端目录
cd frontend

# 安装依赖（这将创建 node_modules 文件夹）
npm install
```

**安装时间：**
- 快速网络：1-3 分钟
- 普通网络：3-5 分钟
- 慢速网络：5-10 分钟或更长

**如果安装很慢（特别是在中国大陆）：**

可以使用国内镜像加速：

```powershell
# 设置淘宝镜像
npm config set registry https://registry.npmmirror.com

# 然后安装
npm install
```

**查看安装进度：**

如果看不到安装进度，可以使用：

```powershell
npm install --loglevel=info
```

### 验证安装

安装完成后，应该看到：
- ✅ 创建了 `node_modules/` 文件夹
- ✅ 终端显示 `added X packages` 或类似消息
- ✅ 没有错误信息

## 🚀 启动项目

### 方式一：使用启动脚本（推荐）

**PowerShell:**
```powershell
cd frontend
.\start.ps1
```

**CMD:**
```cmd
cd frontend
start.bat
```

### 方式二：直接命令

```powershell
cd frontend
npm run dev
```

启动成功后，浏览器访问：**http://localhost:3000**

## ⚠️ 重要提示

### 后端服务必须运行

前端项目依赖后端 API，启动前端前请确保后端服务已运行：

```powershell
# 终端 1：启动后端
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```powershell
# 终端 2：启动前端
cd frontend
npm run dev
```

### 服务地址

- **前端开发服务器**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 📝 可用命令

| 命令 | 说明 |
|------|------|
| `npm install` | 安装依赖（首次克隆后必须执行） |
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 构建生产版本（生成 `dist/` 文件夹） |
| `npm run preview` | 预览生产构建 |
| `npm run lint` | 运行代码检查 |
| `npm run format` | 格式化代码 |

## 🔧 常见问题

### 1. npm 命令未找到

**原因：** Node.js 未安装或未添加到 PATH

**解决方案：**
1. 安装 Node.js: https://nodejs.org/
2. 重启终端
3. 验证：`node --version` 和 `npm --version`

### 2. 端口 3000 已被占用

**解决方案 1：** 查找并关闭占用端口的进程
```powershell
# 查找占用端口的进程
netstat -ano | findstr :3000

# 关闭进程（替换 <PID> 为实际的进程 ID）
taskkill /PID <PID> /F
```

**解决方案 2：** 修改端口
编辑 `vite.config.ts`：
```typescript
server: {
  port: 3001,  // 改为其他端口
}
```

### 3. 无法连接到后端

**检查清单：**
1. ✅ 后端服务是否运行？访问 http://localhost:8000/health 测试
2. ✅ API 代理配置是否正确？（查看 `vite.config.ts`）
3. ✅ 后端 CORS 是否已启用？

### 4. 依赖安装失败

**解决方案 1：** 清理缓存重新安装
```powershell
npm cache clean --force
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
```

**解决方案 2：** 使用国内镜像
```powershell
npm config set registry https://registry.npmmirror.com
npm install
```

**解决方案 3：** 使用管理员权限运行终端

### 5. node_modules 文件夹不存在

**这是正常的！** `node_modules/` 不会被上传到 Git。

**解决方案：** 执行 `npm install` 安装依赖，会自动创建该文件夹。

## 📁 项目结构

```
frontend/
├── src/                    # 源代码目录
│   ├── components/         # 组件
│   ├── pages/              # 页面
│   ├── services/           # API 服务
│   ├── store/              # 状态管理
│   └── ...
├── public/                 # 静态资源
├── node_modules/           # 依赖包（不会上传到 Git）
├── dist/                   # 构建输出（不会上传到 Git）
├── package.json            # 项目配置和依赖声明
├── package-lock.json       # 依赖版本锁定
├── vite.config.ts          # Vite 配置
├── tsconfig.json           # TypeScript 配置
├── .gitignore              # Git 忽略规则
└── INSTALL.md              # 本安装文档
```

## 🔄 工作流程

1. **首次克隆项目**
   ```powershell
   git clone <repository-url>
   cd frontend
   npm install  # 必须执行
   ```

2. **日常开发**
   ```powershell
   npm run dev  # 启动开发服务器
   ```

3. **代码检查**
   ```powershell
   npm run lint   # 检查代码
   npm run format # 格式化代码
   ```

4. **构建生产版本**
   ```powershell
   npm run build  # 生成 dist/ 文件夹
   ```

## 💡 提示

- 每次从 Git 拉取更新后，如果 `package.json` 有变化，建议执行 `npm install` 更新依赖
- 如果遇到奇怪的错误，尝试删除 `node_modules/` 和 `package-lock.json`，然后重新 `npm install`
- 开发时保持后端和前端同时在运行
- 查看 `NPM_INSTALL_TIPS.md` 了解更多安装相关的提示

## 📚 相关文档

- `START.md` - 快速启动指南（英文）
- `NPM_INSTALL_TIPS.md` - npm 安装提示
- `package.json` - 查看项目依赖和脚本

