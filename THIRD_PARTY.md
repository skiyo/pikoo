# Third-party software and attribution

**English** | [简体中文](THIRD_PARTY.zh-CN.md)

Pikoo-authored code, original eye graphics and project documentation use Apache-2.0. Dependencies, copied source, data and external services retain their own terms. The root LICENSE does not replace them. See [NOTICE](NOTICE).

## Software inventory

Versions below describe the current pinned integration, not a claim that all components are the latest. npm transitive dependencies are listed in [the lockfile-derived license inventory](docs/dependency-licenses.csv); ESP-IDF components and hashes are in `firmware/dependencies.lock`. Upstream license texts remain the authority.

| Component and source | Version / revision | Used for / relationship | License |
|---|---|---|---|
| [qwen-audio-agent](https://github.com/QwenAudio/qwen-audio-agent/tree/v2.0.1) | 2.0.1 | Installed server dependency; authentication, realtime provider and memory/session framework; Pikoo adapters are separate | Apache-2.0; retain upstream notices |
| [ESP-IDF](https://github.com/espressif/esp-idf/tree/v5.5.5) | 5.5.5 / `b774170ff46c393eeb5e495ea37936038d3f4f4f` | Firmware framework dependency | Apache-2.0 for framework; bundled third-party components have separate terms |
| [ESP-SR](https://github.com/espressif/esp-sr) | 2.5.3 | AFE/AEC dependency in the historical firmware baseline; built-in WakeNet disabled | ESPRESSIF MIT License, with ESPRESSIF-product limitation; not generic MIT or Pikoo Apache-2.0 |
| [ESP-TFLite-Micro](https://github.com/espressif/esp-tflite-micro) | 1.4.1 | Embedded INT8 inference dependency | Apache-2.0 plus retained third-party notices |
| [microWakeWord](https://github.com/OHF-Voice/micro-wake-word) | `4665173cd35f1cff9a61e06fc427f124766c488e` | Separately installed training code; not copied wholesale into this repository | Apache-2.0; model/data terms are separate |
| [pymicro-features](https://github.com/rhasspy/pymicro-features/tree/96bd69cfad79aa67697e176570d3dd87052c3def) / TensorFlow microfrontend | Copied source revision `96bd69cfad79aa67697e176570d3dd87052c3def`; Python package 2.0.2 | Vendored `pikoo_features`; desktop feature extraction dependency | Apache-2.0; TensorFlow author headers retained; added Pikoo ESP-IDF CMake integration |
| [KissFFT](https://github.com/mborgerding/kissfft) | Source bundled with the pinned feature implementation | Vendored FFT used by microfrontend | Retained BSD-3-Clause notice, Copyright Mark Borgerding, in source headers |
| [LVGL](https://github.com/lvgl/lvgl) | 9.6.0~1 | Historical firmware UI dependency; original eye renderer itself is independent of LVGL | MIT core; optional libraries/fonts retain their own licenses |
| [Waveshare BSP](https://components.espressif.com/components/waveshare/esp32_s3_touch_lcd_1_83/versions/2.0.0) | 2.0.0 | Installed historical 1.83-EN board integration; not DualEye driver support | Apache-2.0 for this BSP; retain dependency licenses |
| [ESP-NN](https://github.com/espressif/esp-nn) | 1.4.1 | Resolved firmware optimized inference dependency; real-board performance pending | Apache-2.0 |
| [ws](https://github.com/websockets/ws) | 8.22.0 in server lockfile | Installed Node WebSocket dependency used by local simulator | MIT |
| [TensorFlow](https://github.com/tensorflow/tensorflow) | 2.18.1 | Optional training/inference dependency | Apache-2.0 plus bundled third-party notices |
| [NumPy](https://github.com/numpy/numpy) | 2.0.2 | Optional training dependency | BSD-3-Clause core plus bundled dependencies |
| [PyYAML](https://github.com/yaml/pyyaml) | 6.0.2 | Optional training configuration dependency | MIT |
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels) | 2.0.14 | Optional voice-activity dependency | MIT wrapper; bundled WebRTC VAD retains upstream BSD-style terms |
| [Node.js](https://github.com/nodejs/node) | Runtime requirement 24+ | Server/simulator runtime; not bundled in Pikoo | MIT and bundled dependency notices |
| [Nginx](https://nginx.org/en/) / [Certbot](https://github.com/certbot/certbot) / [mihomo](https://github.com/MetaCubeX/mihomo) | Operator-installed; Certbot ≥5.4 for documented IP certificate flow | Deployment integration templates, no binaries or source vendored | Nginx BSD-2-Clause; Certbot Apache-2.0; mihomo GPL-3.0. Their own distribution terms apply |

Software binaries, firmware images or containers must include the license texts/notices for the exact dependencies they redistribute. This attribution table is not a substitute for that release-specific bundle. Do not overwrite vendored license headers with Pikoo's license.

## References and external services

| Source | Relationship | Boundary |
|---|---|---|
| [Muse Gadget SDK simulator](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/esp32/simulator/README.md) | Simulator organization and animation pacing reference | No Muse code or Jollybot assets copied; original Pikoo renderer/page/assets |
| [Waveshare DualEye documentation](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/) | Board specifications, schematic and driver-reference entry | Documentation/hardware reference; no blanket relicensing of supplier materials |
| [Google Gemini API](https://ai.google.dev/gemini-api/docs) | External realtime and text service | Service terms, regional availability, quotas and pricing apply separately; not an open-source dependency |
| [Let's Encrypt](https://letsencrypt.org/) | External certificate service | Operator must maintain renewal and follow service requirements |

## Audio, datasets and models

- The current tree distributes **no wake-model weights or audio**. Model cards and aggregate evaluation records remain for transparency.
- Early experimental weights were trained with local macOS system voices. Their redistribution rights have not been established; Apple software ownership does not itself establish public audio/model rights. [Apple's published macOS terms](https://www.apple.com/legal/sla/docs/macOSTahoe.pdf) limit System Voice content to personal non-commercial use and restrict public sharing. They do not expressly settle this wake-model scenario; check the applicable product/version terms before publication.
- Local V5 also used authorized [ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin). Access approval is not permission to redistribute audio or derived weights. Complete gated terms and permission records must be reviewed; dataset-card labels alone are insufficient. V5, recordings and raw manifests remain private.
- [ChildTalk](https://github.com/NKU-HLT/ChildTalk) is a potential research source, not a downloaded or trained component. Its own terms would need review before use.
- Historical Git commits retain an early model. Keeping history does not grant an Apache-2.0 license to those weights. No current release should package them.
- Future public model releases need documented rights for training and model redistribution, provenance, a separate model card/license, and real adult/child and board evaluation. Household recordings are private by default.
