# 固件安装、升级与 USB 维护

[English](firmware.md) | **简体中文**

## 选择正确的操作

| 操作 | 写入内容 | 前提 |
|---|---|---|
| `backup` | 电脑上的私有完整 Flash 备份 | 新目录、稳定 USB |
| `install` | 已检查的板级镜像与配置 | 与设备一致的已验证备份、匹配的构建元数据 |
| `upgrade` | 同分区布局的应用镜像 | 板上与构建分区表一致 |
| `configure` | 完整服务配置，然后重启 | 有效私有 JSON |
| 家庭数据 `export` / `import` | 读取 / 替换快照 | 静音待机、私有文件 |
| `forget` | 删除服务配置，包括 Wi-Fi | 操作后重启，家庭数据保留 |
| `restore` | 从备份恢复全部 16 MiB | 同一设备的已验证备份，会覆盖当前数据 |

完整首次安装步骤见[快速开始](getting-started.zh-CN.md)。在软件包根目录运行，准备 pyserial/esptool，选定一个端口并关闭其他监视器。也可执行交互助手 `python tools/usb-setup.py --language zh-CN`；助手默认英文。

## 构建产物与分区

使用 ESP-IDF 5.5.5，执行 `bash tools/build-device.sh "$PWD/models/hi-pikoo/hi_pikoo.tflite"`。镜像与 `flasher_args.json`、`pikoo-board.json` 必须来自同一次构建。安装器检查板型、镜像范围和布局。Release 中单独的 BIN 只包含应用。

| 分区 | 用途 |
|---|---|
| `nvs` | 音量、屏幕方向等设备设置 |
| `phy_init` | 射频初始化数据 |
| `factory` | 应用，6 MiB，偏移 `0x20000` |
| `model` | 模型资源，4 MiB |
| `agent_secret` | 可更新的 Wi-Fi 与服务配置 |
| `agent_data` | 清单、显式记忆、上下文和写入回执 |

使用安装器而不是手工猜测偏移。日常配置不需要整片擦除、配置 Flash 加密或烧写 eFuse。

## 升级和更新配置

升级前先导出重要数据，然后执行：

```sh
python tools/device.py upgrade --port PORT --build firmware/build-dualeye --dry-run
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py configure --port PORT --config /absolute/private/device.json
python tools/device.py diagnose --port PORT --command status
python tools/device.py diagnose --port PORT --command unmute
```

只有需要更新设置时才执行 `configure`。同分区升级保留配置、家庭数据、音量和方向。布局不一致应停止，核对板型和构建，按已备份的首次安装流程处理，不要直接擦除。

## 导出与导入数据

```sh
python tools/local-agent-usb.py --port PORT export /absolute/private/family.json
python tools/local-agent-usb.py --port PORT import /absolute/private/family.json
python tools/local-agent-usb.py --port PORT reboot
python tools/device.py diagnose --port PORT --command unmute
```

导出要求新文件名，排除服务凭证，但仍包含私有清单、记忆和上下文；设备保持静音。导入是**替换快照**，不是合并。需要保留目标设备数据时，先单独导出。规范化后导入上限为 24 KiB。导入后重启，再读回预期条目确认。

## 删除凭证与恢复设备

```sh
python tools/local-agent-usb.py --port PORT forget
python tools/local-agent-usb.py --port PORT reboot
```

该操作删除包括 Wi-Fi 在内的服务设置，保留家庭数据。再次使用云端服务前需重新配置。完整同板恢复使用：

```sh
python tools/device.py restore --port PORT --backup /absolute/private/board-backup --dry-run
python tools/device.py restore --port PORT --backup /absolute/private/board-backup
```

恢复会覆盖全部 Flash，包括新增数据和凭证。工具会验证写回内容；如停留在下载模式，完成后复位设备。备份应私密保管，不提供自动家庭数据合并或跨设备整片迁移。

## 诊断命令

`device.py diagnose` 支持 `status`、`wake`、`stop`、`end`、`mute`、`unmute`、`tone`、音量与方向命令。`wake` 可能打开付费服务会话，`tone` 会发声，静默测试不要使用。维护工具使用静音待机并处理 USB 控制线路。重启后端口变化时应重新查询，不要反复向旧名称发送命令。

[故障排查](troubleshooting.zh-CN.md) · [上下文与存储](context-memory.zh-CN.md)
