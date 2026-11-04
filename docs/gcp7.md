# Device protocol / 设备协议

GCP 7.0 with Pikoo continuous-audio capabilities. This is the current 1.0.0 device contract; transport provider details stay behind the Gateway.

## Authentication and readiness

Connect to `wss://YOUR_HOST/api/realtime?sessionId=LOGICAL_SESSION_ID` with `Authorization: Bearer DEVICE_TOKEN`. Use a unique stable device instance ID, revocable device credential and trusted TLS CA. Sync time before validating TLS. Never embed provider keys or pin an expiring leaf certificate.

```json
{
  "type":"session.hello",
  "event_id":"device-event-1",
  "protocol":{"min":"7.0.0","max":"7.0.0"},
  "client":{"type":"esp32","version":"1.0.0","instance_id":"living-room-device"},
  "capabilities":["input.audio","input.text","playback.receipts","session.heartbeat","session.takeover","pikoo.audio.continuous.v1","pikoo.audio.pcm16.v1"],
  "locale":"zh-CN",
  "time_zone":"Asia/Shanghai",
  "connection":{"voice_enabled":true,"input_enabled":true,"output_enabled":true,"text_only":false,"takeover":false}
}
```

Wait for `session.ready` and `voice.ready` before audio upload. Read the returned sample rates and stream/generation metadata. An occupied session needs explicit user takeover. Auth/model/quota failures are not successful readiness.

## Audio and playback

Upstream is mono signed little-endian PCM16, 16 kHz, no WAV header:

```json
{"type":"input_audio_buffer.append","event_id":"device-event-2","audio":"BASE64_PCM"}
```

Downstream `audio.delta` carries Base64 PCM, `sampleRate`, `streamId`, `generation`, `sequence` and `continuous:true`. Native Live output is 16 kHz when negotiated. Reset the stream resampler on rate/generation changes; reject older generations and out-of-order duplicate sequence data.

Continuous mode does **not** wait for `audio.done`. Every approximately 200 ms, report actual device playback and local speech activity:

```json
{"type":"pikoo.playback.status","streamId":"LIVE_STREAM_ID","generation":1,"queuedMs":0,"dmaMs":0,"audible":false,"humanSpeaking":false}
```

`dmaMs` is a bounded drain estimate, not proof of per-sample hardware readback. Only report audible while real output is present. Non-continuous clients retain the runtime's response/playback receipt behavior; they cannot pretend to implement Live continuous mode.

## Cancel, sleep and restore

`response.cancel` immediately invalidates local playback; clear queues/DMA, then respect the Gateway's replacement stream generation. Reconnect never plays unfinished old sound. Keep the logical session identifier for valid topic restoration; a new voice transport restores bounded server text, not the previous audio state.

Use session heartbeat and explicit takeover/end behavior from the fixed runtime. The native Live Gateway drives semantic idle and contextual goodbye. Idle sleep closes the connection and eyes without deleting saved topic text. Microphone mute stops capture/inference/upload. Standby runs local wake only.

For exact event parsing and failure behavior, see [device state machine](../firmware/main/main.cpp), [Live adapter](../server/openai-live.mjs) and [Live runtime](../server/live-runtime.mjs). [中文架构说明](architecture.zh-CN.md) · [Architecture](architecture.md).
