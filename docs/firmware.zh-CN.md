# 固件与 USB 安装

[English](firmware.md) | **简体中文**

## 板型与构建

微雪 ESP32-S3-DualEye-LCD-1.28 **非触摸版**，16MiB Flash / 8MiB PSRAM。固定 ESP-IDF **5.5.5**，依赖 ESP-SR 2.5.3、ESP-TFLite-Micro 1.4.1、esp_codec_dev 1.5.11、esp_lcd_gc9a01 2.0.4、esp_websocket_client 1.8.0；传递依赖由 `firmware/dependencies.lock` 固定。

从 [1.0.0 Release](https://github.com/skiyo/pikoo/releases/tag/v1.0.0) 下载模型包，校验摘要并阅读模型条款。

```sh
. /path/to/esp-idf/export.sh
PIKOO_FIRMWARE_VERSION=1.0.0 \
PIKOO_WAKE_POLICY=/absolute/models/wake-policy.json \
bash tools/build-device.sh /absolute/models/hi_pikoo.tflite
```

上述命令只构建，不访问 USB。可用 `PIKOO_BUILD_DIR` 指定独立目录。模型须匹配策略摘要与固件前端；文件上限 512KiB，运行 arena 和耗时单独验证。当前模型 98,064 字节。正常构建关闭诊断、veto 与音量迁移选项。

## 安装下载的发布包

解压 `hi-pikoo-firmware-1.0.0.zip`，从解压根目录操作。工具位于 `tools/`，已校验镜像位于 `firmware/build-dualeye/`，无需编译即可运行相同 USB 命令。先激活 ESP-IDF 5.5.5 Python 环境；macOS 也可双击 `tools/Pikoo-USB.command`。

首次安装前，用 `esptool read_flash 0x0 0x1000000 factory-full.bin` 备份完整 16MiB。私密目录内同时保存 `manifest.json`：`{"full_backup_sha256":"完整备份的SHA256"}`。安装器会先验证备份与实机一致，再迁移分区，不能用其他板子的备份。

私密 JSON 包含 `ssid`、`password`、`endpoint`、`token`。地址为无查询参数的 `wss://YOUR_HOST/api/realtime`。可运行 `python tools/configure.py --output /private/config.nvs.bin` 隐藏输入密码和凭证，或使用 USB 助手。设备不需要模型服务 API Key。

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py diagnose --port PORT --command status
python tools/device.py configure --port PORT --build firmware/build-dualeye --config /private/device.json
python tools/device.py restore --port PORT --backup /private/factory-backup
```

首次安装在写入前准备全部镜像及私人 NVS。升级核对分区后只更新应用，保留 Wi-Fi、凭证、音量和会话状态。重新配置替换 NVS、清除会话；恢复使用完整 16MiB 原厂备份。不整片擦除、不改 eFuse、无 OTA；开发包未启用 Flash/NVS 加密。

## 按键与音频

单击 BOOT 唤醒或停止回答，双击结束会话，长按 2 秒静音；占用状态下长按明确接管。RESET 保留配置重启。待机闭眼。原生 Live 使用双向单声道 PCM16 16kHz；协商为 24kHz 的下行经过重采样。连续播放使用有界预缓冲和播放代次，丢弃旧音频。

音量保存在 NVS，新设备默认 -24dB。推荐家庭初始设置：`python tools/device.py diagnose --port PORT --command 'volume -2'`；按实际外壳和喇叭调整，破音则降低。喇叭异常发热时停止播放并断电。

[接线与引脚](hardware.zh-CN.md) · [协议](gcp7.md) · [模型卡](../models/hi-pikoo/MODEL_CARD.zh-CN.md)
