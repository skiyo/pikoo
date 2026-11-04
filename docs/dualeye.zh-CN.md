# 双眼与模拟器

[English](dualeye.md) | **简体中文**

原创 C++ 绘制核心位于 `firmware/components/pikoo_eyes/`，独立于平台。输入设备状态、时间、固定随机种子、视线和音量，输出左右两块 240 × 240 RGB565。待机闭眼；连接后倾听、思考、说话、静音和故障分别表达。

本机 Node 模拟器启动原生绘制进程，仅监听 127.0.0.1，保留 Host/Origin 检查。慢画面客户端只收最新帧，绘制故障不能阻塞语音。图形演示无需服务端，真实语音与唤醒需明确配置并授权麦克风。

运行 `bash tools/build-eyes.sh`、`bash tools/test-eyes.sh`、`bash tools/start-dualeye.sh`。主入口 http://127.0.0.1:8793/dualeye，`/wake-test` 为可选本地唤醒测试。浏览器回声处理不作为 ESP32 AEC 证据。
