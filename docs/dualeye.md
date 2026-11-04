# Eyes and simulator

**English** | [简体中文](dualeye.zh-CN.md)

The original platform-independent C++ eye renderer lives in `firmware/components/pikoo_eyes/`. It outputs left/right 240 × 240 RGB565 frames from device state, animation time, deterministic seed, gaze and volume. Standby is closed-eye; connected listening, thinking, speaking, mute and faults have distinct expressions.

The local Node simulator starts the native renderer and serves only 127.0.0.1. Host/Origin validation remains enabled. Slow frame clients receive the latest image instead of an unbounded backlog; renderer failure must not stall audio. The visual demo needs no remote service. Real voice and wake require explicit configuration and microphone permission.

Run `bash tools/build-eyes.sh`, `bash tools/test-eyes.sh` and `bash tools/start-dualeye.sh`. Primary route: http://127.0.0.1:8793/dualeye; `/wake-test` is an optional local wake test. Browser echo processing is not ESP32 AEC evidence.
