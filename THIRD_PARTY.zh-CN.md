# 第三方软件与来源

可选声调增强和同声前缀准备使用独立安装的 Praat-Parselmouth 0.4.7（GPL-3.0-or-later，含 Praat），见 `training/requirements-prosody.txt`；不复制进 Pikoo，也不链接到固件中，其自身许可继续适用。

可选的本机合成／检查使用 MLX Audio 0.5.9、MLX 0.32.4（MIT），独立依赖见 `training/requirements-local-audio.txt`。Qwen3-TTS VoiceDesign、Qwen3-ASR-0.6B 源模型卡标注 Apache-2.0；转换后的 MLX 权重保留原许可，不随 Pikoo 分发。语料权利仍决定最终唤醒模型的分发边界；这些不是 ESP32 依赖。见[发音覆盖说明](docs/wake-pronunciations.zh-CN.md)。

[English](THIRD_PARTY.md) | **简体中文**

Pikoo 原创代码、双眼图形和项目文档采用 Apache-2.0。安装依赖、引用源码、数据和外部服务保留自身条款，根目录 LICENSE 不覆盖它们，见 [NOTICE](NOTICE)。

## 软件清单

下表对应当前固定集成版本，不代表全部是最新版本。npm 间接依赖见[锁文件许可清单](docs/dependency-licenses.csv)，ESP-IDF 组件版本和哈希见 `firmware/dependencies.lock`。以相应上游完整许可为准。

| 组件与来源 | 版本/提交 | 用途/引用方式 | 许可 |
|---|---|---|---|
| [qwen-audio-agent](https://github.com/QwenAudio/qwen-audio-agent/tree/v2.0.1) | 2.0.1 | 安装的服务器依赖，提供鉴权、Provider 和记忆/会话框架；Pikoo 适配独立 | Apache-2.0，保留上游声明 |
| [ESP-IDF](https://github.com/espressif/esp-idf/tree/v5.5.5) | 5.5.5 / `b774170ff46c393eeb5e495ea37936038d3f4f4f` | 固件框架依赖 | 框架 Apache-2.0；内含其他独立许可 |
| [ESP-SR](https://github.com/espressif/esp-sr) | 2.5.3 | AFE/AEC 依赖及可选 MN7 本地二次确认开发探针，关闭内置 WakeNet | ESPRESSIF MIT License，限 ESPRESSIF 产品；不能简写为通用 MIT 或 Pikoo Apache-2.0 |
| [ESP-TFLite-Micro](https://github.com/espressif/esp-tflite-micro) | 1.4.1 | INT8 嵌入式推理依赖 | Apache-2.0，加内含第三方声明 |
| [microWakeWord](https://github.com/OHF-Voice/micro-wake-word) | `4665173cd35f1cff9a61e06fc427f124766c488e` | 单独安装的训练代码，不整库搬入 | Apache-2.0，模型/数据另行授权 |
| [pymicro-features](https://github.com/rhasspy/pymicro-features/tree/96bd69cfad79aa67697e176570d3dd87052c3def) / TensorFlow microfrontend | 引用提交 `96bd69cfad79aa67697e176570d3dd87052c3def`；Python 2.0.2 | `pikoo_features` 引用源码及桌面特征依赖 | Apache-2.0；保留 TensorFlow 版权头；新增 Pikoo ESP-IDF CMake 集成 |
| [KissFFT](https://github.com/mborgerding/kissfft) | 随固定特征实现的源码 | microfrontend 引用 FFT | 源码保留 BSD-3-Clause 和 Mark Borgerding 版权 |
| [LVGL](https://github.com/lvgl/lvgl) | 9.6.0~1 | 历史固件界面；原创双眼核心不依赖 LVGL | 核心 MIT；可选库/字体各有许可 |
| [微雪 BSP](https://components.espressif.com/components/waveshare/esp32_s3_touch_lcd_1_83/versions/2.0.0) | 2.0.0 | 安装的旧 1.83-EN 集成，不是双眼驱动 | BSP Apache-2.0，依赖许可保留 |
| [esp_codec_dev](https://github.com/espressif/esp-adf-libs/tree/master/esp_codec_dev) | 1.5.11 | 安装的 ES8311/ES7210 编解码依赖 | Apache-2.0 |
| [esp_lcd_gc9a01](https://components.espressif.com/components/espressif/esp_lcd_gc9a01/versions/2.0.4) | 2.0.4 | 安装的双圆屏驱动；板级集成为 Pikoo 原创 | Apache-2.0 |
| [ESP-NN](https://github.com/espressif/esp-nn) | 1.4.1 | 固件锁定的优化推理依赖；已有生成信号实机计时，真实音频并发待测 | Apache-2.0 |
| [ws](https://github.com/websockets/ws) | 锁文件 8.22.0 | 模拟器使用的 Node WebSocket 依赖 | MIT |
| [TensorFlow](https://github.com/tensorflow/tensorflow) | 2.18.1 | 可选训练/推理依赖 | Apache-2.0，加内含第三方声明 |
| [NumPy](https://github.com/numpy/numpy) | 2.0.2 | 可选训练依赖 | 核心 BSD-3-Clause，加内含依赖许可 |
| [Apache Arrow / PyArrow](https://github.com/apache/arrow) | 19.0.1 | 固定版本 MInDS-14 Parquet 的可选导入器 | Apache-2.0，保留内含依赖声明 |
| [FFmpeg](https://ffmpeg.org/legal.html) | 可选外部工具；本次使用 8.1 | 独立进程处理音高和语速，不附带二进制或链接其库 | 具体构建决定 LGPL/GPL；本次 Homebrew 构建声明 GPL-3.0-or-later |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) / [MLX 模型](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit) | VoiceDesign 4-bit `5c390979e4b93af5f2932f90742ca99c7dd04687` | 本机纯文本合成试验，无参考声音；未进入 V8D 训练 | 模型及代码 Apache-2.0；本仓库不附带权重 |
| [MLX-Audio](https://github.com/Blaizzy/mlx-audio) / [MLX](https://github.com/ml-explore/mlx) | 0.5.9 / 0.32.4 | 可选独立 Apple Silicon 语音合成试验环境 | MIT；依赖保留各自声明 |
| [PyYAML](https://github.com/yaml/pyyaml) | 6.0.2 | 可选训练配置依赖 | MIT |
| [pypinyin](https://github.com/mozillazg/python-pinyin) | 0.55.0 | 可选研究训练的文本转音素标签，单独安装 | MIT |
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels) | 2.0.14 | 可选语音活动依赖 | 封装 MIT，内含 WebRTC VAD 保留上游 BSD 类条款 |
| [Node.js](https://github.com/nodejs/node) | 运行要求 24+ | 服务器/模拟器运行环境，不随项目打包 | MIT 及内含依赖声明 |
| [Nginx](https://nginx.org/en/) / [Certbot](https://github.com/certbot/certbot) / [mihomo](https://github.com/MetaCubeX/mihomo) | 运维安装；文档 IP 证书流程要求 Certbot ≥5.4 | 部署模板集成，不引用源码或二进制 | Nginx BSD-2-Clause；Certbot Apache-2.0；mihomo GPL-3.0，分发各遵守其许可 |

发布软件二进制、固件或容器时，需要按实际打包的版本附完整许可与声明；本表不能替代发布包许可证集合。不要将引用代码的版权头改为 Pikoo 许可。

## 参考与外部服务

| 来源 | 关系 | 边界 |
|---|---|---|
| [Muse Gadget SDK 模拟器](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/esp32/simulator/README.md) | 模拟器组织、动画节奏参考 | 未复制 Muse 代码或 Jollybot 素材；Pikoo 绘制、网页和画面原创 |
| [微雪双眼文档](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/) | 规格、原理图和驱动参考入口 | 硬件/资料参考，不重新授权商家材料 |
| [Google Gemini API](https://ai.google.dev/gemini-api/docs) | 外部实时、文本及可选 TTS 语料生成服务 | 地区、额度、价格和服务条款独立，不是开源组件 |
| [DeepSeek Search API](https://api-docs.deepseek.com/zh-cn/guides/search/) | 外部原始网页搜索服务，Pikoo 原创适配器接入 | 账号、服务与计费条款独立；不打包 DeepSeek LLM 或供应商源码 |
| [Let's Encrypt](https://letsencrypt.org/) | 外部证书服务 | 运维需维护续签并遵守服务要求 |

## 音频、数据与模型

- 当前公开文件树**不分发权重和音频**，保留模型卡及汇总评估记录。
- 早期模型使用本机 macOS 系统声音，分发权利尚未确认；拥有电脑不等于拥有声音的公开分发权。[苹果公开 macOS 条款](https://www.apple.com/legal/sla/docs/macOSTahoe.pdf)将系统声音内容限于个人非商业使用，并限制公开分享；未直接说明此唤醒模型情形，发布前还需核对实际产品/版本条款。
- 本机 V5 使用已授权 [ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin)。获准访问不等于获准转发音频或权重，需审核完整受限条款和许可记录，不能仅看数据卡标签。V5、录音和原始清单保持私密。
- 可选的 [PolyAI MInDS-14 中文子集](https://huggingface.co/datasets/PolyAI/minds14/tree/40ce77cb32a384e4d50a568e1ec39ac804019d33/zh-CN) 使用 CC-BY-4.0。署名：PolyAI；Gerz 等（2021），*Multilingual and Cross-Lingual Intent Detection from Spoken Data*。用途为普通讲话负样本，不提供自定义唤醒词正样本。8kHz 电话录音不等于宽频麦克风或儿童测试；没有说话人/年龄编号，全部只放训练集。
- Google TTS 生成音频是合成语料，遵循 [Gemini API 条款](https://ai.google.dev/gemini-api/terms)，不受仓库 Apache-2.0 重新授权。合成童声不能标为真实儿童录音。音频、清单及实验权重保留本机；自动转写审核仅上传经哈希验证的生成语音。家庭录音只做独立测试，语料工具不会上传家庭录音。
- [ChildTalk](https://github.com/NKU-HLT/ChildTalk) 是备选研究来源，未下载或参与训练，后续使用前需审查条款。
- Git 历史仍含早期模型，保留历史不表示权重获得 Apache-2.0 授权；当前发布包不应包含它们。
- 后续公开模型需记录训练和分发权利、数据来源、独立模型卡/许可，并完成成人/儿童及实板评估。家庭录音默认私密。
