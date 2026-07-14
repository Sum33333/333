#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone ZMQ pub/sub integrity + latency smoke test."""

from __future__ import annotations

import time

import numpy as np

from pipeline.zmq_io import ZmqIqPub, ZmqIqSub


def main() -> None:
    addr = "tcp://127.0.0.1:5556"
    pub = ZmqIqPub(addr)
    sub = ZmqIqSub(addr, timeout_ms=500)
    time.sleep(0.3)  # slow-joiner mitigation

    sent = 0
    got = 0
    latencies = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2.0:
        iq = (np.random.randn(2048) + 1j * np.random.randn(2048)).astype(np.complex64)
        t_send = time.perf_counter()
        pub.send(iq, 1e6)
        sent += 1
        for _ in range(5):
            msg = sub.recv()
            if msg is None:
                break
            rx, rate, seq = msg
            got += 1
            latencies.append((time.perf_counter() - t_send) * 1e3)
            assert rx.shape == iq.shape
            assert rate == 1e6
        time.sleep(0.01)

    pub.close()
    sub.close()
    avg = float(np.mean(latencies)) if latencies else float("nan")
    print(
        f"ZMQ smoke: sent={sent} got={got} "
        f"delivery={got/max(sent,1):.1%} avg_latency_ms={avg:.3f}"
    )
    if got < sent * 0.5:
        raise SystemExit("ZMQ delivery too low")


if __name__ == "__main__":
    main()
