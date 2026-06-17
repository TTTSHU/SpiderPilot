#!/bin/bash
# SpiderPilot — 一键启动 (Web UI + AI 守护进程)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "SpiderPilot 启动..."
echo ""

# 激活 conda 环境（如果存在）
if [ -f "$HOME/miniconda3/bin/activate" ]; then
    source "$HOME/miniconda3/bin/activate" zj-spider 2>/dev/null || true
fi

# 安装依赖
pip install -e "$ROOT" -q 2>/dev/null

# 启动 Web UI
echo "🕸️  Web UI:  http://localhost:8000"
python -m uvicorn spiderpilot.web.app:app --host 0.0.0.0 --port 8000 --reload &
WEB_PID=$!

# 等 Web 启动
sleep 2

# 启动守护进程
echo "🤖 AI 守护: 自动处理待办任务"
SPIDER_HOST=http://127.0.0.1:8000 python "$ROOT/spiderpilot/daemon.py" &
DAEMON_PID=$!

echo ""
echo "✅ 启动完成 (Web PID: $WEB_PID, Daemon PID: $DAEMON_PID)"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
trap "kill $WEB_PID $DAEMON_PID 2>/dev/null; echo 'SpiderPilot 已停止'" EXIT

# 等待
wait
