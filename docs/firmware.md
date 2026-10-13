# 硬件、编译与 USB 交付

## 采购

微雪 ESP32-S3-Touch-LCD-1.83-EN，无电池版，SKU 32791；16MB Flash、8MB PSRAM、1.83 英寸触摸屏。配套扬声器和 MX1.25 连接线须与商家确认；另备 USB-C 数据线、稳定 5V USB 电源和保护壳/桌面支架。150–250 元是预算目标，不是已核实的成交价格。首版不需要电池、摄像头、电机、存储卡或另购麦克风/功放。

[微雪官方硬件与原理图入口](https://docs.waveshare.net/ESP32-S3-Touch-LCD-1.83/)。到货核对具体 PCB 版本后再上电。

## 固定环境

ESP-IDF v5.5.5（提交 `b774170ff46c393eeb5e495ea37936038d3f4f4f`），目标 ESP32-S3。BSP 2.0.0、ESP-SR 2.5.3、ESP-TFLite-Micro 1.4.1；其余依赖由 `main/idf_component.yml` 和 `dependencies.lock` 固定。不要丢弃 lock 文件进行无审查升级。

```sh
git clone --branch v5.5.5 --recursive https://github.com/espressif/esp-idf.git /path/to/esp-idf
cd /path/to/esp-idf
./install.sh esp32s3
. ./export.sh
cd /path/to/pikoo/firmware
idf.py set-target esp32s3
idf.py build
```

下载官方 GitHub 工具失败时可设置 `IDF_GITHUB_ASSETS=dl.espressif.com/github_assets` 使用乐鑫镜像。本次 Mac arm64 已编译出应用、bootloader、分区表和空 SR 模型分区；不是硬件烧录成功的证明。模型在应用中嵌入，未启用 ESP-SR WakeNet。

## USB 配置与烧录

在已激活的 ESP-IDF 环境中：

```sh
cd /path/to/pikoo
python tools/flash.py --port /dev/cu.usbmodemYOURDEVICE --dry-run
python tools/flash.py --port /dev/cu.usbmodemYOURDEVICE
python tools/configure.py --port /dev/cu.usbmodemYOURDEVICE --output /private/pikoo.nvs.bin
```

配置工具交互输入 2.4GHz Wi-Fi、WSS 地址和独立设备 token；密码/token 不回显。不写 Google Key、家庭资料。NVS 位于 `0x9000`，大小 `0x10000`；固件刷写工具根据构建产物读取地址，不覆盖 NVS。配置镜像含凭证，权限 600，不上传 GitHub。开发版尚未启用 Flash/NVS 加密和安全启动，有物理读取条件的人可能取得设备凭证。

可用 `--config /private/config.json` 非交互配置，键为 `ssid,password,endpoint,token`。设备 token 从管理员签发的直连码 `#d.` 后取出并 URL 解码；不要把整条配对 URL 填作 token。首次未配置时屏幕提示 USB 配置，不循环崩溃。固件重刷保留配置；重配会覆盖整个设备 NVS 分区，先保存需要的配置。

恢复：USB 进入板商文档中的下载模式，重刷同一套构建产物，再写入新签发凭证。旧凭证通过服务器 `pikoo-admin revoke ID` 撤销。首版不提供 OTA。

## 音频实现与到板验证顺序

硬件录放统一 16kHz。上行 PCM16 单声道、JSON/Base64；下行 24kHz 经过 63-tap FIR 2/3 重采样。采集、AFE/唤醒、播放和 UI 独立任务，上传队列/下行 PCM/网络队列有上限；溢出关闭本次连接再重连。取消先关功放、换播放代次并清队列，再发送取消和播放回执。结束回执采用 I2S 写入后 50ms 的保守 DMA 上界（4×10ms + 余量），不在收到 `audio.done` 时立即发送。该时序到板后必须测量。

ES7210 四通道 16bit TDM 暂映射为 MIC1、MIC2、参考 ADC3、忽略 ADC4；I2S 使用两个 32bit slot 保持 64 BCLK/LRCK，ES8311 取各 slot 高 16bit。AFE 输入描述 `MMRN`，AEC 打开，WebRTC 降噪，关闭重复 WakeNet。此映射基于 BSP/原理图，尚未用实机录音确认。

到板先核实电源/PMIC、BCLK/LRCK、32bit 高低半字顺序和通道，再播放低音量测试音，分通道录音确认环回，最后标定 AEC 延迟和增益。未经这些检查，不能把“集成 AEC”当作“回声消除可用”。还需测 TFLM 内部状态兼容性、arena 实际占用、PSRAM 推理时延、DMA 下溢和取消停声时间。

待机不发送环境音；本地醒来后等 TLS/语音就绪再提示，之后开始上行。当前提示音与上传时序仍需在实机确保提示音不被误判。静音开关停止网络上传和模型处理，但不等同于物理断开麦克风电源。TLS 信任 CA、验证证书，先 SNTP 校时；不固定短期 IP 证书指纹。

全双工、1 米童声唤醒、自然插话、30 分钟实机通话、8 小时误唤醒与 72 小时稳定性仍待板子和真实家庭环境测试。
