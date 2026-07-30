# Jetson 上部署 mmdet 详细流程（实装成功版）

> 机器：Jetson Thor（`linux-aarch64`）  
> 环境：conda `usrp_dev`（`/home/sribd/miniforge3/envs/usrp_dev`）  
> Torch：`2.13.0+cu130`（CUDA 13.0）  
> 目标：装好带 CUDA ops 的 `mmcv` + `mmdet`，能加载导师权重并在数据集上出框  
> 日期：2026-07-30（按本机实际跑通步骤整理）

---

## 总顺序（先看这个）

1. 进入 conda 环境，确认 torch / GPU  
2. 用 **conda** 安装与 torch 同版本的 CUDA 编译器（`cuda-nvcc=13.0`）  
3. 用 **conda** 补齐 CUDA 开发库（cublas / cusparse / cusolver）  
4. 设置 `CUDA_HOME` / `CUDA_PATH`（指向 conda 的 `targets/sbsa-linux`）  
5. 源码编译安装 `mmcv==2.1.0`（带 ops）  
6. 确认 `mmdet` / `mmengine` 可用  
7. 准备 config 的 `_base_` 软链 + 权重  
8. 跑适配器 / 数据集推理验证  

**原则（导师要求）：CUDA 用 conda 对齐，不要混用 pip 里的 `site-packages/nvidia/cu13` 当编译工具链。**

---

## 0. 进入环境

```bash
conda activate usrp_dev
 whichtorch  # 应为环境内 python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

预期类似：

```text
2.13.0+cu130 True
```

本仓库路径（本机）：

```bash
cd /home/sribd/333
```

---

## 1. 用 conda 安装 CUDA 编译器（与 torch cu130 对齐）

```bash
conda install -c nvidia/label/cuda-13.0.0 cuda-nvcc=13.0 cuda-cccl=13.0 -y
```

确认用的是 **conda 里的 nvcc**，不是系统或其他路径：

```bash
export PATH="$CONDA_PREFIX/bin:$PATH"
which nvcc
nvcc --version
```

预期：

```text
/home/sribd/miniforge3/envs/usrp_dev/bin/nvcc
Cuda compilation tools, release 13.0, ...
```

---

## 2. 用 conda 安装 CUDA 开发库（头文件 / 链接库）

aarch64 上包名是 `lib*`，**不是** `cuda-cublas-dev`。

```bash
conda install -c nvidia/label/cuda-13.0.0 \
  libcublas-dev \
  libcusparse-dev \
  libcusolver-dev \
  cuda-cudart-dev \
  -y
```

头文件实际位置在：

```text
$CONDA_PREFIX/targets/sbsa-linux/include/
```

检查：

```bash
ls "$CONDA_PREFIX/targets/sbsa-linux/include/cusparse.h"
ls "$CONDA_PREFIX/targets/sbsa-linux/include/cublas_v2.h"
ls "$CONDA_PREFIX/targets/sbsa-linux/include/cusolverDn.h"
```

三个文件都应存在。

> 说明：若编 mmcv 时报缺某个 `*.h`，再按缺什么补对应的 `lib*-dev` 即可。

---

## 3. 设置编译环境变量（每次新开终端都要设）

```bash
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CONDA_PREFIX/bin:$PATH"
export CUDA_PATH="$CONDA_PREFIX/targets/sbsa-linux"
export CPATH="$CUDA_PATH/include:${CPATH:-}"
export LIBRARY_PATH="$CUDA_PATH/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$CUDA_PATH/lib:${LD_LIBRARY_PATH:-}"
```

快速确认：

```bash
echo "$CUDA_PATH"
which nvcc
ls "$CUDA_PATH/include/cusparse.h"
```

---

## 4. 编译安装 mmcv（带 CUDA ops）

依赖（若尚未安装）：

```bash
python -m pip install -U pip
python -m pip install ninja opencv-python-headless
# mmengine / mmdet 若已装可跳过
python -m pip install "mmengine>=0.3.0" "mmdet==3.3.0"
```

编译 mmcv（耗时较长，可能几十分钟）：

```bash
FORCE_CUDA=1 MMCV_WITH_OPS=1 \
  python -m pip install "mmcv==2.1.0" --no-build-isolation --no-cache-dir
```

验证：

```bash
python -c "import mmcv; from mmcv.ops import roi_align; print('mmcv', mmcv.__version__, 'roi_align ok')"
python -c "import mmdet; from mmdet.apis import init_detector, inference_detector; print('mmdet', mmdet.__version__, 'apis ok')"
```

---

## 5. 准备模型 config / 权重

### 5.1 文件位置（本机）

| 用途 | 路径 |
|------|------|
| 权重 | `/home/sribd/111/epoch_100.pth` |
| config | `/home/sribd/333/mmdet_configs/my_iq_project/my_fasterrcnn_binary_swin_t_iq.py` |
| 数据集 | `/home/sribd/111/fixed_time_window_Twin_for_yolo_binary` |

### 5.2 补齐 config 依赖的 `_base_`（只需一次）

config 会引用 `../_base_/...`，仓库里没有这份目录，需软链到 mmdet 自带 configs：

```bash
ln -sfn \
  "$CONDA_PREFIX/lib/python3.11/site-packages/mmdet/.mim/configs/_base_" \
  /home/sribd/333/mmdet_configs/_base_

ls /home/sribd/333/mmdet_configs/_base_/models/faster-rcnn_r50_fpn.py
```

### 5.3 试加载权重

PyTorch≥2.6 默认 `weights_only=True`，mmengine checkpoint 需要临时关闭：

```bash
python - <<'PY'
import torch
_orig = torch.load
def _load(*a, **k):
    k.setdefault("weights_only", False)
    return _orig(*a, **k)
torch.load = _load

from mmdet.apis import init_detector
model = init_detector(
    "/home/sribd/333/mmdet_configs/my_iq_project/my_fasterrcnn_binary_swin_t_iq.py",
    "/home/sribd/111/epoch_100.pth",
    device="cuda:0",
)
print("load ok", type(model).__name__)
PY
```

预期：`load ok FasterRCNN`

---

## 6. 接到旧分割端（DetectionClient 协议）

本仓库适配器：

```text
/home/sribd/333/integration/mmdet_adapter_server.py
```

软链（旧代码仍找 `detection_server.py`）：

```bash
ln -sfn /home/sribd/333/integration/mmdet_adapter_server.py /home/sribd/jetson/detection_server.py
ln -sfn /home/sribd/333/integration/mmdet_adapter_server.py /home/sribd/111/detection_server.py
```

单独测适配器：

```bash
python /home/sribd/333/integration/mmdet_adapter_server.py \
  --weights /home/sribd/111/epoch_100.pth \
  --model fasterrcnn_vitdet \
  --threshold 0.1 \
  --imgsz 672 \
  --device cuda:0 <<'EOF'
/tmp/mm_test.png
EXIT
EOF
```

预期 JSON 中：`"backend_mode": "mmdet"`

无显示器时跑分割端：

```bash
QT_QPA_PLATFORM=offscreen python /home/sribd/111/segmentation_engineer_receiver.py --headless
```

预期：

```text
[SEG] detector ready ...
[SEG] mode=real-detector
[WF-headless] started
```

> 若没有 STFT 往 `tcp://127.0.0.1:5560` 发数据，会出现 `recv=0`，属正常。

---

## 7. 在导师数据集上验框

```bash
cd /home/sribd/333
python integration/infer_mentor_dataset.py --num 5
```

本机实测结果：`images_with_dets=5/5`（均能检出框）。

---

## 8. 常见坑（按出现顺序）

| 现象 | 原因 | 处理 |
|------|------|------|
| `PackagesNotFoundError: cuda-cublas-dev` | aarch64 包名不同 | 改用 `libcublas-dev` 等 |
| `include/cusparse.h` 找不到 | 头文件在 `targets/sbsa-linux` | 设 `CUDA_PATH` + `CPATH` |
| `cusolverDn.h: No such file` | 缺 cusolver 开发包 | `conda install ... libcusolver-dev` |
| `weights_only` UnpicklingError | PyTorch 2.6+ 默认变严 | `torch.load(..., weights_only=False)` |
| `FileNotFoundError: .../_base_/models/...` | 缺 base config | 做第 5.2 节软链 |
| `invalid detector json` | mmengine 日志打到 stdout | 适配器已把非 JSON 重定向到 stderr |
| Qt `xcb` 崩溃 | 无图形界面 | `--headless` + `QT_QPA_PLATFORM=offscreen` |

---

## 9. 最终软件栈一览

```text
conda env: usrp_dev
├── torch 2.13.0+cu130
├── conda CUDA 13.0
│   ├── cuda-nvcc / cuda-cccl
│   ├── libcublas-dev / libcusparse-dev / libcusolver-dev
│   └── targets/sbsa-linux/{include,lib}
├── mmcv 2.1.0 (+ CUDA ops)
├── mmengine
└── mmdet 3.3.0
```

---

## 10. 一句话结论

在 Jetson aarch64 上：**先 conda 对齐 CUDA 13.0 工具链与开发库 → 再编 mmcv → 再跑 mmdet**；不要用 pip 自带的 CUDA wheel 路径去编译。按上述顺序，本机已完成权重加载、旧分割端对接，以及导师 `fixed_time_window_Twin_for_yolo_binary` 数据抽检出框。
