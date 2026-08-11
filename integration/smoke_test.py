#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test: start adapter server as subprocess and verify old protocol."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / "mmdet_adapter_server.py"


def make_dummy_png(path: Path, size: int = 128) -> None:
    """Create a small RGB PNG for protocol testing."""
    try:
        from PIL import Image

        img = Image.new("RGB", (size, size), color=(30, 120, 200))
        for y in range(40, 80):
            for x in range(20, 70):
                img.putpixel((x, y), (255, 220, 40))
        img.save(path)
        return
    except ImportError:
        pass

    # Fallback: write a valid 1x1 PNG without Pillow.
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
            "53de0000000c4944415408d763f8cfc00000000300010005fed4ef00000000"
            "49454e44ae426082"
        )
    )


def read_json_line(proc: subprocess.Popen, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.stdout is None:
            raise RuntimeError("stdout is None")
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise TimeoutError("timeout waiting JSON line from adapter")


def main() -> int:
    print("[smoke] adapter:", ADAPTER)
    if not ADAPTER.is_file():
        print("[smoke] FAIL: adapter file missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="seg_smoke_") as td:
        img_path = Path(td) / "window.png"
        make_dummy_png(img_path)

        cmd = [
            sys.executable,
            str(ADAPTER),
            "--weights",
            "",
            "--model",
            "smoke_model",
            "--threshold",
            "0.1",
            "--imgsz",
            "672",
            "--device",
            "cpu",
            "--force-mock",
        ]
        print("[smoke] starting:", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        try:
            ready = read_json_line(proc, timeout_s=8.0)
            print("[smoke] ready:", ready)
            assert ready.get("status") == "ready", ready

            assert proc.stdin is not None
            proc.stdin.write(str(img_path) + "\n")
            proc.stdin.flush()

            resp = read_json_line(proc, timeout_s=8.0)
            print("[smoke] infer:", resp)
            assert resp.get("status") == "ok", resp
            dets = resp.get("detections", [])
            assert isinstance(dets, list) and len(dets) >= 1, resp
            for d in dets:
                for k in ("x1", "y1", "x2", "y2", "label", "score"):
                    assert k in d, d

            proc.stdin.write("EXIT\n")
            proc.stdin.flush()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            print("SMOKE TEST PASSED")
            return 0
        except Exception as exc:  # noqa: BLE001
            print("[smoke] FAIL:", exc)
            try:
                err = proc.stderr.read() if proc.stderr else ""
                print("[smoke] stderr:", err[:2000])
            except Exception:
                pass
            if proc.poll() is None:
                proc.kill()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
