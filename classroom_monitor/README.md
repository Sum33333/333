# 暨南大学番禺校区教室监控（演示系统）

> **重要说明**：本仓库提供的是**校内运维后台原型 + 模拟数据**。  
> 无法从公网直接接入暨大真实教室画面。接入真实屏幕前，须完成学校信息安全与隐私合规审批。

## 功能

- 番禺校区教室列表（南海楼 / 综合楼 / 教学楼J / 实验楼）
- 设备状态：在线 / 使用中 / 待机 / 离线 / 故障
- 设备健康：PC、投影、HDMI、麦克风、CPU
- **网格总览** + **单教室 MJPEG 实时预览**（演示模式为模拟屏幕）
- WebSocket 推送状态更新
- 教室端 Agent 模板（校内部署截屏上报）

## 快速启动

```bash
cd classroom_monitor
pip install -r requirements.txt
cd ..
PYTHONPATH=. python3 classroom_monitor/run_server.py
```

浏览器打开：`http://127.0.0.1:8080`  
默认令牌：`jnu-demo-admin`

自定义令牌：

```bash
export CLASSROOM_ADMIN_TOKEN='your-secret-token'
PYTHONPATH=. python3 classroom_monitor/run_server.py
```

## 合规要求（接入真实画面前必读）

1. 取得学校信息化管理部门书面授权
2. 教室张贴监控范围公示
3. 仅用于设备运维与故障排查，禁止用于教学无关监控
4. 服务部署在**校园内网/VPN**，禁止公网裸露
5. 访问日志留存、权限最小化、定期审计

## 接入真实教室画面

架构：

```
教室 PC (Agent) --HTTPS--> 监控中心 (本服务) --WebSocket/MJPEG--> 运维浏览器
```

1. 在教室 PC 安装 Agent：`classroom_monitor/agent/classroom_agent.py`
2. 配置 `CLASSROOM_ID`、`SERVER_URL`、`AGENT_TOKEN`
3. 在监控中心为教室设置 `stream_mode=agent`
4. 扩展 `POST /api/agent/{room_id}/frame` 接收端点（生产环境实现）

生产环境建议：

- 使用 RTSP/WebRTC 替代轮询 JPEG
- 接入学校统一身份认证（CAS/OAuth）
- 数据库维护教室资产台账，替换 `backend/rooms.py` 静态清单

## API

| 接口 | 说明 |
|------|------|
| `GET /api/summary` | 汇总统计 |
| `GET /api/rooms` | 教室列表 |
| `GET /api/rooms/{id}/frame.jpg` | 单帧快照 |
| `GET /api/rooms/{id}/mjpeg?token=` | MJPEG 流 |
| `WS /ws?token=` | 状态推送 |

所有 API 需 `Authorization: Bearer <token>`（MJPEG 可用 query token）。
