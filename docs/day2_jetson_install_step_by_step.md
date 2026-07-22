# Day2 第3步：Jetson 上安装 mmdet/mmengine（电脑小白逐步手册）

> 目标一句话：让 Jetson 上的 Python 能 `import mmdet`；不行就走基础库/mock 兜底。  
> 你不需要从零写找框 AI，这一步只是在「装跑新模型需要的工具」。

---

## 0. 开始前准备（做之前先弄齐）

请先问导师/同学这 4 个答案，写在纸上：

1. Jetson 怎么登录？（本机键盘鼠标，还是用另一台电脑 SSH）
2. conda 环境名字是什么？（例如 `torch` / `sglang` / `mmdet`）
3. 本仓库代码在 Jetson 上的路径是什么？（例如 `/home/nvidia/333`）
4. 如果没有 conda，实验室平时怎么进 Python 环境？（有时是 `source ~/xxx/bin/activate`）

另外准备：

- 一张纸/备忘录，用来抄命令结果
- 至少 30–60 分钟（安装可能较慢）
- 不要关机、尽量保持网络可用

---

## 1. 打开 Jetson，进入可以打字的黑窗口（终端）

### 1.1 如果你人就在 Jetson 旁边（有屏幕）

1. 打开 Jetson 电源，等到桌面出现  
2. 用鼠标点左下角/应用程序菜单  
3. 搜索并打开：**Terminal**（终端）  
4. 打开后你会看到类似：

```text
nvidia@tegra-ubuntu:~$
```

这就是终端。后面所有命令都敲在这里，敲完按 **Enter（回车）**。

### 1.2 如果你用另一台电脑远程连 Jetson（SSH）

1. 在你自己电脑打开终端（Windows 可用 PowerShell / Windows Terminal）  
2. 问同学要 Jetson 的 IP 和用户名，然后输入（示例）：

```bash
ssh nvidia@192.168.x.x
```

3. 按提示输入密码（输入时屏幕常常不显示小点，这是正常的）  
4. 登录成功后，同样会出现 `用户名@主机名:~$`

---

## 2. 确认你现在在哪、系统能不能用

按顺序执行下面命令，每条敲完回车：

### 2.1 看当前目录

```bash
pwd
```

常见结果：

```text
/home/nvidia
```

### 2.2 看电脑是不是 Jetson（可选，但建议做）

```bash
uname -a
```

输出里通常有 `aarch64`（Jetson 常见架构）。

### 2.3 看有没有 GPU 信息（可选）

```bash
nvidia-smi
```

- 若能显示 GPU 表格：很好  
- 若提示 command not found：先不管，继续装依赖；后面可用 CPU/兜底

---

## 3. 进入 conda 环境（最关键的一步）

### 3.1 先看 conda 在不在

```bash
conda --version
```

#### 结果 A：显示版本号（如 `conda 23.x.x`）

继续 3.2。

#### 结果 B：`conda: command not found`

说明当前终端还没加载 conda。按下面顺序试：

**试法 1（常见）：**

```bash
source ~/miniconda3/etc/profile.d/conda.sh
```

或

```bash
source ~/anaconda3/etc/profile.d/conda.sh
```

然后再：

```bash
conda --version
```

**试法 2：**  
问同学：「我们实验室激活环境的完整命令是什么？」  
有些实验室不用 conda，而用：

```bash
source ~/For_torch_installation/.sglang/bin/activate
```

如果是这种，后面凡是 `conda activate xxx` 都改成这条 `source .../activate`，并且用该环境里的 `python`。

### 3.2 列出所有环境名

```bash
conda env list
```

你会看到类似：

```text
# conda environments:
base                  *  /home/nvidia/miniconda3
torch                    /home/nvidia/miniconda3/envs/torch
sglang                   /home/nvidia/miniconda3/envs/sglang
```

把名字记下来。`*` 表示当前环境。

### 3.3 激活导师指定的环境

把下面的 `环境名` 换成真实名字：

```bash
conda activate 环境名
```

例如：

```bash
conda activate torch
```

成功后，提示符前面通常会出现环境名，例如：

```text
(torch) nvidia@tegra-ubuntu:~$
```

注意左边有 `(torch)` —— 这表示你已经进对环境。

### 3.4 确认你用的是这个环境里的 Python

```bash
which python
python -V
```

期望：

- `which python` 路径里包含环境名（如 `.../envs/torch/bin/python`）
- `python -V` 能显示版本（如 3.8 / 3.10）

如果路径还是 `/usr/bin/python`，说明没激活成功，回到 3.3。

---

## 4. 找到本仓库代码目录

### 4.1 如果你已经把代码放在 Jetson 上

先找目录（按你们实际位置改）：

```bash
ls
```

常见可能：

```bash
cd ~/333
# 或
cd ~/code/333
# 或
cd /home/nvidia/333
```

进入后再确认文件在不在：

```bash
pwd
ls
ls integration
```

你应该能看到：

```text
integration/install_on_jetson.sh
integration/smoke_test.py
integration/mmdet_adapter_server.py
```

只要 `ls integration` 能列出这些文件，就说明目录找对了。

### 4.2 如果 Jetson 上还没有这份代码

**方式 A：U 盘拷贝**

1. 在你自己电脑下载仓库（或从 GitHub 下载 zip）  
2. 拷到 U 盘  
3. 插到 Jetson，复制到例如 `~/333`

**方式 B：git 克隆（有网络时）**

```bash
cd ~
git clone https://github.com/Sum33333/333.git
cd 333
git checkout cursor/mentor-task-2day-plan-257c
ls integration
```

---

## 5. 先装“基础库”（无论 mmdet 成不成功都要）

先确保 `pip` 可用：

```bash
python -m pip --version
```

若报错，先执行：

```bash
python -m ensurepip --upgrade
```

然后安装基础库：

```bash
python -m pip install -U pip
python -m pip install numpy Pillow
```

验证：

```bash
python -c "import numpy; from PIL import Image; print('base ok', numpy.__version__)"
```

必须看到 `base ok ...`。  
如果这里都失败，先别装 mmdet，先找同学解决网络/权限/python 环境问题。

---

## 6. 正式安装 mmengine / mmcv / mmdet

### 6.1 用仓库脚本安装（推荐）

确认你在仓库根目录（能 `ls integration`）：

```bash
pwd
ls integration/install_on_jetson.sh
```

给脚本执行权限（如果还没有）：

```bash
chmod +x integration/install_on_jetson.sh
```

开始安装，并把日志存下来：

```bash
bash integration/install_on_jetson.sh install_log.txt
```

### 6.2 安装时你会看到什么

正常情况会不断刷：

- `Collecting ...`
- `Downloading ...`
- `Installing collected packages ...`

这可能要几分钟到几十分钟。  
**中间不要 Ctrl+C，不要关终端。**

### 6.3 如果脚本中途失败

不要清空屏幕。先看最后 30 行有没有 `ERROR` / `failed`。  
日志文件在当前目录：

```bash
pwd
ls -l install_log.txt
tail -n 50 install_log.txt
```

把 `install_log.txt` 留着（可拷走或截图），汇报时有用。

---

## 7. 验证 mmdet 有没有装成功（最关键验收）

在同一个已激活的环境里执行：

```bash
python -c "import mmengine, mmdet; print('ok', mmengine.__version__, mmdet.__version__)"
```

---

## 8. 成功分支：看到 `ok ...` 之后做什么

说明第 3 步（装依赖）成功了。接着做“能启动适配器”的最小验证：

### 8.1 先跑协议自测

```bash
python integration/smoke_test.py
```

期望最后一行：

```text
SMOKE TEST PASSED
```

### 8.2 再手动启动适配器看 ready

```bash
python integration/mmdet_adapter_server.py --device cuda:0
```

期望先输出一行 JSON，类似：

```json
{"status":"ready", ...}
```

然后：

1. 打开另一个终端（或先 `Ctrl+C` 停掉也行；若要继续测推理就保持运行）  
2. 若保持运行：在当前窗口输入一张图片的绝对路径，回车  
3. 再输入：

```text
EXIT
```

> 注意：这时如果还没接真模型权重，适配器可能仍走 mock（日志里会有 `backend_mode: mock` 或 `init_note`）。  
> 对「第3步装依赖」来说，`import mmengine, mmdet` 成功就已经达标。  
> 接真模型权重是下一步（填 `run_mmdet_infer`）。

---

## 9. 失败分支：`import mmdet` 报错时怎么做（导师允许的兜底）

### 9.1 先原样保存错误

把下面两条的完整输出复制保存：

```bash
python -c "import mmengine, mmdet; print('ok')"
tail -n 80 install_log.txt
```

### 9.2 常见报错怎么理解（不用深究，能对号入座即可）

| 你看到的关键词 | 含义 | 你怎么做 |
|----------------|------|----------|
| `No module named 'mmcv'` | 缺 mmcv | 先记日志，转兜底；有余力再让同学帮装对应版本 |
| `MMCV==... incompatible` | mmcv 版本不匹配 | 不要乱升；转兜底 |
| `CUDA` / `aarch64` / 编译失败 | Jetson 架构安装难 | 直接兜底 |
| `Network` / `timeout` | 下载失败 | 换网络重试 1 次；仍失败就兜底 |

### 9.3 执行兜底（基础库 / mock 路径）

仍在仓库目录、已激活环境中：

```bash
python -c "import numpy; from PIL import Image; print('base ok')"
python integration/smoke_test.py
```

再启动强制 mock：

```bash
python integration/mmdet_adapter_server.py --force-mock --device cpu
```

期望看到：

```json
{"status":"ready", ..., "backend_mode":"mock", ...}
```

然后输入图片路径或直接输入：

```text
EXIT
```

只要 `smoke_test` 通过，就说明：

- 旧接口协议能通  
- 虽然 mmdet 没装上，但你按导师要求走了「基础库版本/可运行路径」

---

## 10. 做完后，如何判断「第3步完成了」

满足下面**任意一条**就算完成：

### 完成标准 A（理想）

- [ ] `conda activate` 成功  
- [ ] `python -c "import mmengine, mmdet; print('ok')"` 成功  
- [ ] 留下安装过程记录  

### 完成标准 B（导师允许的失败兜底）

- [ ] 试过安装，有 `install_log.txt` 或报错截图  
- [ ] 基础库可用：`numpy` + `Pillow`  
- [ ] `python integration/smoke_test.py` 显示 `SMOKE TEST PASSED`  
- [ ] 能说明：mmdet 装失败，已改用基础库/mock 路径  

---

## 11. 今晚给导师汇报（直接复制填空）

```text
1. 我在 Jetson 上进入了 conda 环境：______
2. 执行了 integration/install_on_jetson.sh
3. mmdet/mmengine 结果：成功 / 失败
4. 若失败：已保存 install_log.txt，并完成 smoke_test（PASSED）
5. 下一步：拿到新模型权重/config 后填进 mmdet_adapter_server.py
```

---

## 12. 全流程最短命令清单（找对环境后可整段对照）

```bash
# 0) 如需要，先加载 conda
# source ~/miniconda3/etc/profile.d/conda.sh

# 1) 进环境
conda env list
conda activate 环境名
which python
python -V

# 2) 进仓库
cd /你的路径/333
ls integration

# 3) 基础库
python -m pip install -U pip
python -m pip install numpy Pillow
python -c "import numpy; from PIL import Image; print('base ok')"

# 4) 装 mmdet 套件
bash integration/install_on_jetson.sh install_log.txt

# 5) 验证
python -c "import mmengine, mmdet; print('ok', mmengine.__version__, mmdet.__version__)"

# 6A 成功后
python integration/smoke_test.py

# 6B 失败后（兜底）
python integration/smoke_test.py
python integration/mmdet_adapter_server.py --force-mock --device cpu
```

---

## 13. 你卡在某一步时，按这句话找人帮忙

把下面整段发给同学/导师：

```text
我在 Jetson 上做 mmdet/mmengine 安装。
当前环境名：____
which python 结果：____
失败命令：____
完整报错最后 30 行：____
我已保留 install_log.txt。
```
