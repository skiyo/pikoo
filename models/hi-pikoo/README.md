# Hi Pikoo wake model · 唤醒模型

The weights are included directly in this directory. Technical checks do not establish redistribution permission. **Model publication clearance is pending**: no written permission for publishing weights trained using ChildMandarin has been obtained. Its access terms restrict research-derivative distribution and do not expressly name trained weights. See [distribution status](distribution-status.json); do not treat these weights or firmware embedding them as cleared for redistribution or commercial use.

权重直接保存在本目录，无须 Git LFS。技术校验不代表获得分发授权。**模型公开分发权限待确认**：尚未取得针对 ChildMandarin 训练权重公开发布的书面许可；其访问条款限制研究衍生物向研究组外分发，但未明确单列训练权重。见[分发状态](distribution-status.json)。不能将这些权重或内嵌权重的固件视为已获再分发或商用许可。

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
