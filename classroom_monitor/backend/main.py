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

from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from classroom_monitor.backend.config import (
    AGENT_TOKEN,
    CAMPUS,
    CAS_ENABLED,
    CENTRAL_CONTROL_API_URL,
    DEMO_AGENT_PUSH,
    DEMO_MODE,
    NETC_PORTAL_URL,
    ORG_NAME,
    PANYU_CLASSROOM_COUNT_EST,
    PUBLIC_BASE_URL,
    RECORDER_API_URL,
    SUPPORT_EMAIL,
    SUPPORT_PHONE,
    TECHNICIAN_DEVICE_MAC,
)
from classroom_monitor.backend.api_connector import ConnectResult, UserApiSession, normalize_api_url, _guess_stream_paths
from classroom_monitor.backend.cas_auth import cas_login_redirect_url, cas_logout_redirect_url, is_cas_enabled, validate_cas_ticket
from classroom_monitor.backend.demo_agent import demo_agent_loop
from classroom_monitor.backend.mock_stream import jitter_status, render_mock_frame
from classroom_monitor.backend.platform_sync import PlatformClient, merge_platform_status
from classroom_monitor.backend.mock_platform import router as mock_platform_router

from classroom_monitor.backend.rooms import PANYU_CLASSROOMS, Classroom

ADMIN_TOKEN = os.environ.get("CLASSROOM_ADMIN_TOKEN", "jnu-demo-admin")
_DEMO_ROOMS: dict[str, Classroom] = {r.id: r for r in PANYU_CLASSROOMS}
_rooms: dict[str, Classroom] = dict(_DEMO_ROOMS)
_external_mode = False
_user_api: UserApiSession | None = None
_user_api_meta: ConnectResult | None = None
_tick = 0
_rng = random.Random(7)
_ws_clients: set[WebSocket] = set()


def _snapshot() -> dict[str, Any]:
    online = sum(1 for r in _rooms.values() if r.status != "offline")
    in_use = sum(1 for r in _rooms.values() if r.status == "in_use")
    fault = sum(1 for r in _rooms.values() if r.status == "fault")
    return {
        "campus": CAMPUS,
        "org": ORG_NAME,
        "portal": NETC_PORTAL_URL,
        "public_url": PUBLIC_BASE_URL,
        "classroom_capacity_est": PANYU_CLASSROOM_COUNT_EST,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(_rooms),
        "online": online,
        "in_use": in_use,
        "fault": fault,
        "idle": online - in_use - fault,
        "demo_mode": DEMO_MODE and not _external_mode,
        "external_mode": _external_mode,
        "external_api": _user_api.base_url if _user_api else None,
        "platform_live": _platform.live or _external_mode,
        "agent_frames": len(_agent_frames),
        "demo_agent": DEMO_AGENT_PUSH,
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
        if _external_mode and _user_api:
            await _sync_user_api_once()
        else:
            for rid, room in list(_rooms.items()):
                _rooms[rid] = jitter_status(room, _rng)
        await _broadcast({"type": "telemetry", "summary": _snapshot(), "rooms": [asdict(r) for r in _rooms.values()]})
        await asyncio.sleep(2.0)


async def _sync_user_api_once() -> None:
    if not _user_api:
        return
    result = await _user_api.test_and_load()
    if result.ok and result.rooms:
        for r in result.rooms:
            _rooms[r.id] = r
        for rid in list(_agent_frames.keys()):
            if rid not in _rooms:
                del _agent_frames[rid]
    for rid, room in list(_rooms.items()):
        if room.status in ("in_use", "idle", "online"):
            snap = await _user_api.fetch_snapshot(rid, room)
            if snap:
                _agent_frames[rid] = snap


async def _user_api_poll_loop() -> None:
    while True:
        if _external_mode and _user_api:
            for rid, room in list(_rooms.items()):
                if room.status in ("in_use", "idle") or _external_mode:
                    snap = await _user_api.fetch_snapshot(rid, room)
                    if snap:
                        _agent_frames[rid] = snap
        await asyncio.sleep(1.0)


_agent_frames: dict[str, bytes] = {}
_platform = PlatformClient()
_recorder_cache: dict[str, bytes] = {}


async def _platform_sync_loop() -> None:
    """定时从集控/录播平台同步（不可达时静默跳过）。"""
    if not _platform.live:
        return
    while True:
        try:
            bulk = await _platform.fetch_all_status()
            if bulk:
                by_id = {str(x.get("id") or x.get("room_id")): x for x in bulk}
                for rid, room in list(_rooms.items()):
                    if rid in by_id:
                        _rooms[rid] = merge_platform_status(room, by_id[rid])
            for rid, room in list(_rooms.items()):
                if room.status in ("in_use", "idle"):
                    snap = await _platform.fetch_snapshot_bytes(rid)
                    if snap:
                        _recorder_cache[rid] = snap
                        _agent_frames[rid] = snap
        except Exception:
            pass
        await asyncio.sleep(10.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(_telemetry_loop()), asyncio.create_task(_user_api_poll_loop())]
    if _platform.live and not _external_mode:
        tasks.append(asyncio.create_task(_platform_sync_loop()))
    if DEMO_AGENT_PUSH and not _external_mode:
        tasks.append(
            asyncio.create_task(
                demo_agent_loop(_rooms, _agent_frames, lambda: _tick, interval=1.0, max_rooms=50)
            )
        )
    yield
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="暨南大学番禺校区教室监控",
    description="输入 API 地址连接录播/集控平台，选择教室查看实时画面",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(mock_platform_router)

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
    return {
        "ok": True,
        "demo_mode": DEMO_MODE,
        "cas_enabled": is_cas_enabled(),
        "recorder_api": bool(RECORDER_API_URL),
        "central_control_api": bool(CENTRAL_CONTROL_API_URL),
        "platform_live": _platform.live,
        "rooms_loaded": len(_rooms),
        "agent_frames": len(_agent_frames),
    }


def _public_access_url() -> str | None:
    for p in (
        Path(os.environ.get("PUBLIC_URL_FILE", "/workspace/PUBLIC_URL.txt")),
        Path(__file__).resolve().parents[2] / "PUBLIC_URL.txt",
    ):
        if p.is_file():
            url = p.read_text(encoding="utf-8").strip()
            if url.startswith("http"):
                return url
    return None


@app.get("/api/access")
def access_info():
    """返回当前可访问地址（本机 + 公网隧道）。"""
    port = int(os.environ.get("PORT", "8080"))
    return {
        "ok": True,
        "local_url": f"http://127.0.0.1:{port}",
        "public_url": _public_access_url(),
        "health": "/api/health",
    }


@app.get("/api/config")
def public_config():
    """前端初始化：NETC 门户链接、CAS 登录地址等。"""
    return {
        "org": ORG_NAME,
        "campus": CAMPUS,
        "portal_url": NETC_PORTAL_URL,
        "public_url": PUBLIC_BASE_URL,
        "support_phone": SUPPORT_PHONE,
        "support_email": SUPPORT_EMAIL,
        "demo_mode": DEMO_MODE,
        "cas_enabled": is_cas_enabled(),
        "cas_login_url": cas_login_redirect_url() if is_cas_enabled() else None,
        "classroom_capacity_est": PANYU_CLASSROOM_COUNT_EST,
        "rooms_loaded": len(_rooms),
        "demo_agent": DEMO_AGENT_PUSH,
        "mock_api_example": "/api/mock-platform",
        "default_token": "jnu-demo-admin",
        "technician_device_mac": TECHNICIAN_DEVICE_MAC,
        "public_url": _public_access_url(),
    }


@app.get("/api/auth/cas/callback")
def cas_callback(ticket: str = Query(...), service: str | None = None):
    """CAS 登录回调：校验 ticket 后返回会话令牌（生产需换 JWT/Redis 会话）。"""
    user = validate_cas_ticket(ticket, service)
    if not user:
        raise HTTPException(401, "CAS 票据无效或未启用")
    # 演示：直接返回固定格式令牌；生产应签发短期 JWT
    return {
        "jnuid": user,
        "token": ADMIN_TOKEN,
        "message": "CAS 验证通过（演示环境仍使用运维令牌访问 API）",
    }


@app.get("/api/auth/cas/logout")
def cas_logout():
    return {"logout_url": cas_logout_redirect_url()}


@app.get("/api/connect/status")
def connect_status(_: None = Depends(require_admin)):
    return {
        "connected": _external_mode,
        "api_url": _user_api.base_url if _user_api else None,
        "rooms_path": _user_api.rooms_path if _user_api else None,
        "room_count": len(_rooms),
        "message": _user_api_meta.message if _user_api_meta else "未连接外部 API（演示数据）",
    }


@app.post("/api/connect")
async def connect_api(
    payload: dict = Body(...),
    _: None = Depends(require_admin),
):
    """连接用户输入的录播/集控 API，加载教室列表。"""
    global _external_mode, _user_api, _user_api_meta, _rooms

    api_url = normalize_api_url(str(payload.get("api_url", "")))
    api_key = str(payload.get("api_key") or "").strip()
    session = UserApiSession(base_url=api_url, api_key=api_key)
    result = await session.test_and_load()
    if not result.ok:
        raise HTTPException(400, result.message)

    _user_api = session
    _user_api_meta = result
    _external_mode = True
    _rooms = {r.id: r for r in result.rooms}
    _agent_frames.clear()
    session.rooms_path = result.rooms_path
    snap_tpl, mjpeg_tpl = _guess_stream_paths(api_url, result.rooms_path)
    session.snapshot_template = snap_tpl
    session.mjpeg_template = mjpeg_tpl

    for r in result.rooms:
        snap = await session.fetch_snapshot(r.id, r)
        if snap:
            _agent_frames[r.id] = snap

    await _broadcast({"type": "api_connected", "summary": _snapshot(), "rooms": [asdict(r) for r in _rooms.values()]})
    return {
        "ok": True,
        "api_url": api_url,
        "room_count": len(_rooms),
        "message": result.message,
        "rooms_path": result.rooms_path,
    }


@app.post("/api/disconnect")
async def disconnect_api(_: None = Depends(require_admin)):
    """断开外部 API，恢复演示数据。"""
    global _external_mode, _user_api, _user_api_meta, _rooms

    _external_mode = False
    _user_api = None
    _user_api_meta = None
    _rooms = dict(_DEMO_ROOMS)
    _agent_frames.clear()
    await _broadcast({"type": "api_disconnected", "summary": _snapshot(), "rooms": [asdict(r) for r in _rooms.values()]})
    return {"ok": True, "message": "已恢复演示模式", "room_count": len(_rooms)}


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


@app.post("/api/agent/{room_id}/frame")
async def agent_push_frame(
    room_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """教室 Agent 上报 JPEG 帧。"""
    if not AGENT_TOKEN:
        raise HTTPException(501, "未配置 AGENT_TOKEN")
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1]
    if not secrets.compare_digest(supplied, AGENT_TOKEN):
        raise HTTPException(401, "Agent 令牌无效")
    if room_id not in _rooms:
        raise HTTPException(404, "教室不存在")
    body = await request.body()
    if not body:
        raise HTTPException(400, "空帧")
    _agent_frames[room_id] = body
    room = _rooms[room_id]
    if room.stream_mode != "agent":
        from dataclasses import replace
        _rooms[room_id] = replace(room, stream_mode="agent")
    return {"ok": True, "bytes": len(body)}


@app.get("/api/rooms/{room_id}/frame.jpg")
async def room_frame(room_id: str, _: None = Depends(require_admin)):
    room = _rooms.get(room_id)
    if not room:
        raise HTTPException(404, "教室不存在")
    if room_id in _agent_frames:
        return Response(content=_agent_frames[room_id], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    if room_id in _recorder_cache:
        return Response(content=_recorder_cache[room_id], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    if _external_mode and _user_api:
        snap = await _user_api.fetch_snapshot(room_id, room)
        if snap:
            _agent_frames[room_id] = snap
            return Response(content=snap, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    data = render_mock_frame(room, tick=_tick)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/rooms/{room_id}/mjpeg")
async def room_mjpeg(room_id: str, _: None = Depends(require_admin)):
    room = _rooms.get(room_id)
    if not room:
        raise HTTPException(404, "教室不存在")

    if _external_mode and _user_api:
        async def proxy_gen():
            async for chunk in _user_api.iter_mjpeg(room_id, room):
                yield chunk

        return StreamingResponse(proxy_gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    async def gen():
        local_tick = 0
        while True:
            local_tick += 1
            if room_id in _agent_frames:
                frame = _agent_frames[room_id]
            elif room_id in _recorder_cache:
                frame = _recorder_cache[room_id]
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
