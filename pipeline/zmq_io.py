#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZeroMQ IQ publisher / subscriber (complex64 interleaved)."""

from __future__ import annotations

import struct

import numpy as np
import zmq


MAGIC = b"IQC1"
HEADER = struct.Struct("<4sIdI")  # magic, n_samples, sample_rate, seq


def _normalize_bind_address(address: str) -> str:
    if "://*" in address:
        return address.replace("://*", "://0.0.0.0")
    return address


class ZmqIqPub:
    """PUB socket that binds and streams IQ frames."""

    def __init__(self, address: str = "tcp://127.0.0.1:5555", hwm: int = 10):
        self.address = address
        self.ctx = zmq.Context.instance()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.setsockopt(zmq.SNDHWM, hwm)
        self.sock.bind(_normalize_bind_address(address))
        self._seq = 0

    def send(self, iq: np.ndarray, sample_rate: float) -> None:
        iq = np.ascontiguousarray(iq, dtype=np.complex64)
        header = HEADER.pack(MAGIC, int(iq.size), float(sample_rate), self._seq)
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        try:
            self.sock.send(header + iq.tobytes(), flags=zmq.NOBLOCK)
        except zmq.Again:
            pass

    def close(self) -> None:
        self.sock.close(linger=0)


class ZmqIqSub:
    """SUB socket that connects and receives IQ frames."""

    def __init__(self, address: str = "tcp://127.0.0.1:5555", timeout_ms: int = 1000):
        # Subscribers should connect to a concrete host, not bind wildcards
        connect_addr = address.replace("tcp://*:", "tcp://127.0.0.1:").replace("tcp://0.0.0.0:", "tcp://127.0.0.1:")
        self.address = connect_addr
        self.ctx = zmq.Context.instance()
        self.sock = self.ctx.socket(zmq.SUB)
        self.sock.setsockopt_string(zmq.SUBSCRIBE, "")
        self.sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self.sock.setsockopt(zmq.RCVHWM, 10)
        self.sock.connect(connect_addr)

    def recv(self, block: bool = True) -> tuple[np.ndarray, float, int] | None:
        flags = 0 if block else zmq.NOBLOCK
        try:
            raw = self.sock.recv(flags=flags)
        except zmq.Again:
            return None
        if len(raw) < HEADER.size:
            return None
        magic, n, sample_rate, seq = HEADER.unpack_from(raw)
        if magic != MAGIC:
            return None
        payload = raw[HEADER.size :]
        expected = n * 8  # complex64
        if len(payload) < expected:
            return None
        iq = np.frombuffer(payload, dtype=np.complex64, count=n).copy()
        return iq, float(sample_rate), int(seq)

    def close(self) -> None:
        self.sock.close(linger=0)
