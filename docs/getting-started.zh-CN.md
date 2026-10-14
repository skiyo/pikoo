# 开始使用

[English](getting-started.md) | **简体中文** · [首页](../README.zh-CN.md)

## 离线双眼演示

需要 Node.js 24 或更新版本、npm、Bash 和 C++17 编译器。macOS 安装 Xcode Command Line Tools；Debian/Ubuntu 可使用 `build-essential`。其他具备相应工具的平台可能可用，但尚未验证。浏览器需要 Canvas 和 WebAudio。

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
(cd server && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

打开 http://127.0.0.1:8793/dualeye。启动工具自动编译绘制程序，默认离线运行。可以切换表情、实际像素视图、点击唤醒/会话、停止和模拟断线。离线回复为测试音。麦克风和远程连接需要用户主动操作/配置；离线图形演示不需要模型或 Python。

保持终端窗口打开；按 Ctrl+C 或执行 `bash tools/stop-dualeye.sh` 停止。macOS 也可以双击 `tools/` 中的启动/停止文件。端口占用只提示，不结束其他进程。使用 `PIKOO_SIM_PORT=8794 bash tools/start-dualeye.sh` 换端口；访问 `127.0.0.1`，不要改成 `localhost`，Host/Origin 校验是有意设置的。`/` 保留原模拟器，`/wake-test` 为独立本地唤醒测试页。

直接前台运行也可以：

```sh
bash tools/build-eyes.sh
PIKOO_SIM_PORT=8793 node firmware/simulator/server.mjs
```

## 可选：连接自己的实时服务器

按[服务器运维说明](../server/README.md)部署自己的服务器，并单独签发设备 token。将 JSON 配置保存到仓库外，例如 `/absolute/private/simulator.json`：

```json
{
  "endpoint": "wss://your-server.example/api/realtime",
  "token": "REPLACE_WITH_YOUR_DEVICE_TOKEN"
}
```

```sh
chmod 600 /absolute/private/simulator.json
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

token 留在本机 Node 进程；页面在主动唤醒后连接，需要说话时再授权麦克风。按钮发起对话不需要唤醒模型。保留环境设置但强制离线可使用 `PIKOO_SIM_MOCK=1`。修改配置前先停止已运行的实例：启动工具会复用自己的既有进程，不会暗中替换配置。

## 可选：自己的授权唤醒模型

当前源码不含权重。可以使用本机已保留的模型，或用来源授权明确的音频训练。Git 历史中的实验权重未获本仓库 Apache-2.0 模型授权，见[训练说明](../training/README.md)和[模型卡](../training/models/MODEL_CARD.md)。

训练环境以 Python 3.11 为基线。可选依赖包含 TensorFlow，下载量明显大于单纯图形演示：

```sh
python3.11 -m venv /absolute/private/pikoo-wake-env
/absolute/private/pikoo-wake-env/bin/pip install -r training/requirements.txt
export PIKOO_WAKE_PYTHON=/absolute/private/pikoo-wake-env/bin/python
export PIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite
export PIKOO_WAKE_LABEL='My local wake model'
bash tools/start-dualeye.sh
```

可以同时配置 `PIKOO_SIM_CONFIG`。待机麦克风音频只进本地进程，远程语音就绪后才上传。`/wake-test` 只做本地唤醒评估，不发起远程会话。缺少配置会明确报错，不隐式下载模型。模型要与训练的流式结构及 worker 匹配，不能任意替换 TFLite 文件。

## 固件构建

**当前完整板级集成针对历史 1.83-EN，不要烧录到双眼板。** 独立图形核心和主机检查可以单独使用。按[固件说明](firmware.md)准备 ESP-IDF 5.5.5 后，显式指定授权模型：

```sh
idf.py -C firmware -DPIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite build
```

缺少模型或超过 64 KiB 会拒绝构建。检查和 USB 工具见[开发说明](development.zh-CN.md)。包含受限模型的固件不能公开发布。

## 常见问题

| 现象 | 检查内容 |
|---|---|
| 缺少运行环境/编译器 | Node 24+、C++ 编译器和 `server/` 依赖；`PIKOO_NODE` 可指定可执行文件 |
| 端口占用 | 停止自己的旧实例或修改 `PIKOO_SIM_PORT` |
| 眼睛不可用 | 执行 `bash tools/build-eyes.sh`；图形故障与语音分开定位 |
| 唤醒不可用 | 同时指定可执行 Python、可读模型，并安装可选依赖 |
| 远程鉴权失败 | 核对地址和独立设备 token，不在 Issue 中粘贴凭证 |
| 远程超时 | 区分网络出口、地区、密钥与额度；换模型不能解决地区封禁 |
