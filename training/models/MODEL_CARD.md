# Historical model card: nihao_pikoo / synthetic-v1

**English** | [简体中文](MODEL_CARD.zh-CN.md)

The 25,128-byte synthetic-v1 experimental weights were removed from the current public tree on 2026-10-14 because redistribution rights for the macOS synthetic-voice sources have not been established. The historical Git commits retain them; no Apache-2.0 model license is granted. This card and aggregate evaluation reports are retained as historical evidence. No real-child or physical-board acceptance was established. The local V5 candidate is also private and is not included. Future public models require documented source and distribution rights.

## Original record (Chinese; 2026-10-13)


状态：实验，未通过硬件或真实儿童验收。用途：本地个人研究、固件集成和故障测试。不是商用或儿童可靠性承诺。

- 唤醒词：你好皮酷；语言：普通话。
- MixedNet，TensorFlow 2.18.1；microWakeWord 上游固定提交见训练说明。
- 8 个 macOS 普通话合成音色，6 个训练、1 个验证、1 个独立测试。344 段源音频；训练增强后 2200 个窗口。
- 真实儿童录音：0；家庭成员录音：0。
- INT8 输入 `[1,3,40]`，UINT8 概率输出，内部流式状态。
- 模型 25,128 bytes；SHA256 `3231bce008281864fd107e188b3986beee2392d2a8836d36ecf799d345890990`。
- 固件预留 256KiB tensor arena；实际 arena 使用量、PSRAM 时延和功耗需要到板测量。
- 确切量化模型流式测试：验证集正例 4/5、负例 1/38 触发；测试集正例 5/5、负例 0/38 触发。阈值 0.90、5 次平均。样本很少，同音色的 5 个语速不等于 5 个独立说话人。
- `report.json` 是训练窗口指标，`streaming-report.json` 才是导出模型的流式指标，不能互相替代。
- 实时速率将一个保留测试 WAV 送入本机唤醒服务，得到检测事件，平均概率 0.936；不等同于真人麦克风或板载 TFLM 测试。

局限：没有真实儿童、电视背景声长测、硬件 AEC 输出或远场实录；明显存在验证集误触发。合成声音来源的使用条款需在任何对外商业分发前另行审核；仓库不分发合成音频。下一版优先增加授权普通话童声负例与实际唤醒词正例，再扩大说话人互斥测试。
