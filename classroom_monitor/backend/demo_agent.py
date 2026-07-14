#!/usr/bin/env python3
"""内置演示 Agent：为 agent 模式课室自动推送模拟画面，打通端到端链路。"""

from __future__ import annotations

import asyncio
import logging

from classroom_monitor.backend.mock_stream import render_mock_frame
from classroom_monitor.backend.rooms import Classroom

log = logging.getLogger("demo_agent")


async def demo_agent_loop(
    rooms: dict[str, Classroom],
    frames: dict[str, bytes],
    tick_getter,
    interval: float = 1.0,
    max_rooms: int = 40,
) -> None:
    """周期性为 in_use/idle 且 stream_mode=agent 的教室生成帧。"""
    local_tick = 0
    while True:
        local_tick += 1
        tick = tick_getter()
        pushed = 0
        for rid, room in rooms.items():
            if room.stream_mode != "agent":
                continue
            if room.status not in ("in_use", "idle"):
                continue
            if pushed >= max_rooms:
                break
            frames[rid] = render_mock_frame(room, tick=tick + local_tick + hash(rid) % 100)
            pushed += 1
        if local_tick == 1:
            log.info("demo agent pushing frames for %d classrooms", pushed)
        await asyncio.sleep(interval)
