#!/usr/bin/env python3
"""用户自定义 API 连接器：输入地址即可拉教室列表与实时画面。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlparse

import httpx

from classroom_monitor.backend.rooms import Classroom, Status

log = logging.getLogger("api_connector")

ROOM_LIST_PATHS = (
    "/rooms",
    "/api/rooms",
    "/classrooms",
    "/api/classrooms",
    "/live/list",
    "/api/live/list",
    "/v1/rooms",
)

SNAPSHOT_PATHS = (
    "/rooms/{id}/snapshot.jpg",
    "/rooms/{id}/frame.jpg",
    "/api/rooms/{id}/snapshot.jpg",
    "/live/{id}/snapshot.jpg",
    "/classrooms/{id}/preview.jpg",
    "/rooms/{id}/preview",
)

MJPEG_PATHS = (
    "/rooms/{id}/mjpeg",
    "/api/rooms/{id}/mjpeg",
    "/live/{id}/mjpeg",
    "/rooms/{id}/stream.mjpg",
)


@dataclass
class ConnectResult:
    ok: bool
    api_url: str
    rooms_path: str
    room_count: int
    message: str
    rooms: list[Classroom] = field(default_factory=list)


@dataclass
class UserApiSession:
    base_url: str
    api_key: str = ""
    rooms_path: str = "/rooms"
    snapshot_template: str = "/rooms/{id}/snapshot.jpg"
    mjpeg_template: str | None = "/rooms/{id}/mjpeg"
    timeout: float = 8.0

    def headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
            h["X-Api-Key"] = self.api_key
        return h

    def _url(self, path: str) -> str:
        base = self.base_url.rstrip("/") + "/"
        path = path.lstrip("/")
        return urljoin(base, path)

    async def test_and_load(self) -> ConnectResult:
        last_err = ""
        for path in ROOM_LIST_PATHS:
            url = self._url(path)
            try:
                async with httpx.AsyncClient(timeout=self.timeout, verify=False, follow_redirects=True) as client:
                    r = await client.get(url, headers=self.headers())
                    if r.status_code >= 400:
                        last_err = f"{path} → HTTP {r.status_code}"
                        continue
                    raw = _parse_room_list(r.json())
                    rooms = [_map_room(item) for item in raw if item]
                    if not rooms:
                        last_err = f"{path} → 空列表"
                        continue
                    snap_tpl, mjpeg_tpl = _guess_stream_paths(self.base_url, path)
                    snap_tpl, mjpeg_tpl = _guess_stream_paths(self.base_url, path)
                    self.rooms_path = path
                    self.snapshot_template = snap_tpl
                    self.mjpeg_template = mjpeg_tpl
                    return ConnectResult(
                        ok=True,
                        api_url=self.base_url,
                        rooms_path=path,
                        room_count=len(rooms),
                        message=f"已连接，发现 {len(rooms)} 间教室",
                        rooms=rooms,
                    )
            except Exception as exc:
                last_err = f"{path} → {exc}"
                log.debug("try %s: %s", url, exc)
        return ConnectResult(
            ok=False,
            api_url=self.base_url,
            rooms_path="",
            room_count=0,
            message=f"无法连接 API：{last_err or '未知错误'}",
        )

    async def fetch_snapshot(self, room_id: str, room: Classroom | None = None) -> bytes | None:
        if room and room.stream_url and room.stream_url.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                    r = await client.get(room.stream_url, headers=self.headers())
                    if r.is_success and r.content and _looks_like_image(r):
                        return r.content
            except Exception as exc:
                log.debug("stream_url %s: %s", room.stream_url, exc)

        templates = [self.snapshot_template] + [p for p in SNAPSHOT_PATHS if p != self.snapshot_template]
        for tpl in templates:
            path = tpl.format(id=room_id)
            url = self._url(path)
            try:
                async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                    r = await client.get(url, headers=self.headers())
                    if r.is_success and r.content and _looks_like_image(r):
                        return r.content
            except Exception:
                continue
        return None

    async def iter_mjpeg(self, room_id: str, room: Classroom | None = None) -> AsyncIterator[bytes]:
        """代理外部 MJPEG；若无流则周期性拉 snapshot。"""
        if self.mjpeg_template:
            url = self._url(self.mjpeg_template.format(id=room_id))
            try:
                async with httpx.AsyncClient(timeout=None, verify=False) as client:
                    async with client.stream("GET", url, headers=self.headers()) as resp:
                        if resp.is_success and "multipart" in resp.headers.get("content-type", "").lower():
                            async for chunk in resp.aiter_bytes():
                                yield chunk
                            return
            except Exception as exc:
                log.debug("mjpeg proxy %s: %s", url, exc)

        import asyncio

        while True:
            data = await self.fetch_snapshot(room_id, room)
            if data:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(0.5)


def _looks_like_image(r: httpx.Response) -> bool:
    ct = r.headers.get("content-type", "").lower()
    if "image" in ct or "jpeg" in ct or "octet-stream" in ct:
        return len(r.content) > 100
    return r.content[:3] == b"\xff\xd8\xff"


def _parse_room_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("rooms", "data", "classrooms", "list", "items", "result"):
            if key in data and isinstance(data[key], list):
                return [x for x in data[key] if isinstance(x, dict)]
    return []


def _map_room(item: dict[str, Any]) -> Classroom:
    rid = str(item.get("id") or item.get("room_id") or item.get("classroomId") or item.get("code") or "")
    name = str(item.get("name") or item.get("room_name") or item.get("room") or rid)
    building = str(item.get("building") or item.get("buildingName") or item.get("building_name") or "教学楼")
    if building == "教学楼" and " · " in name:
        building, name = name.split(" · ", 1)
    elif building == "教学楼" and "-" in name:
        parts = name.split("-", 1)
        if len(parts) == 2:
            building, name = parts[0], parts[1]

    status_raw = str(item.get("status") or item.get("state") or "idle").lower()
    status_map = {
        "online": "idle",
        "using": "in_use",
        "active": "in_use",
        "busy": "in_use",
        "in_use": "in_use",
        "idle": "idle",
        "standby": "idle",
        "offline": "offline",
        "down": "offline",
        "fault": "fault",
        "error": "fault",
        "alarm": "fault",
    }
    status: Status = status_map.get(status_raw, "idle")  # type: ignore[assignment]

    stream_url = str(item.get("stream_url") or item.get("preview_url") or item.get("mjpeg_url") or item.get("rtsp") or "")
    stream_mode = "rtsp" if stream_url.startswith("rtsp") else ("agent" if stream_url else "mock")

    return Classroom(
        id=rid or f"room-{hash(name) % 10**8}",
        building=building,
        room=name if name else rid,
        floor=int(item.get("floor") or 1),
        seats=int(item.get("seats") or item.get("capacity") or 80),
        devices=[d.strip() for d in str(item.get("devices", "PC,投影")).split(",") if d.strip()],
        status=status,
        projector_on=bool(item.get("projector_on", item.get("projector", status != "offline"))),
        pc_on=bool(item.get("pc_on", item.get("pc", status != "offline"))),
        hdmi_ok=bool(item.get("hdmi_ok", item.get("hdmi", True))),
        mic_ok=bool(item.get("mic_ok", item.get("mic", True))),
        cpu_pct=float(item.get("cpu_pct") or item.get("cpu") or 0),
        note=str(item.get("note") or item.get("alarm") or ""),
        stream_mode=stream_mode,  # type: ignore[arg-type]
        stream_url=stream_url,
    )


def _guess_stream_paths(base: str, rooms_path: str) -> tuple[str, str | None]:
    # 若 rooms 在 /api/rooms，snapshot 倾向 /api/rooms/{id}/snapshot.jpg
    prefix = rooms_path.rstrip("/")
    if prefix.endswith("/rooms") or prefix.endswith("/classrooms"):
        root = prefix
    else:
        root = "/rooms"
    return f"{root}/{{id}}/snapshot.jpg", f"{root}/{{id}}/mjpeg"


def normalize_api_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url:
        raise ValueError("API 地址不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        url = "http://" + url
    return url.rstrip("/")
