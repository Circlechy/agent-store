# 🚀 快速安装指南

## 方法 1: pip 安装（推荐）

```bash
# 1. 进入项目目录
cd openjiuwen-code

# 2. pip 安装（开发模式）
pip install -e .

# 或者安装到用户目录（推荐，避免权限问题）
pip install --user -e .

# 3. 现在可以在任何目录使用 jiuwen 命令！
jiuwen
```

## 方法 2: 使用虚拟环境（最稳定）

```bash
# 1. 进入项目目录
cd openjiuwen-code

# 2. 创建虚拟环境
python3 -m venv .venv

# 3. 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# 4. 安装
pip install -e .

# 5. 现在可以使用 jiuwen 命令
jiuwen
```

## 配置 API Key

首次使用需要配置 API Key：

```bash
# 方式 1: 交互式配置（推荐）
jiuwen --config

# 方式 2: 环境变量
export ANTHROPIC_API_KEY="sk-ant-xxx"
export OPENAI_API_KEY="sk-xxx"
export ZHIPU_API_KEY="xxx"
```

## 在任何目录使用

安装完成后，`jiuwen` 命令可以在**任何目录**下使用：

```bash
# 在项目 A 中
cd ~/projects/project-a
jiuwen
> 帮我分析这个项目

# 在项目 B 中
cd ~/projects/project-b
jiuwen
> 重构这个函数

# 在家目录
cd ~
jiuwen
> 解释这个代码
```

Jiuwen 会自动使用**当前工作目录**作为项目根目录。

## 验证安装

```bash
# 查看版本
jiuwen --version

# 查看帮助
jiuwen --help

# 运行测试
jiuwen --test
```

## 常见问题

### 1. 命令未找到

如果提示 `jiuwen: command not found`：

```bash
# 检查 PATH（pip 会提示安装位置）
which jiuwen

# 如果在 ~/.local/bin，添加到 PATH
export PATH="$HOME/.local/bin:$PATH"

# 永久添加（添加到 ~/.bashrc）
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. 权限错误

```bash
# 使用 --user 安装
pip install --user -e .

# 或使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. 导入错误

```bash
# 确保在项目根目录安装
cd openjiuwen-code
pip install -e .
```

## 卸载

```bash
pip uninstall openjiuwen-code

# 删除配置（可选）
rm -rf ~/.jiuwen
```

## 下一步

- 运行 `jiuwen --help` 查看所有命令
- 查看 [docs/01-架构设计.md](docs/01-架构设计.md) 了解架构
- 查看 [docs/02-详细技术设计.md](docs/02-详细技术设计.md) 了解实现细节
