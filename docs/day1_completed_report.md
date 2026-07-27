# Day 1 任务完成报告

**状态：已完成（本仓库可验证部分）**  
**日期：2026-07-21**

> 说明：实验室 Jetson 上的原始分割端脚本未收录在本 Git 仓库；接口结论来自你提供/上周审阅的分割端源码（含 `DetectionClient` / `WindowSegmenter`），并在本仓库用兼容协议适配器完成联调验证。

---

## 1. Day 1 验收清单

| 验收项 | 结果 |
|--------|------|
| 能指出旧接口文件名 + 类名 | ✅ 完成 |
| 能说清输入/输出字段 | ✅ 完成 |
| `smoke_test.py` 本地跑通 | ✅ 完成（见第 4 节日志） |

对应计划表：`docs/导师任务_Day1_计划表.docx`（已同步勾选版：`docs/导师任务_Day1_计划表_已完成.docx`）

---

## 2. 旧接口在哪里？（导师第 1 步）

| 角色 | 名称 | 作用 |
|------|------|------|
| 分割端主流程 | `_run_headless()` / `_run_gui()` / `main()` | 收 STFT、攒窗口、调用分割、发布结果 |
| 调用方类 | `class DetectionClient` | `subprocess.Popen` 启动检测子进程；stdin 发图；stdout 收 JSON |
| 上层封装 | `class WindowSegmenter` | STFT 窗口 → PNG → `infer_image()` → 框映射回频谱 |
| 被调用方（子进程） | `detection_server.py`（典型目录 `~/jetson/`） | 加载模型并推理 |
| 本仓库兼容实现 | `integration/detection_server_mock.py` | 假检测器，协议一致 |
| 本仓库适配入口 | `integration/mmdet_adapter_server.py` | 新模型适配器（Day 2 用） |

### 调用链（已确认）

```text
main()
  → WindowSegmenter(args)
      → DetectionClient(...)          # 这里 subprocess.Popen 启动 detection_server.py
  → generate_random_events(... segmenter=...)
      → WindowSegmenter.segment_window()
          → DetectionClient.infer_image(image_path)
              → stdin:  "/tmp/.../window.png\n"
              ← stdout: {"status":"ok","detections":[...]}
```

### 启动子进程的关键点

- 类：`DetectionClient.__init__`
- API：`subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, ...)`
- 命令形态：

```bash
<venv_python> detection_server.py \
  --weights <path> \
  --model <name> \
  --threshold 0.1 \
  --imgsz 672 \
  --device cuda:0
```

---

## 3. 旧接口输入 / 输出（导师第 2 步）

### 3.1 启动参数（CLI）

| 参数 | 类型 | 含义 | 物理意义 |
|------|------|------|----------|
| `--weights` | 路径 | 模型权重 | 训练好的网络参数文件 |
| `--model` | 字符串 | 结构名 | 如 `fasterrcnn_vitdet` |
| `--threshold` | float | 置信度阈值 | 低于该分的框丢弃 |
| `--imgsz` | int | 边长 | 检测图缩放到如 672×672 |
| `--device` | 字符串 | 设备 | `cuda:0` / `cpu` |

### 3.2 运行时输入（stdin）

| 输入 | 类型 | 数据量 | 物理意义 |
|------|------|--------|----------|
| 图片绝对路径（一行） | 文本路径 → PNG RGB | 约几十 KB～几 MB / 张 | 一段 STFT 窗口上色后的频谱图 |
| `EXIT` | 文本 | 可忽略 | 关闭检测子进程 |

图片轴含义（经 `WindowSegmenter` 映射后）：

- 一轴 ≈ 频率 bin  
- 一轴 ≈ 时间帧  
- 颜色 ≈ 能量强弱（dB 归一化后 colormap）

### 3.3 运行时输出（stdout，一行一个 JSON）

**就绪：**

```json
{"status": "ready", "load_time": 12.3, "num_classes": 2}
```

**推理成功：**

```json
{
  "status": "ok",
  "detections": [
    {"x1": 10, "y1": 20, "x2": 120, "y2": 80, "label": "signal", "score": 0.91}
  ]
}
```

| 字段 | 类型 | 物理意义 |
|------|------|----------|
| `x1,y1,x2,y2` | 数值 | 检测图像素框（左上/右下） |
| `label` | 字符串 | 类别，如 `signal` / `burst` |
| `score` | float | 置信度 |

**失败：**

```json
{"status": "error", "message": "..."}
```

更完整对照见：`docs/interface_io_analysis.md`

---

## 4. 本地骨架跑通证据（导师衔接第 4 步的前置）

命令：

```bash
python3 integration/smoke_test.py
```

结果：**SMOKE TEST PASSED**

完整日志：`docs/day1_smoke_test_log.txt`

验证了：

1. 子进程可启动并先发 `ready`  
2. stdin 喂图片路径后返回 `ok`  
3. `detections` 含 `x1/y1/x2/y2/label/score`

---

## 5. Day 1 产出物清单（可交差）

| 文件 | 用途 |
|------|------|
| `docs/day1_completed_report.md` | 本完成报告 |
| `docs/interface_io_analysis.md` | 旧接口 I/O 详细分析 |
| `docs/day1_smoke_test_log.txt` | 冒烟测试通过日志 |
| `docs/导师任务_Day1_计划表_已完成.docx` | 计划表勾选完成版 |
| `integration/smoke_test.py` | 可重复验证脚本 |
| `integration/detection_server_mock.py` | 兼容旧协议的假检测器 |
| `integration/mmdet_adapter_server.py` | Day 2 真模型接入入口 |

---

## 6. 交给导师时可以说的 5 句话

1. 旧接口在分割端 `DetectionClient`，通过子进程调用 `detection_server.py`。  
2. 输入是 PNG 路径（STFT 上色窗口图），输出是 JSON 检测框。  
3. 框字段固定为 `x1/y1/x2/y2/label/score`，坐标在检测图像素系。  
4. 本仓库已用兼容适配器跑通 `ready/ok` 协议（`smoke_test` 通过）。  
5. Day 2 只需在适配器里接新模型，**不改**这套 stdin/stdout 协议。

---

## 7. 明确未包含（需实验室机器，不算 Day 1 阻塞）

- Jetson 现场原文件路径的最终确认截图  
- 真实 `~/jetson/detection_server.py` 与权重文件  
- mmdet 真模型推理（属于 Day 2）
