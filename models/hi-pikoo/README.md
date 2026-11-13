# Hi Pikoo wake model · 唤醒模型

The reviewed weights are included directly in this directory. Clone the repository or open a file below and choose **Download raw file**. Git LFS is not required.

已审核权重直接保存在本目录。克隆仓库即可取得，也可打开文件后选择 **Download raw file** 下载，无须 Git LFS。

| File / 文件 | Purpose / 用途 |
|---|---|
| [hi_pikoo.tflite](hi_pikoo.tflite) | ESP32 inference / ESP32 推理权重，98,064 bytes |
| [checkpoint.weights.h5](checkpoint.weights.h5) | Training checkpoint / 训练检查点，279,208 bytes |
| [model-config.json](model-config.json) | Architecture settings / 网络结构参数 |
| [wake-policy.json](wake-policy.json) | Frozen inference policy / 冻结推理策略 |
| [SHA256SUMS](SHA256SUMS) | File checksums / 文件校验值 |

```sh
cd models/hi-pikoo
sha256sum -c SHA256SUMS
# macOS: shasum -a 256 -c SHA256SUMS
```

These are wake-model weights. Flashable firmware is a separate build artifact; see [firmware setup](../../docs/firmware.md).

这里是唤醒模型权重。可烧录固件是另一个构建产物，见[固件安装](../../docs/firmware.zh-CN.md)。

[Model card / 模型卡](MODEL_CARD.md) · [中文模型卡](MODEL_CARD.zh-CN.md) · [Non-commercial model terms / 非商业模型条款](LICENSE.md) · [Attribution / 来源](ATTRIBUTION.md)
