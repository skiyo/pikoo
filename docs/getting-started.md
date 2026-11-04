# Quick Start

**English** | [简体中文](getting-started.zh-CN.md)

## Offline demo

Requirements: Node.js 24+, npm, Bash, C++17 compiler.

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
(cd server && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

Open http://127.0.0.1:8793/dualeye. Test tones simulate conversation. No credentials, model, Python or microphone are required. Stop with Ctrl+C or `bash tools/stop-dualeye.sh`. Use `PIKOO_SIM_PORT=8794` for another port; use `127.0.0.1` because Host/Origin checks are intentional.

## Real voice

[Deploy the Gateway](../server/README.md) and issue a device token. Save this JSON **outside Git**, with file permissions 0600:

```json
{"endpoint":"wss://YOUR_HOST/api/realtime","token":"YOUR_DEVICE_TOKEN"}
```

```sh
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

The Node process holds the token. Explicitly wake and grant microphone access to start. No wake model is needed for button-initiated conversation. Stop a running launcher instance before changing its configuration.

## Local wake

Download `hi-pikoo-model-1.0.0.zip` from the [release](https://github.com/skiyo/pikoo/releases/tag/v1.0.0), verify `SHA256SUMS`, and read its model terms. Install Python 3.11 dependencies in an isolated environment:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r training/requirements.txt
PIKOO_WAKE_PYTHON="$PWD/.venv/bin/python" \
PIKOO_WAKE_MODEL=/absolute/models/hi_pikoo.tflite \
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

Use a deliberate page action to enable local wake listening. Standby audio is processed locally; microphone permission is explicit. Missing models produce a configuration error, not a silent remote fallback.

## Hardware

Use the [DualEye USB guide](firmware.md). The release does not contain personal Wi-Fi, NVS or server credentials. Model API access and an HTTPS Gateway are required for real conversation.
