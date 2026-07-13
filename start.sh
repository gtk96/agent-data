#!/bin/bash

# 智能问数项目启动脚本

echo "=== 智能问数项目启动 ==="
echo ""

# 检查环境变量
if [ -z "$AGNES_API_KEY" ]; then
    echo "警告: 未设置 AGNES_API_KEY 环境变量"
    echo "请设置: export AGNES_API_KEY=your-api-key"
    echo ""
fi

# 启动后端
echo "启动 Python 后端 (端口 8000)..."
cd "$(dirname "$0")"
uvicorn agent_data.web.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 等待后端启动
echo "等待后端启动..."
sleep 3

# 启动前端
echo "启动 NextChat 前端 (端口 3000)..."
cd nextchat
yarn dev &
FRONTEND_PID=$!

echo ""
echo "=== 服务已启动 ==="
echo "后端: http://localhost:8000"
echo "前端: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# 等待
wait
