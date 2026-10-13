# Pikoo

USB 常供电、带表情屏幕的家庭语音伙伴。设备负责本地唤醒、音频和显示；独立服务器负责中文对话、家庭共享记忆和摘要。首版不做声纹识别、摄像头、电机或手机 App。

**当前是可编译的开发预览，不是已通过实机验收的成品。** 板子尚未到货。已有桌面交互/协议模拟器、ESP32-S3 固件、25KB 的“你好皮酷”实验模型，以及脱敏服务器部署材料。真实中文童声尚未加入本次模型；导入与分组评估已准备好，等待数据访问权。

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
| `training/` | 合成数据生成、模型训练/量化、流式评估、中文童声导入 |
| `tools/` | 核心测试、USB 配置和烧录工具 |
| `docs/` | 协议、采购、构建、部署和实际验收记录 |

## 开发检查

```sh
./tools/test-core.sh
node --test firmware/simulator/*.test.mjs
(cd server && npm test)
python3 -m unittest discover -s tools -p 'test_*.py'
python3 -m unittest discover -s training -p 'test_*.py'
```

固件构建、USB 配置见 [开发与硬件说明](docs/firmware.md)。首选板型 **微雪 ESP32-S3-Touch-LCD-1.83-EN，无电池版，SKU 32791**；不要购买其他尺寸的相似板。还需支持数据的 USB-C 线、5V 电源和匹配扬声器，向商家确认是否随板附带。

家庭资料、API Key、代理订阅、设备凭证、私人录音、模型训练原始数据不提交。训练代码和通用人设模板可公开，使用受限语料训练出的模型默认留在本地。来源和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。

详细通过项、失败项和待验收项见 [实际测试记录](docs/validation.md)。
