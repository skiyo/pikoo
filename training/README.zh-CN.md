# 本地唤醒开发

[English](README.md) | **简体中文** · [项目首页](../README.zh-CN.md)

本模块开发 Pikoo 的本地“你好 Pikoo”唤醒流水线（pī kū / PEE-koo）：准备授权语料、训练和导出候选，再评估是否适合设备。它不运行实时 Agent，也不识别家庭成员。

体验[离线模拟器](../docs/getting-started.zh-CN.md)或用按钮开始语音会话，不需要先训练。**当前公开文件树不提供唤醒模型权重。** 历史模型和分发边界见[模型卡](models/MODEL_CARD.md)。

## 外壳打印资料

三件小猫外壳的原始 STL、打印顺序、装配图解与验收表见[外壳目录](../hardware/enclosure/README.zh-CN.md)。项目家庭已打印、装配验证并在家使用通过（2026-10-27，用户反馈）；这份硬件反馈与本模块的软件/研究检查分别记录。

## 按任务找到入口

| 任务 | 工具或说明 |
|---|---|
| 准备有使用权的音频和清单 | `generate_synthetic.py`、`import_children.py`、`merge_manifests.py` |
| 内容审核与不确定语料隔离 | `clean_corpus.py`、`review_local_corpus.py` |
| 训练或导出候选 | `train.py` 与固定的上游代码 |
| 对比流式验证或测试结果 | `evaluate_iteration.py`，显式选择集合 |
| 检查静态设备兼容性 | `check_esp32_model.py`、`micro_check/` |
| 排查连续讲话或设备容量 | [上下文诊断](../docs/wake-context.zh-CN.md)、[容量说明](../docs/wake-capacity.zh-CN.md) |
| 查看发音覆盖工作 | [发音说明](../docs/wake-pronunciations.zh-CN.md) |
| 查阅旧实验、数据源操作及失败候选 | [完整保留的研究记录](research-notes.zh-CN.md) |

研究记录保留原 README 的命令、日期和数字，属于历史证据，不表示旧候选仍是当前推荐模型。

## 准备环境

以下命令在仓库根目录执行。训练使用 Python 3.11；可选依赖包含 TensorFlow，体积明显大于仅运行图形演示所需的环境。

```sh
python3.11 -m venv training/.venv
training/.venv/bin/pip install -r training/requirements.txt
mkdir -p training/vendor
git clone https://github.com/OHF-Voice/micro-wake-word.git training/vendor/micro-wake-word
git -C training/vendor/micro-wake-word checkout 4665173cd35f1cff9a61e06fc427f124766c488e
```

使用授权的本地 WAV 或允许使用的合成来源。`generate_synthetic.py` 依赖 macOS 的 `say` / `afconvert`：

```sh
training/.venv/bin/python training/generate_synthetic.py --output training/data/synthetic
training/.venv/bin/python training/train.py \
  --upstream training/vendor/micro-wake-word \
  --manifest training/data/synthetic/manifest.json \
  --output training/runs/my-model --defer-test
```

这里生成的是研究候选，不是已验收的唤醒模型。先固定训练、验证和测试划分，再做增强；根据验证集选模，冻结模型和阈值后才评分封存的独立测试。`evaluate_iteration.py` 要求显式传入 `--split validation` 或 `--split test`。

## 数据和评估规则

- 家庭录音仅供评估，不用于训练、增强、量化校准、清洗决策、阈值调整或选模；保留 `evaluation_only=true` 和保护摘要。
- 说话人、原始录音在集合间互斥，派生音频继承父样本划分。儿童普通讲话是负样本来源，不能证明儿童目标词召回。
- 虚构童声、变调和 ASR 核对不能代替真实童声发音与识别验收。已经看过的诊断录音不能重新称为全新盲测。
- 保留语料访问授权、原始摘要、不确定内容隔离和失败成绩。数据卡上的许可标签不能代替完整分发授权。

数据下载和导入步骤保留在研究记录中，受限数据先取得访问许可。没有明确权利时，不发布家庭音频、受限录音或衍生权重；Git 历史中的研究权重不会因项目代码采用 Apache-2.0 而自动改换许可。

## 导出与设备验收

特征流水线使用 16 kHz 单声道 PCM16 和 microfrontend 特征。流式模型接口、量化与注册算子必须和 worker、固件匹配。

```sh
training/.venv/bin/python training/check_esp32_model.py \
  --model /absolute/private/authorized-model.tflite \
  --output training/runs/esp32-static-check.json
```

训练和静态检查默认上限为 **64 KiB**。实验时显式传 `--max-model-bytes 524288`，允许最多 **512 KiB**；当前双眼固件使用较大的实验 Flash 预算，独立的旧款 1.83 英寸工程保留自身上限。文件能放下不代表 arena 内存、推理耗时、准确率或音频/显示并发达标。构建和烧录前读[固件指南](../docs/firmware.zh-CN.md)。

静态检查、主机 Micro 一致性、板上资源测量、流式验证和真人唤醒分别报告。既有家庭验收计划要求每人在一米处至少 18/20 次成功、八小时误唤醒不超过一次；这是目标，不是已完成结果，参见[设备验收](../docs/device-validation.md)。

## 检查与结果记录

在仓库根目录运行 `bash tools/check.sh`，其中包含训练及工具单测，不需要私人音频或模型凭证。未安装可选运行环境时可能出现跳过，跳过不能写成通过。完整环境见[开发指南](../docs/development.zh-CN.md)。

修改文档不需要启动训练、下载大型模型或评分测试录音。新候选结论写入带日期的报告，同时保留模型摘要、来源与划分，以及验收边界。
