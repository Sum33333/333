#!/usr/bin/env python3
"""生成模拟教室屏幕帧（仅用于演示，非真实采集）。"""

from __future__ import annotations

import io
import math
import random
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from classroom_monitor.backend.rooms import Classroom


def _font(size: int = 16):
    for name in ("DejaVuSans.ttf", "WenQuanYiMicroHei.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


SCENES = ("ppt", "desktop", "video", "idle", "login")


def render_mock_frame(room: Classroom, tick: int = 0) -> bytes:
    """Render a JPEG snapshot mimicking classroom display content."""
    w, h = 960, 540
    scene_idx = (hash(room.id) + tick // 30) % len(SCENES)
    scene = SCENES[scene_idx]

    if room.status == "offline":
        img = Image.new("RGB", (w, h), (20, 22, 28))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 80, h // 2 - 10), "设备离线 / 无信号", fill=(120, 125, 135), font=_font(22))
    elif room.status == "fault" or not room.hdmi_ok:
        img = Image.new("RGB", (w, h), (32, 18, 18))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 100, h // 2 - 10), "信号异常 — 请检查 HDMI", fill=(255, 120, 120), font=_font(20))
    elif scene == "ppt":
        img = Image.new("RGB", (w, h), (245, 246, 248))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, w, 56], fill=(120, 24, 36))
        draw.text((20, 16), f"暨南大学 · {room.building} {room.room}", fill=(255, 255, 255), font=_font(18))
        draw.text((60, 120), "课程讲义", fill=(40, 40, 45), font=_font(36))
        draw.text((60, 190), "第 3 章  教学信息化与设备管理", fill=(60, 60, 70), font=_font(22))
        for i, line in enumerate(
            [
                "• 教室多媒体设备巡检规范",
                "• 录播主机与中控系统联调",
                "• 番禺校区网络接入说明",
            ]
        ):
            draw.text((80, 260 + i * 42), line, fill=(80, 80, 90), font=_font(18))
        draw.rectangle([w - 120, h - 50, w - 30, h - 20], fill=(120, 24, 36))
        draw.text((w - 108, h - 42), f"{(tick // 30) % 12 + 1}/12", fill=(255, 255, 255), font=_font(16))
    elif scene == "desktop":
        img = Image.new("RGB", (w, h), (0, 120, 215))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, h - 48, w, h], fill=(22, 28, 38))
        for i in range(6):
            draw.rectangle([30 + i * 90, h - 40, 90 + i * 90, h - 8], fill=(50, 58, 72))
        draw.text((30, 40), "Windows 桌面", fill=(255, 255, 255), font=_font(20))
    elif scene == "video":
        img = Image.new("RGB", (w, h), (18, 18, 22))
        draw = ImageDraw.Draw(img)
        t = tick / 10.0
        for x in range(0, w, 8):
            amp = int(120 + 80 * math.sin(x / 40.0 + t))
            draw.line([(x, h // 2 - amp // 2), (x, h // 2 + amp // 2)], fill=(70, 160, 255), width=2)
        draw.text((30, 30), "教学视频播放中", fill=(220, 220, 230), font=_font(20))
    elif scene == "login":
        img = Image.new("RGB", (w, h), (30, 32, 38))
        draw = ImageDraw.Draw(img)
        draw.rectangle([w // 2 - 160, h // 2 - 100, w // 2 + 160, h // 2 + 100], fill=(45, 48, 56))
        draw.text((w // 2 - 70, h // 2 - 70), "教室登录", fill=(230, 230, 235), font=_font(22))
        draw.rectangle([w // 2 - 120, h // 2 - 20, w // 2 + 120, h // 2 + 20], fill=(60, 64, 74))
    else:
        img = Image.new("RGB", (w, h), (28, 32, 40))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 60, h // 2 - 10), "课间待机", fill=(150, 155, 165), font=_font(22))

    # OSD overlay
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, h - 28, w, h], fill=(0, 0, 0, 180))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    osd = f"暨大番禺 · {room.building}-{room.room} · {ts} · DEMO"
    draw.text((10, h - 22), osd, fill=(180, 220, 255), font=_font(14))
    if room.status == "in_use":
        draw.ellipse([w - 24, h - 22, w - 10, h - 8], fill=(76, 217, 100))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def jitter_status(room: Classroom, rng: random.Random) -> Classroom:
    """Simulate telemetry drift for demo dashboards."""
    from dataclasses import replace

    cpu = max(0.0, min(99.0, room.cpu_pct + rng.uniform(-3, 3)))
    if room.status == "offline":
        return replace(room, cpu_pct=0.0, last_seen=datetime.now().isoformat(timespec="seconds"))
    return replace(
        room,
        cpu_pct=round(cpu, 1),
        last_seen=datetime.now().isoformat(timespec="seconds"),
    )
