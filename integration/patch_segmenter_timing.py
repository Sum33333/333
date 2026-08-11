#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch Jetson segmentation_engineer_receiver.py with stage timing logs.

Adds [TIMING] lines on stderr/stdout-safe prints for:
  - render_png (window -> detector image)
  - detector_roundtrip (DetectionClient.infer_image)
  - map_events (boxes -> events)
  - publish (zmq send)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


DEFAULT_TARGET = Path("/home/sribd/111/segmentation_engineer_receiver.py")


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    if not target.is_file():
        print(f"missing: {target}")
        return 1

    bak = target.with_suffix(target.suffix + ".bak_timing")
    if not bak.exists():
        shutil.copy2(target, bak)
        print(f"backup: {bak}")

    text = target.read_text(encoding="utf-8")
    if "[TIMING] module=detector_roundtrip" in text:
        print("already patched")
        return 0

    # Ensure time import exists
    if "import time\n" not in text and "\nimport time\n" not in text:
        text = text.replace("import json\n", "import json\nimport time\n", 1)

    old = '''        scale_row, scale_col = self._make_detection_image(window_db)
        resp = self.client.infer_image(self._tmp_img_path, self.detect_timeout)
        if resp.get("status") != "ok":
            raise RuntimeError(resp.get("message", "detector inference failed"))
        boxes = self._detections_to_window_boxes(
            detections=resp.get("detections", []),
            scale_row=scale_row,
            scale_col=scale_col,
            fft_size=fft_size,
            window_size=window_size,
        )
        boxes = _merge_all_xy_boxes(boxes, iou_threshold)
        events: list[dict] = []
        for i, box in enumerate(boxes):'''

    new = '''        t_render0 = time.perf_counter()
        scale_row, scale_col = self._make_detection_image(window_db)
        t_render_ms = (time.perf_counter() - t_render0) * 1000.0
        t_det0 = time.perf_counter()
        resp = self.client.infer_image(self._tmp_img_path, self.detect_timeout)
        t_det_ms = (time.perf_counter() - t_det0) * 1000.0
        if resp.get("status") != "ok":
            raise RuntimeError(resp.get("message", "detector inference failed"))
        t_map0 = time.perf_counter()
        boxes = self._detections_to_window_boxes(
            detections=resp.get("detections", []),
            scale_row=scale_row,
            scale_col=scale_col,
            fft_size=fft_size,
            window_size=window_size,
        )
        boxes = _merge_all_xy_boxes(boxes, iou_threshold)
        events: list[dict] = []
        for i, box in enumerate(boxes):'''

    if old not in text:
        print("segment_window core block not found; file may have changed")
        return 2
    text = text.replace(old, new, 1)

    # After events built / before return events in segment_window
    old_ret = '''                }
            )
        return events

    def shutdown(self):'''
    new_ret = '''                }
            )
        t_map_ms = (time.perf_counter() - t_map0) * 1000.0
        print(
            f"[TIMING] module=render_png ms={t_render_ms:.2f} | "
            f"module=detector_roundtrip ms={t_det_ms:.2f} | "
            f"module=map_events ms={t_map_ms:.2f} n_events={len(events)}"
        )
        return events

    def shutdown(self):'''
    if old_ret not in text:
        print("return-events block not found")
        return 3
    text = text.replace(old_ret, new_ret, 1)

    # Publish timing (both headless/gui copies if present)
    pub_old = '''                if pub is not None:
                    try:
                        pub.send_string("seg.v1", flags=zmq.SNDMORE)
                        pub.send_string(json.dumps(payload, ensure_ascii=False))
                        stats.published += 1
                    except Exception:
                        stats.publish_fail += 1'''
    pub_new = '''                if pub is not None:
                    try:
                        t_pub0 = time.perf_counter()
                        pub.send_string("seg.v1", flags=zmq.SNDMORE)
                        pub.send_string(json.dumps(payload, ensure_ascii=False))
                        t_pub_ms = (time.perf_counter() - t_pub0) * 1000.0
                        stats.published += 1
                        if stats.published % 20 == 0:
                            print(f"[TIMING] module=publish ms={t_pub_ms:.2f}")
                    except Exception:
                        stats.publish_fail += 1'''
    count = text.count(pub_old)
    if count == 0:
        print("warn: publish block not patched")
    else:
        text = text.replace(pub_old, pub_new)

    target.write_text(text, encoding="utf-8")
    print(f"patched ok: {target} (publish sites={count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
