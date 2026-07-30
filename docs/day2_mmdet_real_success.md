# Day2 完成记录（真实 mmdet 路径）

日期：2026-07-30  
机器：Jetson Thor（linux-aarch64，compute capability 11.0）  
环境：conda `usrp_dev`（`/home/sribd/miniforge3/envs/usrp_dev`）

## 结论

按导师要求用 **conda 对齐 CUDA** 后，已在板上编译出带 CUDA ops 的 `mmcv==2.1.0`，并成功把 Faster R-CNN IQ 权重接到旧分割端 `DetectionClient` 协议。  
当前模式为 **真实检测器**（`backend_mode=mmdet` / `mode=real-detector`），不再依赖 mock。

## 环境最终状态

| 项 | 结果 |
|----|------|
| `torch` | `2.13.0+cu130` |
| conda `nvcc` | CUDA 13.0（`$CONDA_PREFIX/bin/nvcc`） |
| CUDA headers | `$CONDA_PREFIX/targets/sbsa-linux/include` |
| `mmcv==2.1.0` + ops | **成功**（`from mmcv.ops import roi_align` ok） |
| `mmdet` | 3.3.0 |
| 权重 | `/home/sribd/111/epoch_100.pth`（软链到 jetson 写死路径） |
| config | `mmdet_configs/my_iq_project/my_fasterrcnn_binary_swin_t_iq.py` |
| `_base_` | 软链到 `mmdet/.mim/configs/_base_` |

## 关键问题与处理（按导师：conda 设 CUDA）

1. 缺头文件：`cusparse.h` / `cublas` / `cusolverDn.h`  
   → `conda install -c nvidia/label/cuda-13.0.0 libcublas-dev libcusparse-dev libcusolver-dev`
2. 包名不是 `cuda-cublas-dev`，aarch64 上是 `libcublas-dev` 等
3. 头文件不在 `$CONDA_PREFIX/include`，而在 `targets/sbsa-linux/include`  
   → 编译前 `export CUDA_PATH=$CONDA_PREFIX/targets/sbsa-linux` 与 `CPATH`
4. PyTorch≥2.6 `weights_only=True` 无法直接加载 mmengine ckpt  
   → 适配器内对可信本地权重临时 `weights_only=False`
5. mmengine 日志污染 stdout → DetectionClient 报 `invalid detector json`  
   → 加载/推理时把非 JSON 输出重定向到 stderr
6. 无显示器 Qt `xcb` 崩溃 → `--headless` + `QT_QPA_PLATFORM=offscreen`

## 验证证据

### 1) 适配器单独跑（真 mmdet）

```json
{"status": "ready", "load_time": 3.269, "num_classes": 1, "backend_mode": "mmdet", "model": "fasterrcnn_vitdet", "device": "cuda:0"}
{"status": "ok", "detections": [], "backend_mode": "mmdet"}
```

（`/tmp/mm_test.png` 为全黑测试图，无框属预期）

### 2) 分割端 headless

```text
[SEG] detector ready, load_time=3.153s, classes=1
[SEG] mode=real-detector
[WF-headless] started
[WF-headless] sources: tcp://127.0.0.1:5560
[WF-headless] segmentation mode: real
[WF-headless] stats recv=0 ...
```

`recv=0`：本机没有 STFT 发布端（`tcp://127.0.0.1:5560`）。有频谱流后才会出 window / 检测框 / pub。

## 接口未改动

- 调用方仍是 `DetectionClient`
- 子进程仍是 `detection_server.py`（软链到 `mmdet_adapter_server.py`）
- JSON 字段仍是 `ready` / `ok` + `detections[{x1,y1,x2,y2,label,score}]`

## 给导师的汇报（可直接转发）

潘博好，按您说的用 conda 对齐 CUDA 后，Jetson `usrp_dev` 上已编过 `mmcv==2.1.0`（CUDA ops 可用），`mmdet` 能加载 `epoch_100.pth` 并走真实推理。旧分割端 `--headless` 已显示 `detector ready` / `mode=real-detector`。当前没有 STFT 源所以 `recv=0`，有 `tcp://127.0.0.1:5560` 数据流后即可联调。请您再说明下最终部署模型与验收方式。
