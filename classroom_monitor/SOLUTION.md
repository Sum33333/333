# 一站式解决方案

## 你现在就能用的（已打通）

```bash
./start_classroom_monitor.sh
```

打开 http://127.0.0.1:8080 ，令牌 `jnu-demo-admin`

| 能力 | 状态 |
|------|------|
| 171 间番禺课室清单 | ✅ |
| 设备状态 WebSocket 实时刷新 | ✅ |
| 网格总览 + 单教室 MJPEG | ✅ |
| 内置 Agent 自动推流（50 间） | ✅ |
| NETC / MyNET 配置预留 | ✅ |
| Docker + Nginx 校内部署包 | ✅ |

## 切换真实教室画面（你在校内操作）

### 方式 A：录播/集控平台 API（推荐）

向教育技术部索取内网地址后，编辑 `classroom_monitor/deploy/campus.env`：

```bash
RECORDER_API_URL=http://<录播平台内网>/api
CENTRAL_CONTROL_API_URL=http://<集控中心内网>/api
CLASSROOM_DEMO_MODE=0
DEMO_AGENT_PUSH=0
```

服务会自动每 10 秒同步状态与快照。

### 方式 B：教室 PC Agent

在各课室 PC 运行：

```bash
pip install pillow mss httpx
export CLASSROOM_ID=py-nh-101
export SERVER_URL=https://classroom.netc.jnu.edu.cn
export AGENT_TOKEN=<与服务器一致>
python3 classroom_monitor/agent/classroom_agent.py
```

### 方式 C：校内 Docker 部署

```bash
cd classroom_monitor/scripts
./deploy_campus.sh
```

绑定域名 `classroom.netc.jnu.edu.cn`，证书放 `deploy/certs/`。

## 仍需 NETC 配合的一项

| 事项 | 负责方 |
|------|--------|
| 子域名 DNS | NETC 网络工程部 |
| CAS 客户端注册 | NETC + MyNET |
| 录播/集控 API 地址 | 教育技术部 |
| OpenAPI 密钥（可选） | https://openapi.jnu.edu.cn 申请 |

联系电话：020-85220304 / 85220305 · owl@jnu.edu.cn
