# Hi Pikoo 模型卡

[English](MODEL_CARD.md) | **简体中文**

**维护者已确认发布许可。** 见[许可记录](PERMISSION.md)，继续适用非商业模型条款和来源要求。

当前模型用于完整的 **Hi + piku / piko**。完整 Hi Tikoo/Tiko 的偶发唤醒可接受，但不承诺召回。单独 Hi、单独名字、缺词和普通讲话不是目标。

模型 98,064 字节，16kHz 单声道 PCM16，40 维 microfrontend；INT8 `[1,3,40]` 流式输入、UINT8 标量概率输出。每 30ms 推理，最近 3 次平均概率达到 0.90 触发。精确摘要与前端指纹见 [wake-policy.json](wake-policy.json)。

原生 Micro 与主机特征/概率在工程样本上匹配。板端 600 次基准推理 p99 为 10.414ms，最大 10.437ms，arena 48,796 字节，不代表全部并发场景耗时。

真实家庭正式验收、独立儿童召回、8 小时误唤醒和 72 小时稳定性仍未完成。1.0.0 是当前使用版本的发布，不代表全部准确率目标达标。

权重直接保存在本目录：[hi_pikoo.tflite](hi_pikoo.tflite) 用于 ESP 推理，[checkpoint.weights.h5](checkpoint.weights.h5) 用于训练。克隆仓库即可取得，无须 Git LFS；使用 [SHA256SUMS](SHA256SUMS) 校验。[模型压缩包](https://github.com/skiyo/pikoo/releases/download/v1.0.0/hi-pikoo-model-1.0.0.zip)作为另一种下载方式。阅读[非商业模型条款](LICENSE.md)、[完整来源](ATTRIBUTION.md)及[英文技术参数](MODEL_CARD.md)。不分发原始数据、家庭录音和私密清单。模型条款与代码 Apache-2.0 分开。
