# 🧠 DeepDigest Collector - Chrome 浏览器插件

> 一键捕获网页内容，让知识触手可及

## 📁 文件结构

```
chrome_extension/
├── manifest.json      # 插件配置文件 (Manifest V3)
├── background.js      # 后台服务脚本
├── icons/             # 图标文件夹
│   ├── icon16.png     # 16x16 图标
│   ├── icon48.png     # 48x48 图标
│   └── icon128.png    # 128x128 图标
└── README.md          # 说明文档
```

## 🚀 安装步骤

### 1. 准备图标（可选）

在 `icons/` 文件夹中放入 PNG 图标文件。如果没有图标，Chrome 会使用默认图标。

### 2. 加载插件

1. 打开 Chrome 浏览器
2. 访问 `chrome://extensions/`
3. 开启右上角的 **「开发者模式」**
4. 点击 **「加载已解压的扩展程序」**
5. 选择 `chrome_extension` 文件夹
6. 完成！插件已安装 ✅

## 📖 使用方法

1. **启动 DeepDigest API 服务**
   ```bash
 	python -m deep_digest.src.workflows.api_server
   ```
   确保服务运行在 `http://localhost:8787`

2. **采集网页内容**
   - 在任意网页上选中一段文字
   - 右键点击，选择 **「🧠 存入 DeepDigest」**
   - 看到 ✅ 通知表示保存成功！

## ⚙️ 配置

如需修改 API 地址，编辑 `background.js` 中的：

```javascript
const API_ENDPOINT = "http://localhost:8787/capture";
```

## 🔧 开发调试

- **查看后台日志**: `chrome://extensions/` → 点击插件的「服务工作进程」
- **重新加载**: 修改代码后，点击插件卡片上的刷新按钮

## 📡 API 接口

插件会发送 POST 请求到 `/capture`：

```json
{
  "text": "选中的文字内容",
  "url": "https://example.com/page",
  "title": "网页标题"
}
```

## ❓ 常见问题

**Q: 右键没有出现菜单项？**
- 确保选中了文字（菜单只在选中文字时显示）
- 检查插件是否已启用

**Q: 显示「连接失败」？**
- 确保 DeepDigest API 服务已启动
- 检查端口 8787 是否被占用

**Q: 某些页面无法使用？**
- Chrome 内置页面（如 `chrome://`）不支持插件脚本注入
- 这是 Chrome 的安全限制，属于正常现象
