# 设备接入协议

Pikoo ESP32 接入契约（实测 GCP 7.0.0）
本次只交付服务器接口与参考事件，不包含固件、硬件 AEC、唤醒或设备实测。

地址与身份
WebSocket：wss://203.0.113.10/api/realtime?sessionId=<本次会话ID>
握手 HTTP 头：Authorization: Bearer <单独签发的设备令牌>
浏览器的合法 Origin：https://203.0.113.10
每块设备单独签发并保存可撤销令牌；绝不能把 Google API Key 或服务器 root 凭证写入 ESP32。
以 root SSH 执行 pikoo-admin pair --endpoint https://203.0.113.10 --name 'ESP32 living room'。
生成的 https://203.0.113.10/c#d.<URL编码令牌> 中，取 #d. 后内容并 URL 解码就是设备令牌。二维码/链接本身同样是凭证。
TLS 必须验证可信 CA 与 IP SAN，设备需先校准时间。IP 证书每约 6 天更换，不要固定证书指纹；不要用跳过证书验证的方式投产。

首包
下面的能力集合是服务器实测接受的集合，不必声明尚未实现的能力。
{
  "type":"session.hello",
  "event_id":"esp32-boot-1",
  "protocol":{"min":"7.0.0","max":"7.0.0"},
  "client":{"type":"web","version":"1.0.0","instance_id":"esp32-living-room"},
  "capabilities":["input.audio","input.text","playback.receipts","session.heartbeat","session.takeover"],
  "locale":"zh-CN",
  "time_zone":"Asia/Shanghai",
  "connection":{"voice_enabled":true,"input_enabled":true,"output_enabled":true,"text_only":false}
}
client.type 的可用枚举需按固定版 Schema 实现；此处 web 是验收时使用并被接受的值，不是要求 ESP32 实现网页。
instance_id 为设备稳定标识，重连不变；event_id 每条消息唯一。不同设备不应共享 instance_id。
同一家庭身份只允许一个活动 Client；若明确要抢占旧设备，可在 connection 加 takeover:true。
服务返回 session.ready（protocol_version:"7.0.0"），随后 voice.ready（inputSampleRate:16000, provider:"google-live"）。收到 voice.ready 后再发送音频。
/api/health 的 contractVersion 与 GCP 版本不是同一概念；不能拿健康接口的 5.x 版本号决定 WebSocket 首包。

上行音频
单声道、16,000 Hz、16 bit little-endian signed PCM，无 WAV 文件头。
用 UTF-8 JSON 文本帧承载 Base64 PCM；不要直接发送二进制 Opus、MP3 或 WAV。
实测每 100 ms 发送 3,200 字节 PCM；固件可采用更短帧并做好节流和队列上限。
{"type":"input_audio_buffer.append","event_id":"esp32-audio-2","audio":"<base64 PCM>"}
本次使用 Google 上游 VAD，测试在说话后继续发送 1.5 秒静音以等待断句。真实麦克风连续采集即可，无需为每帧发送 commit。

文字输入
{"type":"conversation.item.create","event_id":"esp32-text-3","parts":[{"type":"text","text":"你好"}]}

下行音频与实际事件
固定 2.0.1 当前实测下发事件为 audio.delta / audio.done，audio.delta.audio 是 Base64 PCM，sampleRate 为 24000，单声道 16 bit little-endian。
每条音频携带 responseId；客户端按 responseId 管理播放队列。不要只依赖文档中的 response.output_audio.* 名称而漏掉当前实际事件。
{"type":"audio.delta","audio":"<base64 PCM>","sampleRate":24000,"responseId":"response_...", "event_id":"evt_..."}
开始实际播放时回复：{"type":"playback.started","event_id":"...","responseId":"response_..."}
收到 audio.done 仅表示发送结束；应等声卡／I2S 缓冲播放完毕后再回复：
{"type":"playback.ended","event_id":"...","responseId":"response_..."}
若硬件输出不是 24 kHz，需在设备端重采样；不能按 16 kHz 直接播放 24 kHz 数据。
服务还会发送 transcript.delta、transcript.final、voice.state 等事件，可用于显示状态。工具执行也可能产生没有音频的完成事件，不能把第一个 audio.done 当作任意回答的播放结束。

打断与取消
自然插话：保持上行采音；服务检测到新语音后下发 playback.clear。立即停止 I2S、清空排队音频，并回复 playback.cancelled。
主动取消：先在本地停止并清空播放，发送 response.cancel 和旧 responseId 的 playback.cancelled；不能等网络返回才清队列。
{"type":"response.cancel","event_id":"esp32-cancel-4"}
{"type":"playback.cancelled","event_id":"esp32-cancel-5","responseId":"旧回答ID","reason":"user_cancel"}
把旧 responseId 标记失效，丢弃迟到音频。验收中主动取消后仍收到 48,000 字节旧音频，被客户端正确丢弃；服务端停止请求不代表网络和声卡缓冲瞬间清空。
当前 Google 取消可能重建上游会话；收到新的 voice.ready 后再继续下一次输入。
硬件全双工还需要 AEC，协议通过不能替代扬声器回声环境实测。

心跳与断线
收到 session.ping：
{"type":"session.pong","event_id":"esp32-pong-6","request_event_id":"收到的 ping.event_id"}
断线立即清空本地播放；重连使用同一个 instance_id，重新鉴权和发送 session.hello。采用带抖动的退避；401/403 应停止重试并排查凭证/Origin，429 应等待额度恢复。
媒体增量不回放，断线前的音频不能自动续播；不要把旧缓冲带入新连接。sessionId 保持相同可继续相同语义会话，改用新值则新开会话。

参考
deployment/ 为实际宿主与兼容代码。
https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/docs/gateway-protocol.zh.md
https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/shared/protocol/gateway-client-protocol.mjs
