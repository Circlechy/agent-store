#!/bin/bash
# Backend V3 Linux/Mac 启动脚本

echo "========================================"
echo "Backend V3 启动脚本"
echo "========================================"

# 检查虚拟环境是否存在
if [ -f "venv/bin/activate" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
else
    echo "警告: 未找到虚拟环境，使用系统 Python"
fi

# 加载 .env 文件（如果存在）
if [ -f ".env" ]; then
    echo "发现 .env 文件，将加载环境变量"
else
    echo "警告: 未找到 .env 文件，请复制 .env.example 为 .env 并配置"
    exit 1
fi

# 设置默认端口
export PORT=${PORT:-8000}

# 启动服务
echo ""
echo "正在启动服务..."
echo "端口: $PORT"
echo "API 文档: http://localhost:$PORT/docs"
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
