#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapter server: wrap new mmdet/base model into old DetectionClient protocol.

Usage (same CLI as old detection_server.py):
  python mmdet_adapter_server.py --weights ... --model ... --threshold 0.1 --imgsz 672 --device cuda:0

Priority:
1) If mmdet + mmengine available and weights exist -> try real mmdet path
2) Else fall back to lightweight mock detections (基础库/联调路径)

You only need to fill `run_mmdet_infer()` when the real model is ready.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="mmdet/base adapter for old seg backend")
    parser.add_argument("--weights", required=False, default="")
    parser.add_argument("--model", default="fasterrcnn_vitdet")
    parser.add_argument("--threshold", type=float, default=0.1)
    parser.add_argument("--imgsz", type=int, default=672)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--config",
        default="",
        help="Optional mmdet config .py path (if your new model needs it)",
    )
    parser.add_argument(
        "--force-mock",
        action="store_true",
        help="Force mock path even if mmdet is installed",
    )
    return parser.parse_args()


def emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def try_import_mmdet() -> tuple[bool, str]:
    try:
        import mmengine  # noqa: F401
        import mmdet  # noqa: F401

        return True, f"mmengine+mmdet import ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"mmdet/mmengine unavailable: {exc}"


class DetectorBackend:
    """Unified backend used by the stdin/stdout protocol loop."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.mode = "mock"
        self.num_classes = 2
        self._model = None
        self._init_error: Optional[str] = None

        has_mmdet, msg = try_import_mmdet()
        weights_ok = bool(args.weights) and os.path.isfile(os.path.expanduser(args.weights))

        if args.force_mock:
            self.mode = "mock"
            self._init_error = "force-mock enabled"
            return

        if has_mmdet and weights_ok:
            try:
                self._model = self._build_mmdet_model()
                self.mode = "mmdet"
            except Exception as exc:  # noqa: BLE001
                self.mode = "mock"
                self._init_error = f"mmdet build failed, fallback mock: {exc}"
        else:
            reasons = []
            if not has_mmdet:
                reasons.append(msg)
            if not weights_ok:
                reasons.append("weights missing or not a file")
            self.mode = "mock"
            self._init_error = "; ".join(reasons)

    def _build_mmdet_model(self) -> Any:
        """Build real mmdet model.

        TODO(你/实验室): 按新模型的实际 config + checkpoint 写法替换这里。
        下面保留最小占位，避免在没有完整依赖时硬崩。
        """
        # Example placeholder for OpenMMLab style:
        # from mmdet.apis import init_detector
        # config = self.args.config or "configs/xxx.py"
        # return init_detector(config, self.args.weights, device=self.args.device)
        raise RuntimeError(
            "run_mmdet_infer/build not wired yet. "
            "Fill _build_mmdet_model() and run_mmdet_infer() with your new model."
        )

    def run_mmdet_infer(self, image_path: str) -> list[dict[str, Any]]:
        """Run real model and convert output to old detections schema.

        Must return list of:
          {"x1":int, "y1":int, "x2":int, "y2":int, "label":str, "score":float}
        """
        # TODO(你/实验室):
        # from mmdet.apis import inference_detector
        # result = inference_detector(self._model, image_path)
        # Convert result -> old detections, apply self.args.threshold
        raise RuntimeError("run_mmdet_infer() not implemented for the new model yet")

    def run_mock_infer(self, image_path: str) -> list[dict[str, Any]]:
        """基础库/联调路径：不依赖 mmdet，保证协议可测通。"""
        w = h = self.args.imgsz
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                w, h = img.size
        except Exception:
            pass

        boxes = [
            {
                "x1": int(w * 0.12),
                "y1": int(h * 0.18),
                "x2": int(w * 0.42),
                "y2": int(h * 0.48),
                "label": "signal",
                "score": 0.86,
            },
            {
                "x1": int(w * 0.58),
                "y1": int(h * 0.52),
                "x2": int(w * 0.88),
                "y2": int(h * 0.82),
                "label": "burst",
                "score": 0.71,
            },
        ]
        return [b for b in boxes if float(b["score"]) >= self.args.threshold]

    def infer(self, image_path: str) -> list[dict[str, Any]]:
        if self.mode == "mmdet":
            return self.run_mmdet_infer(image_path)
        return self.run_mock_infer(image_path)


def main() -> int:
    args = parse_args()
    t0 = time.time()
    backend = DetectorBackend(args)

    ready = {
        "status": "ready",
        "load_time": round(time.time() - t0, 3),
        "num_classes": backend.num_classes,
        "backend_mode": backend.mode,
        "model": args.model,
        "device": args.device,
    }
    if backend._init_error:
        ready["init_note"] = backend._init_error
    emit(ready)

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        if path.upper() == "EXIT":
            break
        try:
            if not os.path.isfile(path):
                emit({"status": "error", "message": f"image not found: {path}"})
                continue
            dets = backend.infer(path)
            emit({"status": "ok", "detections": dets, "backend_mode": backend.mode})
        except Exception as exc:  # noqa: BLE001
            emit({"status": "error", "message": str(exc)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
