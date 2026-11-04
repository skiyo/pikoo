# Hi Pikoo 模型卡

[English](MODEL_CARD.md) | **简体中文**

当前模型用于完整的 **Hi + piku / piko**。完整 Hi Tikoo/Tiko 的偶发唤醒可接受，但不承诺召回。单独 Hi、单独名字、缺词和普通讲话不是目标。

模型 98,064 字节，16kHz 单声道 PCM16，40 维 microfrontend；INT8 `[1,3,40]` 流式输入、UINT8 标量概率输出。每 30ms 推理，最近 3 次平均概率达到 0.90 触发。精确摘要与前端指纹见 [wake-policy.json](wake-policy.json)。

原生 Micro 与主机特征/概率在工程样本上匹配。板端 600 次基准推理 p99 为 10.414ms，最大 10.437ms，arena 48,796 字节，不代表全部并发场景耗时。

真实家庭正式验收、独立儿童召回、8 小时误唤醒和 72 小时稳定性仍未完成。1.0.0 是当前使用版本的发布，不代表全部准确率目标达标。

[模型下载](https://github.com/skiyo/pikoo/releases/download/v1.0.0/hi-pikoo-model-1.0.0.zip)包含 TFLite、训练检查点、配置、策略与摘要。阅读[非商业模型条款](LICENSE.md)、[完整来源](ATTRIBUTION.md)及[英文技术参数](MODEL_CARD.md)。不分发原始数据、家庭录音和私密清单。模型条款与代码 Apache-2.0 分开。
