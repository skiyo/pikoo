# 开发说明

[English](development.md) | **简体中文** · [首页](../README.zh-CN.md)

## 环境与边界

主机开发使用 Node.js 24+、C++17 编译器、Bash 和 Python 3.11。执行 `(cd server && npm ci --ignore-scripts)` 安装依赖。可选唤醒/训练依赖固定于 `training/requirements.txt`，ESP-IDF 5.5.5 和组件固定于 `firmware/dependencies.lock`；不要未经审核刷新锁文件或升级上游包。

原创绘制核心不依赖 ESP-IDF。默认固件现面向非触摸双眼板，1.83-EN 工程隔离保留在 `firmware/boards/legacy183/`。真实语音和 AEC 单独验收。模拟器协议改动应保持取消、播放耗尽与隐私行为和设备一致。

## 软件检查

```sh
bash tools/check.sh
```

统一执行 C++ 核心/眼睛检查、模拟器 Node 测试、服务器测试，以及 Python 工具/训练单元测试。不需要凭证、数据集或权重。未安装可选运行环境时，依赖 TensorFlow 的测试明确跳过，不算通过。通过 `PIKOO_CHECK_PYTHON=/path/to/python` 指定已有训练环境。

针对性执行可使用 `bash tools/test-eyes.sh`、`bash tools/test-core.sh`、`node --test firmware/simulator/*.test.mjs` 或 `(cd server && npm test)`。验收结论以[实际记录](validation-summary.zh-CN.md)为准。

`docs/ci-checks.yml.example` 是示例，不是已启用的 Actions。本次发布凭证缺少工作流写权限，不展示 CI 成功徽章。有权限的维护者可将审核后的示例安装至 `.github/workflows/checks.yml`，确认真实运行后再展示 CI 状态。

## 主机与设备构建

使用 `bash tools/build-eyes.sh` 编译主机绘制程序。测试产物在忽略目录 `firmware/build-host/`。历史固件使用 ESP-IDF 5.5.5，并显式传入 `-DPIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite`，见[固件说明](firmware.md)。缺模型提示和 64 KiB 上限是有意设置。暂不提供公开固件二进制。

`tools/Pikoo-USB.command` 和 `tools/device.py` 提供核对分区的双眼安装、升级、诊断和恢复，见[固件说明](firmware.zh-CN.md)。不要把旧板映射用于双眼板。配置含凭证，应保存在 Git 外，替换时撤销旧 token，按板商资料进入下载模式。

## 文档与发布

公开入口和核心文档以英文为默认；对应中文文件使用 `.zh-CN.md` 后缀。语言链接、示例和验证边界要保持一致。历史中文记录保留，并附带日期明确的英文摘要；模拟器界面暂维持中文。

发布前核对许可和引用、脱敏文档/日志、运行检查并验证干净目录离线启动。不打包凭证、家庭资料、音频或受限权重。后续模型必须记录训练与分发授权；固件二进制发布还需完整第三方许可证包。

另见[贡献指南](../CONTRIBUTING.zh-CN.md)、[安全说明](../SECURITY.zh-CN.md)和[来源说明](../THIRD_PARTY.zh-CN.md)。
