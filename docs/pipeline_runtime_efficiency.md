# 实时管线运行效率与时间（Jetson / usrp_dev）

测量对象：`USRP → untitled1.py(STFT) → segmentation_engineer_receiver → DetectionClient(mmdet) → ZMQ seg.v1`

权重：`/home/sribd/111/epoch_100_stream.pth`  
Config：`mmdet_configs/my_iq_project/my_fasterrcnn_swin_t_iq.py`（14 类）  
设备：`cuda:0`（Thor aarch64）  
USRP：`192.168.101.5` / serial `323855A`

---

## 总表（答辩/汇报可直接用）

| 模块 | 指标 | 数值 | 效率换算 | 数据来源 |
|------|------|------|----------|----------|
| 检测器加载 | `load_time` | **4.309 s** | 启动一次 | `bench_detector_timing.py` |
| 检测器预热 | 首次推理往返 | **700.28 ms** | 冷启动 | 同上 warmup[0] |
| 检测器稳定往返 | mean / median | **105.92 / 106.61 ms** | **≈ 9.4 FPS**（仅检测） | 同上 n=10 |
| 检测器纯推理 | `detector_infer` | **≈ 105 ms** | 与往返接近 | adapter stderr `[TIMING]` |
| STFT 发布 `5560` | 实测速率 | **20.30 Hz** | 间隔 mean **49.15 ms** | `probe_zmq_rates.py` 10s |
| 结果发布 `5571` `seg.v1` | 实测速率 | **21.00 Hz** | 间隔 mean **46.89 ms**（突发：p50 **2.58** / p95 **361**） | 同上 |
| result / stft | 发布比 | **1.034** | 结果消息≈跟 STFT 同频 | 同上 |
| 单条结果样例 | events | 41 / 0 / 0 | 有空窗发布 | probe sample |

---

## 1. 检测器（已实测）

命令：

```bash
cd /home/sribd/333
conda activate usrp_dev
python integration/bench_detector_timing.py \
  --weights /home/sribd/111/epoch_100_stream.pth \
  --config /home/sribd/333/mmdet_configs/my_iq_project/my_fasterrcnn_swin_t_iq.py \
  --device cuda:0 \
  --runs 10 --warmup 2
```

结果摘要：

| 项 | 值 |
|----|----|
| load_time | 4.309 s |
| warmup[0] roundtrip | 700.28 ms |
| warmup[1] roundtrip | 88.40 ms |
| stable mean | 105.92 ms |
| stable median | 106.61 ms |
| stable min / max | 100.00 / 108.51 ms |
| stable stdev | 2.39 ms |
| 仅检测理论上限 | ≈ 1000/106.61 ≈ **9.4 FPS** |

说明：稳定阶段往返 ≈ 纯 `detector_infer`，子进程 IPC 开销很小。

---

## 2. STFT 发布（ZMQ 实测 + 日志）

端点：`tcp://127.0.0.1:5560`  
启动：`python untitled1.py --enable-stft-pub --stft-publish-fps 20`

| 项 | 值 |
|----|----|
| 日志目标 / 实际帧率 | 20.00 / **20.35 FPS** |
| ZMQ 实测（10s） | n=203 → **20.30 Hz** |
| inter-arrival mean / p50 / p95 | **49.15 / 49.14 / 49.64 ms** |
| min / max | 48.54 / 50.05 ms |

间隔非常稳，STFT 发布侧健康。

---

## 3. 分割结果发布（ZMQ 实测）

端点 / topic：`tcp://*:5571` / `seg.v1`

| 项 | 值 |
|----|----|
| ZMQ 实测（10s） | n=210 → **21.00 Hz** |
| inter-arrival mean | **46.89 ms** |
| p50 / p95 | **2.58 / 361.25 ms**（突发分布） |
| min / max | 1.84 / 431.58 ms |
| result/stft | **1.034** |
| sample events | 41, 0, 0（含空检测窗） |

复现：

```bash
# 管线运行中
python /home/sribd/333/integration/probe_zmq_rates.py --duration 10
```

说明：结果消息平均与 STFT **同频约 21 Hz**；间隔呈突发（短间隔成对/成簇 + 较长间隙），且会发布 `events=0` 的空结果。这与「仅每 10 帧才调一次检测器」可以并存——发布节奏 ≠ 每次都做重推理。

---

## 4. 效率结论（给导师）

1. **STFT**：约 **20.3 FPS**，帧间隔约 **49 ms**，抖动很小。
2. **检测器算力**：稳定推理约 **106 ms**（约 **9.4 FPS** 上限）；加载 **4.3 s**，首次预热约 **0.7 s**。
3. **结果出口**：`seg.v1` 约 **21 Hz**，与 STFT 基本 1:1；下游应按消息处理，不要假设「每 10 帧才出一条」。
4. **算力余量**：若内部仍按低于 9.4 FPS 的节奏调用检测器，GPU 有余量；若改为每帧检测，会跟不上 20 FPS STFT。
5. **启动成本**：模型加载约 **4.3 s**（一次性）。

---

## 5. 与早期 mock / 旧权重对比（参考）

| 场景 | load_time |
|------|-----------|
| mock | ~0.17–0.24 s |
| 早期 mmdet 实跑（旧权重） | ~3.15–3.36 s |
| 本表 stream 权重 bench | **4.31 s** |
