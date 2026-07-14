#!/usr/bin/env python3
"""暨南大学番禺校区教室清单（演示数据，可按资产台账替换）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["online", "offline", "idle", "in_use", "fault"]


@dataclass
class Classroom:
    id: str
    building: str
    room: str
    floor: int
    seats: int
    devices: list[str]
    status: Status = "offline"
    projector_on: bool = False
    pc_on: bool = False
    hdmi_ok: bool = False
    mic_ok: bool = True
    cpu_pct: float = 0.0
    last_seen: str = ""
    note: str = ""
    stream_mode: Literal["mock", "agent", "rtsp"] = "mock"
    stream_url: str = ""


# 番禺校区主要教学楼（示例编号，请按学校资产系统维护）
PANYU_CLASSROOMS: list[Classroom] = [
    Classroom("py-n1-101", "南海楼", "N101", 1, 120, ["PC", "投影", "录播", "中控"], "in_use", True, True, True, True, 34.2, note="多媒体教室"),
    Classroom("py-n1-102", "南海楼", "N102", 1, 120, ["PC", "投影", "录播"], "in_use", True, True, True, True, 28.5),
    Classroom("py-n1-201", "南海楼", "N201", 2, 80, ["PC", "投影"], "idle", True, True, True, True, 12.0, note="课间待机"),
    Classroom("py-n1-202", "南海楼", "N202", 2, 80, ["PC", "投影"], "offline", False, False, False, True, 0.0, note="未开机"),
    Classroom("py-n2-301", "南海楼", "N301", 3, 60, ["PC", "投影", "智慧黑板"], "in_use", True, True, True, False, 41.0, note="麦克风异常"),
    Classroom("py-n2-302", "南海楼", "N302", 3, 60, ["PC", "投影"], "fault", True, True, False, True, 55.0, note="HDMI 无信号"),
    Classroom("py-z1-101", "综合楼", "Z101", 1, 200, ["PC", "投影", "录播", "同声传译"], "in_use", True, True, True, True, 38.7),
    Classroom("py-z1-102", "综合楼", "Z102", 1, 200, ["PC", "投影", "录播"], "idle", True, True, True, True, 15.3),
    Classroom("py-z2-201", "综合楼", "Z201", 2, 150, ["PC", "投影"], "in_use", True, True, True, True, 22.1),
    Classroom("py-z2-202", "综合楼", "Z202", 2, 150, ["PC", "投影"], "offline", False, False, False, True, 0.0),
    Classroom("py-j1-101", "教学楼J", "J101", 1, 90, ["PC", "投影", "录播"], "in_use", True, True, True, True, 31.4),
    Classroom("py-j1-102", "教学楼J", "J102", 1, 90, ["PC", "投影"], "idle", True, True, True, True, 9.8),
    Classroom("py-j2-301", "教学楼J", "J301", 3, 70, ["PC", "投影", "智慧黑板"], "in_use", True, True, True, True, 44.6),
    Classroom("py-j2-302", "教学楼J", "J302", 3, 70, ["PC", "投影"], "fault", True, True, False, True, 62.0, note="投影过热保护"),
    Classroom("py-lab-01", "实验楼", "Lab01", 1, 40, ["PC", "投影", "实验台"], "in_use", True, True, True, True, 67.2, note="上机实验"),
    Classroom("py-lab-02", "实验楼", "Lab02", 1, 40, ["PC", "投影"], "offline", False, False, False, True, 0.0),
]
