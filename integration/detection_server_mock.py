#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mock detection_server compatible with DetectionClient protocol.

Protocol (must keep stable):
- On startup, print one JSON line: {"status":"ready", ...}
- Then read image paths from stdin (one path per line)
- For each path, print one JSON line: {"status":"ok","detections":[...]}
- On line "EXIT", quit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock detector for backend interface test")
    parser.add_argument("--weights", default="mock.pth")
    parser.add_argument("--model", default="mock_detector")
    parser.add_argument("--threshold", type=float, default=0.1)
    parser.add_argument("--imgsz", type=int, default=672)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def emit(obj: dict[str, Any]) -> None:
    """Write one JSON line to stdout and flush immediately."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def mock_detections(image_path: str, imgsz: int, threshold: float) -> list[dict[str, Any]]:
    """Generate deterministic fake boxes from image path + size."""
    # Prefer reading the real image size when PIL is available.
    w = h = imgsz
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            w, h = img.size
    except Exception:
        pass

    # Stable pseudo boxes: two regions that usually survive threshold.
    boxes = [
        {
            "x1": int(w * 0.10),
            "y1": int(h * 0.15),
            "x2": int(w * 0.40),
            "y2": int(h * 0.45),
            "label": "signal",
            "score": 0.88,
        },
        {
            "x1": int(w * 0.55),
            "y1": int(h * 0.50),
            "x2": int(w * 0.90),
            "y2": int(h * 0.85),
            "label": "burst",
            "score": 0.76,
        },
    ]
    return [b for b in boxes if float(b["score"]) >= threshold]


def main() -> int:
    args = parse_args()
    t0 = time.time()
    # Pretend model load cost.
    time.sleep(0.05)
    emit(
        {
            "status": "ready",
            "load_time": round(time.time() - t0, 3),
            "num_classes": 2,
            "model": args.model,
            "device": args.device,
            "weights": args.weights,
        }
    )

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        if path.upper() == "EXIT":
            break

        try:
            dets = mock_detections(path, args.imgsz, args.threshold)
            emit({"status": "ok", "detections": dets})
        except Exception as exc:  # noqa: BLE001 - protocol must always reply
            emit({"status": "error", "message": str(exc)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
