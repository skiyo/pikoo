# Live and Terra

This page describes the retained GCP 7 Gateway mode. See [local Agent deployment](local-agent.zh-CN.md) for current ESP behavior and limits.

**English** | [简体中文](openai-live.zh-CN.md)

The active path is native **gpt-live-1 + gpt-6.1-terra**, not a renamed Realtime adapter. `PIKOO_VOICE_PROVIDER=openai-live` selects it, `AGENT_PROTOCOL=none` remains in effect. Both models require account access. There is no automatic provider fallback.

## Speech

Live uses Chinese-only replies, keeps the name Pikoo, and defaults to Marin. Use `PIKOO_LIVE_VOICE` to select a supported built-in voice; changing it requires a new session. Speaking style is requested through instructions, not an exact playback-rate multiplier. Server gain `PIKOO_LIVE_OUTPUT_GAIN_DB` (0–12 dB) and device DAC volume are separate; default templates use 12 dB server gain and devices preserve NVS volume.

Live handles speech and decides whether a response is appropriate. It is instructed to avoid family background chatter, coughs, television and unnecessary acknowledgements. This is probabilistic, not guaranteed speaker-address detection, and does not require the name in every turn.

## Audio and interruption

Native mono PCM16 is 16 kHz both ways. Capability `pikoo.audio.continuous.v1` is required. `pikoo.audio.pcm16.v1` enables native-rate device output; compatibility clients can receive stateful 24 kHz conversion. Rate metadata is authoritative. Audio frames carry stream ID, generation and sequence. Continuous mode does not synthesize `audio.done`.

Devices report queue/DMA estimates, actual audible output and speech activity. Playback uses 900 ms prefill with a 1500 ms wait limit. Stop clears local audio immediately and replaces the upstream connection with saved text; stale generations remain rejected. Natural interruption is provider-driven and depends on physical AEC and buffering.

## Terra and lifecycle

Responses delegation handles reasoning and tools. Separate Terra calls classify interaction and organize memory, using Standard/default service tier, low reasoning and `store:false`. Directed interaction, background and unknown are private decisions, never spoken labels.

Classification coalesces new transcript content, at most one in flight and once per 5 seconds; 5-second failure becomes unknown without a retry loop. Only directed interaction refreshes semantic activity and enters automatic long-term learning. Effective idle is 60 seconds with at most 15 seconds extra for pending speech/uncertainty; relevant playback and bounded tasks protect ongoing work.

Goodbye is interpreted in context; a quoted word or family-to-family farewell must not end the session. Valid farewell audio drains before closing, with bounded waiting. Sleep retains text context, never unfinished audio. Tools keep owner scope, timeouts and durable call-ID reservations; late results do not revive closed sessions.

## Operations

[Server setup](../server/README.md) · [Memory](context-memory.md) · [Protocol](gcp7.md). `GET /api/pikoo/live-status` is local-only diagnostic data, not an account balance. Persisted usage distinguishes voice, delegation, classification, summaries and memory; missing final usage is marked estimated. API smoke tests require private credentials and incur provider charges.
