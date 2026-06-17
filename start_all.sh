#!/bin/bash
# SpiderPilot — 启动 Web UI
ROOT="$(cd "$(dirname "$0")" && pwd)"

# 杀掉旧进程
pkill -f "uvicorn.*spiderpilot" 2>/dev/null
sleep 1

# conda 环境
[ -f "$HOME/miniconda3/bin/activate" ] && source "$HOME/miniconda3/bin/activate" zj-spider

pip install -e "$ROOT" -q 2>/dev/null

echo "🕸️  SpiderPilot: http://localhost:9002"
python -m uvicorn spiderpilot.web.app:app --host 0.0.0.0 --port 9002 --reload
