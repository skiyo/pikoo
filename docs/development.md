# Development

**English** | [简体中文](development.zh-CN.md)

## Environment and checks

Node.js 24+, npm, Bash and C++17 are enough for the offline simulator. Python 3.11 is used for USB/training tooling. Install `training/requirements.txt` only when training/inference is needed. Firmware requires ESP-IDF 5.5.5. Keep upstream versions pinned.

```sh
(cd server && npm ci --ignore-scripts)
bash tools/check.sh
```

The checks exercise native audio/session/eye cores, simulator/server behavior and Python tooling. Optional runtimes may skip checks when not installed; do not interpret a skip as success. No tests should open a family microphone or call a paid API implicitly.

## Change an expression

Edit `firmware/components/pikoo_eyes/`, retain the platform-independent C++ API and 240 × 240 RGB565 output. Use `bash tools/test-eyes.sh`, then `bash tools/start-dualeye.sh`. Keep rendering lower priority than audio and drop stale frames.

## Add a board

Introduce an explicit board adapter for display, audio, amplifier and controls. Start from `firmware/main/board_display.cpp` and `board_audio.cpp`; preserve the device state machine in `pikoo_core`. Verify microphone/reference order and DMA timing before enabling full duplex. Never reuse a different board's flash layout without migration and backup checks.

## ESP local Agent

Sessions/tools live in `firmware/components/pikoo_core/pikoo_agent.cpp`; ESP storage and transport adapters are `firmware/main/agent_storage.cpp` and `agent_tunnel.cpp`. Update schemas, durable validation, call-ID deduplication and native regressions together. Run silent shared-core tests with `tools/test-local-agent.sh`. The Node tool/Provider sections below apply to the retained Gateway.

## Add a tool

Start at `server/family-tools.mjs` and `deepseek-search.mjs`. Register tool schemas with the runtime, validate input, retain owner scope, enforce timeouts and return factual errors. Follow the durable call-ID handling in `openai-live.mjs`; late results must not speak into closed sessions. Extend `*.test.mjs` before making external calls.

## Replace a voice Provider

Use the registry in `server/host.mjs` and the native Provider in `server/openai-live.mjs`. Preserve continuous-audio capability negotiation, rate metadata, cancellation generations, playback feedback, text history and authentication. Verify real provider access separately from offline tests. Do not change only a model-name string between incompatible APIs.

## Train/export a wake model

See [training](../training/README.md). Keep family recordings outside training, augmentation, calibration and model selection. Bind every export to its policy hash and frontend fingerprint; keep host and firmware smoothing identical. Evaluate natural fast speech without shifting pitch and continuous speech negatives without resetting frontend state per clip.

## Release changes

Update `VERSION`, package metadata, firmware project version and the model card together. Use the [release checklist](release.md). Include third-party license texts for redistributed binaries. Do not commit NVS, generated audio, credentials or personal memory.
