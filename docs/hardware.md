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

## Assembly and electrical checks

## Before connecting power

Inspect the board revision and confirm it is the non-touch target. Connect the speaker only while unpowered, following the connector label and vendor requirements. Do not infer polarity or purpose from connector shape. Keep exposed electronics on a non-conductive surface and provide cable strain relief. A charge-only USB cable cannot perform setup.

## Bring-up sequence

1. Verify USB enumeration and both displays before enclosing the board.
2. Configure the device and check status without immediately raising volume.
3. Unmute intentionally, test low-volume playback and full-phrase wake.
4. Install the optional enclosure following its illustrated guide; avoid loading display glass or covering microphone openings.
5. Repeat wake, interruption, playback and supply checks in the assembled enclosure.

A software simulator does not verify speaker impedance, wiring, power integrity, thermal behavior or acoustics. Pin compatibility alone is insufficient for another board. Porting requires correct codec routing, microphone/reference channel order, display timing and PSRAM/Flash layout.

## What to record

Record board revision, speaker specification, cable/supply, enclosure material and firmware identity with any hardware result. Measure at normal intended volume, not only on an open bench. AEC behavior depends on the reference path and final acoustic geometry; inspect interruptions and first-syllable loss as well as whether any reply is audible.
