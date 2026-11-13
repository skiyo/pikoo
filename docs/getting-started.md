# Quick start: from download to your first conversation

**English** | [简体中文](getting-started.zh-CN.md)

This guide installs Pikoo on the **non-touch Waveshare ESP32-S3-DualEye-LCD-1.28**. Start with the firmware ZIP if you want to use the device; build from source if you intend to change firmware. All terminal commands run from the extracted package or repository root. Examples use a macOS/Linux shell; replace paths and `PORT` for your computer.

## 1. Prepare hardware and service access

You need the target board (16 MiB Flash, 8 MiB PSRAM), its microphones and displays, a compatible connected speaker, a USB **data** cable, stable 5 V power and 2.4 GHz Wi-Fi. An enclosure is optional during initial setup. Check the speaker connector against the [hardware guide](hardware.md) before powering on.

You also need two service capabilities:

| Service | Required capability | What to obtain |
|---|---|---|
| Live voice | `openai_live`, client delegation, PCM audio, transcripts and Decisions | Full WSS endpoint, model, voice, API key |
| Reasoning | Responses or Chat Completions with function calling | Full HTTPS endpoint, model, API key |
| Search (optional) | Tavily or Responses web search | Independent endpoint and key; model for Responses |

A generic “OpenAI-compatible” chat endpoint does **not** imply Live compatibility. Check access with your provider before buying API credits. Keys and models can differ between services. See [configuration](configuration.md) for the exact protocol contract. Search can remain disabled for the first conversation.

## 2. Download the right package

Open [Pikoo 2.0.0 downloads](https://github.com/skiyo/pikoo/releases/tag/v2.0.0). Download `hi-pikoo-firmware-2.0.0.zip` and `SHA256SUMS`. The ZIP contains source, installation tools, board images and notices. Extract it into a new directory. The standalone application BIN is **not** a complete first-install image.

Verify the downloaded ZIP against its corresponding line in `SHA256SUMS`. On macOS use `shasum -a 256 hi-pikoo-firmware-2.0.0.zip`; on Linux use `sha256sum hi-pikoo-firmware-2.0.0.zip`. After extraction, verify the internal files with `shasum -a 256 -c SHA256SUMS` (macOS) or `sha256sum -c SHA256SUMS` (Linux). Stop if any file fails. Read the [model terms](../models/hi-pikoo/LICENSE.md): source and model licensing are distinct.

The packaged images are under `firmware/build-dualeye/`. If using these images, skip the source-build section below; ESP-IDF is not required just to run the USB installer.

## 3. Prepare Python and a private configuration directory

Install Python 3.11 or newer and create an isolated environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pyserial esptool
mkdir -p "$HOME/.config/pikoo"
chmod 700 "$HOME/.config/pikoo"
cp examples/device.example.json "$HOME/.config/pikoo/device.json"
chmod 600 "$HOME/.config/pikoo/device.json"
```

On Windows, activate `.venv\Scripts\Activate.ps1` in PowerShell and use a private folder outside the checkout. USB port names are typically `COM3` rather than Unix device paths. Source build scripts require a Bash environment supported by ESP-IDF.

Edit the private JSON file locally. Replace **every** `YOUR_...` value and the example hostnames with your own Wi-Fi and provider settings. Keep `version: 1`, start with `search.enabled: false` and `network: {}`. The default conversation language is `en`; set `agent.language` to `zh-CN` for Chinese. Do not paste the completed JSON into issues or chat logs.

Alternatively, create a new file interactively (the destination must not already exist):

```sh
python tools/configure.py --init "$HOME/.config/pikoo/device.json"
```

Validate it:

```sh
python tools/configure.py --config "$HOME/.config/pikoo/device.json" --dry-run
```

Expected: `Configuration is valid`. Validation checks structure and limits without contacting a provider or USB device; it does not prove that the key, model or endpoint actually works.

## 4. Find the USB port and back up the board

Connect one board directly, close serial monitors and list ports:

```sh
python -m serial.tools.list_ports
```

Use the port that appears when connecting the board: commonly `/dev/cu.usbmodem...` on macOS, `/dev/ttyACM0` on Linux, or `COM3` on Windows. Substitute it for `PORT` below. Linux may require serial-device group permissions; reconnect your login after your administrator grants access.

Create a **new** backup directory outside the repository:

```sh
python tools/device.py backup --port PORT --backup "$HOME/.config/pikoo/board-backup"
```

Expected: a verified full 16 MiB Flash image and a manifest. This backup may include credentials and personal data. Keep it private and associate it with this physical board. The installer checks it before writing; do not edit it or substitute an unrelated board's backup.

## 5. Validate and install

```sh
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup "$HOME/.config/pikoo/board-backup" \
  --config "$HOME/.config/pikoo/device.json" --dry-run
python tools/device.py install --port PORT --build firmware/build-dualeye \
  --backup "$HOME/.config/pikoo/board-backup" \
  --config "$HOME/.config/pikoo/device.json"
```

The dry run checks files, ranges, layout and private inputs without touching hardware. The actual install verifies the device backup, writes the checked images, provisions configuration and reboots. Keep power stable and wait for completion. A brief USB re-enumeration at application startup is normal; re-list ports if its name changes.

## 6. Confirm status and start a conversation

```sh
python tools/device.py diagnose --port PORT --command status
python tools/device.py diagnose --port PORT --command unmute
```

`MIC OFF` means the device is muted. USB maintenance deliberately enters muted standby; explicitly unmute when ready. `USB SETUP` means configuration is missing or invalid. Review the [troubleshooting guide](troubleshooting.md) if the device does not become ready.

Say the complete English wake phrase **“Hi, Pikoo”**, then wait for the greeting before speaking. For a first functional check, ask what Pikoo can do, add one disposable shopping item, read the list back and remove that exact item. With Chinese configured, speak Chinese after the same English wake phrase. Start at low speaker volume. Search needs a separately enabled configuration.

## 7. Make later changes

Changing Wi-Fi, keys, models or language does not require recompilation:

```sh
python tools/device.py configure --port PORT --config "$HOME/.config/pikoo/device.json"
python tools/device.py diagnose --port PORT --command unmute
```

For firmware updates, backups, imports and recovery, follow [firmware and USB](firmware.md). For everyday controls and voice examples, use the [user guide](usage.md).

## Build from source instead of using packaged images

Install and activate **ESP-IDF 5.5.5** with ESP32-S3 tools using Espressif's installation instructions. Then:

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
. /path/to/esp-idf/export.sh
idf.py --version
bash tools/build-device.sh "$PWD/models/hi-pikoo/hi_pikoo.tflite"
```

Expected output includes `firmware/build-dualeye/pikoo.bin`, partition/bootloader images and installation metadata. The matching wake policy is loaded beside the model; the build rejects a mismatched pair. Do not copy only `pikoo.bin` into an unrelated build directory. Continue at configuration and backup above. See [development](development.md) for desktop tests and [FAQ](faq.md) for common setup questions.
