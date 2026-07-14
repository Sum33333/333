#!/usr/bin/env python3
"""
教室端采集 Agent（校内部署模板）

在教室 PC 上运行，定时截屏并上报到监控中心。
须在学校授权、教室公示、专网隔离前提下部署。

依赖（教室 PC）:
  pip install pillow mss httpx

环境变量:
  CLASSROOM_ID=py-n1-101
  SERVER_URL=http://monitor.internal.jnu.edu.cn
  AGENT_TOKEN=<由信息中心签发>
"""

from __future__ import annotations

import io
import os
import sys
import time

try:
    import httpx
    import mss
    from PIL import Image
except ImportError:
    print("请安装: pip install pillow mss httpx", file=sys.stderr)
    sys.exit(1)

ROOM_ID = os.environ.get("CLASSROOM_ID", "py-n1-101")
SERVER = os.environ.get("SERVER_URL", "http://127.0.0.1:8080").rstrip("/")
TOKEN = os.environ.get("AGENT_TOKEN", "")
INTERVAL = float(os.environ.get("AGENT_INTERVAL", "1.0"))


def capture_jpeg() -> bytes:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img = img.resize((960, 540))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()


def push_frame(data: bytes) -> None:
    url = f"{SERVER}/api/agent/{ROOM_ID}/frame"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "image/jpeg"}
    r = httpx.post(url, content=data, headers=headers, timeout=10.0)
    r.raise_for_status()


def main() -> None:
    if not TOKEN:
        print("请设置 AGENT_TOKEN（校内签发）", file=sys.stderr)
        sys.exit(2)
    print(f"Agent 启动: room={ROOM_ID} server={SERVER} interval={INTERVAL}s")
    while True:
        try:
            push_frame(capture_jpeg())
        except Exception as exc:
            print(f"上报失败: {exc}", file=sys.stderr)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
