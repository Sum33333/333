#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day1 reference: old detection interface contract (no model code).

This module documents the stable protocol that Day2 adapters must keep.
It is intentionally runnable as a tiny self-check of field names.
"""

from __future__ import annotations

from typing import Any


REQUIRED_DET_KEYS = ("x1", "y1", "x2", "y2", "label", "score")


def validate_ready_message(msg: dict[str, Any]) -> None:
    if msg.get("status") != "ready":
        raise ValueError(f"ready.status expected 'ready', got {msg.get('status')!r}")


def validate_ok_message(msg: dict[str, Any]) -> None:
    if msg.get("status") != "ok":
        raise ValueError(f"ok.status expected 'ok', got {msg.get('status')!r}")
    dets = msg.get("detections")
    if not isinstance(dets, list):
        raise ValueError("ok.detections must be a list")
    for i, d in enumerate(dets):
        for k in REQUIRED_DET_KEYS:
            if k not in d:
                raise ValueError(f"detections[{i}] missing key: {k}")


def example_ready() -> dict[str, Any]:
    return {"status": "ready", "load_time": 0.2, "num_classes": 2}


def example_ok() -> dict[str, Any]:
    return {
        "status": "ok",
        "detections": [
            {
                "x1": 10,
                "y1": 20,
                "x2": 120,
                "y2": 80,
                "label": "signal",
                "score": 0.91,
            }
        ],
    }


if __name__ == "__main__":
    validate_ready_message(example_ready())
    validate_ok_message(example_ok())
    print("Day1 interface contract self-check: OK")
    print("Caller class : DetectionClient")
    print("Wrapper class: WindowSegmenter")
    print("Server script: detection_server.py  (stdin path / stdout JSON)")
    print("Required box fields:", ", ".join(REQUIRED_DET_KEYS))
