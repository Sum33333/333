#!/usr/bin/env python3
"""内置模拟外部 API，用于测试「输入 API → 选教室 → 看画面」流程。"""

from __future__ import annotations

import time
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

from classroom_monitor.backend.mock_stream import render_mock_frame
from classroom_monitor.backend.rooms import PANYU_CLASSROOMS, Classroom

router = APIRouter(prefix="/api/mock-platform", tags=["mock-platform"])

# 完整 171 间番禺课室（与主站演示数据一致）
_MOCK_ROOMS: list[Classroom] = list(PANYU_CLASSROOMS)
_tick = 0


def _room_dict(r: Classroom) -> dict:
    d = asdict(r)
    d["name"] = f"{r.building}{r.room}"
    d["room_name"] = r.room
    d["stream_url"] = ""
    return d


@router.get("/rooms")
def list_rooms():
    return {"rooms": [_room_dict(r) for r in _MOCK_ROOMS]}


@router.get("/rooms/{room_id}/snapshot.jpg")
def snapshot(room_id: str):
    global _tick
    _tick += 1
    room = next((r for r in _MOCK_ROOMS if r.id == room_id), None)
    if not room:
        return Response(status_code=404)
    data = render_mock_frame(room, tick=_tick + hash(room_id) % 50)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/rooms/{room_id}/mjpeg")
async def mjpeg(room_id: str):
    import asyncio

    room = next((r for r in _MOCK_ROOMS if r.id == room_id), None)
    if not room:
        return Response(status_code=404)

    async def gen():
        local = 0
        while True:
            local += 1
            frame = render_mock_frame(room, tick=_tick + local + hash(room_id) % 50)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.33)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/health")
def health():
    return {"ok": True, "name": "JNU Mock Classroom API", "rooms": len(_MOCK_ROOMS)}
