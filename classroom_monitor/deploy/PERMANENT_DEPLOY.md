# 暨南大学教室监控 — 永久网站校内部署指南

> **说明**：MAC 地址 `8E:B8:5E:51:4D:58` 用于**校园网终端登记**（运维人员设备入网），  
> **不能**作为网站永久地址。永久网站需要 **固定域名 + 校内服务器 7×24 运行**。

## 永久方案架构

```
用户浏览器
    ↓ HTTPS
classroom.netc.jnu.edu.cn  （NETC 分配的固定域名）
    ↓
校内服务器 Nginx :443
    ↓
教室监控服务 :8080
    ↓
录播/集控 API / 教室 Agent
```

## 一、向 NETC 申请（必做）

使用 `NETC_APPLICATION_TEMPLATE.md` 填写申请表，需申请：

| 项目 | 建议值 |
|------|--------|
| 域名 | `classroom.netc.jnu.edu.cn` |
| 服务器 | 番禺校区内网固定 IP 一台 |
| SSL 证书 | NETC 统一证书或 Let's Encrypt（内网） |
| CAS 客户端 | service URL = `https://classroom.netc.jnu.edu.cn` |
| 运维终端 MAC | `8E:B8:5E:51:4D:58`（MyNET 设备绑定） |

联系电话：**020-85220304 / 85220305** · **owl@jnu.edu.cn**

## 二、校内服务器一键安装（Linux）

```bash
# 1. 克隆代码到服务器
git clone https://github.com/Sum33333/qys123.git
cd qys123

# 2. 配置环境
cp classroom_monitor/deploy/campus.env.example classroom_monitor/deploy/campus.env
nano classroom_monitor/deploy/campus.env   # 填写录播 API、强随机令牌等

# 3. 永久安装（systemd 开机自启）
sudo ./classroom_monitor/deploy/install_permanent.sh

# 4. 配置 Nginx + 证书（见 deploy/nginx.conf）
sudo ./classroom_monitor/scripts/deploy_campus.sh
```

安装后服务名：`jnu-classroom-monitor`，开机自动启动。

## 三、验证

```bash
curl -s http://127.0.0.1:8080/api/health
curl -s https://classroom.netc.jnu.edu.cn/api/health   # DNS 生效后
```

## 四、与临时演示的区别

| | 临时（cloudflared） | 永久（本方案） |
|--|---------------------|----------------|
| 地址 | `*.trycloudflare.com` 会变 | `classroom.netc.jnu.edu.cn` 固定 |
| 运行环境 | 云端 Agent，会停 | 校内服务器 7×24 |
| 认证 | 演示令牌 | JNUID CAS |
| 数据 | 模拟 | 真实录播/集控 API |

## 五、运维人员设备入网（MAC）

你的设备 MAC：`8E:B8:5E:51:4D:58`

1. 登录 [https://mynet.jnu.edu.cn/](https://mynet.jnu.edu.cn/)
2. 网络自助服务 → 终端/设备管理 → 添加 MAC
3. 格式：`8E:B8:5E:51:4D:58` 或 `8E-B8-5E-51-4D-58`

登记后，你在番禺校区连校园 WiFi 即可维护服务器；**与网站域名无关**。
