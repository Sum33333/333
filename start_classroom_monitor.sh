#!/usr/bin/env bash
# 暨南大学番禺校区教室监控 — 一键启动
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
USE_TUNNEL=0

for arg in "$@"; do
  case "$arg" in
    --tunnel|-t) USE_TUNNEL=1 ;;
    --help|-h)
      echo "用法: $0 [--tunnel]"
      echo "  --tunnel  通过 cloudflared 生成公网可访问地址（云端环境推荐）"
      exit 0
      ;;
  esac
done

echo "[1/3] 检查依赖..."
python3 -c "import fastapi, uvicorn, httpx, PIL" 2>/dev/null || {
  pip3 install -q -r classroom_monitor/requirements.txt
}

if ! python3 -c "import fastapi, uvicorn, httpx, PIL" 2>/dev/null; then
  echo "错误: 依赖安装失败，请手动执行: pip3 install -r classroom_monitor/requirements.txt"
  exit 1
fi

echo "[2/3] 检查端口 ${PORT}..."
if python3 -c "import socket; s=socket.socket(); s.bind(('$HOST', $PORT))" 2>/dev/null; then
  s.close 2>/dev/null || true
  NEED_START=1
else
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    echo "端口 ${PORT} 已有服务在运行"
    NEED_START=0
  else
    echo "错误: 端口 ${PORT} 被占用且不是本服务。可执行: PORT=8081 $0"
    exit 1
  fi
fi

export PYTHONPATH=.
export CLASSROOM_ADMIN_TOKEN="${CLASSROOM_ADMIN_TOKEN:-jnu-demo-admin}"
export AGENT_TOKEN="${AGENT_TOKEN:-jnu-agent-demo}"
export DEMO_AGENT_PUSH="${DEMO_AGENT_PUSH:-1}"
export HOST PORT

SESSION="jnu-classroom-server"
TMUX_CONF="${TMUX_CONF:-/exec-daemon/tmux.portal.conf}"
if command -v tmux >/dev/null 2>&1 && [[ -f "$TMUX_CONF" ]]; then
  tmux -f "$TMUX_CONF" has-session -t "=$SESSION" 2>/dev/null || \
    tmux -f "$TMUX_CONF" new-session -d -s "$SESSION" -c "$ROOT" -- "${SHELL:-bash}" -l
fi

if [[ "${NEED_START:-1}" == "1" ]]; then
  echo "[3/3] 启动服务..."
  if command -v tmux >/dev/null 2>&1 && tmux -f "$TMUX_CONF" has-session -t "=$SESSION" 2>/dev/null; then
    tmux -f "$TMUX_CONF" send-keys -t "$SESSION:0.0" C-c "cd '$ROOT' && PYTHONPATH=. HOST=$HOST PORT=$PORT python3 classroom_monitor/run_server.py" C-m
  else
    PYTHONPATH=. HOST="$HOST" PORT="$PORT" python3 classroom_monitor/run_server.py &
    echo $! > /tmp/classroom_monitor.pid
  fi
  for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
fi

if ! curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
  echo "错误: 服务启动失败。请检查:"
  echo "  PYTHONPATH=. python3 classroom_monitor/run_server.py"
  exit 1
fi

LOCAL_URL="http://127.0.0.1:${PORT}"
echo ""
echo "============================================"
echo " 服务已就绪"
echo " 本机访问: ${LOCAL_URL}"
echo " 令牌: ${CLASSROOM_ADMIN_TOKEN}"
echo " 测试 API: ${LOCAL_URL}/api/mock-platform"
echo "============================================"

if [[ "$USE_TUNNEL" == "1" ]]; then
  CF="${CLOUDFLARED:-/tmp/cloudflared}"
  if [[ ! -x "$CF" ]]; then
    echo "正在下载 cloudflared..."
    curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o "$CF"
    chmod +x "$CF"
  fi
  echo "正在创建公网隧道（约 5 秒）..."
  LOG=/tmp/classroom_tunnel.log
  pkill -f "cloudflared.*${PORT}" 2>/dev/null || true
  nohup "$CF" tunnel --url "http://127.0.0.1:${PORT}" >"$LOG" 2>&1 &
  for i in $(seq 1 45); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
    if [[ -n "$URL" ]]; then
      echo "$URL" > "$ROOT/PUBLIC_URL.txt"
      echo ""
      echo " 公网访问: ${URL}"
      echo " （请用此链接打开，旧链接会失效）"
      echo " 已写入: $ROOT/PUBLIC_URL.txt"
      echo "============================================"
      exit 0
    fi
    sleep 1
  done
  echo "隧道创建失败，请本机访问 ${LOCAL_URL}"
  tail -5 "$LOG" 2>/dev/null || true
fi
