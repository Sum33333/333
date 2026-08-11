#!/usr/bin/env python3
"""Quick infer a few images from mentor IQ dataset with local epoch_100.pth."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import torch

_orig = torch.load


def _load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig(*args, **kwargs)


torch.load = _load


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--data-root",
        default="/home/sribd/111/fixed_time_window_Twin_for_yolo_binary",
    )
    p.add_argument(
        "--config",
        default="/home/sribd/333/mmdet_configs/my_iq_project/my_fasterrcnn_binary_swin_t_iq.py",
    )
    p.add_argument("--weights", default="/home/sribd/111/epoch_100.pth")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--threshold", type=float, default=0.1)
    p.add_argument("--num", type=int, default=5)
    p.add_argument("--out", default="/tmp/mentor_data_infer.json")
    args = p.parse_args()

    root = Path(args.data_root)
    img_dirs = [
        root / "images" / "val2017",
        root / "images" / "train2017",
        root / "val2017",
        root / "train2017",
    ]
    imgs: list[Path] = []
    for d in img_dirs:
        if d.is_dir():
            imgs = sorted(
                [x for x in d.iterdir() if x.suffix.lower() in {".png", ".jpg", ".jpeg"}]
            )[: args.num]
            if imgs:
                print(f"[infer] using images from: {d}")
                break
    if not imgs:
        # fallback: any image under root
        imgs = sorted(root.rglob("*.png"))[: args.num]
        if not imgs:
            imgs = sorted(root.rglob("*.jpg"))[: args.num]
    if not imgs:
        raise SystemExit(f"no images found under {root}")

    from mmdet.apis import inference_detector, init_detector

    print(f"[infer] config={args.config}")
    print(f"[infer] weights={args.weights}")
    model = init_detector(args.config, args.weights, device=args.device)
    class_names = list((getattr(model, "dataset_meta", {}) or {}).get("classes") or ["class_0"])

    results = []
    for img in imgs:
        out = inference_detector(model, str(img))
        pred = out.pred_instances
        scores = pred.scores.detach().cpu().tolist()
        bboxes = pred.bboxes.detach().cpu().tolist()
        labels = pred.labels.detach().cpu().tolist()
        dets = []
        for s, b, lab in zip(scores, bboxes, labels):
            if float(s) < args.threshold:
                continue
            name = class_names[int(lab)] if int(lab) < len(class_names) else str(int(lab))
            dets.append(
                {
                    "x1": int(round(b[0])),
                    "y1": int(round(b[1])),
                    "x2": int(round(b[2])),
                    "y2": int(round(b[3])),
                    "label": name,
                    "score": float(s),
                }
            )
        item = {"image": str(img), "num_dets": len(dets), "detections": dets}
        results.append(item)
        print(f"[infer] {img.name}: {len(dets)} boxes")
        for d in dets[:5]:
            print(f"         {d}")

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[infer] wrote {args.out}")
    n_hit = sum(1 for r in results if r["num_dets"] > 0)
    print(f"[infer] images_with_dets={n_hit}/{len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
