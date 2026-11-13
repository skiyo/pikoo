# Getting started

**English** | [简体中文](getting-started.zh-CN.md)

## Device setup

Prepare the [hardware](hardware.md), ESP-IDF 5.5.5 and Python 3.11. Download a compatible [wake model bundle](https://github.com/skiyo/pikoo/releases/tag/v1.0.0), check its SHA256SUMS and model terms, and keep the weights/checkpoint outside Git. The build verifies its frozen policy hash.

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
. /path/to/esp-idf/export.sh
PIKOO_WAKE_POLICY="$PWD/models/hi-pikoo/wake-policy.json" \
  bash tools/build-device.sh /private/hi_pikoo.tflite
```

Copy the example outside Git, fill the [service configuration](configuration.md), create and verify a full device backup, then follow the [USB installation guide](firmware.md). Service accounts, networking and inference are supplied by you; running a Pikoo application server is unnecessary.

## Offline eye preview

Node.js 24+, npm and a C++17 compiler are only needed for the desktop preview:

```sh
(cd firmware/simulator && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

Open `http://127.0.0.1:8793/dualeye`. Buttons preview device states and expressions, with no microphone, audio output or model requests. Stop with Ctrl+C or `tools/stop-dualeye.sh`. Protocol, tool and performance tests use the separate native C++ simulator described in [development](development.md).
