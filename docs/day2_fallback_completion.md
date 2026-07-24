# Day2 完成记录（Jetson 兜底路径）

日期：2026-07-24  
机器：Jetson（aarch64）  
环境：`usrp_dev`（`/home/sribd/miniforge3/envs/usrp_dev`）

## 结论

完整 `mmcv==2.1.0`（带 CUDA ops）在 aarch64 上源码编译失败，已按导师允许的**基础库 / mock 兜底**完成联通验证。

## 环境尝试结果

| 项 | 结果 |
|----|------|
| `torch` + CUDA | 可用 |
| `mmengine` | 已安装 |
| `mmdet` | 已安装，但缺 `mmcv` 时不可完整使用 |
| `mmcv==2.1.0` 带 ops 编译 | **失败**（CUDA compiler / toolkit headers incompatible 等） |
| 基础库 `numpy` + `Pillow` | 可用 |

## 兜底验证证据

### 1) 仓库 smoke test

```text
SMOKE TEST PASSED
backend_mode: mock
```

命令：

```bash
cd ~/333
git checkout cursor/mentor-task-2day-plan-257c
python integration/smoke_test.py
```

### 2) 适配器按旧协议启动（软链到分割端目录）

```bash
ln -s /home/sribd/333/integration/mmdet_adapter_server.py /home/sribd/111/detection_server.py
```

启动结果（ready JSON）：

```json
{"status": "ready", "load_time": 0.177, "num_classes": 2, "backend_mode": "mock", "model": "fasterrcnn_vitdet", "device": "cpu", "init_note": "mmdet/mmengine unavailable: No module named 'mmcv'"}
```

说明：旧 `DetectionClient` 需要的 `detection_server.py` 已就位；无 mmcv 时自动降级 mock，协议字段不变。

### 3) 分割端启动脚本（参数已改到 usrp_dev）

旧默认 `--venv-activate=~/For_torch_installation/.sglang/bin/activate` 已不存在。  
已写入：

`/home/sribd/111/run_segmentation_mock.sh`

核心参数：

- `--venv-activate /home/sribd/miniforge3/envs/usrp_dev/bin/activate`
- `--jetson-dir /home/sribd/111`
- `--weights /home/sribd/111/epoch_100.pth`
- `--device cpu`（当前 mock）

## 旧接口对接方式（未改协议）

- 调用方：`DetectionClient`（`segmentation_engineer_receiver.py`）
- 子进程脚本名仍为：`detection_server.py`
- 实际实现：软链到 `mmdet_adapter_server.py`
- stdout JSON 仍为：`ready` / `ok` + `detections[{x1,y1,x2,y2,label,score}]`

## 给导师的一句话汇报

Jetson aarch64 上 mmcv CUDA 编译失败；已用基础库 mock 适配器替换 `detection_server.py`，`smoke_test` 与 `ready` JSON 验证通过；分割端通过 `run_segmentation_mock.sh` 指向 `usrp_dev` 即可联调。后续若拿到可用 mmcv/预编译包，再把 `backend_mode` 从 mock 切到真模型。
