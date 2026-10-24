# Quiet companion mode

**English** | [简体中文](companion.zh-CN.md)

Pikoo can remain connected after an explicit wake and let Gemini Live decide whether speech is directed to it. Family conversation and background audio should receive no acknowledgement; calling Pikoo, asking for its opinion, and clear follow-up questions should receive a reply. This is a model decision, not a guaranteed addressee classifier or speaker identification.

## Enable both ends

1. Set `PIKOO_COMPANION_MODE=on` in the private server configuration and restart the gateway when no call is active. The default public template is `off`.
2. Upgrade the physical device to `0.2.0-bm17-comp1` or newer through the normal application-only upgrade flow. This preserves Wi-Fi, credentials, screen rotation and recent conversation identity.
3. Send `companion on` through the existing owned USB monitor, or `python tools/device.py diagnose --port YOUR_PORT --command 'companion on'`. The setting is saved in device NVS. Diagnostics show `companion=1`.
4. Explicitly wake the device. It greets once and keeps its eyes open while connected. The 30-second inactivity sleep is disabled in this mode; **microphone audio continues to be uploaded to the server and Google until mute, farewell or explicit end**. Idle before wake and muted states still do not upload.

The browser simulator currently retains its ordinary 30-second inactivity timer; the persistent companion setting described here is for the physical board. BOOT long press mutes, double press ends, and normal press stops a playing reply. `Pikoo，再见` and `Goodbye, Pikoo` are recognized whole-utterance farewell examples; ordinary existing farewell phrases remain supported. A bare family-to-family goodbye can still match this conservative phrase matcher. It is not addressee-aware farewell intent detection.

To revert, send `companion off` and set the server flag to `off` before the next session. Device automatic sleep returns; the local wake model is unchanged.

## Native API and composition

The provider sends `proactivity: {proactiveAudio: true}` with the quiet-companion policy. In the tested deployment on 2026-10-20, the normal **v1beta endpoint rejected this field with 1007**, despite the [capabilities guide](https://ai.google.dev/gemini-api/docs/live-api/capabilities#proactive-audio) listing it. The same model and key accepted it on **v1alpha**. Opt-in companion connections therefore use the verified Google v1alpha endpoint; ordinary connections keep their original endpoint. Unsupported custom endpoints fail explicitly rather than silently losing selective responses. Recheck this behavior on provider upgrades.

`companion-runtime.mjs` is a fixed-version composition hook for `qwen-audio-agent@2.0.1`. For automatic Google microphone turns only, it disables the missing-reply watchdog and keeps the display listening: silence is an expected result. Transcript recording and turn cleanup remain active. Explicit text/tool requests and network timeouts retain their existing safeguards. No installed upstream package is edited and no backend LLM is added.

## Identity, context and memory

The canonical written name is **Pikoo**, spoken **pī kū / pee-koo**, both level syllables. New and reconnected sessions receive this identity policy. The device and simulator submit `你好 Pikoo` at wake; old Chinese spellings in history do not rename it. Actual pronunciation remains a listening check rather than a text-transcript guarantee.

Recent context and family memory retain the [existing rules](context-memory.md): no inferred speaker identity; no ambiguous personal preferences; no stored secrets; corrections and deletion invalidate obsolete learning. Explicit stable facts may be saved with memory tools without a request to “remember”. Background batch extraction runs after session closure and can be delayed or fail; this change does not guarantee continuous extraction during an indefinitely open conversation. Muted or disconnected speech was not heard. Transport reconnection can still occur; this mode is not a promise of an uninterrupted connection.

The original household wake recordings remain test-only. Generic synthetic audio is only protocol/behavior evidence, not child wake-word, acoustic echo-cancellation, or long-duration hardware acceptance.

See [actual validation and pending checks](companion-validation.md).

## Silence-label fix, 2026-10-24

Google's native selective audio is enabled. It can choose silence; it is not
a deterministic addressee or name check. Pikoo keeps that behavior and natural
follow-ups, with no mandatory name keyword.

The provider has emitted the reserved `<no speech>` label, sometimes followed
by `{pause}`. Older composition treated it as assistant dialogue. The new
`silence-output.mjs` suppresses known label forms and their initial buffered
PCM before presentation or history. Normal speech is released once ordinary
transcription arrives; audio-only output falls back at turn completion. The
initial buffer is bounded, cancellation clears it and lifecycle completion
continues. Existing assistant-only label messages are omitted from restored
Live context; original stored history is retained. User quotations and normal
English explanations remain intact.

43 server checks passed on the production Node runtime. Seven isolated real
Google scenarios passed: silence before/after, Chinese/English background
conversation, directed Chinese/English replies and an English follow-up without
repeating the name. The final native run did not generate a silence label;
known-format suppression is verified separately in protocol/frontend tests.
The first failed native run, including the suffix defect, is retained. The
fix is deployed and the existing ESP32 reconnected. No firmware was flashed.
Physical listening and longer household observation remain pending. See the
[sanitized validation record](../server/reports/silence-output-20261024.json).
