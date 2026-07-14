#!/usr/bin/env python3
"""CAS / JNUID 登录辅助（需 NETC 签发 CAS 客户端后启用）。"""

from __future__ import annotations

import os
import urllib.parse

import httpx

from classroom_monitor.backend.config import (
    CAS_BASE_URL,
    CAS_ENABLED,
    CAS_LOGIN_URL,
    CAS_LOGOUT_URL,
    CAS_SERVICE_NAME,
)


def cas_login_redirect_url() -> str:
    service = urllib.parse.quote(CAS_SERVICE_NAME, safe="")
    return f"{CAS_LOGIN_URL}?service={service}"


def cas_logout_redirect_url() -> str:
    service = urllib.parse.quote(CAS_SERVICE_NAME, safe="")
    return f"{CAS_LOGOUT_URL}?service={service}"


def validate_cas_ticket(ticket: str, service: str | None = None) -> str | None:
    """
    校验 CAS ticket，返回 JNUID（用户名）。
    生产环境启用 CAS_ENABLED=1 并配置 service URL。
    """
    if not CAS_ENABLED:
        return None
    service = service or CAS_SERVICE_NAME
    url = f"{CAS_BASE_URL}/serviceValidate"
    params = {"ticket": ticket, "service": service, "format": "JSON"}
    try:
        r = httpx.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        success = data.get("serviceResponse", {}).get("authenticationSuccess", {})
        user = success.get("user")
        return str(user) if user else None
    except Exception:
        return None


def is_cas_enabled() -> bool:
    return CAS_ENABLED
