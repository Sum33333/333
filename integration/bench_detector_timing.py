#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Benchmark detection-server round-trip timing (load + N infers)."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def make_png(path: Path, size: int = 672) -> None:
    try:
        import numpy as np
        from PIL import Image

        arr = np.random.randint(0, 255, (size, size, 3), dtype=np.uint8)
        Image.fromarray(arr).save(path)
    except Exception:
        path.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
                "53de0000000c4944415408d763f8cfc00000000300010005fed4ef00000000"
                "49454e44ae426082"
            )
        )


def read_json_line(proc: subprocess.Popen, timeout_s: float = 120.0) -> dict:
    deadline = time.time() + timeout_s
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise TimeoutError("timeout waiting JSON from detector")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", default=str(Path(__file__).with_name("mmdet_adapter_server.py")))
    p.add_argument("--weights", required=True)
    p.add_argument("--config", default="")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--threshold", type=float, default=0.1)
    p.add_argument("--imgsz", type=int, default=672)
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--warmup", type=int, default=3)
    args = p.parse_args()

    cmd = [
        sys.executable,
        args.adapter,
        "--weights",
        args.weights,
        "--model",
        "bench",
        "--threshold",
        str(args.threshold),
        "--imgsz",
        str(args.imgsz),
        "--device",
        args.device,
    ]
    if args.config:
        cmd.extend(["--config", args.config])

    print("[bench] cmd:", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None

    try:
        ready = read_json_line(proc, timeout_s=180.0)
        print("[bench] ready:", ready)
        if ready.get("status") != "ready":
            return 1

        with tempfile.TemporaryDirectory(prefix="det_bench_") as td:
            img = Path(td) / "bench.png"
            make_png(img, size=args.imgsz)

            times_ms: list[float] = []
            total = args.warmup + args.runs
            for i in range(total):
                t0 = time.perf_counter()
                proc.stdin.write(str(img) + "\n")
                proc.stdin.flush()
                resp = read_json_line(proc, timeout_s=60.0)
                dt = (time.perf_counter() - t0) * 1000.0
                if resp.get("status") != "ok":
                    print("[bench] bad resp:", resp)
                    return 1
                tag = "warmup" if i < args.warmup else "run"
                print(f"[bench] {tag}[{i}] roundtrip_ms={dt:.2f} n_dets={len(resp.get('detections', []))}")
                if i >= args.warmup:
                    times_ms.append(dt)

            proc.stdin.write("EXIT\n")
            proc.stdin.flush()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

        print("---")
        print(f"[bench] load_time_s={ready.get('load_time')}")
        print(f"[bench] n={len(times_ms)} mean_ms={statistics.mean(times_ms):.2f}")
        print(f"[bench] median_ms={statistics.median(times_ms):.2f}")
        print(f"[bench] min_ms={min(times_ms):.2f} max_ms={max(times_ms):.2f}")
        if len(times_ms) >= 2:
            print(f"[bench] stdev_ms={statistics.stdev(times_ms):.2f}")
        return 0
    finally:
        if proc.poll() is None:
            proc.kill()
        err = proc.stderr.read() if proc.stderr else ""
        if err:
            print("[bench] stderr tail:")
            print("\n".join(err.strip().splitlines()[-30:]))


if __name__ == "__main__":
    raise SystemExit(main())
