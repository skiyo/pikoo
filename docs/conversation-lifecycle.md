# Conversation lifecycle

[English](conversation-lifecycle.md) | [简体中文](conversation-lifecycle.zh-CN.md)

Updated: 2026-10-17. This changes interaction behavior without retraining V8D.

- A local wake detection or explicit wake button opens WSS. The eyes stay closed while connecting and open on `voice.ready`.
- The device submits `你好皮酷` as the first user text turn, using GCP `conversation.item.create` and `input.text`. The server answers without a second utterance. Repeated readiness, provider cancellation and automatic reconnect do not repeat the greeting.
- A complete final **user** transcript matching an explicit farewell (such as `再见`, `皮酷再见`, `拜拜` or `晚安`) stops microphone upload. The device waits for the corresponding farewell response to finish hardware playback, then closes WSS, clears the conversation identifier and returns to closed-eye standby. If the response stalls, it closes within 20 seconds; connection loss during farewell also returns to standby without retrying.
- This is a conservative phrase matcher, not general intent recognition. Questions, quoted mentions and negations such as `再见是什么意思` or `不要说再见` do not end the call. An unrecognized farewell wording still needs BOOT double-click or inactivity timeout.
- Connecting, offline, muted, occupied and authentication-error states have closed eyes with separate labels. Listening, thinking and speaking have open eyes, with normal blinking. Closing/opening animates over approximately 220 ms. An explicit enum mapping prevents speaking/thinking from being swapped.
- Automatic network recovery preserves the recent conversation identifier; explicit farewell, explicit end and 30-second conversational inactivity clear it. Long-term server memory is independent.

Portable C++ and browser regression tests cover greeting repetition, final-user-only matching, negations, playback drain, stalled responses, disconnect during farewell and closed-eye states. These tests do not establish human wake accuracy, acoustic AEC quality or physical screen appearance. Live device evidence is recorded separately in the device validation report.
