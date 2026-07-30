# 旧后端检测接口 · 输入输出分析

基于上周分割端代码中的 `DetectionClient` ↔ `detection_server.py` 协议整理。  
目的：让**新模型**只改内部推理，**外层 I/O 保持不变**。

---

## 1. 旧接口在哪里？

| 角色 | 位置（典型） | 作用 |
|------|--------------|------|
| 调用方 | 分割端脚本里的 `class DetectionClient` | 启动子进程、发图片路径、收 JSON |
| 被调用方 | `~/jetson/detection_server.py` | 加载模型、推理、打印 JSON |
| 上层封装 | `class WindowSegmenter` | STFT 窗口 → PNG → 调 DetectionClient → 框映射回频谱 |

调用链：

```text
WindowSegmenter.segment_window()
  → DetectionClient.infer_image(image_path)
      → 子进程 stdin 写入图片路径
      ← 子进程 stdout 读回 JSON
```

---

## 2. 旧接口：启动参数（CLI）

`DetectionClient` 实际拼出来的命令大致是：

```bash
<venv_python> detection_server.py \
  --weights <权重路径> \
  --model <模型名> \
  --threshold 0.1 \
  --imgsz 672 \
  --device cuda:0
```

| 参数 | 类型 | 含义 | 物理意义 |
|------|------|------|----------|
| `--weights` | 字符串路径 | 模型权重文件 | 训练好的网络参数 |
| `--model` | 字符串 | 模型结构名 | 例如 `fasterrcnn_vitdet` |
| `--threshold` | float `[0,1]` | 置信度阈值 | 低于此分数的框丢掉 |
| `--imgsz` | int | 送入网络的边长 | 常见 672：图被缩放到 672×672 |
| `--device` | 字符串 | 推理设备 | `cuda:0` = 第一块 GPU |

---

## 3. 旧接口：运行时输入（stdin）

通信方式：**一行一个命令**（文本）。

| 输入行 | 含义 |
|--------|------|
| `/tmp/seg_window_xxx/window.png` | 要推理的图片绝对路径 |
| `EXIT` | 结束进程 |

### 图片本身的数据含义

| 项目 | 内容 |
|------|------|
| 文件格式 | PNG，RGB |
| 典型尺寸 | `imgsz × imgsz`（如 672×672） |
| 内容来源 | 一段 STFT 瀑布窗口上色后的图 |
| 横轴物理意义* | 频率 bin（频谱格子） |
| 纵轴物理意义* | 时间帧（窗口内相对时间） |
| 颜色物理意义 | 能量强弱（dB 归一化后映射颜色） |

\*若分割端开了 transpose，图上的横纵可能对调；映射回频谱时由 `WindowSegmenter` 负责。

**数据量粗算：**

- 一张 672×672 RGB PNG ≈ 几十 KB～几 MB（视压缩）
- 每窗口推理 1 张图；窗口滑动例如每 10 帧一次

---

## 4. 旧接口：运行时输出（stdout，JSON 行）

### 4.1 启动成功

```json
{"status": "ready", "load_time": 12.3, "num_classes": 2}
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `status` | 字符串 | 固定 `"ready"` |
| `load_time` | 数字 | 模型加载秒数 |
| `num_classes` | 整数 | 类别数 |

### 4.2 推理成功

```json
{
  "status": "ok",
  "detections": [
    {"x1": 10, "y1": 20, "x2": 120, "y2": 80, "label": "signal", "score": 0.91}
  ]
}
```

| 字段 | 类型 | 含义 | 物理意义 |
|------|------|------|----------|
| `x1,y1,x2,y2` | int/float | 框左上/右下像素坐标 | 在**检测图**上的位置（不是最终频率轴） |
| `label` | 字符串 | 类别名 | 如 `signal` / `burst` |
| `score` | float | 置信度 | 模型认为「这是目标」的把握 |

### 4.3 推理失败

```json
{"status": "error", "message": "detector timeout after 15.0s"}
```

---

## 5. 分割端收到框之后还会做什么？

这不属于 `detection_server` 协议，但你要知道「物理意义最终落点」：

1. 像素框 → 映射回 STFT 窗口坐标（频率 bin × 时间帧）
2. 算 `peak_db`、宽高等
3. 打包成 ZMQ 事件 `spectrum_segmentation`
4. GUI 再转成绝对时间 `y1_abs/y2_abs` 画瀑布框

所以：**适配器只要保证检测图坐标系下的框协议正确**，后面旧代码能接上。

---

## 6. 新模型需要对齐的 I/O（你要填的表）

把导师给的新代码填进右列：

| 项目 | 旧接口（已确定） | 新模型（待你填） |
|------|------------------|------------------|
| 输入类型 | PNG 路径 / RGB 图 | ？ |
| 输入尺寸 | 672×672（可配置） | ？ |
| 输入物理意义 | STFT 上色瀑布窗口 | ？是否同一套图 |
| 输出类型 | `detections[]` JSON | ？原始输出是什么 |
| 输出坐标 | 像素 xyxy | ？xyxy / xywh / 归一化 |
| 输出类别 | `label` 字符串 | ？类别 id 还是名字 |
| 单次数据量 | 1 图 → 若干框 | ？ |
| 依赖库 | 旧 torch 脚本 | mmdet / mmengine / 基础库？ |

**适配器要做的事一句话：**

> 把「新模型的原始输出」翻译成上表「旧接口」那一列，一行 JSON 打出来。

---

## 7. 适配原则（写代码时牢记）

1. **stdin / stdout 协议不要改**
2. 内部可以换模型、换预处理
3. 坐标必须落在检测图像素范围（0 ~ imgsz-1）
4. 没有检测到目标时返回 `"detections": []`，不要崩溃
5. 启动后先发 `ready`，否则旧客户端会超时
