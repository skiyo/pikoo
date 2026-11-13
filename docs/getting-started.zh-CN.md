# 快速开始

[English](getting-started.md) | **简体中文**

## 安装设备

准备[硬件](hardware.zh-CN.md)、ESP-IDF 5.5.5 和 Python 3.11。权重与训练检查点随源码保存在 [models/hi-pikoo](../models/hi-pikoo/MODEL_CARD.zh-CN.md)，校验目录中的 SHA256SUMS 并阅读模型条款。构建会校验冻结策略与权重哈希。

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
. /path/to/esp-idf/export.sh
PIKOO_WAKE_POLICY="$PWD/models/hi-pikoo/wake-policy.json" \
  bash tools/build-device.sh "$PWD/models/hi-pikoo/hi_pikoo.tflite"
```

把示例复制到 Git 外，填写[服务配置](configuration.zh-CN.md)，完成整片 Flash 备份与校验，再按 [USB 安装指南](firmware.zh-CN.md)安装。账号、网络和模型服务由使用者提供，无须部署 Pikoo 应用服务器。

## 离线双眼预览

桌面预览另需 Node.js 24+、npm 和 C++17 编译器：

```sh
(cd firmware/simulator && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

打开 `http://127.0.0.1:8793/dualeye`，选择状态和表情。页面不打开麦克风、不播放声音、不请求模型。按 Ctrl+C 或运行 `tools/stop-dualeye.sh` 停止。协议、工具和性能验证使用独立的原生 C++ 模拟器，见[开发指南](development.zh-CN.md)。
