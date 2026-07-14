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
# 完整 171 间课室由 room_catalog.load_classrooms() 生成
from classroom_monitor.backend.room_catalog import load_classrooms

PANYU_CLASSROOMS: list[Classroom] = load_classrooms()
