# 二次开发

[English](development.md) | **简体中文**

## 环境与检查

离线模拟器需要 Node.js 24+、npm、Bash、C++17。USB 与训练使用 Python 3.11，只有需要训练/推理时才安装 `training/requirements.txt`。固件固定 ESP-IDF 5.5.5，保持上游版本锁定。

```sh
(cd server && npm ci --ignore-scripts)
bash tools/check.sh
```

检查包含原生音频、会话、双眼、模拟器、服务端与 Python 工具。缺少可选运行时可能跳过，跳过不能当通过。测试不得隐式开启家庭麦克风或调用收费 API。

## 更换表情

修改 `firmware/components/pikoo_eyes/`，保持独立于平台的 C++ 接口与 240 × 240 RGB565 输出。运行 `bash tools/test-eyes.sh`，再启动双眼模拟器。音频优先，绘制来不及时丢弃旧帧。

## 适配板卡

明确封装显示、音频、功放和按键，可从 `firmware/main/board_display.cpp` 与 `board_audio.cpp` 入手。保留 `pikoo_core` 状态机；启用全双工前核实麦克风、参考通道和 DMA 时序。更换分区布局必须设计备份与迁移。

## 增加工具

从 `server/family-tools.mjs`、`deepseek-search.mjs` 入手，注册工具参数、校验输入、保留家庭 owner 隔离和超时，并如实返回失败。遵循 `openai-live.mjs` 的持久调用 ID 去重，迟到结果不能进入已关闭会话。先扩展 `*.test.mjs`，再调用外部接口。

## 更换语音 Provider

参考 `server/host.mjs` 注册表与 `server/openai-live.mjs` 原生适配器。保留连续音频协商、采样率、取消代次、播放回报、文字历史和鉴权。真实模型权限与离线测试分开验证，不兼容的 API 不能只替换模型名。

## 训练与导出

按[训练说明](../training/README.zh-CN.md)操作。家庭录音不得训练、增强、校准或选模。每个导出绑定策略摘要与前端指纹；主机和固件使用相同平滑判定。快读采用不改变音高的变速增强；连续负样本测试保持前端状态。

## 版本发布

同步 `VERSION`、包元数据、固件版本与模型卡，按[发布检查](release.zh-CN.md)操作。二进制随附第三方许可正文，不提交 NVS、生成音频、凭证或私人记忆。
