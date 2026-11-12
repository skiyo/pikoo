# 快速开始

ESP32 端侧模式请先读[本地 Agent](local-agent.zh-CN.md)和[固件安装](firmware.zh-CN.md)。下文图形演示不变，可选联网语音使用保留的 Gateway。

[English](getting-started.md) | **简体中文**

## 离线体验

需要 Node.js 24+、npm、Bash 和 C++17 编译器。

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
(cd server && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

打开 http://127.0.0.1:8793/dualeye。测试音模拟对话，不需要凭证、模型、Python 或麦克风。Ctrl+C 或 `bash tools/stop-dualeye.sh` 停止。可用 `PIKOO_SIM_PORT=8794` 换端口；Host/Origin 检查要求使用 `127.0.0.1`。

## 真实语音

[部署 Gateway](../server/README.zh-CN.md)，签发设备凭证。以下 JSON 保存在 **Git 仓库外**，权限设为 0600：

```json
{"endpoint":"wss://YOUR_HOST/api/realtime","token":"YOUR_DEVICE_TOKEN"}
```

```sh
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

凭证由本机 Node 进程保存；主动唤醒并授权麦克风后才开始。按钮通话不需要唤醒模型。修改配置前先停止已运行的启动器实例。

## 本地唤醒

从 [Release](https://github.com/skiyo/pikoo/releases/tag/v1.0.0) 下载 `hi-pikoo-model-1.0.0.zip`，验证 `SHA256SUMS` 并阅读模型条款。在 Python 3.11 独立环境安装依赖：

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r training/requirements.txt
PIKOO_WAKE_PYTHON="$PWD/.venv/bin/python" \
PIKOO_WAKE_MODEL=/absolute/models/hi_pikoo.tflite \
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

通过页面主动启用本地唤醒，麦克风需要明确授权。待机声音只在本机处理；模型缺失会明确提示，不会偷偷切换为远程识别。

## 实机

按[双眼 USB 安装说明](firmware.zh-CN.md)操作。发布包不含个人 Wi-Fi、NVS 或服务器凭证。真实对话需要模型 API 权限和 HTTPS Gateway。
