# Release verification — 2.0.0

**English** | [简体中文](release.zh-CN.md)

Repository, firmware and compatibility package versions are 2.0.0. The ESP C++ Agent connects to OpenAI through Mihomo and keeps replaceable credentials, lists, explicit memory and bounded text context locally. The old Gateway remains available for rollback.

Status: 2.0.0 is built and flashed. The migrated shopping list was read correctly in a human voice test. The owner accepted the audio and authorized submission and main integration after silent regression. The device is left muted; the old remote Agent is stopped and disabled, while the Mihomo device proxy is active and enabled.

Validation completed: 93 simulator/server tests, 60 Python tooling tests, ASan/UBSan core regressions, accelerated eight-hour PCM playback with zero underruns, and 100 actual Mihomo/mock-OpenAI nested TLS/CONNECT/WebSocket cases. Earlier 30-minute/eight-hour wall-clock soaks used the initial streaming core. Board tests cover 100 USB reopen cycles, 20 control-line resets, credential replacement/recovery, 16/24 kHz speech and persistent write/reboot readback. Interruption, stale tool results and split transcript constraints have regression coverage.

See [measurements and commands](local-agent.zh-CN.md) and [sanitized results](verification-2.0.0.json). Occasional speech discontinuity was reported before the owner requested no more audible tests; its acoustic cause is unconfirmed. This does not certify all family acoustics, real-child wake recall, physical zero-underrun behavior or 24-hour board endurance.

Build with the [firmware guide](firmware.md), with detailed Agent tracing disabled. The existing public model bundle remains compatible when its hash matches the policy. `tools/package-release.py` packages tracked source, firmware, USB tools, model, checkpoint, licenses and checksums; private inputs remain outside Git. Never publish private NVS, Wi-Fi, API/proxy credentials, family profiles or recordings. Original code/artwork uses Apache-2.0; model-containing firmware retains separate model and dependency terms.

Export new family data before rollback. Keep a verified backup for the same board and the legacy connection configuration. Start the compatibility Gateway before selecting legacy mode over USB.

Public model/firmware packaging is blocked while [model redistribution permission](../models/hi-pikoo/distribution-status.json) is pending. See the [publication audit](public-audit.md). Technical test success does not grant upstream rights.
