# Pikoo

USB 常供电、带表情屏幕的家庭语音伙伴。设备负责本地唤醒、音频和显示；独立服务器负责中文对话、家庭共享记忆和摘要。首版不做声纹识别、摄像头、电机或手机 App。

**当前是可编译的开发预览，不是已通过实机验收的成品。** 当前目标板为已购买、尚未到货的 **ESP32-S3-DualEye-LCD-1.28**。已有原创双眼图形组件、桌面语音/唤醒模拟器和脱敏服务器部署材料；现有板级固件仍是1.83-EN基线，双眼板驱动尚待接入。公开仓库保留早期25KB唤醒基线，本机试用加载45,128字节的V5受限模型；模型权重、家庭录音和受限儿童语料不分发。

双眼试用入口 `http://127.0.0.1:8793/dualeye`：见 [双眼设计与启动说明](docs/dualeye.md) 和 [本轮实际验收记录](docs/dualeye-validation.md)。

![Pikoo 双眼模拟器](docs/images/dualeye/simulator.jpg)

## 快速试用模拟器

使用 Node.js 24 LTS（24.15+）：

```sh
cd server
npm ci --ignore-scripts
cd ..
node firmware/simulator/server.mjs
```

打开 `http://127.0.0.1:8787`。默认使用本地测试音验证唤醒按钮、播放、打断、静音和断网恢复；不需要 Google Key。它模拟应用行为和 GCP 协议，不模拟 ESP32 电气、I2S、AEC 或真实扬声器延迟。

启用实验语音唤醒：按照 [训练说明](training/README.md) 安装 Python 环境，再设置 `PIKOO_WAKE_PYTHON=/absolute/path/to/venv/bin/python` 启动。勾选麦克风后，待机音频仅进入本机模型，不上传服务器、不保存录音。模型启动需要几秒。点击唤醒始终可用。

连接真实服务：在仓库外建立权限为 `600` 的 JSON 文件，包含 `endpoint`（`wss://你的服务器/api/realtime`）与独立签发的 `token`。设置 `PIKOO_SIM_CONFIG=/absolute/private/config.json` 启动。凭证只留在本机服务端，浏览器不会收到它。默认不会抢占其他设备；占用时需明确点击接管。仅监听 `127.0.0.1`。

## 工程入口

| 路径 | 内容 |
|---|---|
| `server/` | 固定 qwen-audio-agent 2.0.1、Gemini 兼容适配、systemd/Nginx/mihomo 模板 |
| `firmware/` | ESP-IDF 5.5.5、微雪 BSP 2.0.0、LVGL、ESP-SR AEC、TFLite Micro |
| `firmware/simulator/` | 浏览器设备模拟器、本地唤醒接口、真实 WSS 连接 |
| `firmware/components/pikoo_eyes/` | 原创、无平台依赖的双眼 RGB565 绘制核心 |
| `training/` | 合成数据生成、模型训练/量化、流式评估、中文童声导入 |
| `tools/` | 核心测试、USB 配置和烧录工具 |
| `docs/` | 协议、采购、构建、部署和实际验收记录 |

## 开发检查

```sh
./tools/test-core.sh
bash tools/test-eyes.sh
node --test firmware/simulator/*.test.mjs
(cd server && npm test)
python3 -m unittest discover -s tools -p 'test_*.py'
python3 -m unittest discover -s training -p 'test_*.py'
```

当前双眼板开发边界见 [双眼说明](docs/dualeye.md)。历史1.83-EN固件构建和USB配置见 [开发与硬件说明](docs/firmware.md)；该构建产物不能直接烧录到已购双眼板。另备USB-C数据线、稳定5V电源和匹配扬声器，向商家确认是否随板附带。

家庭资料、API Key、代理订阅、设备凭证、私人录音、模型训练原始数据不提交。训练代码和通用人设模板可公开，使用受限语料训练出的模型默认留在本地。来源和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。

详细通过项、失败项和待验收项见 [实际测试记录](docs/validation.md)。
