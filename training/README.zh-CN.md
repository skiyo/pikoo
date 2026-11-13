# 唤醒模型训练

[English](README.md) | **简体中文**

目标为完整 **Hi + piku / piko**，接受自然连读和中国口音。完整 Hi Tikoo/Tiko 的偶发唤醒可以容忍，但不承诺召回。单独 Hi、单独名字和缺词仍为负样本。训练在本机离线进行，不参与在线通话。

## 当前模型

[模型卡](../models/hi-pikoo/MODEL_CARD.zh-CN.md) · [权重及检查点](https://github.com/skiyo/pikoo/releases/tag/v2.0.0) · [条款及来源](../models/hi-pikoo/ATTRIBUTION.md)

包内包含 `hi_pikoo.tflite`、`checkpoint.weights.h5`、`model-config.json`、`wake-policy.json` 和摘要。推理权重 98,064 字节，不分发家庭录音和原始语料。网络配置：96 通道、64 单元分类头、72 步有序上下文、无 BatchNorm、种子 42。`hi_pikoo_model.build` 可重建结构；JSON 中的元数据不能全部直接当函数参数。

## 环境

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r training/requirements.txt
git clone https://github.com/OHF-Voice/micro-wake-word.git training/vendor/micro-wake-word
git -C training/vendor/micro-wake-word checkout 4665173cd35f1cff9a61e06fc427f124766c488e
.venv/bin/python training/hi_pikoo_train.py --help
.venv/bin/python training/wake_int8_iterate.py --help
```

固定 TensorFlow 2.18.1、NumPy 2.0.2、pymicro-features 2.0.2，使用上述 Apache-2.0 microWakeWord 提交的流式层与转换工具。需要保音高变速时单独安装 FFmpeg，不随项目打包其二进制。

## 数据与流程

预先声明目标 JSON：`target=hi-piku-piko-v2`、`accepted_names=[piku,piko]`、`declared_before_corpus_training=true`。Manifest 记录本地相对路径、音频 SHA-256、split、标签、目标版本、来源/说话人和审核证据。完整字段校验以 `hi_pikoo_train.py:admit` 和 `--help` 为准；保护摘要登记禁止进入 TRAIN/DEV 的录音。

ChildMandarin 仅提供真实儿童普通讲话，并非目标词录音。合成童声只是风格，不能当真实儿童。标签依赖具体波形的发音、完整度审核，不能只相信提示词或 ASR。

原音、声线身份及其全部增强后代不能跨 TRAIN/DEV/TEST。家庭录音只用于冻结后的 TEST，不训练、不增强、不校准、不选模。原始数据、审核资料和私人清单留在本机。普通软件检查不下载数据、不生成收费语音。

1. `hi_pikoo_train.py` 根据显式审核清单准备 16kHz microfrontend 特征并训练、导出因果网络。
2. `wake_int8_iterate.py` 做受控微调和原生 Micro DEV 评分，数据准入、变速等选项需要相应证据，不能伪造验收文件绕过。
3. `wake_tempo.py` 对 TRAIN 用 `atempo` 做 1.15/1.30/1.50 倍变速，不改变音高；先转换时间标签再做声学增强，后代保持原 split。
4. `sequence_export_check.py`、`streaming_runtime.py`、`micro_check/` 验证流式导出、状态重置和后端一致性，使用量化原生结果，不能只看浮点成绩。
5. 冻结模型与策略后再打开独立 TEST。`wake_native_finalize.py` 保留严格来源和评估门槛；发布策略为脱敏运行子集，不伪造达标证明。

仓库提供源码与当前检查点，不分发私密原始训练清单。逐字节重训需完整合法数据和证据；重新构建固件只需发布的 TFLite/策略对。模型检查命令和详细字段见[英文说明](README.md)。

设备耗时/arena、音频显示并发、真人自然快读和连续背景误唤醒分别验证。连续负样本不能逐条重置前端。真实儿童、8 小时与 72 小时目标尚未完成，见模型卡。


可选 Node 合成与审核工具使用本目录独立依赖：显式生成前在 `training/` 运行 `npm ci --ignore-scripts`。导入计划与单元测试模块不会访问模型服务。

## 选择工作流程

- 直接使用 Pikoo：采用发布的 TFLite 与策略，不需要训练。
- 检查 checkpoint：按 `model-config.json` 重建网络，载入权重，修改阈值前验证流式导出。
- 训练替代模型：取得数据权限，准备审核后的 manifest，并在选模型前保留独立 TEST。

语料目录、生成音频、API 凭证和实验输出放在公开仓库外。先查看各脚本 `--help`，不要把私人路径复制进公开命令。特征提取、浮点训练、量化、原生运行时一致性和板上调度是独立验证阶段，应报告跳过项和实际数据/评估范围。比较指标前阅读[模型卡](../models/hi-pikoo/MODEL_CARD.zh-CN.md)。
