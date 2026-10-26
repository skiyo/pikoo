# Architecture

**English** | [简体中文](architecture.zh-CN.md) · [Home](../README.md)

Pikoo’s family realtime voice AI Agent separates the device, Agent runtime and external realtime model. Offline training is a development workflow, not part of an online conversation. The desktop simulator exercises the device protocol and shares the board’s eye renderer.

## Module boundaries

| Module | Input → output | Responsibility |
|---|---|---|
| `firmware/components/pikoo_core` | PCM, GCP events, user actions → bounded audio/session state | Shared protocol, playback generations, cancellation and resampling |
| `firmware/components/pikoo_eyes` | State, time, seed, gaze, level → two RGB565 frames | Original animation; no ESP-IDF dependency or dynamic allocation |
| `firmware/main` | Board peripherals and core state → capture/play/display | Non-touch DualEye board integration; physical acceptance tracked separately |
| `firmware/simulator` | Explicit browser actions → local graphics/wake and optional remote session | WebAudio/canvas UI, Node relay, C++ process and Python wake worker |
| `server` | Authenticated GCP session → realtime provider and memory tools | Fixed upstream composition plus compatibility adapters |
| `training` | Authorized local audio → INT8 model and evaluation reports | Offline preparation, training, streaming evaluation and Micro compatibility |

## Conversation and audio

1. Standby keeps audio local to the wake model; the UI shows closed eyes. Opening a page does not start capture.
2. Explicit wake connects to the server. Capture is uploaded only after voice readiness; microphone permission is a separate user action.
3. GCP 7 uses JSON/Base64 mono PCM16: 16 kHz upstream, 24 kHz downstream. The firmware baseline resamples output to 16 kHz; browser playback uses its audio context.
4. The player reports completion only after buffered audio drains. Cancellation, interruption and disconnection clear playback and reject late chunks for old responses.
5. Muting stops capture/upload. Thirty seconds of idle conversation returns to standby. The device does not infer speaker identity.

The simulator binds only to `127.0.0.1`, checks Host/Origin and keeps remote tokens in its Node process. `/device` carries audio/session events; `/eyes` is a separate local frame channel with acknowledgement and latest-frame backpressure. A renderer failure does not stop the voice path. Browser AEC is not evidence of ESP32 AEC performance. See [GCP details](gcp7.md) and [eye implementation](dualeye.md).

## State and persistence

- Device: Wi-Fi and revocable device token in NVS; no Google key or household profile. The development firmware has not enabled encrypted NVS/Flash or secure boot.
- Server: provider credentials, persona, shared Markdown memory, summaries and session journal/history in private persistent storage. Deployment templates are in `server/deploy/`.
- Browser: only an opaque conversation ID and timestamp in tab-scoped session storage, expiring after 24 hours since the last connection; no credentials or transcripts are stored there.
- Training computer: authorized datasets, recordings, model weights and detailed reports stay private and outside published artifacts.

Reusing the conversation ID lets the server inject saved recent text into a new provider connection before voice readiness. The fixed upstream implementation limits this to recent messages (approximately 40 messages / 3,500 characters); it is not Gemini native audio-session resumption. Untranscribed speech cannot be recovered, and old audio is not replayed. Explicit End clears the ID; idle, mute and temporary disconnection preserve it.

## Provider and memory integration

`qwen-audio-agent@2.0.1` supplies the gateway, authentication and memory/session machinery. Pikoo's `host.mjs` composes it with Gemini Live compatibility and text-call timeout adapters without rewriting installed upstream files. Gemini Live handles conversation; a configured text model handles memory extraction and summaries. This is an external service with separate availability and terms.

`context-runtime.mjs` composes automatic memory and topic summarisation through a private durable outbox. Both text calls use a 45-second deadline, serial execution, bounded retries and explicit-edit invalidation. Ordinary shared-family facts can be remembered without a “remember” command. Inferred individual profiles remain disabled on the shared device. Connection clocks use Beijing time; current-time questions use the official `get_current_time` tool. See [context, memory and time](context-memory.md) for retention, limits and verification.

The committed server template keeps `AGENT_PROTOCOL=none`. The product term AI Agent describes the combined conversation, memory and tool behavior; it does not require an additional backend Agent process. Configured native tools are described in [Family tools](family-tools.md). MCP integrations require explicit configuration and compatibility/security review; weather and smart-home examples are extension directions, not default services.

Training is not required to serve a conversation. Training/static checks default to 64 KiB, while the current DualEye firmware permits a separate explicit experimental budget up to 512 KiB; see [Training](../training/README.md) and [Firmware](firmware.md). Memory use, timing, accuracy and source rights remain separate release gates. Current public sources provide the pipeline but no weights.
