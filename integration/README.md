# 分割检测接入（适配旧后端接口）

给电脑小白用的最短路径：

## 1. 先本地试跑（不需要 Jetson）

```bash
python3 integration/smoke_test.py
```

看到 `SMOKE TEST PASSED` 就说明：

- 子进程协议通了（和旧 `DetectionClient` 一样）
- 适配器能返回 `ready` / `ok` + `detections`

## 2. 文件说明

| 文件 | 干什么 |
|------|--------|
| `detection_server_mock.py` | 假检测器，协议与旧后端一致 |
| `mmdet_adapter_server.py` | 新模型适配器（mmdet 优先，失败自动 mock） |
| `smoke_test.py` | 一键验证协议 |
| `install_on_jetson.sh` | Jetson conda 环境安装脚本 |

## 3. Jetson 上怎么接真模型

1. `conda activate usrp_dev`（或你的环境）
2. 确认 `mmcv` CUDA ops 可用：`python -c "from mmcv.ops import roi_align; print('ok')"`
3. 补齐 config 依赖的 `_base_`（只需一次）：
   ```bash
   ln -sfn "$CONDA_PREFIX/lib/python3.11/site-packages/mmdet/.mim/configs/_base_" \
     /home/sribd/333/mmdet_configs/_base_
   ```
4. 适配器已接好 Faster R-CNN IQ config + `init_detector` / `inference_detector`；
   默认 config：`mmdet_configs/my_iq_project/my_fasterrcnn_binary_swin_t_iq.py`
   （也可用 `--config` 或环境变量 `MMDET_CONFIG`）
5. 用旧分割端原来的方式启动（参数保持 `--weights/--model/--threshold/--imgsz/--device`）

## 4. 千万别改的协议字段

```json
{"status":"ok","detections":[{"x1":0,"y1":0,"x2":10,"y2":10,"label":"signal","score":0.9}]}
```
