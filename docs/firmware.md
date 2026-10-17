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

A first press does not wait for double-click detection. Release BOOT for normal startup; use the official BOOT/RESET procedure for recovery download mode. Standby keeps eyes closed and sends no ambient audio. Upload starts after the ready tone drains. Mute stops I2S input, ADC, inference and upload. Thirty seconds without user speech or playback ends the conversation. Network reconnection preserves its identifier; explicit end/idle expiry clears it. The identifier expires after 24 hours. Restoration recovers recent text context, never interrupted audio.

## Audio, graphics and diagnostics

Original Pikoo integration uses two GC9A01 panels with PSRAM rendering and an internal DMA strip. Target animation is 20 fps; measured results are recorded separately. SPI2 uses MOSI42/SCLK41/DC45; left CS47/RST48/BL46, right CS38/RST8/BL39. I2C SDA11/SCL10; I2S MCLK12/BCLK13/WS14, ADC data15/DAC data16; amplifier9; BOOT0.

The schematic connects the physical microphone to ES7210 MIC1 and attenuated amplifier-output reference to MIC3. The [ES7210 datasheet](https://files.waveshare.com/wiki/common/ES7210_DS.pdf), Figure 2e and register 0x12, explains why ordinary ADC12 stereo does not contain MIC3. Levels and echo cancellation require physical validation. ESP-SR uses `MR` and WakeNet is disabled. The audio wire uses two 32-clock stereo slots at 16 kHz; ADC TDM I²S is packed in the order ADC1/ADC3/ADC2/ADC4, with ADC1 and ADC3 unpacked as microphone/reference. The DAC receives PCM16 in the upper half of each slot. Downstream 24 kHz PCM uses the shared streaming FIR resampler. Four 10 ms DMA descriptors use a conservative 50 ms drain bound. Cancellation immediately gates PA, invalidates the playback generation and rejects late response audio.

Keep one USB connection open for endurance observation:

```sh
python tools/monitor.py --port PORT --private-log /private/device.log
```

Opening a fresh USB serial connection may restart the board. Commands: `status`, `wake`, `stop`, `end`, `mute`, `unmute`, `takeover`, `tone`, `volume low`, `volume normal`, `volume higher`, `rotate 90`, `rotate 270`. Short tones are available only in standby. Default DAC is -24 dB; allowed range is -50 to -18 dB. Stop immediately if the speaker heats up.

Metrics exclude credentials, transcripts and family facts: uptime/reset reason, heap/internal/PSRAM, frame rate, microphone/reference/output levels, I2S errors, upload frames, reconnects and wake inference time. USB controls do not add public GCP events.

References: [Waveshare non-touch source, pinned commit](https://github.com/waveshareteam/ESP32-S3-DualEye-Touch-LCD-1.28/tree/f16371ca7b7d4e17de6d6f6ea293981b37c0ca51/example/ESP32-S3-DualEye-LCD-1.28/ESP-IDF-5.5.1), [official board documentation](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/). Integration and artwork are original; Espressif panel/codec drivers retain their licenses. No vendor player or Jollybot assets are copied. See [physical validation](device-validation.md) and the [historical 1.83 notes](firmware-legacy183.md).
