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
| Actual voice wake | Earlier V5: the adult user reported no response. Later V7B informal household feedback: both adult testers could wake it, while both child testers consistently could not. **Child wake failed**; no complete individually assigned 20-trial acceptance is available |
| Frozen V7B offline wake check (2026-10-17) | 44/46 development positives detected; 0/455 negative clips triggered, including 0/390 real Mandarin child negatives. After freezing weights/threshold, six reserved adult USB recordings produced 3/3 target hits and 0/3 false wakes. These recordings were excluded from training, tuning, model selection and quantization. Not the 20-trial live-device acceptance |
| V8D follow-up | Software gate: 46/46 original development targets, 0/455 non-target triggers; 19/20 pitch/tempo surrogate targets, 0/20 surrogate non-target triggers. Frozen before board update; image from `1fb83b0` written and device digest verified. Startup inference observed without errors. No family recording used for training, tuning or selection; no real child wake acceptance yet |
| Bounded V7B board runtime | Image `874ca69`: 1,800.464 seconds, 59,510 inferences, no observed resets, inference errors, wake queue drops or I2S errors; uploaded samples 0; maximum inference 8,014 μs. Includes graphics, standby and controlled replay, not natural conversation. Later local-test image has only its separately recorded short checks |
| Authentication / provider | Device validates public TLS certificate and reaches authenticated GCP `voice.ready` |
| Host relay isolation | A direct text request received ten audio chunks. This checks the server, not the device microphone or speaker |
| Device acoustic loop | Three computer-generated Mandarin phrases produced 46, 17 and 16 received audio chunks, returned to listening, and retained the same connection during all three rounds |
| Listening quality | Initial replies were choppy. After 10 ms streaming playback and corrected capture framing, the user confirmed smooth speech, but normal volume remained too quiet; volume adjustment and sustained listening are pending |
| Upload scheduling | Earlier upload queue overflow reproduced. Moving network work and bounding receive processing allowed the three acoustic rounds without overflow/reconnect; longer validation is pending |
| Graphics performance | Observed approximately 8–12 fps in short runs, lower during heavy audio processing; 20 fps target is not met |
| Software regression | Native audio/session and both renderer checks; Node simulator/server suites; seven USB Python tests; training units (two optional runtime tests skipped) passed. These are not hardware acceptance |

## Known issues and remaining acceptance

- Wake diagnosis: the fixed synthesized fixture scored 0.996 offline but did not trigger through the physical microphone. AFE input reached an interval average peak of 0.112; a raw-microphone standby path also failed, so bypassing conversational AEC is not a complete fix. A settled 200-frame feature trace matched desktop reference inference to within 0.0000005, and a four-second USB capture produced exactly matching quantized frontend features on desktop (132 inference blocks). The sample's acquisition rate was consistent with 16 kHz. Tests on that captured audio varied below threshold with gain and pre-roll context. These observations support an acoustic/context generalization problem in V5, not a claim that the speaker, microphone or neural runtime is broken. The threshold remains 0.90 pending measured calibration.
- Standby now sends bounded local raw microphone blocks to the wake microfrontend; conversation upload retains AFE/AEC. Mute, discontinuity and session epochs reset the local model, and local queue drops are counted. Explicit idle-only USB commands `wake trace` (at most 200 inference feature frames) and `wake capture` (at most four seconds of PCM) support private diagnostics. Neither command is part of normal wake operation; interrupted captures are rejected during analysis. Their output may contain sensitive audio/features and must stay in permission-protected local logs. No capture or raw audio is added to this repository.
- Context-only V6 experiments did not establish usable adult wake. The later V7 corpus adds 88 label-screened Google TTS clips (including explicitly synthetic youthful delivery), 502 MInDS-14 Mandarin training negatives and the existing restricted child corpus. Twenty-eight Google clips were excluded as whole batches after transcript/alignment review. V7A improved recall but falsely triggered on three child validation clips and was rejected. V7B retained 44/46 streaming validation target hits with 0/455 false wakes at the unchanged 0.90 threshold. It is 45,128 bytes and passed static compatibility and host Micro/reference parity. Its frozen six-clip adult held-out test passed both exact captured PCM and a separately reported quiet-prefix condition. Source manifests, family audio and restricted weights remain local; fresh live-device adult/child trials are still required. See [wake experiment record](../training/reports/wake-v7b-summary.json).
- Broader frozen-model regression: 53/54 synthesized targets and 1/578 non-target false trigger, including 0/410 real Mandarin child non-targets. The one false trigger is a synthesized incomplete near-phrase; neither full false-wake acceptance nor real child wake recall is passed. Actual device/reference parity on 200 captured feature frames agreed on threshold decisions (maximum probability difference about 0.0000005). Desktop loudspeaker development replay detected 2/4 and 3/4 targets at computer volume 60% and 80%, with 0/4 non-target triggers at each level; geometry/SPL were uncalibrated. Soft youthful synthetic playback remains weak. V7C–F acoustic variants all added validation false triggers and were not promoted. These studies did not use household recordings for model selection.
- New USB-only local evaluation window (`wake test on/off`) blocks remote session creation during wake trials and automatically expires after five minutes. Default/reboot behavior remains ordinary wake. On image `e56222f`, manual session starts and a real neural trigger both stayed local: no reconnect or uploaded samples; automatic expiry was observed after 300.85 seconds. Twenty ordinary-speech child validation clips from distinct corpus speakers replayed through the desktop loudspeaker produced no triggers, inference errors or wake queue drops. This is development replay, not live child target-word acceptance. Normal unmuted standby was restored. The guided run was subsequently interrupted at the user's request; per-trial participants were not recorded, so no individual twenty-trial acceptance is claimed (see follow-up below). Window-close/termination signals (`SIGHUP`, `SIGTERM`) were separately injected into the host test controller with the real board: both restored ordinary unmuted standby with zero uploaded samples. Regression checks also cover a failed result write and a failed local-mode-disable command.
- Playback pauses: whole-chunk conversion was replaced by 10 ms streaming blocks; observed conversion maximum around 2–3 ms in short runs. The user subsequently confirmed smooth playback at normal volume; volume remained too quiet. The user found -24, -18 and -12 dB too quiet; -6 dB has been selected for the next check. The volume build adds -12/-6 dB presets, register readback and NVS persistence; -12/-6 dB read back as registers 174/186. Intermittent write/TLS timeouts caused repeated reconnects; they remain unresolved. A subsequent build doubles TCP buffers, allows a longer write deadline and reports Wi-Fi RSSI for measurement. Sustained speaker checks are pending.
- Hardware AEC reference: the initial stereo capture did not expose MIC3. Two 32-clock slots now unpack ES7210 TDM I²S ADC1/ADC3 correctly; playback reference peaks of about 0.028–0.041 were observed, with quiet floor around 0.00003. Natural interruption and echo rejection still need acceptance.
- User reported a clipped/stuttering beginning followed by smooth speech, especially on the second reply. Diagnostics reproduced a one-sample prefix arriving about 315 ms before real PCM: the previous 200 ms fallback started playback too early. The fallback now starts after at least 10 ms of PCM is queued; the prefix is retained, and short completed responses still start immediately. A regression reproduces this packet timing. Amplifier startup is prepared during an active conversation, with silence during startup; idle/mute/end still turn it off.
- Quiet-test comparison: both FD low-cost and high-performance AEC still saw provider cancellation at -6 dB. At -24 dB, two consecutive rounds completed without unexpected cancellation, but the second had a 114 ms supply gap. This supports residual echo as a working hypothesis, not proof of complete echo rejection. High-performance mode reduced graphics performance and was not retained. The current firmware uses FD low-cost AEC, supports its 512-frame capture blocks, and removes the additional WebRTC NS stage discouraged by ESP-SR's config check.
- Earlier short-run result: with the prefix fix, FD low-cost AEC and server start sensitivity `low` / prefix padding 180 ms, two consecutive acoustic Mandarin rounds at -6 dB received 18 and 21 chunks, with no unexpected playback clear, measured supply gap or reconnect. This is a bounded diagnostic result; it was not heard clearly by the user. No playback-time microphone muting was introduced to obtain this result.
- Subsequent replay did not reproduce that clean result: one response received 13 chunks with a 412 ms supply gap; the next round reconnected without an answer, and another attempt also reconnected. One send was measured at 14.7 seconds despite a nominal 1-second send timeout. The short successful run above therefore does not establish connection reliability. The current candidate uses 40 ms upstream PCM packets (Base64/JSON fits one 4096-byte TLS record) while retaining the 800 ms queue bound. Startup prefill is 500 ms with a 600 ms fallback after substantive PCM arrives; this trades extra onset latency for resilience to the observed initial packet delay. Tiny prefixes remain queued, completed short replies bypass the wait, and cancellation remains immediate. A native regression reproduces the 140 ms first chunk / 520 ms next-arrival trace.
- Current candidate replay: two consecutive replies received 23 and 19 chunks without unexpected cancellation or reconnect. Supply gaps were 2 in the first reply and 0 in the second. The user explicitly confirmed that the **second reply's opening was complete and smooth**. First-reply supply interruptions, longer network reliability and natural barge-in remain unaccepted; increasing prefill did not eliminate all gaps.
- Adult and child wake trials, natural interruption, measured button-stop latency and acoustic echo rejection.
- Same-context recovery after network loss and reset; stale audio rejection on actual hardware.
- Device token revocation and upgrade preservation checks; full factory recovery rehearsal after migration.
- Explicit and automatic memory, correction/deletion and service-restart recall, including the existing long-session extraction timeout.
- Thirty-minute continuous real conversation, eight-hour background false-wake test and 72-hour endurance run. None is claimed passed here.

Credentials, raw device/server logs, household facts, audio and restricted model-containing firmware remain private. Public evidence includes only operational counts and bounded resource measurements. No downloadable full-release firmware is published while these checks remain incomplete.

## 中文摘要

双屏方向已由用户确认正常。当前音量为 -6 dB。缩小上行音频块并增加有上限的起播缓冲后，最近两轮分别收到 23、19 段音频，没有意外取消或重连。用户明确确认第二轮开头完整、顺畅；第一轮仍有两次供音间隙。网络长期可靠性、真实成人/儿童唤醒、自然插话及长期运行尚未验收。V7B 已烧入：开发验证 44/46 命中、0/455 误触发，冻结后六段成人保留录音为 3/3 命中、0/3 误触发。先前镜像的 30 分钟待机与受控回放未观察到重启或推理错误；新版已验证本地测试隔离及五分钟自动退出。真人 20 次测试、儿童目标词和长时间误唤醒仍待完成。本文不把编译、模拟器或收到音频包视为完整实机交付。

## Child wake follow-up / 儿童唤醒后续

The user reported successful adult wake and consistent failure for both child testers. A guided run started but was stopped at the user's request; per-trial participant identity was not recorded, so its partial aggregate cannot establish individual adult or child acceptance. No raw audio was saved, and the board returned to normal standby.

Existing real child corpus rows are ordinary-speech **negatives**, with no natural child recording of the target phrase. A development-only experiment derives pitch/tempo variants from Google TTS for both target and non-target phrases. Source speakers retain their original splits; protected household hashes are rejected before processing. These clips are synthetic surrogates, not real child target positives. The Google Voice Design prototype request for a fictional child voice returned HTTP 400 with a safety-policy rejection; no voice was created and no bypass retries were attempted. This experiment does not automatically change the board model or threshold.

用户报告两位成人能唤醒、两位儿童均无法唤醒。引导测试应用户要求中止，没有逐次记录测试者，部分计数不能作为任何一人的验收；未保存录音，设备已恢复正常待机。现有真实儿童语料仅为非目标普通讲话，负样本成绩不能代表儿童目标词召回率。新实验只对 Google 合成语音做音高、语速增强，保留音色划分并拒绝家庭录音；这些仍不是自然童声正样本。Google 童声音色创建探测被接口安全策略拒绝，没有创建音色或尝试绕过。是否更新板上模型取决于独立开发验证，儿童实测仍未通过。

After training-only mining selected 173 non-target prefixes (130 derived from child corpus training recordings), V8D passed the predefined software gate and was flashed with digest verification. The wake threshold remains 0.90. Fresh individual adult and child trials remain pending. See [V8 development evidence](../training/reports/wake-v8-summary.json).

随后仅从训练集筛出 173 个困难负样本前缀（其中 130 个派生自儿童训练录音），V8D 通过既定软件门槛，已烧入并校验；阈值仍为 0.90。成人及儿童的新一轮实测仍待完成，不能把合成变体成绩当成儿童验收。

## Conversation lifecycle follow-up / 会话交互修复（2026-10-17）

Behavior and limitations: [English](conversation-lifecycle.md) | [简体中文](conversation-lifecycle.zh-CN.md).

Firmware source `dc94618` was built with ESP-IDF 5.5.5 and the unchanged private V8D model, then upgraded in the application partition with device digest verification. Wi-Fi, credentials and screen rotation were preserved.

| Check | Actual evidence |
|---|---|
| Wake is the first utterance | A USB **manual** wake, without a second spoken/text input, produced a real authenticated server answer: 22 audio chunks, followed by listening with upload enabled; this does not measure neural wake accuracy |
| Audio after greeting | The device continued uploading after the answer; no RX/TX or wake inference errors were observed in the short run. A ready-tone cancellation race found during the first run was fixed before the final flash |
| Goodbye logic | Portable C++ and local real-WebSocket integration verify final-user-only matching, farewell playback drain before close, a 20-second stall fallback and no greeting repetition on recovery |
| Acoustic goodbye | Initial computer-generated `皮酷，再见` did not produce a recognized farewell; that run ended by inactivity timeout and was not counted as a pass. A subsequent user trial produced one neural wake detection, an automatic spoken answer, a recognized final-user farewell, and `conversation ended reason=farewell; standby`. The connection closed approximately 3.9 seconds after the farewell transcript, after the answer finished playing. Upload was off in standby |
| Eyes and connectivity | Both C++ renderers verify closed poses for connecting/offline/muted/occupied/auth error; explicit session-to-renderer mapping corrects swapped speaking/thinking states. The user confirmed that the eyes opened after connection and closed after farewell, and that speech was complete |

随后一次真人实测已完成：本地唤醒 1 次，自动回应，识别告别，播放完成后主动断开；用户确认开闭眼正常、声音完整。这是单次会话交互通过，不是四位家庭成员各 20 次的唤醒率验收。儿童识别率、实机自然插话及长期运行的验收状态保持待完成。本轮没有保存麦克风录音；电脑合成音只用于交互测试，没有加入训练数据。设备已回闭眼待机。

## Wake recording and pronunciation audit / 录音与发音覆盖核对（2026-10-17）

The earlier "20 trials" run completed 17 trials on V7B, with 6 detections and no saved audio. Per-trial speakers were not recorded, so the aggregate is not an individual adult/child score and cannot be re-scored with V8D. The separate private recording inventory contains six adult heldout clips (three targets, three non-targets) and two earlier diagnostic clips.

A post-freeze V8D re-test of all eight recordings found **1/3 target hits as recorded, 2/3 with a quiet prefix, and 0/3 non-target false wakes**. The two previously inspected diagnostic positives were both missed and are not blind-test evidence. These findings expose poor real-voice recall despite passing the earlier synthetic development gate; V8D is not accepted for household wake reliability. No household audio was used for training, tuning or model selection, and the board model was not replaced based on these results. [Sanitized evaluation and coverage report](../training/reports/wake-v8d-household-evaluation.json).

The current training manifest has 268 positive rows, including derived variants, all spelling the target in Chinese. It contains no explicit `你好 Pikoo` positive with the intended flatter `pī kū` pronunciation. Future public/synthetic training data must cover both allowed readings, and score adult and childlike voices separately; pitch/tempo augmentation alone does not establish that coverage. Text metadata cannot prove the exact pronunciation of every synthesized clip.

此前所谓“近 20 个样本”是 17 次现场检测记录，没有保存录音，不能重放到新版模型。另存的 8 段成人录音现已全部在冻结的 V8D 上补测，主要 3 段目标词原样仅命中 1 段；静音前缀条件命中 2 段。3 段非目标没有误唤醒，2 段旧诊断目标均漏识别。当前模型不能认定唤醒验收通过。另收到儿童约五六次成功一次的使用反馈，这不是受控的个人 20 次验收。

During a later, separately awakened conversation, one `bounded queue overflow reason=5` and a reconnect were observed. This remains an audio-streaming reliability issue; the successful greeting/farewell interaction does not establish long-session stability.
