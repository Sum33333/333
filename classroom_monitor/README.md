# 暨南大学番禺校区教室监控

## 永久网站（校内正式部署）

**临时 cloudflared 链接会失效，不是永久站。**

| 你要的 | 做法 |
|--------|------|
| 永久网址 | `https://classroom.netc.jnu.edu.cn`（向 NETC 申请 DNS） |
| 设备 MAC `8E:B8:5E:51:4D:58` | MyNET 终端登记（运维电脑连校园 WiFi），**不是网站地址** |

步骤：

1. 提交 NETC 申请 → [NETC_APPLICATION_TEMPLATE.md](deploy/NETC_APPLICATION_TEMPLATE.md)
2. 校内服务器安装 → `sudo deploy/install_permanent.sh`
3. 详见 [PERMANENT_DEPLOY.md](deploy/PERMANENT_DEPLOY.md)

## 本地演示（临时）

```bash
./start_classroom_monitor.sh
# http://127.0.0.1:8080  令牌: jnu-demo-admin
```

网站内输入录播 API 即可选教室看画面，接口规范见 [API.md](API.md)
