# ESP32 本地 Agent

这个开发分支保留原有 GCP 7 模式，另提供 ESP32-S3 发起的原生 GPT‑Live 会话。设备执行家庭工具、保存文字上下文和控制麦克风与播放。Terra、网页搜索和 Decisions 分类由 OpenAI 在同一 Live 连接上运行。远程主机只需要 Mihomo 的转发能力。

## 网络

将 `server/deploy/mihomo-device.yaml.example` 的 listener 和两条规则合入 Mihomo。把专用规则放在宽泛的域名或 MATCH 规则前。使用设备可验证、与主机名匹配的 TLS 证书和专用代理凭证。现有只绑定回环的混合端口可以保留。先在目标版本用 `mihomo -t -f /path/to/config.yaml` 检查配置。设备以 TLS 连接 Mihomo，在 CONNECT 隧道上再次校验 OpenAI TLS，并只在内层发送 OpenAI Bearer。此路径需要 OpenAI 项目有 GPT‑Live 1、Terra、Decisions 和托管搜索权限。

## 设备

1. 构建固件后备份原机 Flash。首次迁移要刷应用和更新后的分区表。表中新增加密凭证和家庭数据分区，原分区位置不变。不要用本地安装工具把密钥打包进任何 NVS 镜像。
2. 专用凭证分区需要一个已有、已妥善保护的 HMAC_UP eFuse 密钥块。固件检查该条件，利用 HMAC 分别派生两个 NVS XTS 密钥。固件不会自动烧录 eFuse。USB 写入在设备处于静音待机时才开放。
3. 用 ESP-IDF 环境运行 `python tools/local-agent-usb.py --port /dev/cu.usbmodem… provision`。凭证由终端提示输入，写入设备后重启。首次真机测试前保留旧网关作为回滚路径。
4. `export 备份.json` 导出家庭数据到权限为 0600 的新文件。`import 备份.json` 载入数据，重启后生效。`legacy` 切回原模式并重启。导出包含家庭内容，凭证分区不参与导入导出。导入现有服务端数据时，将已确认的条目映射到下列格式，原始备份在验证条目数前保留。

```json
{"version":1,"shopping":["牛奶"],"todo":["拿快递"],"memory":["家里偏好温水"],"calls":[],"history":[]}
```

每组最多 32 项，每项最多 512 UTF‑8 字节。快照总上限为 24 KiB。设备以双槽提交，最近 32 个写调用 ID 与状态保存在同一快照。短期上下文最多 12 条。背景用户转写只在内存等候分类，未获明确互动判定的内容不保存。清单、显式记忆和上下文独立。设备对确切条目执行删除和修改，清空要求确认。指定网页能否读取取决于 OpenAI 搜索返回的来源。此版不运行后台自动记忆学习，也不做跨设备共享。

## 无声回归

宿主需要 C++17、OpenSSL 开发库、ESP-IDF 源码中的 cJSON，以及 Python 3。macOS 可将 `OPENSSL_PREFIX` 指向 Homebrew 的 OpenSSL。测试只处理固定合成 PCM 和内存帧。

```sh
# ASan/UBSan 和短跑
PIKOO_SANITIZE=1 tools/test-local-agent.sh 15
# 100 次真实 Mihomo TLS / CONNECT / TLS / WS，OpenAI 端为本机假服务
tools/test-local-agent.sh --network --mihomo /path/to/mihomo --cycles 100
# 30 分钟墙钟跑流
tools/test-local-agent.sh 1800 --realtime
# 加速的 8 小时等量 PCM 和双眼帧回放
tools/test-local-agent.sh 28800
# 8 小时墙钟浸泡
tools/test-local-agent.sh 28800 --realtime
```

本机网络测量是 Mihomo 到回环夹具的 TLS、CONNECT 和首 PCM 延迟。桌面网络驱动用系统 TLS，设备的嵌套 mbedTLS 通过 ESP-IDF 交叉编译验证，实际握手峰值需要上板。虚拟播放延迟包含保留的 900 ms 预缓冲。旧链路对照测的是同一 PCM 的旧事件解析和播放入队，远程部署端到端延迟留到实机对照。生产切换必须验证真实出口、证书、模型权限、硬件 AEC 和 Wi‑Fi 后再停旧网关。

## 静默测量记录

Mihomo v1.19.33 与本机 OpenAI 夹具完成 100/100 次双 TLS、CONNECT 和 Live WebSocket 连接。测量覆盖外层及内层证书拒绝、代理 403/407、目的域名与端口拒绝、模拟 API 401/429、代理重启和 WebSocket 分片。

| 回环指标 | P50 | P95 |
| --- | ---: | ---: |
| TCP + 代理 TLS | 2.54 ms | 4.95 ms |
| CONNECT | 0.27 ms | 1.17 ms |
| OpenAI 内层 TLS | 4.37 ms | 8.38 ms |
| 连接开始到首个模拟 PCM | 10.07 ms | 18.51 ms |

加速回放处理 8 小时等量 PCM，执行 100 次本地会话重建，播放欠载为 0，队列峰值 14,720 样本（920 ms），虚拟唤醒到播放 P50/P95 均为 910 ms。新路径单包解析、解码和入队 P95 为 4 µs，同进程旧事件格式对照为 2 µs。整场测试约 4.59 CPU 秒，macOS 峰值 RSS 约 2.95 MiB。此组是桌面加速回放，墙钟浸泡和硬件测量独立验收。
