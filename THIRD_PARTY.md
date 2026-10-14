# 来源与许可证

Pikoo 自有代码采用 Apache-2.0（见 LICENSE）；模型与语料使用限制单独见模型卡，不能由代码许可证覆盖。

- qwen-audio-agent 2.0.1：[QwenAudio/qwen-audio-agent](https://github.com/QwenAudio/qwen-audio-agent/tree/v2.0.1)，Apache-2.0。通过包依赖安装，保留原包 LICENSE/NOTICE，Pikoo 适配器独立于上游。
- microWakeWord：[OHF-Voice/micro-wake-word](https://github.com/OHF-Voice/micro-wake-word)，固定 `4665173cd35f1cff9a61e06fc427f124766c488e`，Apache-2.0。训练时独立克隆，没有复制整个项目。
- `firmware/components/pikoo_features`：取自 [rhasspy/pymicro-features](https://github.com/rhasspy/pymicro-features)，固定 `96bd69cfad79aa67697e176570d3dd87052c3def`。保留 Apache-2.0 LICENSE、TensorFlow microfrontend 文件版权头及 KissFFT BSD-3-Clause 版权/免责声明；仅增加 ESP-IDF CMake 接入，不删除来源标识。
- ESP-IDF、ESP-TFLite-Micro、ESP-SR、微雪 BSP、LVGL 等由组件管理器安装，固定版本与内容哈希见 `firmware/dependencies.lock`。组件各自的许可证（包括 ESP-SR 预编译库许可及字体许可）继续适用，发布固件时附带许可证包，不能统一声称全部第三方代码为 Apache。
- ChildMandarin、ChildTalk 没有随仓库分发；获取与使用必须遵守各自申请协议。真实家庭录音不上传。
- macOS 合成声音由本机系统提供；仓库不分发其音频。实验模型只用于本地研发，商业用途需另行核实语音来源和衍生模型权利。
- 双眼界面参考 [Muse Gadget SDK 模拟器](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/esp32/simulator/README.md) 的组织方式与动画节奏；未复制其代码或 Jollybot 角色/素材。`pikoo_eyes` 和双眼网页均为 Pikoo 原创代码，生成的状态设计图来自同一原创绘制核心；按本仓库 Apache-2.0 许可。
