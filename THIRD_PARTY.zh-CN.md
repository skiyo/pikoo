# 第三方软件与来源

[English](THIRD_PARTY.md) | **简体中文**

Pikoo 原创代码、双眼图形和项目文档采用 Apache-2.0。安装依赖、引用源码、数据和外部服务保留自身条款，根目录 LICENSE 不覆盖它们，见 [NOTICE](NOTICE)。

## 软件清单

下表对应当前固定集成版本，不代表全部是最新版本。npm 间接依赖见[锁文件许可清单](docs/dependency-licenses.csv)，ESP-IDF 组件版本和哈希见 `firmware/dependencies.lock`。以相应上游完整许可为准。

| 组件与来源 | 版本/提交 | 用途/引用方式 | 许可 |
|---|---|---|---|
| [qwen-audio-agent](https://github.com/QwenAudio/qwen-audio-agent/tree/v2.0.1) | 2.0.1 | 安装的服务器依赖，提供鉴权、Provider 和记忆/会话框架；Pikoo 适配独立 | Apache-2.0，保留上游声明 |
| [ESP-IDF](https://github.com/espressif/esp-idf/tree/v5.5.5) | 5.5.5 / `b774170ff46c393eeb5e495ea37936038d3f4f4f` | 固件框架依赖 | 框架 Apache-2.0；内含其他独立许可 |
| [ESP-SR](https://github.com/espressif/esp-sr) | 2.5.3 | 历史基线 AFE/AEC 依赖，关闭内置 WakeNet | ESPRESSIF MIT License，限 ESPRESSIF 产品；不能简写为通用 MIT 或 Pikoo Apache-2.0 |
| [ESP-TFLite-Micro](https://github.com/espressif/esp-tflite-micro) | 1.4.1 | INT8 嵌入式推理依赖 | Apache-2.0，加内含第三方声明 |
| [microWakeWord](https://github.com/OHF-Voice/micro-wake-word) | `4665173cd35f1cff9a61e06fc427f124766c488e` | 单独安装的训练代码，不整库搬入 | Apache-2.0，模型/数据另行授权 |
| [pymicro-features](https://github.com/rhasspy/pymicro-features/tree/96bd69cfad79aa67697e176570d3dd87052c3def) / TensorFlow microfrontend | 引用提交 `96bd69cfad79aa67697e176570d3dd87052c3def`；Python 2.0.2 | `pikoo_features` 引用源码及桌面特征依赖 | Apache-2.0；保留 TensorFlow 版权头；新增 Pikoo ESP-IDF CMake 集成 |
| [KissFFT](https://github.com/mborgerding/kissfft) | 随固定特征实现的源码 | microfrontend 引用 FFT | 源码保留 BSD-3-Clause 和 Mark Borgerding 版权 |
| [LVGL](https://github.com/lvgl/lvgl) | 9.6.0~1 | 历史固件界面；原创双眼核心不依赖 LVGL | 核心 MIT；可选库/字体各有许可 |
| [微雪 BSP](https://components.espressif.com/components/waveshare/esp32_s3_touch_lcd_1_83/versions/2.0.0) | 2.0.0 | 安装的旧 1.83-EN 集成，不是双眼驱动 | BSP Apache-2.0，依赖许可保留 |
| [ESP-NN](https://github.com/espressif/esp-nn) | 1.4.1 | 固件锁定的优化推理依赖，实机表现待测 | Apache-2.0 |
| [ws](https://github.com/websockets/ws) | 锁文件 8.22.0 | 模拟器使用的 Node WebSocket 依赖 | MIT |
| [TensorFlow](https://github.com/tensorflow/tensorflow) | 2.18.1 | 可选训练/推理依赖 | Apache-2.0，加内含第三方声明 |
| [NumPy](https://github.com/numpy/numpy) | 2.0.2 | 可选训练依赖 | 核心 BSD-3-Clause，加内含依赖许可 |
| [PyYAML](https://github.com/yaml/pyyaml) | 6.0.2 | 可选训练配置依赖 | MIT |
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels) | 2.0.14 | 可选语音活动依赖 | 封装 MIT，内含 WebRTC VAD 保留上游 BSD 类条款 |
| [Node.js](https://github.com/nodejs/node) | 运行要求 24+ | 服务器/模拟器运行环境，不随项目打包 | MIT 及内含依赖声明 |
| [Nginx](https://nginx.org/en/) / [Certbot](https://github.com/certbot/certbot) / [mihomo](https://github.com/MetaCubeX/mihomo) | 运维安装；文档 IP 证书流程要求 Certbot ≥5.4 | 部署模板集成，不引用源码或二进制 | Nginx BSD-2-Clause；Certbot Apache-2.0；mihomo GPL-3.0，分发各遵守其许可 |

发布软件二进制、固件或容器时，需要按实际打包的版本附完整许可与声明；本表不能替代发布包许可证集合。不要将引用代码的版权头改为 Pikoo 许可。

## 参考与外部服务

| 来源 | 关系 | 边界 |
|---|---|---|
| [Muse Gadget SDK 模拟器](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/esp32/simulator/README.md) | 模拟器组织、动画节奏参考 | 未复制 Muse 代码或 Jollybot 素材；Pikoo 绘制、网页和画面原创 |
| [微雪双眼文档](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/) | 规格、原理图和驱动参考入口 | 硬件/资料参考，不重新授权商家材料 |
| [Google Gemini API](https://ai.google.dev/gemini-api/docs) | 外部实时与文本服务 | 地区、额度、价格和服务条款独立，不是开源组件 |
| [Let's Encrypt](https://letsencrypt.org/) | 外部证书服务 | 运维需维护续签并遵守服务要求 |

## 音频、数据与模型

- 当前公开文件树**不分发权重和音频**，保留模型卡及汇总评估记录。
- 早期模型使用本机 macOS 系统声音，分发权利尚未确认；拥有电脑不等于拥有声音的公开分发权。[苹果公开 macOS 条款](https://www.apple.com/legal/sla/docs/macOSTahoe.pdf)将系统声音内容限于个人非商业使用，并限制公开分享；未直接说明此唤醒模型情形，发布前还需核对实际产品/版本条款。
- 本机 V5 使用已授权 [ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin)。获准访问不等于获准转发音频或权重，需审核完整受限条款和许可记录，不能仅看数据卡标签。V5、录音和原始清单保持私密。
- [ChildTalk](https://github.com/NKU-HLT/ChildTalk) 是备选研究来源，未下载或参与训练，后续使用前需审查条款。
- Git 历史仍含早期模型，保留历史不表示权重获得 Apache-2.0 授权；当前发布包不应包含它们。
- 后续公开模型需记录训练和分发权利、数据来源、独立模型卡/许可，并完成成人/儿童及实板评估。家庭录音默认私密。
