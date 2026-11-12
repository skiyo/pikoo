# Live 与 Terra

本页说明保留的 GCP 7 Gateway 模式。端侧 Agent 的当前行为、部署与限制见[本地 Agent](local-agent.zh-CN.md)。

[English](openai-live.md) | **简体中文**

当前路径为原生 **gpt-live-1 + gpt-6.1-terra**。配置 `PIKOO_VOICE_PROVIDER=openai-live`、`AGENT_PROTOCOL=none`，两模型都需要账号权限，无自动供应商切换。

Live 默认 Marin，只用中文回答，名字保留 Pikoo。`PIKOO_LIVE_VOICE` 可选受支持的内置音色，新会话生效；语气指令不保证固定倍速。服务器 PCM 增益 `PIKOO_LIVE_OUTPUT_GAIN_DB` 为 0–12dB，与设备 DAC 音量独立；模板为 12dB，设备保留 NVS 音量。

Live 按上下文选择是否回复，不要求每轮叫名字；指令要求避免家人闲聊、咳嗽、电视和无意义应声，但不能保证准确识别每段话的对象。

原生音频双向为单声道 PCM16 16kHz。需要 `pikoo.audio.continuous.v1`；`pikoo.audio.pcm16.v1` 开启设备原生采样率输出，兼容客户端可收到流式转换的 24kHz。以事件采样率为准。连续音频携带流标识、代次和序号，不伪造 `audio.done`。

设备回报播放队列、DMA 估计、可听输出和人声活动。预缓冲 900ms、最大等待 1500ms。停止立即清空本地播放，再用保存文字重建连接；旧代次丢弃。自然插话由 Provider 驱动，受 AEC 和缓冲影响。

Terra 通过 Responses 委派完成推理、工具；独立请求做互动分类、摘要和记忆，Standard/default、低推理、`store:false`。分类每 5 秒最多一次、单会话一个在途、超时 5 秒视为未知，不阻塞逐包音频。只把明确互动纳入自动长期学习。有效空闲 60 秒、语音/不确定最多延长 15 秒；相关播放与有界工具执行期间不误休眠。

告别按上下文判断，等待相关回答播放排空后关闭，异常等待有上限。休眠保留近期文字，不恢复旧声音。工具保留家庭隔离、超时及调用 ID 持久去重，迟到结果不重启旧会话。

[服务端配置](../server/README.zh-CN.md) · [记忆](context-memory.zh-CN.md) · [协议](gcp7.md) · [完整技术说明](openai-live.md)。本机诊断 `/api/pikoo/live-status` 区分语音、委派、分类及记忆用量；缺失最终用量标为估计，不代表组织余额。真实 API 测试会收费。
