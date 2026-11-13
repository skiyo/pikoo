# 快速开始：从下载到第一次对话

[English](getting-started.md) | **简体中文**

本指南面向 **非触摸版 Waveshare ESP32-S3-DualEye-LCD-1.28**。想直接使用设备，优先下载固件 ZIP；需要修改固件时再从源码构建。以下命令均在解压后的软件包或仓库根目录执行，示例采用 macOS/Linux Shell。请按自己的电脑替换路径和 `PORT`。

## 1. 准备硬件与服务

准备目标开发板（16 MiB Flash、8 MiB PSRAM）、板载麦克风与双屏、兼容且正确连接的扬声器、支持**数据传输**的 USB 线、稳定的 5 V 电源和 2.4 GHz Wi-Fi。首次调试可以不装外壳。通电前按[硬件指南](hardware.zh-CN.md)核对扬声器接口。

还需要以下服务能力：

| 服务 | 协议要求 | 需要准备的内容 |
|---|---|---|
| 实时语音 | `openai_live`，支持客户端委派、PCM、转写和 Decisions | 完整 WSS 地址、模型、音色、API 密钥 |
| 推理 | 支持函数调用的 Responses 或 Chat Completions | 完整 HTTPS 地址、模型、API 密钥 |
| 搜索（可选） | Tavily 或 Responses 网页搜索 | 独立地址、密钥；Responses 还需要模型 |

服务商标注“兼容 OpenAI”不代表支持 Live。购买 API 额度前，先确认对应协议与模型权限。三个服务可以使用不同供应商和密钥。具体要求见[配置参考](configuration.zh-CN.md)。第一次对话可以先关闭搜索。

## 2. 下载正确的软件包

打开 [Pikoo 2.0.0 下载页](https://github.com/skiyo/pikoo/releases/tag/v2.0.0)，下载 `hi-pikoo-firmware-2.0.0.zip` 和 `SHA256SUMS`，解压到新目录。固件 ZIP 包含源码、安装工具、板级镜像及许可说明；单独的应用 BIN **不能作为首次安装的完整镜像**。

先对照 `SHA256SUMS` 中同名文件的记录校验 ZIP。macOS 执行 `shasum -a 256 hi-pikoo-firmware-2.0.0.zip`，Linux 执行 `sha256sum hi-pikoo-firmware-2.0.0.zip`。解压后，在解压目录使用 `shasum -a 256 -c SHA256SUMS`（macOS）或 `sha256sum -c SHA256SUMS`（Linux）校验内部文件。任何校验失败都应停止安装。请阅读[模型条款](../models/hi-pikoo/LICENSE.md)，源码许可与模型许可不同。

预编译镜像位于 `firmware/build-dualeye/`。使用该软件包时无需安装 ESP-IDF，可以直接继续配置和 USB 安装。

## 3. 准备 Python 和私有配置目录

安装 Python 3.11 或更新版本，创建独立环境：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pyserial esptool
mkdir -p "$HOME/.config/pikoo"
chmod 700 "$HOME/.config/pikoo"
cp examples/device.example.json "$HOME/.config/pikoo/device.json"
chmod 600 "$HOME/.config/pikoo/device.json"
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活环境，将私有配置放到仓库外的个人目录。串口通常是 `COM3` 这样的名称。源码构建脚本需要 ESP-IDF 支持的 Bash 环境。

在本地编辑 JSON，将所有 `YOUR_...` 占位值和示例域名替换为自己的 Wi-Fi 与服务配置。保留 `version: 1`，初次使用建议 `search.enabled: false`、`network: {}`。对话默认英文；中文用户把 `agent.language` 改为 `zh-CN`。不要将填好密钥的 JSON 粘贴到公开 Issue 或日志中。

也可通过交互助手创建新文件，注意目标文件必须尚不存在：

```sh
python tools/configure.py --init "$HOME/.config/pikoo/device.json" --language zh-CN
```

校验配置：

```sh
python tools/configure.py --config "$HOME/.config/pikoo/device.json" --dry-run
```

预期出现 `Configuration is valid`。此步骤仅校验格式和边界，不访问 USB 或服务商，因此不代表密钥、模型权限或网络已经可用。

## 4. 确认 USB 串口并备份

只连接一块板，尽量直连电脑，关闭其他串口监视器，然后列出端口：

```sh
python -m serial.tools.list_ports
```

选取接入开发板后出现的端口。macOS 常见 `/dev/cu.usbmodem...`，Linux 常见 `/dev/ttyACM0`，Windows 常见 `COM3`。将下面所有 `PORT` 替换为实际名称。Linux 如提示访问被拒绝，需要配置串口设备组权限，配置后重新登录。

在仓库外指定一个**尚不存在**的备份目录：

```sh
python tools/device.py backup --port PORT --backup "$HOME/.config/pikoo/board-backup"
```

预期生成经过设备校验的完整 16 MiB Flash 镜像及清单。备份可能包含密钥和个人数据，请私密保存并明确对应哪块物理设备。安装器写入前会核对备份，不要修改文件或使用其他设备的备份。

## 5. 预检查并安装

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup "$HOME/.config/pikoo/board-backup" \
  --config "$HOME/.config/pikoo/device.json" --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup "$HOME/.config/pikoo/board-backup" \
  --config "$HOME/.config/pikoo/device.json"
```

预检查验证文件、镜像范围、分区和私有输入，不操作设备。实际安装会核对板上内容与备份，写入镜像，通过 USB 配置服务并重启。操作期间保持供电，不要拔线。应用启动时 USB 短暂重新枚举属于正常现象；端口变化后重新查询即可。

## 6. 确认状态并开始对话

```sh
python tools/device.py diagnose --port PORT --command status
python tools/device.py diagnose --port PORT --command unmute
```

屏幕显示 `MIC OFF` 表示静音。USB 维护会主动进入静音待机，准备对话时需明确取消静音。`USB SETUP` 表示没有有效配置。状态异常时参阅[故障排查](troubleshooting.zh-CN.md)。

说出完整英文唤醒词 **“Hi, Pikoo”**，等待问候，再开始提问。首次验收可询问设备能做什么，添加一条临时购物项，读回清单，再删除这条准确内容。配置中文后，唤醒词仍然是英文，后续使用中文对话。扬声器先使用较低音量，搜索功能需另行开启。

## 7. 后续修改

更换 Wi-Fi、密钥、模型或对话语言无需重新编译：

```sh
python tools/device.py configure --port PORT --config "$HOME/.config/pikoo/device.json"
python tools/device.py diagnose --port PORT --command unmute
```

固件升级、数据导入导出与恢复见[固件和 USB](firmware.zh-CN.md)，日常按键和语音示例见[使用指南](usage.zh-CN.md)。

## 从源码构建

按 Espressif 的安装说明准备并激活 **ESP-IDF 5.5.5** 及 ESP32-S3 工具链：

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
. /path/to/esp-idf/export.sh
idf.py --version
bash tools/build-device.sh "$PWD/models/hi-pikoo/hi_pikoo.tflite"
```

预期生成 `firmware/build-dualeye/pikoo.bin`、分区表、引导镜像和安装元数据。构建脚本读取模型旁的唤醒策略，并检查模型与策略是否匹配。不要把单个 `pikoo.bin` 随意放入另一套构建目录。构建后继续本页的配置与备份步骤。桌面验证见[开发指南](development.zh-CN.md)，常见疑问见 [FAQ](faq.zh-CN.md)。
