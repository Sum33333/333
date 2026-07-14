# 暨南大学番禺校区教室监控（NETC 运维后台）

> 主管部门：[网络与教育技术中心](https://netc.jnu.edu.cn/)  
> `netc.jnu.edu.cn` 是中心门户，**不是**画面流地址。监控站建议部署为 `classroom.netc.jnu.edu.cn`（需向 NETC 申请）。

## 快速启动（演示）

```bash
./start_classroom_monitor.sh
# http://127.0.0.1:8080  令牌: jnu-demo-admin
```

## 校内正式部署

详见 [DEPLOY_NETC.md](DEPLOY_NETC.md) — CAS（MyNET）、录播平台 API、Agent 上报。

## 功能

- 番禺校区课室设备状态与画面预览（演示为模拟）
- 网格总览 + MJPEG 单画面
- WebSocket 实时推送
- JNUID / CAS 登录预留（`CAS_ENABLED=1`）
- 教室 Agent 模板

## API

| 接口 | 说明 |
|------|------|
| `GET /api/config` | NETC 门户、CAS 地址、服务热线 |
| `GET /api/summary` | 汇总（需令牌） |
| `GET /api/rooms/{id}/mjpeg` | 画面流 |
| `GET /api/auth/cas/callback` | CAS 回调 |

所有受保护 API 需 `Authorization: Bearer <token>`。
