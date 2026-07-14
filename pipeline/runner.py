#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end IQ pipeline: source -> (ZMQ) -> visualize / benchmark."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.signal import windows

from pipeline.sim_source import SimConfig, SimIqSource
from pipeline.visual import IqVisualizer
from pipeline.zmq_io import ZmqIqPub, ZmqIqSub


@dataclass
class BenchResult:
    mode: str
    sample_rate: float
    chunk_size: int
    duration_s: float
    chunks: int
    viz_frames: int
    samples: int
    achieved_msps: float
    realtime_ratio: float
    avg_chunk_compute_ms: float
    p95_chunk_compute_ms: float
    avg_viz_fps: float
    zmq_roundtrip_ok: bool | None
    notes: str


def _process_fft_db(iq: np.ndarray, fft_size: int, win: np.ndarray, win_power: float) -> np.ndarray:
    block = iq[:fft_size]
    spec = np.fft.fftshift(np.fft.fft(block * win))
    return 20.0 * np.log10(np.maximum(np.abs(spec) / np.sqrt(win_power), 1e-12))


def run_pipeline(
    sample_rate: float = 1e6,
    center_freq: float = 920e6,
    chunk_size: int = 16384,
    duration_s: float = 5.0,
    enable_zmq: bool = True,
    zmq_address: str = "tcp://127.0.0.1:5555",
    realtime: bool = True,
    fft_size: int = 1024,
    viz_hz: float = 10.0,
    artifact_dir: str | Path = "artifacts",
    save_pngs: bool = True,
) -> BenchResult:
    """Stream IQ on a producer thread; visualize latest buffer at viz_hz."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    src = SimIqSource(
        SimConfig(
            sample_rate=sample_rate,
            center_freq=center_freq,
            chunk_size=chunk_size,
            realtime=False,
        )
    )
    viz = IqVisualizer(
        sample_rate=sample_rate,
        center_freq=center_freq,
        fft_size=fft_size,
        title=f"USRP IQ Pipeline (SIM) @ {center_freq/1e6:.1f} MHz",
    )

    pub = ZmqIqPub(zmq_address) if enable_zmq else None
    sub = ZmqIqSub(zmq_address, timeout_ms=5) if enable_zmq else None
    if enable_zmq:
        time.sleep(0.25)

    latest_lock = threading.Lock()
    latest_iq: list[np.ndarray | None] = [None]
    stop = threading.Event()
    stats = {
        "samples": 0,
        "chunks": 0,
        "compute_times": [],
        "zmq_ok": None,
    }

    def producer() -> None:
        t0 = time.perf_counter()
        while not stop.is_set():
            if time.perf_counter() - t0 >= duration_s:
                break
            if realtime:
                due = t0 + (stats["samples"] / sample_rate)
                delay = due - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)

            t_chunk = time.perf_counter()
            iq = src.read(chunk_size)
            if pub is not None:
                pub.send(iq, sample_rate)
                if sub is not None and (stats["chunks"] % 8 == 0):
                    for _ in range(8):
                        got = sub.recv(block=False)
                        if got is None:
                            break
                        stats["zmq_ok"] = True
            compute_ms = (time.perf_counter() - t_chunk) * 1e3
            stats["compute_times"].append(compute_ms)
            stats["samples"] += iq.size
            stats["chunks"] += 1
            with latest_lock:
                latest_iq[0] = iq

    thread = threading.Thread(target=producer, name="iq-producer", daemon=True)
    t0 = time.perf_counter()
    thread.start()

    viz_frames = 0
    viz_interval = 1.0 / max(viz_hz, 0.1)
    next_viz = t0
    try:
        while thread.is_alive() or (time.perf_counter() - t0) < duration_s:
            now = time.perf_counter()
            if now - t0 >= duration_s + 0.2:
                break
            if now < next_viz:
                time.sleep(min(0.005, next_viz - now))
                continue
            with latest_lock:
                iq = None if latest_iq[0] is None else latest_iq[0].copy()
            if iq is None:
                time.sleep(0.005)
                continue
            elapsed = max(time.perf_counter() - t0, 1e-9)
            achieved = stats["samples"] / elapsed / 1e6
            last_compute = stats["compute_times"][-1] if stats["compute_times"] else 0.0
            viz.update(
                iq,
                stats={
                    "msps": achieved,
                    "fps": viz_frames / elapsed,
                    "latency_ms": last_compute,
                    "frames": viz_frames + 1,
                    "zmq_ok": bool(stats["zmq_ok"]),
                },
            )
            viz_frames += 1
            next_viz = time.perf_counter() + viz_interval

        stop.set()
        thread.join(timeout=2.0)
        if save_pngs:
            # One more refresh from latest buffer
            with latest_lock:
                iq = None if latest_iq[0] is None else latest_iq[0].copy()
            if iq is not None:
                elapsed = max(time.perf_counter() - t0, 1e-9)
                viz.update(
                    iq,
                    stats={
                        "msps": stats["samples"] / elapsed / 1e6,
                        "fps": viz_frames / elapsed,
                        "latency_ms": stats["compute_times"][-1] if stats["compute_times"] else 0.0,
                        "frames": viz_frames,
                        "zmq_ok": bool(stats["zmq_ok"]),
                    },
                )
            final_path = viz.save(artifact_dir / "final_view.png")
            print(f"Saved visual: {final_path}")
    finally:
        stop.set()
        thread.join(timeout=1.0)
        src.close()
        viz.close()
        if pub:
            pub.close()
        if sub:
            sub.close()

    elapsed = max(time.perf_counter() - t0, 1e-9)
    arr = np.array(stats["compute_times"], dtype=np.float64) if stats["compute_times"] else np.array([0.0])
    result = BenchResult(
        mode="sim+zmq" if enable_zmq else "sim",
        sample_rate=sample_rate,
        chunk_size=chunk_size,
        duration_s=elapsed,
        chunks=int(stats["chunks"]),
        viz_frames=viz_frames,
        samples=int(stats["samples"]),
        achieved_msps=stats["samples"] / elapsed / 1e6,
        realtime_ratio=(stats["samples"] / elapsed) / sample_rate,
        avg_chunk_compute_ms=float(arr.mean()),
        p95_chunk_compute_ms=float(np.percentile(arr, 95)),
        avg_viz_fps=viz_frames / elapsed,
        zmq_roundtrip_ok=stats["zmq_ok"],
        notes=f"Synthetic IQ; threaded producer; viz@{viz_hz:.0f}Hz; realtime={realtime}",
    )
    (artifact_dir / "bench_result.json").write_text(json.dumps(asdict(result), indent=2))
    print(json.dumps(asdict(result), indent=2))
    return result


def run_visual_sequence(
    sample_rate: float = 1e6,
    center_freq: float = 920e6,
    frames: int = 30,
    chunk_size: int = 16384,
    artifact_dir: str | Path = "artifacts/visual",
) -> Path:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    src = SimIqSource(
        SimConfig(sample_rate=sample_rate, center_freq=center_freq, chunk_size=chunk_size, realtime=False)
    )
    viz = IqVisualizer(
        sample_rate=sample_rate,
        center_freq=center_freq,
        title=f"USRP IQ Pipeline (SIM) @ {center_freq/1e6:.1f} MHz",
    )
    t0 = time.perf_counter()
    for i in range(1, frames + 1):
        iq = src.read(chunk_size)
        elapsed = time.perf_counter() - t0
        viz.update(
            iq,
            stats={
                "msps": (i * chunk_size) / max(elapsed, 1e-9) / 1e6,
                "fps": i / max(elapsed, 1e-9),
                "latency_ms": 0.0,
                "frames": i,
                "zmq_ok": "-",
            },
        )
        viz.save(artifact_dir / f"frame_{i:04d}.png")
    final = viz.save(artifact_dir / "final_view.png")
    src.close()
    viz.close()

    mp4 = artifact_dir / "preview.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        "10",
        "-i",
        str(artifact_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Saved preview video: {mp4}")
    except Exception as exc:
        print(f"ffmpeg preview skipped: {exc}")
    print(f"Saved visual sequence: {final}")
    return final


def run_process_bench(
    sample_rate: float = 1e6,
    chunk_size: int = 8192,
    duration_s: float = 2.0,
    fft_size: int = 1024,
    artifact_dir: str | Path = "artifacts",
) -> dict:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    src = SimIqSource(SimConfig(sample_rate=sample_rate, chunk_size=chunk_size, realtime=False))
    win = windows.blackmanharris(fft_size).astype(np.float64)
    win_power = float(np.sum(win**2))

    samples = 0
    chunks = 0
    times: list[float] = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration_s:
        t1 = time.perf_counter()
        iq = src.read(chunk_size)
        _ = _process_fft_db(iq, fft_size, win, win_power)
        times.append((time.perf_counter() - t1) * 1e3)
        samples += iq.size
        chunks += 1
    src.close()

    elapsed = max(time.perf_counter() - t0, 1e-9)
    arr = np.asarray(times, dtype=np.float64)
    result = {
        "mode": "process_only",
        "sample_rate_target": sample_rate,
        "chunk_size": chunk_size,
        "fft_size": fft_size,
        "duration_s": elapsed,
        "chunks": chunks,
        "samples": samples,
        "achieved_msps": samples / elapsed / 1e6,
        "realtime_ratio": (samples / elapsed) / sample_rate,
        "avg_chunk_ms": float(arr.mean()),
        "p95_chunk_ms": float(np.percentile(arr, 95)),
    }
    (artifact_dir / "process_bench.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


def run_throughput_sweep(
    rates: list[float] | None = None,
    duration_s: float = 2.0,
    chunk_size: int = 8192,
    artifact_dir: str | Path = "artifacts",
) -> list[dict]:
    rates = rates or [1e6, 2e6, 5e6, 10e6, 20e6]
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        run_process_bench(
            sample_rate=rate,
            chunk_size=chunk_size,
            duration_s=duration_s,
            artifact_dir=artifact_dir / f"sweep_{int(rate/1e6)}Msps",
        )
        for rate in rates
    ]
    path = artifact_dir / "throughput_sweep.json"
    path.write_text(json.dumps(rows, indent=2))
    print(f"Wrote {path}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="USRP-style IQ pipeline (simulation)")
    parser.add_argument("--sample-rate", type=float, default=1e6)
    parser.add_argument("--center-freq", type=float, default=920e6)
    parser.add_argument("--chunk-size", type=int, default=16384)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--no-zmq", action="store_true")
    parser.add_argument("--zmq-address", default="tcp://127.0.0.1:5555")
    parser.add_argument("--no-realtime", action="store_true")
    parser.add_argument("--viz-hz", type=float, default=10.0)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--process-bench", action="store_true")
    parser.add_argument("--visual-sequence", action="store_true")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--artifact-dir", default="artifacts")
    args = parser.parse_args()

    if args.sweep:
        run_throughput_sweep(
            duration_s=args.duration,
            chunk_size=max(args.chunk_size, 8192),
            artifact_dir=args.artifact_dir,
        )
        return
    if args.process_bench:
        run_process_bench(
            sample_rate=args.sample_rate,
            chunk_size=args.chunk_size,
            duration_s=args.duration,
            artifact_dir=args.artifact_dir,
        )
        return
    if args.visual_sequence:
        run_visual_sequence(
            sample_rate=args.sample_rate,
            center_freq=args.center_freq,
            frames=args.frames,
            chunk_size=args.chunk_size,
            artifact_dir=args.artifact_dir,
        )
        return

    run_pipeline(
        sample_rate=args.sample_rate,
        center_freq=args.center_freq,
        chunk_size=args.chunk_size,
        duration_s=args.duration,
        enable_zmq=not args.no_zmq,
        zmq_address=args.zmq_address,
        realtime=not args.no_realtime,
        viz_hz=args.viz_hz,
        artifact_dir=args.artifact_dir,
    )


if __name__ == "__main__":
    main()
