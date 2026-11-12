# Firmware and USB setup

**English** | [简体中文](firmware.zh-CN.md)

Target: non-touch Waveshare ESP32-S3-DualEye-LCD-1.28, 16 MiB Flash and 8 MiB PSRAM. Use ESP-IDF 5.5.5 and the locked dependencies. The existing [public model bundle](https://github.com/skiyo/pikoo/releases/tag/v1.0.0) remains compatible when its model hash matches the frozen policy.

```sh
. /path/to/esp-idf/export.sh
PIKOO_WAKE_POLICY=/absolute/path/wake-policy.json \
bash tools/build-device.sh /absolute/path/hi_pikoo.tflite
```

The build does not access USB. Release builds disable detailed Agent tracing and benchmark options. Keep a verified full 16 MiB backup outside Git before flashing; that private backup includes any credentials already on the device.

First migration from an older partition layout writes the new partition table and application while preserving existing NVS/model offsets. Use the installer's backup verification and dry-run. Later upgrades on the same layout write only the application. No full-chip erase or eFuse changes are required.

For a new device, save a private Wi-Fi JSON configuration outside Git and pass it to the installer below. `tools/configure.py --local-agent` can also generate its NVS image separately. This mode requires no Gateway endpoint/token and rejects API secrets in the generated image. The installer JSON is `{"mode":"local","ssid":"your network","password":"your password"}`. Pass its private path to `tools/device.py install --config`, with a verified backup and build directory.

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye --backup /private/factory-backup --config /private/device.json
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/local-agent-usb.py --port PORT provision
python tools/local-agent-usb.py --port PORT reboot
python tools/local-agent-usb.py --port PORT export /private/family.json
python tools/local-agent-usb.py --port PORT import /private/family.json
```

Existing devices retain Wi-Fi settings. USB provision writes Mihomo connection settings and the OpenAI project key into replaceable ordinary NVS. Credentials are excluded from firmware and family exports. Reboot after updates/imports. `forget` removes credentials and disables local mode; `legacy` selects the retained Gateway mode, which requires valid legacy connection settings. Writes are accepted only in fully muted standby.

The default audio rate is 16 kHz mono PCM16, with a selectable 24 kHz path. Single press wakes/stops, double press ends a session, and hold mutes. RESET retains configuration. Volume survives upgrades; new-device default is -24 dB. Adjust it for the actual enclosure and distance.

The macOS console avoids reset-line changes when opening. Firmware briefly reattaches USB at startup; the host may see the port re-enumerate. Use one serial monitor at a time.

[Local Agent deployment and tests](local-agent.zh-CN.md) · [Hardware](hardware.md) · [Legacy GCP 7](gcp7.md)
