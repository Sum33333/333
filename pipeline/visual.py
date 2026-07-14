#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Four-panel SDR-style visualizer: spectrum / waterfall / time / constellation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import windows

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize


class IqVisualizer:
    def __init__(
        self,
        sample_rate: float = 1e6,
        center_freq: float = 920e6,
        fft_size: int = 1024,
        waterfall_rows: int = 120,
        title: str = "USRP IQ Pipeline",
    ):
        self.sample_rate = float(sample_rate)
        self.center_freq = float(center_freq)
        self.fft_size = int(fft_size)
        self.waterfall_rows = int(waterfall_rows)
        self.title = title

        self._win = windows.blackmanharris(self.fft_size).astype(np.float64)
        self._win_power = np.sum(self._win**2)
        self._waterfall = np.full((self.waterfall_rows, self.fft_size), -120.0, dtype=np.float32)
        self._last_iq: np.ndarray | None = None
        self._frame = 0

        self.fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), dpi=120)
        self.ax_freq, self.ax_wf = axes[0]
        self.ax_time, self.ax_const = axes[1]
        self.fig.suptitle(self.title, fontsize=13, color="#e8e8e8")
        self.fig.patch.set_facecolor("#12141a")
        for ax in (self.ax_freq, self.ax_wf, self.ax_time, self.ax_const):
            ax.set_facecolor("#0b0d12")
            ax.tick_params(colors="#9aa0a6")
            for spine in ax.spines.values():
                spine.set_color("#2a2f3a")
            ax.xaxis.label.set_color("#c5c9d0")
            ax.yaxis.label.set_color("#c5c9d0")
            ax.title.set_color("#d7dbe2")

        freqs = self._freq_axis_mhz()
        (self.line_psd,) = self.ax_freq.plot(freqs, np.full_like(freqs, -120.0), color="#3DDC97", lw=1.1)
        self.ax_freq.set_ylim(-120, 0)
        self.ax_freq.set_xlim(freqs[0], freqs[-1])
        self.ax_freq.set_xlabel("Frequency (MHz)")
        self.ax_freq.set_ylabel("PSD (dB)")
        self.ax_freq.set_title("Spectrum")
        self.ax_freq.grid(True, alpha=0.25, color="#3a4050")

        self.im_wf = self.ax_wf.imshow(
            self._waterfall,
            aspect="auto",
            origin="lower",
            extent=[freqs[0], freqs[-1], 0, self.waterfall_rows],
            cmap="magma",
            vmin=-110,
            vmax=-20,
            interpolation="nearest",
        )
        self.ax_wf.set_xlabel("Frequency (MHz)")
        self.ax_wf.set_ylabel("History")
        self.ax_wf.set_title("Waterfall")

        (self.line_i,) = self.ax_time.plot([], [], color="#5B8CFF", lw=0.8, label="I")
        (self.line_q,) = self.ax_time.plot([], [], color="#FF7A59", lw=0.8, label="Q")
        self.ax_time.set_ylim(-1.2, 1.2)
        self.ax_time.set_xlabel("Sample")
        self.ax_time.set_ylabel("Amplitude")
        self.ax_time.set_title("Time Domain")
        self.ax_time.legend(loc="upper right", facecolor="#1a1d24", edgecolor="#2a2f3a", labelcolor="#c5c9d0")
        self.ax_time.grid(True, alpha=0.25, color="#3a4050")

        self.sc_const = self.ax_const.scatter([], [], s=4, c="#F0C14A", alpha=0.55, linewidths=0)
        self.ax_const.set_xlim(-1.5, 1.5)
        self.ax_const.set_ylim(-1.5, 1.5)
        self.ax_const.set_aspect("equal")
        self.ax_const.set_xlabel("I")
        self.ax_const.set_ylabel("Q")
        self.ax_const.set_title("Constellation")
        self.ax_const.grid(True, alpha=0.25, color="#3a4050")

        self._stats = self.fig.text(0.01, 0.01, "", fontsize=9, color="#9aa0a6", family="monospace")
        self.fig.tight_layout(rect=[0, 0.03, 1, 0.96])

    def _freq_axis_mhz(self) -> np.ndarray:
        freqs = np.fft.fftshift(np.fft.fftfreq(self.fft_size, d=1.0 / self.sample_rate))
        return (self.center_freq + freqs) / 1e6

    def update(self, iq: np.ndarray, stats: dict | None = None) -> None:
        if iq.size < self.fft_size:
            return
        self._last_iq = iq
        block = iq[: self.fft_size]
        windowed = block * self._win
        spec = np.fft.fftshift(np.fft.fft(windowed))
        psd = 20.0 * np.log10(np.maximum(np.abs(spec) / np.sqrt(self._win_power), 1e-12))

        self._waterfall = np.roll(self._waterfall, -1, axis=0)
        self._waterfall[-1, :] = psd.astype(np.float32)

        freqs = self._freq_axis_mhz()
        self.line_psd.set_data(freqs, psd)
        self.im_wf.set_data(self._waterfall)
        self.im_wf.set_norm(Normalize(vmin=-110, vmax=-20))

        n_show = min(1024, iq.size)
        x = np.arange(n_show)
        self.line_i.set_data(x, iq[:n_show].real)
        self.line_q.set_data(x, iq[:n_show].imag)
        self.ax_time.set_xlim(0, n_show - 1)

        # Decimate for constellation clarity
        step = max(1, iq.size // 2000)
        pts = iq[::step][:2000]
        self.sc_const.set_offsets(np.column_stack([pts.real, pts.imag]))

        if stats:
            self._stats.set_text(
                f"rate={stats.get('msps', 0):.3f} MS/s  "
                f"target={self.sample_rate/1e6:.3f} MS/s  "
                f"fps={stats.get('fps', 0):.1f}  "
                f"latency={stats.get('latency_ms', 0):.2f} ms  "
                f"frames={stats.get('frames', 0)}  "
                f"zmq_ok={stats.get('zmq_ok', '-')}"
            )
        self._frame += 1

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fig.savefig(path, facecolor=self.fig.get_facecolor())
        return path

    def close(self) -> None:
        plt.close(self.fig)
