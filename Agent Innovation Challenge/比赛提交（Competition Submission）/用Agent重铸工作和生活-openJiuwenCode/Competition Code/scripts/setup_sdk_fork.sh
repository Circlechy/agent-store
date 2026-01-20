#!/bin/bash
# 配置 agent-core SDK 使用个人 Fork

set -e

echo "================================"
echo "配置 agent-core SDK 使用个人 Fork"
echo "================================"
echo ""

# 1. 检查当前目录
if [ ! -d "agent-core" ]; then
    echo "❌ 错误：agent-core 目录不存在"
    echo "请先运行：git submodule update --init --recursive"
    exit 1
fi

cd agent-core

# 2. 检查 remote 是否已添加
echo "1️⃣ 检查 remote 配置..."
if git remote | grep -q "k00591264"; then
    echo "✓ remote k00591264 已存在"
    git remote -v | grep k00591264
else
    echo "❌ remote k00591264 不存在"
    echo "正在添加..."
    git remote add k00591264 https://gitcode.com/SnapeK/agent-core.git
    echo "✓ remote k00591264 已添加"
fi

echo ""

# 3. 检查或创建 openjiuwen-code 分支
echo "2️⃣ 检查 openjiuwen-code 分支..."
if git rev-parse --verify openjiuwen-code >/dev/null 2>&1; then
    echo "✓ 分支 openjiuwen-code 已存在"
    git checkout openjiuwen-code
else
    echo "⚠️  分支 openjiuwen-code 不存在"
    echo ""
    echo "请选择："
    echo "  1) 创建新的 openjiuwen-code 分支（基于当前分支）"
    echo "  2) 使用现有的 develop 分支"
    echo "  3) 从 fork 的 openjiuwen-code 分支拉取"
    echo ""
    read -p "请输入选项 (1/2/3) [默认: 1]: " choice

    choice=${choice:-1}

    case $choice in
        1)
            echo "创建新的 openjiuwen-code 分支..."
            git checkout -b openjiuwen-code
            echo "✓ 分支已创建"
            ;;
        2)
            echo "使用 develop 分支..."
            git checkout develop
            echo "⚠️  将使用 develop 分支代替 openjiuwen-code"
            ;;
        3)
            echo "从 fork 拉取 openjiuwen-code 分支..."
            git fetch k00591264
            git checkout -b openjiuwen-code --track k00591264/openjiuwen-code 2>/dev/null || \
            git checkout openjiuwen-code
            echo "✓ 已切换到 openjiuwen-code"
            ;;
        *)
            echo "❌ 无效选项，使用 develop 分支"
            git checkout develop
            ;;
    esac
fi

echo ""

# 4. 推送分支到 fork（如果需要）
echo "3️⃣ 检查是否需要推送到 fork..."
read -p "是否推送 openjiuwen-code 分支到你的 fork? (y/N) " push_choice

if [[ $push_choice =~ ^[Yy]$ ]]; then
    echo "推送到 fork..."
    git push -u k00591264 openjiuwen-code
    echo "✓ 分支已推送"
else
    echo "跳过推送"
fi

cd ..

echo ""
echo "================================"
echo "4️⃣ 更新 .gitmodules 配置"
echo "================================"
echo ""

# 5. 更新 .gitmodules
if [ -f ".gitmodules" ]; then
    echo "更新 .gitmodules 指向你的 fork..."

    # 备份原 .gitmodules
    cp .gitmodules .gitmodules.backup

    # 更新配置
    cat > .gitmodules << 'EOF'
[submodule "agent-core"]
	path = agent-core
	url = https://gitcode.com/SnapeK/agent-core.git
	branch = openjiuwen-code
EOF

    echo "✓ .gitmodules 已更新"
    echo ""
    echo "旧配置："
    cat .gitmodules.backup | grep -v "^#" | grep -v "^$"
    echo ""
    echo "新配置："
    cat .gitmodules | grep -v "^#" | grep -v "^$"
else
    echo "创建 .gitmodules..."
    cat > .gitmodules << 'EOF'
[submodule "agent-core"]
	path = agent-core
	url = https://gitcode.com/SnapeK/agent-core.git
	branch = openjiuwen-code
EOF
    echo "✓ .gitmodules 已创建"
fi

echo ""
echo "================================"
echo "✅ 配置完成！"
echo "================================"
echo ""
echo "下一步："
echo "  1. 提交 .gitmodules 的更改"
echo "     git add .gitmodules"
echo "     git commit -m 'chore: use personal fork for agent-core SDK'"
echo ""
echo "  2. 其他开发者使用："
echo "     git clone <repo>"
echo "     cd openjiuwen-code"
echo "     git submodule update --init --recursive"
echo ""
echo "  3. 更新 SDK："
echo "     cd agent-core"
echo "     git pull k00591264 openjiuwen-code"
echo ""
echo "📚 详细文档：docs/SDK_PATCHES_GUIDE.md"
