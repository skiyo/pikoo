# Hardware

**English** | [简体中文](hardware.zh-CN.md)

Target: [Waveshare ESP32-S3-DualEye-LCD-1.28](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/), non-touch, ESP32-S3, 16 MiB Flash, 8 MiB PSRAM, two GC9A01A 240 × 240 round displays, ES8311 output codec and ES7210 ADC.

Prepare a compatible speaker and matching speaker cable, data-capable USB-C cable, stable 5 V USB supply, 2.4 GHz Wi-Fi and optional [printed enclosure](../hardware/enclosure/README.md). This release needs no battery, SD card or external microphone.

Connect the speaker only to the documented **speaker connector**, never a same-looking power connector. Confirm connector labels and speaker impedance with the board documentation/vendor before powering it. Low-volume playback comes first.

| Interface | Pins |
|---|---|
| Display SPI | MOSI42 / SCLK41 / DC45 |
| Left screen | CS47 / RST48 / BL46 |
| Right screen | CS38 / RST8 / BL39 |
| I2C | SDA11 / SCL10 |
| I2S | MCLK12 / BCLK13 / WS14 / ADC15 / DAC16 |
| Amplifier / BOOT | GPIO9 / GPIO0 |

The schematic maps the microphone to ES7210 MIC1 and attenuated output reference to MIC3. Firmware unpacks the configured ADC1/ADC3/ADC2/ADC4 order as mic/reference. ESP-SR processes the reference for AEC; the presence of a codec alone does not prove successful echo cancellation. Test with the final enclosure, normal volume and natural interruption.

[USB installation](firmware.md) · [Enclosure and STLs](../hardware/enclosure/README.md)
