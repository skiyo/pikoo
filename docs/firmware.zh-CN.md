# 固件与 USB 安装

[English](firmware.md) | **简体中文**

## 构建

目标为微雪 ESP32-S3-DualEye-LCD-1.28 非触摸版，16 MiB Flash / 8 MiB PSRAM。使用 ESP-IDF 5.5.5 和 `firmware/dependencies.lock` 固定的依赖。现有公开[模型包](https://github.com/skiyo/pikoo/releases/tag/v1.0.0)中的权重可继续使用，必须与仓库冻结策略哈希匹配。

```sh
. /path/to/esp-idf/export.sh
PIKOO_WAKE_POLICY=/absolute/path/wake-policy.json \
bash tools/build-device.sh /absolute/path/hi_pikoo.tflite
```

该命令不访问 USB。版本来自 `VERSION` 对应的固件默认版本，可显式设置 `PIKOO_FIRMWARE_VERSION`。正式构建关闭详细 Agent 追踪、benchmark、veto 与音量迁移选项。

## 安装与升级

刷写前备份完整 16 MiB Flash，并校验设备与备份摘要。备份、Wi-Fi 配置、API 密钥和家庭数据保存在仓库外的私密目录。完整备份会包含设备当时的凭证。

从旧布局首次迁移，需写入更新的分区表和应用，保留原 NVS 与模型区；此后相同布局的升级只更新应用。使用 `tools/device.py install` 的备份校验和 dry-run 检查首次迁移，使用 `upgrade` 更新相同布局。不要整片擦除，不写 eFuse。

新设备先在仓库外保存仅含 Wi-Fi 的私有 JSON 配置，再交给下面的安装器。`configure.py --local-agent` 不要求 Gateway 地址与旧设备 token，也不接受将 OpenAI 密钥写入 NVS 镜像。

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json
python tools/local-agent-usb.py --port PORT provision
python tools/local-agent-usb.py --port PORT reboot
```

安装器使用的本地模式 JSON 格式为 `{"mode":"local","ssid":"自己的网络","password":"自己的密码"}`，通过 `--config` 指定私密文件。已配置 Wi-Fi 的设备保留原配置，直接用 USB provision 写入自己的 Mihomo 主机名、代理凭证、OpenAI 项目密钥及采样率即可。凭证在独立普通 NVS 中可覆盖或删除，不进入固件或家庭数据导出。

```sh
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/local-agent-usb.py --port PORT export /private/family.json
python tools/local-agent-usb.py --port PORT import /private/family.json
python tools/local-agent-usb.py --port PORT forget
```

导入或凭证修改后运行 `reboot`。`forget` 删除凭证并关闭本地模式；若要切回旧 Gateway，须事先保留有效的旧连接配置。旧模式可用 `legacy` 选择。USB 写入仅在完全静音待机时接受。

## 音频与操作

单击 BOOT 唤醒或停止回答，双击结束会话，长按静音。RESET 保留配置重启。默认 16 kHz 单声道 PCM16，可通过 provision 选择 24 kHz。I²S、AEC、双眼和唤醒仍为本地实现。音量写入原 NVS，升级保留；新设备默认 -24 dB。按实际外壳与距离调整音量。

macOS 控制台打开时避免触发复位控制线。固件启动会短暂重连 USB 外设，主机可能看到一次端口重新枚举。不要同时运行两个串口监视器。

[本地 Agent、代理和测试](local-agent.zh-CN.md) · [接线](hardware.zh-CN.md) · [旧 GCP 7 协议](gcp7.md)
