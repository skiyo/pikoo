# 固件与 USB

[English](firmware.md) | **简体中文**

## 构建

目标为非触摸版微雪 DualEye ESP32-S3，16 MiB Flash、8 MiB PSRAM。使用 ESP-IDF 5.5.5 与锁定组件。按[快速开始](getting-started.zh-CN.md)下载模型并构建，版本默认来自 `VERSION`。正式构建关闭详细 Agent 追踪与诊断镜像。

## USB 安装流程

使用 IDF Python 环境与 pyserial/esptool，只连接一块板，并关闭其他串口监视器。安装前使用[设备工具](../tools/device.py)创建并校验完整 Flash 备份；备份含私人凭证，须放在 Git 外，仅用于原板恢复。

```sh
python tools/device.py backup --port PORT --backup /private/factory-backup
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup /private/factory-backup --config /private/pikoo.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup /private/factory-backup --config /private/pikoo.json
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py configure --port PORT --config /private/pikoo.json
```

首次安装写入经校验的构建镜像，再经 USB 写入统一配置。同布局升级只更新应用，修改配置只更新配置；家庭数据、音量和屏幕方向保留。未配置设备显示 USB SETUP，不开启语音连接。不整片擦除，不写 eFuse。

```sh
python tools/local-agent-usb.py --port PORT export /private/family.json
python tools/local-agent-usb.py --port PORT import /private/family.json
python tools/local-agent-usb.py --port PORT forget
python tools/local-agent-usb.py --port PORT reboot
```

USB 写入要求静音待机。导入和忘记配置后需重启。`forget` 删除包括 Wi-Fi 在内的服务配置，保留家庭数据。家庭导出不含服务凭证。设备尚无当前格式配置时，需要重新填写并 provision。

## 按键与音频

单击 BOOT 唤醒或停止回答，双击结束并清除短期上下文，长按静音或解除静音；RESET 保留设置重启。新设备默认音量 -24 dB，已有音量保留；USB 助手可调音量与屏幕方向。

macOS 控制台打开时避免额外改写复位控制线。应用启动会短暂重连 USB 外设，出现一次重新枚举属预期行为。不要同时运行两个串口监视器。
