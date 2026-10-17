# DualEye device validation — 2026-10-17

[English firmware guide](firmware.md) | [中文固件说明](firmware.zh-CN.md)

**Development testing is in progress. This is not the complete household release.** Simulator and software checks are separate from physical acceptance. Results below apply to a non-touch ESP32-S3-DualEye-LCD-1.28 with 16 MiB Flash and 8 MiB PSRAM.

## Speaker report correction

The user subsequently corrected the heating report: the speaker had **not** heated, and explicitly requested another playback. The temporary mute/end stop was lifted for a short controlled replay at the normal conservative volume. The user subsequently confirmed smooth speech, while -24 dB and -18 dB remained too quiet; sustained speaker operation is not accepted by this correction alone.

用户随后澄清：喇叭并未发热，先前反馈有误，并要求重播。已解除临时静音。随后用户确认声音顺畅，但 -24 和 -18 dB 两档均偏小；持续播放验收仍待确认。

## Observed results

| Check | Evidence / status |
|---|---|
| USB, flash and recovery material | Chip identified, complete 16 MiB factory backup verified against device before partition migration; private backup retained locally |
| First installation and upgrades | DualEye build flashed with image verification; upgrades check actual partition layout and write only the application |
| Display orientation | Both displays render; initial 90-degree orientation defect corrected and user confirmed normal direction |
| Speaker short test | Two low-volume tones heard clearly; user reported no heat. This does not establish sustained or normal-volume operation |
| Input audio | Physical microphone responds; AFE produces approximately 16,000 samples/s; no observed I2S read/write errors in the recorded short runs |
| Wake resources | Local restricted V5 file 45,128 bytes; allocated arena 256 KiB, reported arena use 18,828 bytes; observed maximum inference roughly 8–10 ms in these runs. Target-word accuracy is not accepted |
| Authentication / provider | Device validates public TLS certificate and reaches authenticated GCP `voice.ready` |
| Host relay isolation | A direct text request received ten audio chunks. This checks the server, not the device microphone or speaker |
| Device acoustic loop | Three computer-generated Mandarin phrases produced 46, 17 and 16 received audio chunks, returned to listening, and retained the same connection during all three rounds |
| Listening quality | Initial replies were choppy. After 10 ms streaming playback and corrected capture framing, the user confirmed smooth speech, but normal volume remained too quiet; volume adjustment and sustained listening are pending |
| Upload scheduling | Earlier upload queue overflow reproduced. Moving network work and bounding receive processing allowed the three acoustic rounds without overflow/reconnect; longer validation is pending |
| Graphics performance | Observed approximately 8–12 fps in short runs, lower during heavy audio processing; 20 fps target is not met |
| Software regression | Native audio/session and both renderer checks; Node simulator/server suites; seven USB Python tests; training units (two optional runtime tests skipped) passed. These are not hardware acceptance |

## Known issues and remaining acceptance

- Playback pauses: whole-chunk conversion was replaced by 10 ms streaming blocks; observed conversion maximum around 2–3 ms in short runs. The user subsequently confirmed smooth playback at normal volume; volume remained too quiet. The user found -24, -18 and -12 dB too quiet; -6 dB has been selected for the next check. The volume build adds -12/-6 dB presets, register readback and NVS persistence; -12/-6 dB read back as registers 174/186. Intermittent write/TLS timeouts caused repeated reconnects; they remain unresolved. A subsequent build doubles TCP buffers, allows a longer write deadline and reports Wi-Fi RSSI for measurement. Sustained speaker checks are pending.
- Hardware AEC reference: the initial stereo capture did not expose MIC3. Two 32-clock slots now unpack ES7210 TDM I²S ADC1/ADC3 correctly; playback reference peaks of about 0.028–0.041 were observed, with quiet floor around 0.00003. Natural interruption and echo rejection still need acceptance.
- User reported a clipped/stuttering beginning followed by smooth speech. The new build adds 120 ms initial audio buffering (200 ms maximum wait, short completed replies start immediately), 30 ms silent amplifier startup and later playback-start receipts. Software edge-case tests passed, but the user still reported truncation, especially on the second conversational reply. Timing diagnostics observed provider-cancelled responses as well as one 145 ms supply gap. Quiet-room isolation is pending; echo-triggered cancellation is a hypothesis, not established acceptance.
- Adult and child wake trials, natural interruption, measured button-stop latency and acoustic echo rejection.
- Same-context recovery after network loss and reset; stale audio rejection on actual hardware.
- Device token revocation and upgrade preservation checks; full factory recovery rehearsal after migration.
- Explicit and automatic memory, correction/deletion and service-restart recall, including the existing long-session extraction timeout.
- Thirty-minute continuous real conversation, eight-hour background false-wake test and 72-hour endurance run. None is claimed passed here.

Credentials, raw device/server logs, household facts, audio and restricted model-containing firmware remain private. Public evidence includes only operational counts and bounded resource measurements. No downloadable full-release firmware is published while these checks remain incomplete.

## 中文摘要

双屏方向已由用户确认正常。实机经三轮电脑合成中文输入均收到了回答，三轮没有重连。更新为小块连续播放并修正采集格式后，用户确认声音顺畅，但正常音量偏小，正在调整；AEC 参考通道、真实成人/儿童唤醒、自然插话及长期运行也没有完成验收。本文不把编译、模拟器或收到音频包视为完整实机交付。
