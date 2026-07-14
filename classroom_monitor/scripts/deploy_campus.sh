#!/usr/bin/env bash
# 校内一键部署（Docker）
set -euo pipefail
cd "$(dirname "$0")/deploy"
if [[ ! -f campus.env ]]; then
  cp campus.env.example campus.env
  echo "已生成 campus.env，请编辑后重新运行"
  exit 1
fi
docker compose up -d --build
echo "部署完成: 请配置 DNS classroom.netc.jnu.edu.cn → 本机，并放置 SSL 证书到 deploy/certs/"
