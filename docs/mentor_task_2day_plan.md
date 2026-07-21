# 导师任务 · 两天执行计划（电脑小白版）

> 目标：把**新分割检测模型**接到**上周看过的后端接口**上。  
> 原则：先对齐输入输出，再上 Jetson 装环境；装不上就用基础库版本兜底。

---

## 导师原话拆成 5 步

| 顺序 | 导师要求 | 白话意思 | 你要交什么 |
|------|----------|----------|------------|
| 1 | 找到现有分割检测函数的接口 | 后端现在怎么调用检测器 | 接口位置 + 函数/协议说明 |
| 2 | 确认旧接口输入输出 | 旧系统吃什么、吐什么 | 一张 I/O 对照表 |
| 3 | 分析新模型输入输出的类型、数据量、物理意义 | 新模型要什么图、出什么框，框代表什么 | 新模型 I/O 说明 |
| 4 | 改造新模型 I/O 适配旧接口 | 写一层「翻译器/适配器」 | `detection_server` 兼容程序 |
| 5 | Jetson conda 装 `mmdet`/`mmengine`；失败则装基础库版本 | 板子上跑得起来 | 安装记录 + 能跑通的命令 |

本仓库已提供可本地试跑的适配器骨架（`integration/`），你在 Jetson 上把「真模型」填进去即可。

### 云端已替你试跑的结果（供参考）

| 项目 | 结果 |
|------|------|
| `python3 integration/smoke_test.py` | **通过**（`SMOKE TEST PASSED`） |
| `mmengine` 安装 | 成功（本环境 0.10.7） |
| `mmdet` + `mmcv` | x86 上可用组合示例：`mmcv==2.1.0` + `mmdet==3.3.0`；先装错版本会报兼容错误 |
| Jetson 注意 | 板子架构/CUDA 不同，仍可能装失败 → 按导师说的走基础库/mock 兜底 |
| 本云环境 | **不是 Jetson**，无 GPU；真机安装仍需你在板子上做 |

---

## Day 1（今天）：对齐接口 + 本地跑通骨架

### 上午（约 2–3 小时）— 找旧接口

在 Jetson / 实验室电脑上找这些文件（按优先级）：

1. 分割端主程序（你之前看过的 STFT 瀑布图脚本，常见名如 `seg_engineer*.py`）
2. `DetectionClient` 类（里面有 `subprocess.Popen`）
3. `~/jetson/detection_server.py`（子进程检测服务）

**你要确认的 3 句话（写进笔记）：**

- 主程序怎么启动检测器？（命令行参数有哪些）
- 主程序怎么发一张图？（stdin 写图片路径）
- 检测器怎么回结果？（stdout 一行 JSON）

> 对照文档：`docs/interface_io_analysis.md`

### 下午（约 3–4 小时）— 本地跑通「假模型」适配器

在本仓库执行：

```bash
cd /path/to/this/repo
python3 integration/smoke_test.py
```

期望看到：`SMOKE TEST PASSED`。

然后读懂：

- `integration/detection_server_mock.py`：完全兼容旧协议的假检测器
- `integration/mmdet_adapter_server.py`：以后换真 mmdet 模型的适配器入口

**Day 1 完成标准：**

- [ ] 能指出旧接口在哪（文件名 + 类名）
- [ ] 能说清输入/输出字段
- [ ] `smoke_test.py` 本地跑通

---

## Day 2（明天）：Jetson 环境 + 真模型接入（或基础库兜底）

### 上午 — 装环境

在 **NVIDIA Jetson** 上，先进入 conda 环境再装：

```bash
# 示例：按实验室实际环境名改
conda activate your_env_name

# 先试官方/OpenMMLab 路线（Jetson 经常会失败，失败别慌）
bash integration/install_on_jetson.sh
```

**成功标准：**

```bash
python -c "import mmengine; import mmdet; print('ok', mmengine.__version__, mmdet.__version__)"
```

**失败怎么办（导师说的兜底）：**

- 不要死磕 mmdet 编译
- 改用「基础库版本」：只用 `torch + torchvision + PIL + numpy` 跑检测
- 本仓库适配器在 mmdet 不可用时会自动降级到 mock/基础推理路径

把失败日志保存下来（截图或 `install_log.txt`），汇报时有用。

### 下午 — 把新模型接到适配器

1. 把新模型权重路径填进启动参数 `--weights`
2. 在 `mmdet_adapter_server.py` 的 `run_mmdet_infer()` 里接上真实推理
3. **不要改** stdout JSON 协议（旧后端才能无痛接入）
4. 用一张真实 STFT 窗口 PNG 试推理：

```bash
python integration/mmdet_adapter_server.py \
  --weights /path/to/best_model.pth \
  --model your_model_name \
  --threshold 0.1 \
  --imgsz 672 \
  --device cuda:0
# 进程起来后，手动输入一张图片绝对路径回车，看是否吐出 detections
```

再让旧分割端指向这个新 server（或替换 `~/jetson/detection_server.py`）。

**Day 2 完成标准：**

- [ ] Jetson 上要么 mmdet 可用，要么基础库版本可用（二选一即可）
- [ ] 适配器能按旧协议返回 `ready` / `ok` + `detections`
- [ ] 分割端能收到框（哪怕先是 mock 框也算联通；真模型框更好）

---

## 两天里「不要做」的事

1. 先不要大改分割端 GUI / ZMQ 主循环
2. 先不要重新训练模型
3. 先不要纠结 mmdet 装很久——超过半天没进展就切基础库版本
4. 不要改 JSON 字段名（`x1/y1/x2/y2/label/score`），否则后端对不上

---

## 建议你给导师的汇报结构（晚上发）

1. **旧接口**：文件路径 + 输入输出一句话  
2. **新模型 I/O**：类型、大概数据量、物理意义  
3. **适配方式**：加了哪一层 adapter，协议是否兼容  
4. **环境结果**：mmdet 成功 / 失败原因 + 是否已用基础库版本  
5. **演示**：贴一条 `ready` JSON 和一条 `ok` detections JSON

---

## 需要你向导师/同学再确认的 3 个问题（卡住时再问）

1. 「新分割检测代码」具体是哪个文件夹/哪个 `.py` / 哪份权重？  
2. Jetson 上现成的 conda 环境名字是什么？  
3. 「基础库版本」是不是指不用 mmdet、直接用 torchvision Faster R-CNN / 你们自研脚本？
