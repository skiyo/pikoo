# 🐱Hi Pikoo🐱

[English](README.md) | **简体中文**

**Pikoo 是一个基于 Live 模型的家庭 AI Agent 宠物。**

[官网](https://pikoo.lol/) · [下载 1.0.0](https://github.com/skiyo/pikoo/releases/tag/v1.0.0) · [项目文档](docs/README.zh-CN.md)

![Pikoo 双眼小猫外壳——概念渲染](docs/images/pikoo-enclosure.webp)

## Quick Start

**先在电脑上体验双眼。** 需要 Node.js 24+、npm、Bash 和 C++17 编译器。macOS 安装 Xcode Command Line Tools；Debian/Ubuntu 安装 `build-essential`。

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
(cd server && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

打开 **http://127.0.0.1:8793/dualeye**。离线演示不需要 API Key、唤醒模型或板子；按钮用测试音模拟交互，不会自动开始 AI 对话或录音。按 Ctrl+C 或运行 `bash tools/stop-dualeye.sh` 停止。

**接入真实语音：** [部署自己的 Gateway](server/README.zh-CN.md)，签发设备凭证，再[配置模拟器](docs/getting-started.zh-CN.md#真实语音)。

**安装实机：** 下载 [1.0.0 固件与模型](https://github.com/skiyo/pikoo/releases/tag/v1.0.0)，按 [USB 安装说明](docs/firmware.zh-CN.md)操作，在本机填写自己的 2.4GHz Wi-Fi 和设备凭证。

## 当前功能

- 本地 **“Hi, Pikoo”** 唤醒，接受 `piku`、`piko` 两种读音。
- 连续中文对话、插话、停止回答、静音与重连。
- 两块 240 × 240 表情眼屏，与桌面模拟器共用原创 C++ 绘制核心。
- 服务端管理话题续接、自动家庭记忆、摘要和持久清单。
- 通过配置的工具搜索互联网、阅读公开网页。
- Gateway 自行部署；模型密钥和家庭资料留在服务器。

闭眼表示待机。唤醒后连接语音服务，就绪后睁眼并主动问候；告别结束当前语音连接。空闲休眠释放计费语音连接，服务端文字上下文可供下次唤醒恢复。

## 整体架构

```mermaid
flowchart LR
    Device["ESP32-S3 / desktop simulator<br/>Wake · capture · playback · eyes"] <-->|"GCP / WSS · PCM audio"| Gateway["Pikoo Gateway<br/>Auth · sessions · audio · tools"]
    Gateway <-->|"Native Live WebSocket"| Live["GPT-Live 1<br/>Listen · speak · interrupt"]
    Live <-->|"Responses delegation"| Terra["GPT-6.1 Terra<br/>Reasoning · tool selection"]
    Terra <-->|"Function calls / results"| Gateway
    Gateway <--> Store[("Private text context<br/>Family memory · lists")]
    Gateway --> Background["Terra<br/>Interaction classification · summaries"]
    Training["Offline training / export"] -.->|"Model + frozen policy"| Device
```

设备负责声音和表情。Gateway 组合 **Qwen Audio Agent 2.0.1** 与 Pikoo 原生 Live Provider。Live 负责听说，Terra 负责委派推理、工具、互动分类和记忆整理。恢复的是保存的文字语义，不是未播完的声音。[架构设计](docs/architecture.zh-CN.md) · [上下文与记忆](docs/context-memory.zh-CN.md)

## 设备

目标板为 **微雪 ESP32-S3-DualEye-LCD-1.28 非触摸版**：16MiB Flash、8MiB PSRAM，两块 240 × 240 圆屏。另需匹配的喇叭、USB 数据线、稳定 USB 供电和 2.4GHz Wi-Fi。板载音频编解码器与麦克风。

[硬件与接线](docs/hardware.zh-CN.md) · [三件式小猫外壳与 STL](hardware/enclosure/README.zh-CN.md)

## 部署与二次开发

| 模块 | 职责 | 入口 |
|---|---|---|
| `firmware/` | 板级接口、唤醒推理、音频、按键与双眼 | [固件](docs/firmware.zh-CN.md) |
| `firmware/simulator/` | 本机图形演示与可选真实语音 | [快速开始](docs/getting-started.zh-CN.md) |
| `server/` | Live/Terra、鉴权、会话、工具与持久化 | [服务端](server/README.zh-CN.md) |
| `training/` | 数据隔离、变速增强、训练、量化与评估 | [训练](training/README.zh-CN.md) |
| `models/hi-pikoo/` | 当前模型卡、策略、来源与使用条款 | [模型卡](models/hi-pikoo/MODEL_CARD.zh-CN.md) |
| `tools/` | 构建、USB 安装、诊断和检查 | [开发说明](docs/development.zh-CN.md) |

使用 `bash tools/check.sh` 运行软件检查。[开发说明](docs/development.zh-CN.md)介绍如何替换表情、适配板卡、增加工具、更换 Provider 和导出模型；[文档目录](docs/README.zh-CN.md)提供全部当前入口。

## 使用要求与限制

联网对话需要自己的服务器、模型 API 权限和可用网络；模型和搜索服务可能单独收费。唤醒效果受读音、距离、噪声和外壳声学影响。本次版本不声称完成真实儿童召回、8 小时误唤醒和 72 小时稳定性认证。浏览器测试不能证明实机 AEC 效果。

## 贡献与许可证

[贡献](CONTRIBUTING.zh-CN.md) · [安全](SECURITY.zh-CN.md) · [第三方来源](THIRD_PARTY.zh-CN.md) · [发布检查](docs/release.zh-CN.md)

原创代码、眼睛图形及文档采用 **Apache-2.0**。唤醒权重和包含权重的固件附有[独立非商业模型条款](models/hi-pikoo/LICENSE.md)。第三方组件和训练数据保留各自条款，Apache 许可不替代这些条款。不分发训练音频、家庭录音、私人资料或凭证。
