#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic IQ source that mimics a USRP stream for offline testing."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass
class SimConfig:
    sample_rate: float = 1e6
    center_freq: float = 920e6
    chunk_size: int = 4096
    tone_offset_hz: float = 50e3
    tone_amp: float = 0.35
    noise_sigma: float = 0.08
    qpsk_amp: float = 0.25
    qpsk_symbol_rate: float = 50e3
    realtime: bool = True


class SimIqSource:
    """Generate complex baseband IQ with tone + QPSK + AWGN."""

    def __init__(self, cfg: SimConfig | None = None):
        self.cfg = cfg or SimConfig()
        self._n = 0
        self._phase = 0.0
        self._sym_phase = 0
        self._rng = np.random.default_rng(42)
        self._last_emit = time.perf_counter()
        # Precompute QPSK constellation
        self._qpsk = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j], dtype=np.complex64) / np.sqrt(2)

    def read(self, n: int | None = None) -> np.ndarray:
        cfg = self.cfg
        n = int(n or cfg.chunk_size)
        t0 = self._n / cfg.sample_rate
        t = t0 + np.arange(n, dtype=np.float64) / cfg.sample_rate

        # CW tone offset from DC
        tone = cfg.tone_amp * np.exp(2j * np.pi * cfg.tone_offset_hz * t)

        # Simple QPSK bursts (rectangular pulse, no pulse shaping for speed)
        samples_per_sym = max(1, int(cfg.sample_rate / cfg.qpsk_symbol_rate))
        n_syms = (n + samples_per_sym - 1) // samples_per_sym + 1
        syms = self._qpsk[self._rng.integers(0, 4, size=n_syms)]
        qpsk = np.repeat(syms, samples_per_sym)[:n] * cfg.qpsk_amp

        noise = (self._rng.normal(0, cfg.noise_sigma, n) + 1j * self._rng.normal(0, cfg.noise_sigma, n))

        iq = (tone + qpsk + noise).astype(np.complex64)
        self._n += n

        if cfg.realtime:
            # Pace emission to approximate hardware sample rate
            due = n / cfg.sample_rate
            now = time.perf_counter()
            sleep_for = due - (now - self._last_emit)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_emit = time.perf_counter()

        return iq

    def close(self) -> None:
        return None
