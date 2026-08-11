#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External ZMQ rate probe for live STFT → segmentation pipeline.

Does NOT patch segmenter internals. While the live pipeline is running,
subscribe to:
  - STFT pub  (default tcp://127.0.0.1:5560)
  - result pub (default tcp://127.0.0.1:5571, topic seg.v1)

Reports message count, Hz, and inter-arrival latency stats.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from typing import Any


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _summarize(name: str, gaps_ms: list[float], n: int, elapsed_s: float) -> dict[str, Any]:
    hz = n / elapsed_s if elapsed_s > 0 else 0.0
    out: dict[str, Any] = {
        "name": name,
        "messages": n,
        "elapsed_s": round(elapsed_s, 3),
        "hz": round(hz, 3),
    }
    if gaps_ms:
        s = sorted(gaps_ms)
        out.update(
            {
                "gap_ms_mean": round(statistics.fmean(s), 2),
                "gap_ms_p50": round(_pct(s, 50), 2),
                "gap_ms_p95": round(_pct(s, 95), 2),
                "gap_ms_min": round(s[0], 2),
                "gap_ms_max": round(s[-1], 2),
            }
        )
    return out


def _print_summary(row: dict[str, Any]) -> None:
    print(
        f"[{row['name']}] n={row['messages']}  "
        f"elapsed={row['elapsed_s']:.1f}s  "
        f"rate={row['hz']:.2f} Hz",
        flush=True,
    )
    if "gap_ms_mean" in row:
        print(
            f"  inter-arrival ms: mean={row['gap_ms_mean']:.2f}  "
            f"p50={row['gap_ms_p50']:.2f}  p95={row['gap_ms_p95']:.2f}  "
            f"min={row['gap_ms_min']:.2f}  max={row['gap_ms_max']:.2f}",
            flush=True,
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stft", default="tcp://127.0.0.1:5560", help="STFT ZMQ PUB endpoint")
    p.add_argument("--result", default="tcp://127.0.0.1:5571", help="result ZMQ PUB endpoint")
    p.add_argument("--result-topic", default="seg.v1", help="result topic filter (empty=all)")
    p.add_argument("--stft-topic", default="", help="STFT topic filter (empty=all)")
    p.add_argument("--duration", type=float, default=30.0, help="sample window seconds")
    p.add_argument("--rcv-timeout-ms", type=int, default=200)
    p.add_argument("--json-out", default="", help="optional path to write summary JSON")
    p.add_argument("--no-stft", action="store_true")
    p.add_argument("--no-result", action="store_true")
    args = p.parse_args()

    try:
        import zmq
    except ImportError:
        print("need pyzmq: pip install pyzmq", file=sys.stderr)
        return 1

    ctx = zmq.Context.instance()
    socks: list[tuple[str, Any]] = []

    if not args.no_stft:
        s = ctx.socket(zmq.SUB)
        s.setsockopt(zmq.RCVTIMEO, args.rcv_timeout_ms)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(args.stft)
        s.setsockopt_string(zmq.SUBSCRIBE, args.stft_topic)
        socks.append(("stft", s))
        print(f"[probe] SUB stft   {args.stft} topic={args.stft_topic!r}", flush=True)

    if not args.no_result:
        s = ctx.socket(zmq.SUB)
        s.setsockopt(zmq.RCVTIMEO, args.rcv_timeout_ms)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(args.result)
        s.setsockopt_string(zmq.SUBSCRIBE, args.result_topic)
        socks.append(("result", s))
        print(
            f"[probe] SUB result {args.result} topic={args.result_topic!r}",
            flush=True,
        )

    if not socks:
        print("nothing to probe", file=sys.stderr)
        return 2

    counts = {name: 0 for name, _ in socks}
    gaps: dict[str, list[float]] = {name: [] for name, _ in socks}
    last_t: dict[str, float | None] = {name: None for name, _ in socks}
    sample_events = 0

    print(f"[probe] sampling {args.duration:.1f}s ...", flush=True)
    t0 = time.perf_counter()
    deadline = t0 + args.duration

    poller = zmq.Poller()
    for name, sock in socks:
        poller.register(sock, zmq.POLLIN)
    name_by_sock = {sock: name for name, sock in socks}

    while time.perf_counter() < deadline:
        remaining_ms = max(1, int((deadline - time.perf_counter()) * 1000))
        events = dict(poller.poll(min(args.rcv_timeout_ms, remaining_ms)))
        now = time.perf_counter()
        for sock, ev in events.items():
            if not (ev & zmq.POLLIN):
                continue
            name = name_by_sock[sock]
            try:
                parts = sock.recv_multipart(zmq.NOBLOCK)
            except zmq.Again:
                continue
            counts[name] += 1
            prev = last_t[name]
            if prev is not None:
                gaps[name].append((now - prev) * 1000.0)
            last_t[name] = now
            if name == "result" and sample_events < 3 and parts:
                # best-effort peek at payload size / event count
                payload = parts[-1]
                try:
                    text = payload.decode("utf-8", errors="replace")
                    obj = json.loads(text)
                    n_ev = None
                    if isinstance(obj, dict):
                        data = obj.get("data") or obj
                        result = data.get("result") if isinstance(data, dict) else None
                        if isinstance(result, dict) and "events" in result:
                            n_ev = len(result["events"])
                        elif "events" in obj:
                            n_ev = len(obj["events"])
                    print(
                        f"[probe] result sample#{sample_events+1}: "
                        f"parts={len(parts)} bytes={len(payload)}"
                        + (f" events={n_ev}" if n_ev is not None else ""),
                        flush=True,
                    )
                except Exception:
                    print(
                        f"[probe] result sample#{sample_events+1}: "
                        f"parts={len(parts)} bytes={len(parts[-1])}",
                        flush=True,
                    )
                sample_events += 1

    elapsed = time.perf_counter() - t0
    rows = [_summarize(name, gaps[name], counts[name], elapsed) for name, _ in socks]

    print("---", flush=True)
    for row in rows:
        _print_summary(row)

    # Convenience: if both present, rough end-to-end cadence vs STFT
    by_name = {r["name"]: r for r in rows}
    if "stft" in by_name and "result" in by_name:
        stft_hz = by_name["stft"]["hz"]
        res_hz = by_name["result"]["hz"]
        print("---", flush=True)
        print(
            f"[ratio] result/stft = "
            f"{(res_hz / stft_hz) if stft_hz > 0 else float('nan'):.3f}  "
            f"(result ~{res_hz:.2f} Hz, stft ~{stft_hz:.2f} Hz)",
            flush=True,
        )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"duration_s": args.duration, "channels": rows}, f, indent=2)
        print(f"[probe] wrote {args.json_out}", flush=True)

    for _, sock in socks:
        sock.close(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
