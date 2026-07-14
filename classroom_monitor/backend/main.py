#!/usr/bin/env python3
"""FastAPI 服务：教室列表、状态、模拟画面流、WebSocket 推送。"""

from __future__ import annotations

import asyncio
import json
import os
import random
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from classroom_monitor.backend.mock_stream import jitter_status, render_mock_frame
from classroom_monitor.backend.rooms import PANYU_CLASSROOMS, Classroom

ADMIN_TOKEN = os.environ.get("CLASSROOM_ADMIN_TOKEN", "jnu-demo-admin")
DEMO_MODE = os.environ.get("CLASSROOM_DEMO_MODE", "1") != "0"

_rooms: dict[str, Classroom] = {r.id: r for r in PANYU_CLASSROOMS}
_rng = random.Random(7)
_tick = 0
_ws_clients: set[WebSocket] = set()


def _snapshot() -> dict[str, Any]:
    online = sum(1 for r in _rooms.values() if r.status != "offline")
    in_use = sum(1 for r in _rooms.values() if r.status == "in_use")
    fault = sum(1 for r in _rooms.values() if r.status == "fault")
    return {
        "campus": "番禺校区",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(_rooms),
        "online": online,
        "in_use": in_use,
        "fault": fault,
        "idle": online - in_use - fault,
        "demo_mode": DEMO_MODE,
    }


async def _broadcast(payload: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    text = json.dumps(payload, ensure_ascii=False)
    for ws in list(_ws_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


async def _telemetry_loop() -> None:
    global _tick
    while True:
        _tick += 1
        for rid, room in list(_rooms.items()):
            _rooms[rid] = jitter_status(room, _rng)
        await _broadcast({"type": "telemetry", "summary": _snapshot(), "rooms": [asdict(r) for r in _rooms.values()]})
        await asyncio.sleep(2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_telemetry_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="暨南大学番禺校区教室监控",
    description="校内运维演示系统 — 默认模拟数据，需部署 Agent 接入真实画面",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(authorization: str | None = Header(default=None), token: str | None = Query(default=None)) -> None:
    supplied = token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1]
    if not supplied or not secrets.compare_digest(supplied, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="需要有效的管理员令牌")


@app.get("/api/health")
def health():
    return {"ok": True, "demo_mode": DEMO_MODE}


@app.get("/api/summary")
def summary(_: None = Depends(require_admin)):
    return _snapshot()


@app.get("/api/rooms")
def list_rooms(
    building: str | None = None,
    status: str | None = None,
    _: None = Depends(require_admin),
):
    rows = list(_rooms.values())
    if building:
        rows = [r for r in rows if r.building == building]
    if status:
        rows = [r for r in rows if r.status == status]
    return [asdict(r) for r in rows]


@app.get("/api/rooms/{room_id}")
def get_room(room_id: str, _: None = Depends(require_admin)):
    room = _rooms.get(room_id)
    if not room:
        raise HTTPException(404, "教室不存在")
    return asdict(room)


_agent_frames: dict[str, bytes] = {}


@app.post("/api/agent/{room_id}/frame")
async def agent_push_frame(
    room_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """教室 Agent 上报 JPEG 帧。"""
    agent_token = os.environ.get("AGENT_TOKEN", "")
    if not agent_token:
        raise HTTPException(501, "未配置 AGENT_TOKEN，Agent 上报未启用")
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1]
    if not secrets.compare_digest(supplied, agent_token):
        raise HTTPException(401, "Agent 令牌无效")
    if room_id not in _rooms:
        raise HTTPException(404, "教室不存在")
    body = await request.body()
    if not body:
        raise HTTPException(400, "空帧")
    _agent_frames[room_id] = body
    return {"ok": True, "bytes": len(body)}


@app.get("/api/rooms/{room_id}/frame.jpg")
def room_frame(room_id: str, _: None = Depends(require_admin)):
    room = _rooms.get(room_id)
    if not room:
        raise HTTPException(404, "教室不存在")
    if room.stream_mode == "agent" and room_id in _agent_frames:
        return Response(content=_agent_frames[room_id], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    data = render_mock_frame(room, tick=_tick)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/rooms/{room_id}/mjpeg")
def room_mjpeg(room_id: str, _: None = Depends(require_admin)):
    room = _rooms.get(room_id)
    if not room:
        raise HTTPException(404, "教室不存在")

    async def gen():
        local_tick = 0
        while True:
            local_tick += 1
            if room.stream_mode == "agent" and room_id in _agent_frames:
                frame = _agent_frames[room_id]
            else:
                frame = render_mock_frame(room, tick=_tick + local_tick)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.33)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")):
    if not secrets.compare_digest(token, ADMIN_TOKEN):
        await ws.close(code=4401)
        return
    await ws.accept()
    _ws_clients.add(ws)
    try:
        await ws.send_text(
            json.dumps(
                {"type": "hello", "summary": _snapshot(), "rooms": [asdict(r) for r in _rooms.values()]},
                ensure_ascii=False,
            )
        )
        while True:
            await ws.receive_text()  # keepalive / ignore client msgs
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(FRONTEND, "index.html")
    if os.path.isfile(index_path):
        return HTMLResponse(open(index_path, encoding="utf-8").read())
    return HTMLResponse("<h1>frontend missing</h1>")
