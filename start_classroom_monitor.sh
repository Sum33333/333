#!/usr/bin/env bash
# 暨南大学番禺校区教室监控 — 一键启动
set -euo pipefail
cd "$(dirname "$0")"
pip install -q -r classroom_monitor/requirements.txt
export PYTHONPATH=.
export CLASSROOM_ADMIN_TOKEN="${CLASSROOM_ADMIN_TOKEN:-jnu-demo-admin}"
export AGENT_TOKEN="${AGENT_TOKEN:-jnu-agent-demo}"
export DEMO_AGENT_PUSH="${DEMO_AGENT_PUSH:-1}"
echo "============================================"
echo " 暨南大学番禺校区教室监控（演示模式）"
echo " 访问: http://127.0.0.1:8080"
echo " 令牌: $CLASSROOM_ADMIN_TOKEN"
echo "============================================"
exec python3 classroom_monitor/run_server.py
