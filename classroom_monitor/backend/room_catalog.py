#!/usr/bin/env python3
"""生成番禺校区 171 座多媒体课室清单（可按 CSV 覆盖）。"""

from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

from classroom_monitor.backend.rooms import Classroom, Status

# 番禺校区主要教学楼（2026 三期改造覆盖范围）
PANYU_BUILDINGS: list[tuple[str, str, int, int, list[str]]] = [
    # (楼名, 编号前缀, 楼层数, 每层教室数, 设备)
    ("南海楼", "NH", 5, 8, ["PC", "投影", "录播", "中控"]),
    ("万国楼", "WG", 4, 7, ["PC", "投影", "录播"]),
    ("理学楼", "LX", 4, 6, ["PC", "投影", "录播"]),
    ("坪苑学园", "PY", 3, 5, ["PC", "投影"]),
    ("实验楼", "SY", 3, 4, ["PC", "投影", "实验台"]),
]

STATUSES: list[Status] = ["in_use", "idle", "offline", "fault", "in_use", "idle"]


def _seed_status(room_id: str) -> Status:
    h = int(hashlib.md5(room_id.encode()).hexdigest(), 16)
    return STATUSES[h % len(STATUSES)]


def _status_flags(status: Status) -> tuple[bool, bool, bool, bool, float]:
    if status == "offline":
        return False, False, False, True, 0.0
    if status == "fault":
        return True, True, False, True, 45.0 + (hash("f") % 20)
    if status == "idle":
        return True, True, True, True, 8.0 + (hash("i") % 10)
    # in_use
    return True, True, True, True, 20.0 + (hash("u") % 35)


def generate_panyu_classrooms(target: int = 171) -> list[Classroom]:
    rooms: list[Classroom] = []
    for building, prefix, floors, per_floor, devices in PANYU_BUILDINGS:
        for floor in range(1, floors + 1):
            for num in range(1, per_floor + 1):
                if len(rooms) >= target:
                    return rooms
                room_code = f"{prefix}{floor}{num:02d}"
                rid = f"py-{prefix.lower()}-{floor}{num:02d}"
                status = _seed_status(rid)
                pc, proj, hdmi, mic, cpu = _status_flags(status)
                seats = 60 + (hash(rid) % 140)
                note = ""
                if status == "fault":
                    note = "HDMI 无信号" if not hdmi else "设备告警"
                elif status == "offline":
                    note = "未开机"
                stream_mode = "agent" if status in ("in_use", "idle") else "mock"
                rooms.append(
                    Classroom(
                        id=rid,
                        building=building,
                        room=room_code,
                        floor=floor,
                        seats=seats,
                        devices=devices.copy(),
                        status=status,
                        projector_on=proj,
                        pc_on=pc,
                        hdmi_ok=hdmi,
                        mic_ok=mic,
                        cpu_pct=round(cpu, 1),
                        note=note,
                        stream_mode=stream_mode,
                    )
                )
    extra = 1
    while len(rooms) < target:
        rid = f"py-nh-x{extra:03d}"
        status = _seed_status(rid)
        pc, proj, hdmi, mic, cpu = _status_flags(status)
        rooms.append(
            Classroom(
                id=rid,
                building="南海楼",
                room=f"NH-X{extra:02d}",
                floor=5 + (extra // 10),
                seats=80,
                devices=["PC", "投影", "录播", "中控"],
                status=status,
                projector_on=proj,
                pc_on=pc,
                hdmi_ok=hdmi,
                mic_ok=mic,
                cpu_pct=round(cpu, 1),
                stream_mode="agent" if status in ("in_use", "idle") else "mock",
            )
        )
        extra += 1
    return rooms[:target]


def load_classrooms() -> list[Classroom]:
    csv_path = Path(os.environ.get("CLASSROOM_CSV", ""))
    if not csv_path.is_file():
        default = Path(__file__).resolve().parent.parent / "data" / "panyu_rooms.csv"
        csv_path = default if default.is_file() else Path()

    if csv_path.is_file():
        return _load_csv(csv_path)
    return generate_panyu_classrooms(171)


def _load_csv(path: Path) -> list[Classroom]:
    rows: list[Classroom] = []
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            devices = [d.strip() for d in row.get("devices", "PC,投影").split(",") if d.strip()]
            rows.append(
                Classroom(
                    id=row["id"],
                    building=row["building"],
                    room=row["room"],
                    floor=int(row.get("floor", 1)),
                    seats=int(row.get("seats", 80)),
                    devices=devices,
                    status=row.get("status", "offline"),  # type: ignore[arg-type]
                    projector_on=row.get("projector_on", "0") in ("1", "true", "True"),
                    pc_on=row.get("pc_on", "0") in ("1", "true", "True"),
                    hdmi_ok=row.get("hdmi_ok", "1") in ("1", "true", "True"),
                    mic_ok=row.get("mic_ok", "1") in ("1", "true", "True"),
                    stream_mode=row.get("stream_mode", "agent"),  # type: ignore[arg-type]
                    stream_url=row.get("stream_url", ""),
                    note=row.get("note", ""),
                )
            )
    return rows
