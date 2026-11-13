# Firmware and USB

**English** | [简体中文](firmware.zh-CN.md)

## Build

Target: non-touch Waveshare DualEye ESP32-S3, 16 MiB Flash and 8 MiB PSRAM. Use ESP-IDF 5.5.5 and locked components. [Obtain the model and build](getting-started.md); the firmware version defaults to `VERSION`. The release build disables detailed Agent tracing and diagnostic images.

## USB workflow

Use the IDF Python environment, install pyserial/esptool, select one board and close competing serial monitors. [Create and verify a complete Flash backup](../tools/device.py) before installation. A backup includes private credentials and must stay outside Git. Keep it for recovery to the same board.

```sh
python tools/device.py backup --port PORT --backup /private/factory-backup
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup /private/factory-backup --config /private/pikoo.json --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup /private/factory-backup --config /private/pikoo.json
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py configure --port PORT --config /private/pikoo.json
```

Installation writes checked build images, then sends the unified configuration over USB. Same-layout upgrades write only the application; configuration changes only update configuration. Existing family data, volume and orientation are retained. A device without valid configuration shows USB SETUP and does not open a voice session. Do not erase the whole chip or burn eFuses.

```sh
python tools/local-agent-usb.py --port PORT export /private/family.json
python tools/local-agent-usb.py --port PORT import /private/family.json
python tools/local-agent-usb.py --port PORT forget
python tools/local-agent-usb.py --port PORT reboot
```

Writes require muted standby. Import and forget need a reboot. `forget` deletes service configuration, including Wi-Fi, and preserves family data. Exports never contain service credentials. Provisioning must be repeated when installing this configuration format on a device without it.

## Controls

Press BOOT to wake or stop an answer, double-press to end and clear short-term context, hold to mute/unmute. RESET keeps saved settings. The default new-device speaker volume is -24 dB; existing volume stays unchanged. The USB assistant also adjusts volume and screen orientation.

macOS console opening avoids unsolicited control-line resets. Application startup briefly reconnects the USB peripheral; one re-enumeration is expected. Do not run two serial monitors simultaneously.
