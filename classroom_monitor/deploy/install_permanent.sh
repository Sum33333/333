#!/usr/bin/env bash
# 暨南大学教室监控 — 永久安装（systemd 开机自启）
# 用法: sudo ./install_permanent.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请使用 root 运行: sudo $0"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/classroom_monitor/deploy/campus.env}"
SERVICE_NAME="jnu-classroom-monitor"
PY="${PYTHON:-python3}"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/classroom_monitor/deploy/campus.env.example" "$ENV_FILE"
  echo "已生成 $ENV_FILE ，请先编辑后再运行本脚本"
  exit 1
fi

echo "[1/4] 安装 Python 依赖..."
"$PY" -m pip install -q -r "$ROOT/classroom_monitor/requirements.txt"

echo "[2/4] 创建运行用户..."
id -u jnu-monitor &>/dev/null || useradd -r -s /usr/sbin/nologin -d /opt/jnu-classroom-monitor jnu-monitor

echo "[3/4] 安装应用..."
install -d -o jnu-monitor -g jnu-monitor /opt/jnu-classroom-monitor
rsync -a --delete \
  --exclude '.git' --exclude '__pycache__' --exclude 'artifacts' \
  "$ROOT/" /opt/jnu-classroom-monitor/
chown -R jnu-monitor:jnu-monitor /opt/jnu-classroom-monitor

echo "[4/4] 注册 systemd 服务..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=JNU Panyu Classroom Monitor (Permanent)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=jnu-monitor
Group=jnu-monitor
WorkingDirectory=/opt/jnu-classroom-monitor
Environment=PYTHONPATH=/opt/jnu-classroom-monitor
EnvironmentFile=${ENV_FILE}
ExecStart=${PY} /opt/jnu-classroom-monitor/classroom_monitor/run_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 2
if curl -sf http://127.0.0.1:8080/api/health >/dev/null; then
  echo ""
  echo "============================================"
  echo " 永久服务已安装并启动"
  echo " 服务名: ${SERVICE_NAME}"
  echo " 状态:   systemctl status ${SERVICE_NAME}"
  echo " 日志:   journalctl -u ${SERVICE_NAME} -f"
  echo " 本机:   http://127.0.0.1:8080"
  echo " 正式域名需在 NETC 配置 DNS 后使用:"
  echo "  https://classroom.netc.jnu.edu.cn"
  echo "============================================"
else
  echo "服务启动异常，请执行: journalctl -u ${SERVICE_NAME} -n 50"
  exit 1
fi
