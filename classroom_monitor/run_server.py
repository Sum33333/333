#!/usr/bin/env python3
"""启动教室监控演示服务。"""

import os
import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(
        "classroom_monitor.backend.main:app",
        host=host,
        port=port,
        reload=False,
    )
