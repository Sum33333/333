# 前两周工作整理与系统 Pipeline 报告

整理日期：2026-07-27  
整理人：陈泓森  
用途：向导师汇报前两周进展，并说明泽慧系统完整链路，以及上周 mmdet 未能跑通的原因与结论。

---

## 一、前两周工作内容总览

### 第一周（熟悉检测框架与环境）

| 项目 | 内容 |
|------|------|
| 主要任务 | 熟悉导师提供的目标检测相关代码与配置；安装、配置开发环境；了解模型工具链；按导师要求整理学习笔记 |
| 主要收获 | 初步掌握 PyTorch、mmdet 使用思路、Linux 常用命令、Git、远程开发等方式；对检测配置与代码结构有了整体认识 |
| 主要困难 | 代码模块多、体量大，阅读源码时较难一次理清模块之间的调用关系 |

### 第二周（接口对接 + Jetson 环境 + 联调）

| 项目 | 内容 |
|------|------|
| 主要任务 | 梳理旧分割端检测接口的输入/输出；尝试把新检测权重接到现有后端；在 Jetson 上安装 mmengine / mmdet / mmcv 并测试；安装受阻后改用另一套可运行方案，保证接口链路先通 |
| 已完成 | ① 旧接口协议整理清楚；② 适配层代码写好并接入；③ 分割端无界面模式可成功拉起检测子进程并收到 ready；④ 记录安装失败原因与联调证据 |
| 未完成 / 待继续 | ① 完整 mmcv 仍未装通，暂不能用 `epoch_100.pth` 做真实推理；② 本机缺少频谱数据源时，还看不到实际出框 |

---

## 二、泽慧系统完整 Pipeline（整理）

说明：原分割端脚本不在本 Git 仓库内，以下根据实验室代码（`segmentation_engineer_receiver.py`）与联调结果整理。该系统是当前后端要对接的主体。

### 2.1 一句话概括

系统从频谱数据流入手，把一段时间的 STFT 瀑布图画成窗口图，送给检测服务找信号框，再把框映射回频谱坐标并对外发布。

### 2.2 端到端流程

```text
频谱/STFT 发布端
    │  ZMQ 推送（常见地址：tcp://127.0.0.1:5560）
    ▼
分割接收端 segmentation_engineer_receiver.py
    │  累积瀑布图窗口
    │  渲染成彩色 PNG（频率 × 时间）
    ▼
窗口分割封装 WindowSegmenter
    │  segment_window()
    ▼
检测客户端 DetectionClient
    │  子进程方式启动 detection_server.py
    │  stdin 发送图片路径
    │  stdout 读取 JSON 结果
    ▼
检测服务 detection_server.py（原实现 / 现可替换为适配器）
    │  加载权重并推理
    │  输出检测框
    ▼
WindowSegmenter 把像素框映射回频谱坐标
    │  计算峰值、宽高等属性
    ▼
结果发布（ZMQ，如 tcp://*:5571）
    + 可选 GUI 瀑布图叠加显示
```

### 2.3 关键模块与职责

| 模块 | 作用 |
|------|------|
| STFT / 频谱发布端 | 持续发送频谱帧数据 |
| `segmentation_engineer_receiver.py` | 接收频谱、维护瀑布图、调度检测与发布 |
| `WindowSegmenter` | 窗口切分、画图、调用检测、坐标回映 |
| `DetectionClient` | 管理检测子进程，负责发图、收 JSON |
| `detection_server.py` | 真正做检测的服务进程 |
| 结果发布 | 把分割/检测事件发给下游 |

### 2.4 检测子进程协议（不能随意改）

**启动参数（示例）：**

```bash
python detection_server.py \
  --weights <权重路径> \
  --model <模型名> \
  --threshold 0.1 \
  --imgsz 672 \
  --device cuda:0
```

**运行时通信：**

| 方向 | 内容 | 含义 |
|------|------|------|
| 输入（stdin） | 图片绝对路径（一行） | 对该 STFT 窗口图做检测 |
| 输入（stdin） | `EXIT` | 结束进程 |
| 输出（stdout） | `{"status":"ready", ...}` | 服务已就绪 |
| 输出（stdout） | `{"status":"ok","detections":[...]}` | 本张图检测结果 |
| 输出（stdout） | `{"status":"error","message":"..."}` | 出错 |

**单个检测框字段（必须保留）：**

- `x1, y1, x2, y2`：图上像素坐标  
- `label`：类别名（如 signal / burst）  
- `score`：置信度  

**图片物理含义：**

- 来源：一段 STFT 瀑布窗口上色后的 PNG  
- 尺寸：常见缩放到 672×672  
- 横纵：频率 bin / 时间帧（若做了转置，由 `WindowSegmenter` 负责映回）  
- 颜色：能量强弱  

### 2.5 实验室机器上的关键路径（联调时）

| 用途 | 路径 |
|------|------|
| 分割端脚本 | `/home/sribd/111/segmentation_engineer_receiver.py` |
| 检测服务入口（写死） | `~/jetson/detection_server.py` |
| 权重（写死相对路径） | `~/jetson/outputs/training/.../best_model.pth` |
| 实际权重文件 | `/home/sribd/111/epoch_100.pth` |
| 当前 Python 环境 | conda 环境 `usrp_dev` |
| 适配器代码仓库 | `/home/sribd/333` |

说明：分割端部分路径写死在旧环境上。联调时用软链接把旧路径指到现有环境和适配器，业务逻辑本身未大改。

### 2.6 当前联调状态（相对完整 Pipeline）

| 环节 | 状态 |
|------|------|
| 检测协议与适配器 | 已通（smoke test 通过；分割端可收到 ready） |
| 分割端拉起检测子进程 | 已通（无界面模式） |
| STFT 数据源 `tcp://127.0.0.1:5560` | 联调当时本机无数据，表现为 `recv=0` |
| 用权重做真实检测 | 未通（缺完整 mmcv，见下一节） |

---

## 三、上周为什么 mmdet 没法跑通

目标：在 Jetson 上用 mmdet 加载 `epoch_100.pth` 做真实检测。  
结论先说：**不是接口写错，而是完整 mmcv（带 CUDA 算子）在 ARM 板上编译失败，导致 mmdet 无法真正工作。**

### 3.1 依赖关系（为什么必须装 mmcv）

```text
分割端 DetectionClient
    → detection_server / 适配器
        → mmdet（检测框架）
            → mmcv（底层算子，如 roi_align 等）
                → 与当前 torch / CUDA 匹配
```

`epoch_100.pth` 按 mmdet（Faster R-CNN 一类）训练得到。  
按现有 mmdet 调用路径，没有可用的 mmcv，就无法正常加载该权重做推理。

### 3.2 实验过程与现象

| 步骤 | 操作 | 现象 / 结果 |
|------|------|-------------|
| 1 | 使用 conda 环境 `usrp_dev`，安装 torch | 成功，CUDA 可用 |
| 2 | 安装 mmengine | 成功 |
| 3 | 安装 mmdet | 包装上了，但后续因缺 mmcv 无法完整使用 |
| 4 | 安装完整 mmcv（目标版本约 2.1.0，带 CUDA ops） | 需在 aarch64 上源码编译（官方几乎无对应现成包） |
| 5 | 补齐编译工具与 CUDA 相关头文件（含 `nvidia-cuda-cccl`） | 早期 `nv/target` 缺失问题可解决 |
| 6 | 再次强制编译 mmcv | 失败 |

**关键报错（结论性原文大意）：**

1. `CUDA compiler and CUDA toolkit headers are incompatible`  
   → 编译器用的 CUDA 头文件与 nvcc 不匹配。  
2. 日志提示：检测到的 CUDA 为 13.3，而编译当前 PyTorch 时用的是 13.0  
   → 版本次要号不一致，扩展模块编不过。  
3. 适配器启动时可见：`No module named 'mmcv'`  
   → 运行期确认完整 mmcv 未安装成功。

### 3.3 实验性结论

1. **平台限制明显**  
   Jetson 为 aarch64。官方带 CUDA 的 mmcv 轮子主要面向 x86，板上往往只能源码编译，成本和失败率都更高。

2. **失败点不在“不会 import mmdet”这一句本身**  
   mmdet 包装上后仍会因缺少 mmcv 在真实推理链路中不可用。真正卡点是 **mmcv CUDA 扩展编译失败**。

3. **版本匹配是硬条件**  
   当前环境中 PyTorch 对应 CUDA 13.0，本机 nvcc 为 13.3，头文件/工具链不一致时，mmcv ops 无法编过。强行继续编译收益很低。

4. **因此暂时不能调用 `epoch_100.pth` 做真实推理**  
   不是权重文件坏了，而是运行该权重所需的 mmdet/mmcv 工具链在板上未就绪。

### 3.4 因此采取的另一套方案（已验证）

在不改动旧 JSON 协议的前提下，增加检测适配器：

- 文件：`integration/mmdet_adapter_server.py`  
- 作用：对外仍伪装成 `detection_server.py`；完整依赖可用时走 mmdet，不可用时走模拟检测，保证协议联通  

**验证结果：**

| 验证项 | 结果 |
|--------|------|
| `python integration/smoke_test.py` | `SMOKE TEST PASSED` |
| 单独启动适配器 | 输出 `status=ready`，`backend_mode=mock` |
| 分割端 `--headless` | 出现 `Starting detection subprocess...` 与 `detector ready` |

说明：  
**旧系统 Pipeline 的“检测接口层”已经打通；卡在“真实 mmdet 推理层”。**

### 3.5 后续若要真正跑通 mmdet，需要什么

1. 使用与当前 PyTorch 匹配的 CUDA / mmcv（或实验室提供的 Jetson 预编译包）  
2. 确认 `import mmcv` 且 `from mmcv.ops import roi_align` 可用  
3. 在适配器中接好配置与 `epoch_100.pth` 的真实推理  
4. 接上 STFT 数据源后再做端到端出框验证  

---

## 四、当前总体结论（给导师）

1. **泽慧系统的完整 Pipeline 已梳理清楚**：频谱流 → 瀑布窗口 → PNG → 检测子进程 → JSON 框 → 坐标回映 → 结果发布。  
2. **前两周已完成接口梳理、适配接入、无界面联调**；检测服务可被分割端成功拉起。  
3. **上周 mmdet 没跑通的直接原因**：Jetson aarch64 上完整 mmcv 源码编译失败（CUDA 工具链/头文件与 PyTorch 的 CUDA 版本不一致），导致无法用现有 mmdet 路径加载 `epoch_100.pth` 做真实推理。  
4. **下一步**：在现有已打通的接口上，接入最终要部署的模型方案（待导师说明）。

---

## 五、附录：相关材料位置

| 内容 | 位置 |
|------|------|
| 适配器与联调脚本 | 仓库 `integration/` |
| Day1 接口与完成说明 | `docs/day1_completed_report.md`、`docs/interface_io_analysis.md` |
| Day2 安装与失败记录 | `docs/day2_fallback_completion.md`、`docs/day2_jetson_install_step_by_step.md` |
| 两日任务计划 | `docs/mentor_task_2day_plan.md` |
