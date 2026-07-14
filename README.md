# USRP / IQ Realtime Pipeline

Realtime IQ capture with a **simulation path** (no USRP required) and a **hardware path** (GNU Radio + UHD).

```
Sim/USRP Source ──► ZeroMQ PUB (optional)
                 └─► Spectrum / Waterfall / Time / Constellation
```

## Simulation (this environment)

```bash
pip install -r requirements.txt
export PYTHONPATH=.

# Realtime paced stream @ 1 MS/s + ZMQ + 10 Hz visuals
python3 run_pipeline.py --duration 5 --artifact-dir artifacts/demo

# Visual sequence + preview.mp4
python3 run_pipeline.py --visual-sequence --frames 24 --artifact-dir artifacts/visual

# Pure generate+FFT headroom sweep
python3 run_pipeline.py --sweep --duration 2 --artifact-dir artifacts/sweep

# ZMQ integrity smoke
python3 scripts/zmq_smoke.py
```

## Measured results (this cloud VM)

| Test | Result |
|------|--------|
| Realtime stream @ 1 MS/s + ZMQ + viz | **0.96× realtime** (~0.96 MS/s), viz ~9.6 FPS, ZMQ OK |
| Chunk compute | **~0.85 ms** avg / 16k samples |
| ZMQ smoke latency | **~0.4 ms** |
| Process-only headroom | **~23 MS/s** (generate + Blackman-Harris FFT) |
| Headroom vs 20 MS/s target | **~1.16× realtime** |

Artifacts: `artifacts/demo/final_view.png`, `artifacts/visual/preview.mp4`, JSON benches under `artifacts/`.

## Hardware (GNU Radio)

```bash
python3 usrp_rt_capture.py \
  --device-ip 192.168.101.100 \
  --center-freq 920M \
  --sample-rate 1M \
  --receive-gain 10 \
  --enable-zmq \
  --zmq-address tcp://*:5555
```

Cleanups vs original GRC export: channel-0-only setters, RF frequency axis on, optional serial, ZMQ bind default `tcp://*:5555`.
