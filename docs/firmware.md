# DualEye firmware and USB deployment

English | [简体中文](firmware.zh-CN.md)

The default target is **ESP32-S3-DualEye-LCD-1.28, non-touch**. The previous 1.83 project is retained in `firmware/boards/legacy183/`; never flash it to DualEye. Compilation, simulator tests and physical acceptance are separate.

## Build

Use ESP-IDF **5.5.5**. Dependencies are pinned: ESP-SR 2.5.3, ESP-TFLite-Micro 1.4.1, esp_codec_dev 1.5.11, esp_lcd_gc9a01 2.0.4 and esp_websocket_client 1.8.0. No wake weights are distributed.

```sh
. /path/to/esp-idf/export.sh
./tools/build-device.sh /absolute/private/authorized-model.tflite
```

The script uses an isolated configuration in `firmware/build-dualeye/`, 240 MHz CPU and 8 MB octal PSRAM. Wake files are limited to 64 KiB; inference arena, AFE and frame buffers consume additional runtime RAM. Builds containing restricted weights remain local and ignored by Git.

## USB deployment

On macOS double-click `tools/Pikoo-USB.command`. It finds an active IDF environment, `PIKOO_IDF_PATH`, a workspace toolchain, or `~/esp/esp-idf`. It does not terminate other processes. Connect one board only. The assistant offers first installation, upgrade, status, factory recovery and private configuration changes.

```sh
python tools/device.py install --port PORT --backup /private/factory-backup --config /private/config.json --dry-run
python tools/device.py install --port PORT --backup /private/factory-backup --config /private/config.json
python tools/device.py upgrade --port PORT
python tools/device.py configure --port PORT --config /private/config.json
python tools/device.py diagnose --port PORT --command status
python tools/device.py restore --port PORT --backup /private/factory-backup
```

Private JSON fields: `ssid`, `password`, `endpoint`, `token`. The endpoint is `wss://HOST/api/realtime` without query parameters. Issue one revocable device token per board. Never store provider API keys or family facts in firmware. Private inputs use mode 600 files in mode 700 directories. This developer workflow does not enable secure boot or flash/NVS encryption; physical flash access may expose device credentials.

First installation migrates the partition layout. It requires `factory-full.bin` (exactly 16 MiB) and `manifest.json` with `full_backup_sha256`, then verifies the backup against the device before writing. It prepares private NVS before writing bootloader, partition table, application, SR resources and NVS in one operation. It never erases the whole chip or changes eFuses. Factory recovery restores and verifies the full 16 MiB.

Layout: NVS `0x9000`, 64 KiB; application `0x20000`, 6 MiB; SR resources `0x620000`, 4 MiB. Upgrade compares actual device/build partition tables and updates only the application. Reconfiguration replaces NVS and clears the conversation identifier. No OTA is included.

## Interaction

| Input | Action |
|---|---|
| BOOT press | Wake from standby; locally stop a speaking/thinking response |
| Double press | End conversation and close eyes |
| Hold 2 seconds | Toggle mute; while occupied, confirm takeover instead |
| RESET | Restart with configuration and a valid conversation identifier |

A first press does not wait for double-click detection. Release BOOT for normal startup; use the official BOOT/RESET procedure for recovery download mode. Standby keeps eyes closed and sends no ambient audio. Wake readiness submits the greeting as the first user turn; reconnects use a ready tone before upload. Mute stops I2S input, ADC, inference and upload. Thirty seconds without user speech or playback closes the transport and sleeps. Network reconnection, mute and idle sleep preserve the conversation identifier; explicit end and farewell clear it. The identifier expires after 24 hours. Restoration recovers recent text context, never interrupted audio.

## Audio, graphics and diagnostics

Original Pikoo integration uses two GC9A01 panels with PSRAM rendering and an internal DMA strip. Target animation is 20 fps; measured results are recorded separately. SPI2 uses MOSI42/SCLK41/DC45; left CS47/RST48/BL46, right CS38/RST8/BL39. I2C SDA11/SCL10; I2S MCLK12/BCLK13/WS14, ADC data15/DAC data16; amplifier9; BOOT0.

The schematic connects the physical microphone to ES7210 MIC1 and attenuated amplifier-output reference to MIC3. The [ES7210 datasheet](https://files.waveshare.com/wiki/common/ES7210_DS.pdf), Figure 2e and register 0x12, explains why ordinary ADC12 stereo does not contain MIC3. Levels and echo cancellation require physical validation. ESP-SR uses `MR` and WakeNet is disabled. The audio wire uses two 32-clock stereo slots at 16 kHz; ADC TDM I²S is packed in the order ADC1/ADC3/ADC2/ADC4, with ADC1 and ADC3 unpacked as microphone/reference. The DAC receives PCM16 in the upper half of each slot. Downstream 24 kHz PCM uses the shared streaming FIR resampler. Responses initially buffer 900 ms of audio, with a 1500 ms maximum wait and an immediate start for completed short replies. Amplifier startup sends 30 ms of silence before speech. Four 10 ms DMA descriptors use a conservative 50 ms drain bound. Cancellation immediately gates PA, invalidates the playback generation and rejects late response audio.

Keep one USB connection open for endurance observation:

```sh
python tools/monitor.py --port PORT --private-log /private/device.log
```

Opening a fresh USB serial connection may restart the board. Commands: `status`, `wake`, `stop`, `end`, `mute`, `unmute`, `takeover`, `tone`, `volume low`, `volume normal`, `volume higher`, `volume louder`, `volume full`, `rotate 90`, `rotate 270`. Short tones are available only in standby. First-start DAC is -24 dB. Presets are low -36 dB, normal -24 dB, higher -12 dB, louder -6 dB and full 0 dB; allowed range is -50 to 0 dB. The full preset adds 6 dB over the previous ceiling and does not add software PCM amplification. Volume is saved in NVS and restored at startup. Diagnostics report the selected dB and DAC register readback. Stop immediately if the speaker heats up.

Metrics exclude credentials, transcripts and family facts: uptime/reset reason, heap/internal/PSRAM, frame rate, microphone/reference/output levels, I2S errors, upload frames, reconnects and wake inference time. USB controls do not add public GCP events.

References: [Waveshare non-touch source, pinned commit](https://github.com/waveshareteam/ESP32-S3-DualEye-Touch-LCD-1.28/tree/f16371ca7b7d4e17de6d6f6ea293981b37c0ca51/example/ESP32-S3-DualEye-LCD-1.28/ESP-IDF-5.5.1), [official board documentation](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/). Integration and artwork are original; Espressif panel/codec drivers retain their licenses. No vendor player or Jollybot assets are copied. See [physical validation](device-validation.md) and the [historical 1.83 notes](firmware-legacy183.md).

## Transport recovery and display load

The client coalesces each masked WebSocket header and payload into one TLS write. The ESP-IDF 5.5.5 client still owns handshake, certificate verification, receive framing and its TX lock. A project linker wrapper intercepts only the explicitly bound connection; it supports the configured 8192-byte send fragments and control frames. Do not use `esp_transport_get_payload_transport_handle()` to find the parent in this hook: the pinned implementation resets receive-frame state. The original SDK checkout is not patched.

A dedicated sender task drains control events before microphone packets, so upload stalls cannot block session dispatch or downstream decoding. Event IDs are atomic across the two producers. A nominal 2.5-second send timeout and bounded 3.2-second upload queue tolerate brief TCP retransmission delays. This is recovery capacity, not a deliberate playback delay; sustained loss can still add latency or disconnect. Queue storage is explicitly in PSRAM; FreeRTOS dynamic queue allocation otherwise consumes internal RAM required by Wi-Fi/TLS. Cancellation still invalidates queued audio by epoch.

Shutdown interrupts socket IO before joining the client task. It avoids the pinned graceful-close API's unbounded CLOSE-send path; intentional shutdown may therefore appear as an abnormal WebSocket close in gateway logs. Objects and the coalescing buffer are freed only after the client has stopped. Diagnostics add `frame_tx`, `frame_tx_errors`, `stop_max_us`, `upload_pending`, `session_steps` and `tx_holds`. The explicit USB-only `tx hold` command pauses only the sender for 1.5 seconds, once, to verify dispatch/playback isolation; normal operation never enables it.

After a complete sleeping frame, standby redraws only the union of the previous and current sleeping-arc row bounds (about 30 rows in ordinary standby). State/rotation changes and wake transitions redraw the whole frame. Host tests compare clipped output with complete frames for all states and both eyes, and check damage coverage at extreme gaze/tilt. The connecting ring computes its angular phase once per frame instead of repeating trigonometric functions per pixel. Frame rate and audio concurrency still require physical measurements; software-triggered transport cycles do not count as human wake-word acceptance.

### 2026-10-19 engineering verification

The private `0.2.0-bm17-net5` image completed two 25-second software-triggered device sessions: audio was received, no extra reconnect or playback-supply gap was counted, and commanded end returned to standby in 274–279 ms. During an explicit 1.5-second sender pause, wire transmission stopped while session dispatch continued and the bounded microphone backlog recovered. One in-flight write was cancelled during commanded shutdown and remains recorded in diagnostics. Idle graphics measured about 18–19 fps; transition/conversation samples still fell below the 20 fps target. These observations do not qualify the wake model or establish human sound quality, 30-minute conversation reliability, 8-hour false-wake performance or 72-hour stability. Private weights, firmware images and raw logs are not distributed.

### Reconnect greeting follow-up

A later NET5 listening test failed: the listener heard a smooth first greeting but two opening stutters after disconnect/reconnect. Device counters recorded one 244 ms supply gap in the second run. The first six audio packets included a one-sample prefix and a 929 ms arrival interval. An independent 24 kHz playback-clock replay of that timing reproduces 222 ms of starvation with the old 500 ms / 600 ms startup policy. The 900 ms / 1500 ms policy avoids starvation in that measured prefix while retaining every sample. This adds 403 ms before playback in this trace; completed short replies still bypass the wait. It cannot protect against arbitrary network stalls. Human listening and repeated device cycles must be reported separately from this deterministic test.

The NET6 device follow-up had no supply gaps before it failed on an audio append refusal and reconnected during its second session. This is retained as a failure; its exact append cause was not instrumented. NET7 keeps the same startup policy and adds `audio append refused cause=...` diagnostics: 1 invalid data, 2 rejected response, 3 already completed, 4 PCM capacity, 5 response metadata capacity. It does not silently relax queue limits. Three subsequent 24-second NET7 device cycles received audio without extra reconnects, in-session write errors or supply-gap counts; commanded end returned to standby in 138–244 ms. The append-refusal fault did not recur in those cycles and remains unresolved. The listener subsequently confirmed complete, smooth openings in the replayed greetings. This accepts those greeting openings only; software-triggered cycles do not measure voice-wake recall or long-conversation reliability.

### Context retention update

CTX1 fixes idle sleep incorrectly clearing the NVS conversation identifier. It logs identity reuse without printing the identifier. The default PCM queue now bounds bursts to 30 seconds / 1.44 MB in PSRAM; the initial playback prefill remains 900 ms. An ordinary NET7 turn reached 7960 ms queued and refused the next 80 ms packet (capacity cause 4), which previously forced a reconnect. The larger bound is not a guarantee against arbitrarily long provider bursts. See [context and memory](context-memory.md) for server restoration, automatic learning and Beijing time.

Explicit companion mode overrides the ordinary 30-second inactivity rule; see [companion settings](companion.md).

For an explicitly requested installed-device volume upgrade when USB commands cannot be acknowledged, build with `-DPIKOO_VOLUME_BOOT_UPGRADE=ON`. This opt-in build migrates the saved DAC setting to 0 dB once and marks `volume_v3` in NVS. Subsequent manual reductions are preserved; ordinary builds default this option to OFF. Verify saved values and human listening separately.
