# 暨南大学番禺校区教室监控 — NETC 部署说明

## 关于 netc.jnu.edu.cn

[https://netc.jnu.edu.cn/](https://netc.jnu.edu.cn/) 是**网络与教育技术中心**信息公开门户（办事流程、通知公告、MyNET 入口等），**不是**教室实时画面流地址。

本监控系统建议部署为 NETC 子域，例如：

| 用途 | 建议地址 |
|------|----------|
| 信息公开门户 | `https://netc.jnu.edu.cn/` |
| 运维监控后台 | `https://classroom.netc.jnu.edu.cn`（需申请 DNS） |
| 统一认证 | `https://mynet.jnu.edu.cn/cas` |
| 录播/集控 API | 校内地址（向教育技术部索取） |

番禺校区 2026 年三期改造约 **171 座**多媒体课室；演示清单为子集，生产环境请导入资产台账。

## 校内部署步骤

### 1. 向 NETC 申请

- 子域名与反向代理（Nginx → 本服务 `:8080`）
- CAS 客户端注册（service URL = `https://classroom.netc.jnu.edu.cn`）
- 录播管理平台 / 集控中心 API 文档与内网地址

### 2. 环境变量

```bash
export PUBLIC_BASE_URL=https://classroom.netc.jnu.edu.cn
export NETC_PORTAL_URL=https://netc.jnu.edu.cn/
export CAS_ENABLED=1
export CAS_BASE_URL=https://mynet.jnu.edu.cn/cas
export CLASSROOM_ADMIN_TOKEN='<强随机令牌>'
export AGENT_TOKEN='<Agent上报令牌>'
# 录播平台（示例，以 NETC 提供为准）
export RECORDER_API_URL=http://<校内录播平台>/api
export CENTRAL_CONTROL_API_URL=http://<集控中心>/api
```

### 3. 启动

```bash
./start_classroom_monitor.sh
```

### 4. 教室 Agent（各课室 PC）

```bash
export CLASSROOM_ID=py-nh-101
export SERVER_URL=https://classroom.netc.jnu.edu.cn
export AGENT_TOKEN=<同上>
python3 classroom_monitor/agent/classroom_agent.py
```

## 演示模式（当前）

未接校内 API 时自动使用模拟画面与演示令牌 `jnu-demo-admin`。

## 技术支持

- 电话：020-85220304 / 85220305
- 邮箱：owl@jnu.edu.cn
- 门户：https://netc.jnu.edu.cn/
