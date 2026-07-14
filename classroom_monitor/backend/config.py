#!/usr/bin/env python3
"""暨南大学 NETC 部署配置。"""

from __future__ import annotations

import os

# 网络与教育技术中心门户（信息公开站，非监控流地址）
NETC_PORTAL_URL = os.environ.get("NETC_PORTAL_URL", "https://netc.jnu.edu.cn/")

# 建议生产部署子域（需向 NETC 申请 DNS + 反向代理）
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "https://classroom.netc.jnu.edu.cn",
)

# 统一身份认证（MyNET / CAS）
CAS_BASE_URL = os.environ.get("CAS_BASE_URL", "https://mynet.jnu.edu.cn/cas")
CAS_LOGIN_URL = f"{CAS_BASE_URL}/login"
CAS_LOGOUT_URL = f"{CAS_BASE_URL}/logout"

# 是否启用 CAS（需向 NETC 申请 CAS 客户端 service URL）
CAS_ENABLED = os.environ.get("CAS_ENABLED", "0") == "1"
CAS_SERVICE_NAME = os.environ.get("CAS_SERVICE_NAME", PUBLIC_BASE_URL.rstrip("/"))

# 番禺校区录播/集控平台 API（校内地址，由 NETC 教育技术部提供）
RECORDER_API_URL = os.environ.get("RECORDER_API_URL", "")
CENTRAL_CONTROL_API_URL = os.environ.get("CENTRAL_CONTROL_API_URL", "")

# 暨南大学 OpenAPI 平台 https://openapi.jnu.edu.cn
OPENAPI_BASE_URL = os.environ.get("OPENAPI_BASE_URL", "https://openapi.jnu.edu.cn")
OPENAPI_APP_KEY = os.environ.get("OPENAPI_APP_KEY", "")
OPENAPI_ENABLED = os.environ.get("OPENAPI_ENABLED", "0") == "1"

DEMO_MODE = os.environ.get("CLASSROOM_DEMO_MODE", "1") != "0"
DEMO_AGENT_PUSH = os.environ.get("DEMO_AGENT_PUSH", "1") == "1"
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "jnu-agent-demo")

ORG_NAME = "暨南大学网络与教育技术中心"
CAMPUS = "番禺校区"
SUPPORT_PHONE = "020-85220304 / 85220305"
SUPPORT_EMAIL = "owl@jnu.edu.cn"

# 番禺校区多媒体课室规模（2026 年三期改造约 171 座，演示清单为子集）
PANYU_CLASSROOM_COUNT_EST = 171
