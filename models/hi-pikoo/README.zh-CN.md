# Hi Pikoo 唤醒模型

[English](README.md) | **简体中文**

本目录保存完整“Hi, Pikoo”本地唤醒模型。对话推理由配置的外部服务提供，这些文件不包含聊天大语言模型。

| 文件 | 用途 |
|---|---|
| `hi_pikoo.tflite` | 固件嵌入的量化流式推理模型 |
| `checkpoint.weights.h5` | 训练权重，需要匹配的 Python 网络结构 |
| `model-config.json` | checkpoint 结构和配置元数据 |
| `wake-policy.json` | 与模型哈希绑定的前端和判定策略 |
| `SHA256SUMS` | 分发文件完整性校验 |
| `MODEL_CARD.md` | 输入输出契约、测量和限制 |
| `LICENSE.md`、`ATTRIBUTION.md`、`PERMISSION.md` | 模型条款、来源和发布记录 |

克隆仓库或下载 [2.0.0 模型 ZIP](https://github.com/skiyo/pikoo/releases/download/v2.0.0/hi-pikoo-model-2.0.0.zip)，不需要 Git LFS。在本目录，macOS 执行 `shasum -a 256 -c SHA256SUMS`，Linux 执行 `sha256sum -c SHA256SUMS`。模型和策略必须配套，单独修改会导致构建校验失败。

烧录应用参阅[快速开始](../../docs/getting-started.zh-CN.md)，重建或训练网络参阅[训练指南](../../training/README.zh-CN.md)与[模型卡](MODEL_CARD.zh-CN.md)。checkpoint 元数据还包含说明字段，不要把 JSON 的所有键直接作为模型构造参数。

模型产物版本独立于 Pikoo 应用版本。权重及包含权重的固件适用非商业条款，源码采用 Apache-2.0。不分发原始数据集或私有录音；公开 checkpoint 不代表已经完成所有自然说话人或长稳验收。
