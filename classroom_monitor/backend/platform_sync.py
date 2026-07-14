#!/usr/bin/env python3
"""对接录播平台 / 集控中心 / OpenAPI（无内网时自动降级为本地模拟）。"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import Any

import httpx

from classroom_monitor.backend.config import (
    CENTRAL_CONTROL_API_URL,
    OPENAPI_APP_KEY,
    OPENAPI_BASE_URL,
    OPENAPI_ENABLED,
    RECORDER_API_URL,
)
from classroom_monitor.backend.rooms import Classroom

log = logging.getLogger("platform_sync")


class PlatformClient:
    def __init__(self) -> None:
        self.recorder = RECORDER_API_URL.rstrip("/") if RECORDER_API_URL else ""
        self.central = CENTRAL_CONTROL_API_URL.rstrip("/") if CENTRAL_CONTROL_API_URL else ""
        self.openapi = OPENAPI_BASE_URL.rstrip("/") if OPENAPI_ENABLED and OPENAPI_BASE_URL else ""
        self.app_key = OPENAPI_APP_KEY
        self._timeout = float(os.environ.get("PLATFORM_TIMEOUT", "5.0"))

    @property
    def live(self) -> bool:
        return bool(self.recorder or self.central)

    async def fetch_room_status(self, room_id: str) -> dict[str, Any] | None:
        if not self.central:
            return None
        url = f"{self.central}/rooms/{room_id}/status"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                r = await client.get(url, headers=self._auth_headers())
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            log.debug("central status %s: %s", room_id, exc)
            return None

    async def fetch_snapshot_bytes(self, room_id: str) -> bytes | None:
        if not self.recorder:
            return None
        url = f"{self.recorder}/live/{room_id}/snapshot.jpg"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                r = await client.get(url, headers=self._auth_headers())
                if r.is_success and r.content:
                    return r.content
        except Exception as exc:
            log.debug("recorder snapshot %s: %s", room_id, exc)
        return None

    async def fetch_all_status(self) -> list[dict[str, Any]] | None:
        if not self.central:
            return None
        url = f"{self.central}/rooms"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                r = await client.get(url, headers=self._auth_headers())
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    return data
                return data.get("rooms") or data.get("data")
        except Exception as exc:
            log.warning("central fetch_all failed: %s", exc)
            return None

    def _auth_headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.app_key:
            h["X-App-Key"] = self.app_key
            h["Authorization"] = f"Bearer {self.app_key}"
        return h


def merge_platform_status(room: Classroom, payload: dict[str, Any]) -> Classroom:
    kwargs: dict[str, Any] = {}
    for src, dst in (
        ("status", "status"),
        ("state", "status"),
        ("projector_on", "projector_on"),
        ("projector", "projector_on"),
        ("pc_on", "pc_on"),
        ("pc", "pc_on"),
        ("hdmi_ok", "hdmi_ok"),
        ("hdmi", "hdmi_ok"),
        ("mic_ok", "mic_ok"),
        ("cpu_pct", "cpu_pct"),
        ("cpu", "cpu_pct"),
        ("note", "note"),
        ("alarm", "note"),
        ("stream_url", "stream_url"),
        ("rtsp", "stream_url"),
    ):
        if src in payload and payload[src] is not None:
            kwargs[dst] = payload[src]
    if kwargs.get("stream_url"):
        kwargs["stream_mode"] = "rtsp"
    return replace(room, **kwargs) if kwargs else room
