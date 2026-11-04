# Firmware and USB installation

**English** | [简体中文](firmware.zh-CN.md)

## Target and build

Waveshare ESP32-S3-DualEye-LCD-1.28 **non-touch**, 16 MiB Flash / 8 MiB PSRAM. Use ESP-IDF **5.5.5**. Pinned components: ESP-SR 2.5.3, ESP-TFLite-Micro 1.4.1, esp_codec_dev 1.5.11, esp_lcd_gc9a01 2.0.4, esp_websocket_client 1.8.0; `firmware/dependencies.lock` fixes transitive versions.

Download the model package from the [1.0.0 release](https://github.com/skiyo/pikoo/releases/tag/v1.0.0), verify its checksums and read its model terms.

```sh
. /path/to/esp-idf/export.sh
PIKOO_FIRMWARE_VERSION=1.0.0 \
PIKOO_WAKE_POLICY=/absolute/models/wake-policy.json \
bash tools/build-device.sh /absolute/models/hi_pikoo.tflite
```

The command builds only; it never accesses USB. Set `PIKOO_BUILD_DIR` to use a separate directory. The model must match its policy SHA-256 and firmware frontend. The file cap is 512 KiB; runtime arena/timing are separate limits. The current model is 98,064 bytes. Diagnostic, veto and volume-migration options remain disabled for a normal build.

## Install a downloaded release

Extract `hi-pikoo-firmware-1.0.0.zip` and run commands from its root. It contains `tools/` and the validated images under `firmware/build-dualeye/`, so the same USB commands work without compiling. Activate ESP-IDF 5.5.5's Python environment first. macOS also supports `tools/Pikoo-USB.command`.

Before first installation, back up all 16 MiB using `esptool read_flash 0x0 0x1000000 factory-full.bin`. Keep it in a private backup directory with `manifest.json` containing `{"full_backup_sha256":"SHA256_OF_FACTORY_FULL_BIN"}`. The install tool verifies the backup against the device before partition migration. Do not reuse another board's backup.

Create private JSON with `ssid`, `password`, `endpoint` and `token`. Endpoint: `wss://YOUR_HOST/api/realtime`, without query parameters. Use `python tools/configure.py --output /private/config.nvs.bin` for hidden password/token entry, or the USB assistant. Provider API keys do not belong on the device.

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py diagnose --port PORT --command status
python tools/device.py configure --port PORT --build firmware/build-dualeye --config /private/device.json
python tools/device.py restore --port PORT --backup /private/factory-backup
```

Install prepares all images and private NVS before writing. Upgrade compares device/build partition tables and updates only the app. It preserves Wi-Fi, device token, volume and session state. Reconfiguration replaces NVS and clears conversation state. Recovery restores the full 16 MiB backup. No full-chip erase, eFuse changes or OTA are used. Flash/NVS encryption is not enabled by this developer package.

## Controls and audio

BOOT press wakes or stops a response; double press ends a conversation; hold 2 seconds toggles mute, or explicitly takes over an occupied session. RESET restarts with saved configuration. Standby eyes are closed. Native Live audio uses mono PCM16 at 16 kHz; negotiated 24 kHz output is resampled. Continuous playback uses a bounded startup buffer and generation-based stale-audio rejection.

Volume is retained in NVS. Fresh devices start quietly at -24 dB. `python tools/device.py diagnose --port PORT --command 'volume -2'` selects the recommended household starting level; adjust for your enclosure and speaker. If clipping occurs, reduce it. If the speaker heats unexpectedly, stop playback and disconnect power.

[Hardware and pins](hardware.md) · [Protocol](gcp7.md) · [Model card](../models/hi-pikoo/MODEL_CARD.md)
