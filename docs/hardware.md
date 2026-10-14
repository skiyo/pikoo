# Hardware

**English** | [简体中文](hardware.zh-CN.md) · [Home](../README.md)

The prototype target is **Waveshare ESP32-S3-DualEye-LCD-1.28**, selected for two expressive round eyes in a DIY pet enclosure. The enclosure shown in the README is a simulator concept; printable mechanical files are not supplied yet.

| Part | Target specification |
|---|---|
| Controller | ESP32-S3R8, dual-core Xtensa LX7, up to 240 MHz |
| Memory | 16 MB Flash, 8 MB PSRAM |
| Displays | Two 1.28-inch, 240 × 240 color LCDs |
| Network/power | 2.4 GHz Wi-Fi; USB-C power/data for the first prototype |
| Audio resources | ES8311 codec, ES7210 ADC, onboard microphone and amplifier, speaker connector |

Specifications and board revision details: [Waveshare official documentation](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/). Check the exact supplied SKU, PCB revision and schematic before wiring; touch variants and connector assignments must not be inferred from similar product names.

## Accessories

Prepare one matching speaker and cable, a USB-C **data** cable, stable 5 V USB supply and a temporary protective stand. Confirm speaker impedance, connector and included accessories with the supplier. The first prototype does not require a battery, camera, motors or microSD card. Final enclosure geometry follows acoustic and cable-clearance tests.

## Audio and AEC

Having an ADC and codec does not establish working echo cancellation. Bring-up must verify microphone/reference channels, clocks, sample packing, playback reference delay and gain against the actual board schematic and recordings. Then test whether a person can interrupt while Pikoo speaks without its own speaker triggering speech detection. The enclosure and playback volume affect the result.

## Firmware compatibility

The checked-in BSP remains `waveshare/esp32_s3_touch_lcd_1_83@2.0.0`, an older **1.83-EN baseline**. Its pin mapping and firmware images are not DualEye support. **Do not flash those images onto this board.** The portable eye component has compiled for ESP32-S3, but the two display drivers and audio bring-up are still pending. See [legacy firmware notes](firmware.md).

Acceptance still requires real-board display timing, audio quality, AEC, wake-word accuracy, natural interruption, resource measurements, network/power recovery and long-duration operation.
