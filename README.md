# qys123

## 项目

1. **USRP IQ Pipeline** — GNU Radio / 仿真 IQ 采集与性能测试（见 `pipeline/`）
2. **教室监控演示** — 暨南大学番禺校区教室设备监控后台原型（见 `classroom_monitor/`）

### 教室监控快速启动

```bash
pip install -r classroom_monitor/requirements.txt
PYTHONPATH=. python3 classroom_monitor/run_server.py
# http://127.0.0.1:8080  令牌: jnu-demo-admin
```

详见 [classroom_monitor/README.md](classroom_monitor/README.md)
