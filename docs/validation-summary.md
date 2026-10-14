# Validation summary

**English** | [简体中文](validation-summary.zh-CN.md) · [Home](../README.md)

This page summarizes dated historical evidence, not fresh acceptance of every later commit. Full original records: [baseline validation](validation.md), [dual-eye validation](dualeye-validation.md), [training history](../training/README.md), and [model card](../training/models/MODEL_CARD.md).

## Recorded evidence — 2026-10-13 / 2026-10-14

- Native eye checks covered 13 states, deterministic output, round clipping, transitions and blinking under ASan/UBSan. The portable component compiled for ESP32-S3; the full historical 1.83 firmware also built. No DualEye board driver acceptance was performed.
- The initial dual-eye version completed two separate 30-minute runs: host mock audio/native rendering and browser WebAudio/canvas. These were automated, with microphone off and browser output muted; they are not real-device calls or listening tests. Host renderer averaged 19.48 fps. Browser process memory was not measured.
- Real-server checks exercised three rounds of synthesized Mandarin audio, cancellation, synthesized interruption, reconnect and mute. One subsequent connection failed before TLS readiness with `ECONNRESET`; later retries passed. The failure remains recorded.
- The later full-round-eye/closed-standby revision passed 16 Node session/simulator regressions and a real-server recent-context restoration check (11.704 seconds, 14 audio chunks, no observed errors). Its change did not receive a new 30-minute endurance run; the earlier run is not relabeled as revision acceptance.
- V5 research weights are 45,128 bytes. Synthetic held-out tests and 410 real-child **ordinary-speech negative clips** do not establish real-child target-word recall. The public model history has known limitations; current sources no longer distribute weights.
- A server `memory.extract_failed` timeout was observed. Automatic memory extraction/summary stability remains an unresolved item.

## Still pending

Real microphone household wake testing, separate adult/child target-word results, real speaker quality, natural interruption latency, DualEye display/audio drivers, actual AEC reference mapping, board FPS/peak resources, enclosure acoustics, 8-hour false-wake testing and 72-hour endurance. Successful simulation or compilation does not substitute for these checks.

For the open-source documentation/startup revision, see [repository publication checks](open-source-validation.md). That report records fresh checks separately from the historical voice and hardware evidence.
