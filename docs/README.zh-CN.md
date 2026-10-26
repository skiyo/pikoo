# Pikoo 文档导航

[English](README.md) | **简体中文** · [项目首页](../README.zh-CN.md) · [官网](https://pikoo.lol/)

按眼前要做的事选择文档。项目 README 负责介绍面向家庭的实时语音 AI Agent；这里分别承接运行、修改和验证步骤。

## 开始使用与制作

| 目标 | 对应文档 |
|---|---|
| 先体验电脑双眼，再按需连接真实服务端 | [开始使用](getting-started.zh-CN.md) |
| 选择板卡、喇叭和音频硬件 | [硬件说明](hardware.zh-CN.md) |
| 构建、配置、诊断或恢复双眼设备 | [固件与 USB](firmware.zh-CN.md) |
| 理解设备、服务端、模型与训练的边界 | [整体架构](architecture.zh-CN.md) |
| 查环境、检查命令和贡献入口 | [开发指南](development.zh-CN.md) |
| 配置 Agent 运行框架和运维私密网关 | [服务端](../server/README.zh-CN.md) |
| 开发有授权的本地唤醒模型 | [训练](../training/README.zh-CN.md) |

## 修改具体行为

| 主题 | 对应文档 |
|---|---|
| 眼睛绘制和表情 | [双眼渲染器](dualeye.md) |
| 唤醒、休眠、主动结束和重连 | [会话生命周期](conversation-lifecycle.zh-CN.md) |
| 当前上下文、家庭记忆、回顾、时间及输出语言 | [上下文与记忆](context-memory.zh-CN.md) |
| 搜索、网页阅读与家庭清单 | [家庭工具](family-tools.zh-CN.md) |
| 主动开启的选择性回应与静默处理 | [安静陪伴模式](companion.zh-CN.md) |
| 设备音频和事件传输 | [GCP 7 协议](gcp7.md) |

## 核对验证证据

将软件结果解释为实物验收前，先读[验证摘要](validation-summary.zh-CN.md)。[设备验收](device-validation.md)、[双眼验收](dualeye-validation.md)及[开源发布检查](open-source-validation.zh-CN.md)记录各自日期下的观察。

唤醒研究分为[发音覆盖](wake-pronunciations.zh-CN.md)、[连续讲话上下文](wake-context.zh-CN.md)、[容量测量](wake-capacity.zh-CN.md)和[完整保留的训练记录](../training/research-notes.zh-CN.md)。旧结果保留原日期和限制。

核心指南有中英文对应版本，部分历史工程和主机记录仍保留中文。英文摘要说明这些记录的范围，不把旧成绩改写成当前已经通过。

贡献、安全和复用规则见[贡献指南](../CONTRIBUTING.zh-CN.md)、[安全说明](../SECURITY.zh-CN.md)及[第三方来源](../THIRD_PARTY.zh-CN.md)。
