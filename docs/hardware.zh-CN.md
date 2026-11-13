# 硬件与接线

[English](hardware.md) | **简体中文**

目标为[微雪 ESP32-S3-DualEye-LCD-1.28](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/) **非触摸版**：ESP32-S3、16MiB Flash、8MiB PSRAM、两块 GC9A01A 240 × 240 圆屏、ES8311 输出与 ES7210 采集。

准备匹配的喇叭及线材、可传数据的 USB-C 线、稳定 5V USB 电源、2.4GHz Wi-Fi，以及可选的[打印外壳](../hardware/enclosure/README.zh-CN.md)。无需电池、SD 卡或外接麦克风。

喇叭只能接官方标明的 **扬声器接口**，不能因外观相似接到电源接口。通电前按官方资料或商家确认插座和阻抗，先低音量测试。

| Interface | Pins |
|---|---|
| Display SPI | MOSI42 / SCLK41 / DC45 |
| Left screen | CS47 / RST48 / BL46 |
| Right screen | CS38 / RST8 / BL39 |
| I2C | SDA11 / SCL10 |
| I2S | MCLK12 / BCLK13 / WS14 / ADC15 / DAC16 |
| Amplifier / BOOT | GPIO9 / GPIO0 |

原理图中麦克风为 ES7210 MIC1，衰减的播放参考为 MIC3；固件按已配置的 ADC1/ADC3/ADC2/ADC4 通道次序提取麦克风与参考。ESP-SR 使用参考做 AEC，板上有编解码芯片不等于已经完成回声验收；需要装壳、正常音量和自然插话实测。

[USB 安装](firmware.zh-CN.md) · [外壳与 STL](../hardware/enclosure/README.zh-CN.md)

## 通电前

核对板卡版本及非触摸目标型号。断电连接扬声器，按接口标注与厂商要求接线，不凭插头形状判断用途或极性。裸板放在绝缘表面，给线缆留出应力释放空间。仅充电 USB 线不能完成配置。

## 初次上电顺序

1. 装壳前确认 USB 枚举和双屏显示。
2. 配置设备并查询状态，不要立即提高音量。
3. 明确取消静音，测试低音量播放和完整唤醒词。
4. 按图文指南安装外壳，不挤压屏幕玻璃或遮挡麦克风。
5. 装壳后重复唤醒、插话、播放和供电检查。

模拟器不能验证阻抗、接线、供电、发热或声学。其他板型仅引脚相似也不够，还需要正确的编解码器路由、麦克风/参考通道顺序、显示时序与 PSRAM/Flash 布局。

## 记录哪些条件

硬件结果应同时记录板卡版本、扬声器规格、线材电源、外壳材料与固件身份。使用预期日常音量测量，不只做裸板测试。AEC 依赖参考通道和最终声学结构，应检查插话与首字丢失，而不只是是否能听到回答。
