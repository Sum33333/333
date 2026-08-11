# 实时管线运行效率与时间（Jetson / usrp_dev）

测量对象：`USRP → untitled1.py(STFT) → segmentation_engineer_receiver → DetectionClient(mmdet) → ZMQ seg.v1`

权重：`/home/sribd/111/epoch_100_stream.pth`  
Config：`mmdet_configs/my_iq_project/my_fasterrcnn_swin_t_iq.py`（14 类）  
设备：`cuda:0`（Thor aarch64）

---

## 总表（答辩/汇报可直接用）

| 模块 | 指标 | 数值 | 效率换算 | 数据来源 |
|------|------|------|----------|----------|
| 检测器加载 | `load_time` | **4.309 s** | 启动一次 | `bench_detector_timing.py` |
| 检测器预热 | 首次推理往返 | **700.28 ms** | 冷启动 | 同上 warmup[0] |
| 检测器稳定往返 | mean / median | **105.92 / 106.61 ms** | **≈ 9.4 FPS**（仅检测） | 同上 n=10 |
| 检测器纯推理 | `detector_infer` | **≈ 105 ms** | 与往返接近 | adapter stderr `[TIMING]` |
| STFT 发布 | 目标 / 实际帧率 | **20.00 / 20.35 FPS** | 间隔 **≈ 49.1 ms** | 实机 USRP 日志 |
| 分割调用节奏 | detect interval | **每 10 帧一次** | 约每 **491 ms** 调一次检 | segmenter 配置日志 |
| 结果发布（推算） | `seg.v1` 速率 | **≈ 2.04 Hz** | 间隔 **≈ 491 ms** | STFT×(1/10) |
| 端到端检测吞吐 | 管线输出检测率 | **≈ 2 次/秒** | 非每帧检测 | 同上 |

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

## 2. STFT 发布（实机日志）

| 项 | 值 |
|----|----|
| 端点 | `tcp://127.0.0.1:5560` |
| 目标帧率 | 20.00 FPS（`--stft-publish-fps 20`） |
| 实际帧率 | **20.35 FPS** |
| 帧间隔 | ≈ 1000/20.35 ≈ **49.1 ms** |

---

## 3. 分割结果发布（由配置推算）

| 项 | 值 |
|----|----|
| 端点 / topic | `tcp://*:5571` / `seg.v1` |
| detect interval | every **10** frames |
| 推算结果速率 | 20.35 / 10 ≈ **2.04 Hz** |
| 推算结果间隔 | ≈ **491 ms** |

未改 segmenter 内部代码；若要 **ZMQ 实测**（不改业务代码）在管线运行时执行：

```bash
python /home/sribd/333/integration/probe_zmq_rates.py --duration 10
```

会打印 `stft` / `result` 的 Hz 与 inter-arrival ms。

---

## 4. 效率结论（给导师）

1. **瓶颈不在检测器**：每 10 帧检测一次，间隔约 491 ms；单次推理约 106 ms，余量约 **4.6×**。
2. **若改为每帧检测**：检测上限约 **9.4 FPS**，会低于 STFT 的 20 FPS，结果会积压或掉帧。
3. **当前管线有效检测吞吐 ≈ 2 Hz**，由 `detect interval=10` 决定，不是模型算力打满。
4. **启动成本**：模型加载约 **4.3 s**（一次性）；首次推理约 **0.7 s**（CUDA 预热）。

---

## 5. 与早期 mock / 旧权重对比（参考）

| 场景 | load_time |
|------|-----------|
| mock | ~0.17–0.24 s |
| 早期 mmdet 实跑（旧权重） | ~3.15–3.36 s |
| 本表 stream 权重 bench | **4.31 s** |
