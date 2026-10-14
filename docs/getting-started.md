# Getting started

**English** | [简体中文](getting-started.zh-CN.md) · [Home](../README.md)

## Offline dual-eye demo

Requirements: Node.js 24 or newer, npm, Bash and a C++17 compiler. macOS needs Xcode Command Line Tools; Debian/Ubuntu can use `build-essential`. Other platforms with equivalent tools may work but have not been validated. A browser with Canvas and WebAudio is required.

```sh
git clone https://github.com/skiyo/pikoo.git
cd pikoo
(cd server && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

Open http://127.0.0.1:8793/dualeye. The script builds the renderer and starts an offline service by default. Try the expression buttons, pixel view, wake/session, stop and simulated disconnect. Offline replies are test tones. Microphone and remote connections require explicit actions/configuration; no model or Python is needed for this demo.

Keep the terminal open. Stop with Ctrl+C or `bash tools/stop-dualeye.sh`. macOS also has double-click start/stop files in `tools/`. A busy port is reported without terminating another process. Use `PIKOO_SIM_PORT=8794 bash tools/start-dualeye.sh` to select a different port; always open `127.0.0.1`, not `localhost`, because Host/Origin checks are intentional. `/` retains the older simulator and `/wake-test` is the separate local wake test page.

For direct foreground use:

```sh
bash tools/build-eyes.sh
PIKOO_SIM_PORT=8793 node firmware/simulator/server.mjs
```

## Optional: your realtime server

Deploy your own server following [server operations](../server/README.md). Obtain a separately issued device token. Create a JSON configuration **outside the repository**, for example `/absolute/private/simulator.json`:

```json
{
  "endpoint": "wss://your-server.example/api/realtime",
  "token": "REPLACE_WITH_YOUR_DEVICE_TOKEN"
}
```

```sh
chmod 600 /absolute/private/simulator.json
PIKOO_SIM_CONFIG=/absolute/private/simulator.json bash tools/start-dualeye.sh
```

The token stays in the local Node process. The page connects only after explicit wake; allow microphone access only when you want to speak. No model is needed for button-initiated conversation. To force offline mode while retaining environment settings, use `PIKOO_SIM_MOCK=1`. Stop an already running launcher-managed service before changing configuration: the launcher reuses an existing instance rather than silently replacing it.

## Optional: your authorized wake model

Current sources do not include weights. Use a privately retained model or train one with documented source rights. The old experimental weights in Git history are not granted an Apache-2.0 model license. See [training](../training/README.md) and the [model card](../training/models/MODEL_CARD.md).

Python 3.11 is the training baseline. This optional installation downloads TensorFlow and is much larger than the graph-only demo:

```sh
python3.11 -m venv /absolute/private/pikoo-wake-env
/absolute/private/pikoo-wake-env/bin/pip install -r training/requirements.txt
export PIKOO_WAKE_PYTHON=/absolute/private/pikoo-wake-env/bin/python
export PIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite
export PIKOO_WAKE_LABEL='My local wake model'
bash tools/start-dualeye.sh
```

You can combine wake settings with `PIKOO_SIM_CONFIG`. Standby microphone audio goes only to the local worker; conversation audio is uploaded after server readiness. `/wake-test` tests local wake without connecting a remote session. Missing model settings produce an actionable error, not an implicit download. Weights must fit the trained streaming architecture used by the worker; arbitrary TFLite models are not interchangeable.

## Firmware build

**The current full-board integration is for the historical 1.83-EN board. Do not flash it onto DualEye.** The shared renderer and host checks can be used independently. After setting up ESP-IDF 5.5.5 as described in [firmware notes](firmware.md), explicitly supply an authorized model:

```sh
idf.py -C firmware -DPIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite build
```

The build rejects missing weights and files larger than 64 KiB. Use [Development](development.md) for checks and the existing USB tooling. Binary releases embedding restricted weights must not be published.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Missing runtime/compiler | Node 24+, C++ compiler and installed `server/` dependencies; `PIKOO_NODE` may select an executable |
| Port busy | Stop your previous instance or select another `PIKOO_SIM_PORT` |
| Eyes unavailable | Run `bash tools/build-eyes.sh`; graphics failures are separate from voice |
| Wake unavailable | Configure both executable Python and readable model, with optional packages installed |
| Remote authentication failure | Endpoint and separately revocable token; never paste token into an issue |
| Remote timeout | Provider network/egress, region, key and quota are separate causes; model rotation does not fix region restrictions |
