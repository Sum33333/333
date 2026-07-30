#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapter server: wrap new mmdet/base model into old DetectionClient protocol.

Usage (same CLI as old detection_server.py):
  python mmdet_adapter_server.py --weights ... --model ... --threshold 0.1 --imgsz 672 --device cuda:0

Priority:
1) If mmdet + mmcv + config + weights available -> real mmdet path
2) Else fall back to lightweight mock detections (基础库/联调路径)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    REPO_ROOT / "mmdet_configs" / "my_iq_project" / "my_fasterrcnn_binary_swin_t_iq.py"
)


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
        help="mmdet config .py path (default: repo mmdet_configs/.../my_fasterrcnn_binary_swin_t_iq.py)",
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
        import mmcv  # noqa: F401
        import mmengine  # noqa: F401
        import mmdet  # noqa: F401
        from mmcv.ops import roi_align  # noqa: F401

        return True, "mmcv+mmengine+mmdet import ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"mmdet/mmcv unavailable: {exc}"


def _patch_torch_load_for_mmengine() -> None:
    """PyTorch>=2.6 defaults weights_only=True; mmengine ckpts need False."""
    import torch

    if getattr(torch.load, "_mmdet_adapter_patched", False):
        return

    _orig = torch.load

    def _load(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return _orig(*args, **kwargs)

    _load._mmdet_adapter_patched = True  # type: ignore[attr-defined]
    torch.load = _load  # type: ignore[assignment]


def _resolve_config(args: argparse.Namespace) -> str:
    if args.config:
        return os.path.expanduser(args.config)
    env_cfg = os.environ.get("MMDET_CONFIG", "").strip()
    if env_cfg:
        return os.path.expanduser(env_cfg)
    return str(DEFAULT_CONFIG)


def _class_names(model: Any) -> list[str]:
    meta = getattr(model, "dataset_meta", None) or {}
    classes = meta.get("classes")
    if isinstance(classes, (list, tuple)) and classes:
        return [str(c) for c in classes]
    return ["class_0"]


def _det_to_dicts(result: Any, threshold: float, class_names: list[str]) -> list[dict[str, Any]]:
    """Convert mmdet DetDataSample / legacy results to old DetectionClient schema."""
    pred = getattr(result, "pred_instances", None)
    if pred is None:
        return []

    scores = pred.scores.detach().cpu().tolist()
    bboxes = pred.bboxes.detach().cpu().tolist()
    labels = pred.labels.detach().cpu().tolist()

    out: list[dict[str, Any]] = []
    for score, box, lab in zip(scores, bboxes, labels):
        if float(score) < threshold:
            continue
        if len(box) < 4:
            continue
        idx = int(lab)
        label = class_names[idx] if 0 <= idx < len(class_names) else str(idx)
        out.append(
            {
                "x1": int(round(box[0])),
                "y1": int(round(box[1])),
                "x2": int(round(box[2])),
                "y2": int(round(box[3])),
                "label": label,
                "score": float(score),
            }
        )
    return out


class DetectorBackend:
    """Unified backend used by the stdin/stdout protocol loop."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.mode = "mock"
        self.num_classes = 2
        self._model = None
        self._class_names: list[str] = ["signal", "burst"]
        self._init_error: Optional[str] = None

        has_mmdet, msg = try_import_mmdet()
        weights_ok = bool(args.weights) and os.path.isfile(os.path.expanduser(args.weights))
        config_path = _resolve_config(args)
        config_ok = bool(config_path) and os.path.isfile(config_path)

        if args.force_mock:
            self.mode = "mock"
            self._init_error = "force-mock enabled"
            return

        if has_mmdet and weights_ok and config_ok:
            try:
                self._model = self._build_mmdet_model(config_path)
                self.mode = "mmdet"
                self._class_names = _class_names(self._model)
                self.num_classes = max(1, len(self._class_names))
            except Exception as exc:  # noqa: BLE001
                self.mode = "mock"
                self._init_error = f"mmdet build failed, fallback mock: {exc}"
        else:
            reasons = []
            if not has_mmdet:
                reasons.append(msg)
            if not weights_ok:
                reasons.append("weights missing or not a file")
            if not config_ok:
                reasons.append(f"config missing: {config_path}")
            self.mode = "mock"
            self._init_error = "; ".join(reasons)

    def _build_mmdet_model(self, config_path: str) -> Any:
        _patch_torch_load_for_mmengine()
        from mmdet.apis import init_detector

        weights = os.path.expanduser(self.args.weights)
        return init_detector(config_path, weights, device=self.args.device)

    def run_mmdet_infer(self, image_path: str) -> list[dict[str, Any]]:
        """Run real model and convert output to old detections schema."""
        from mmdet.apis import inference_detector

        result = inference_detector(self._model, image_path)
        return _det_to_dicts(result, self.args.threshold, self._class_names)

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
