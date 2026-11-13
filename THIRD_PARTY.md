# Third-party sources and licenses

**English** | [简体中文](THIRD_PARTY.zh-CN.md)

## Software inventory

Optional prosody augmentation and matched-prefix preparation use [Praat-Parselmouth](https://github.com/YannickJadoul/Parselmouth) 0.4.7 (GPL-3.0-or-later, including Praat). It is a separately installed workstation dependency, not copied into Pikoo or linked into firmware; see `training/requirements-prosody.txt`. Its own license remains authoritative.

Optional workstation synthesis/review uses [MLX Audio](https://github.com/Blaizzy/mlx-audio) 0.5.9 and MLX 0.32.4 (MIT), with separate pins in `training/requirements-local-audio.txt`. The source model cards for [Qwen3-TTS VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) and [Qwen3-ASR-0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) specify Apache-2.0. Converted MLX weights retain source terms and are not included here. Corpus rights still govern the wake model. These are not ESP32 dependencies. See [pronunciation development](models/hi-pikoo/MODEL_CARD.md).

Versions below describe the current pinned integration, not a claim that all components are the latest. npm transitive dependencies are listed in [the lockfile-derived license inventory](docs/dependency-licenses.csv); ESP-IDF components and hashes are in `firmware/dependencies.lock`. Upstream license texts remain the authority.

| Component and source | Version / revision | Used for / relationship | License |
|---|---|---|---|
| [ESP-IDF](https://github.com/espressif/esp-idf/tree/v5.5.5) | 5.5.5 / `b774170ff46c393eeb5e495ea37936038d3f4f4f` | Firmware framework dependency | Apache-2.0 for framework; bundled third-party components have separate terms |
| [ESP-SR](https://github.com/espressif/esp-sr) | 2.5.3 | AFE/AEC dependency; built-in WakeNet disabled | ESPRESSIF MIT License, with ESPRESSIF-product limitation; not generic MIT or Pikoo Apache-2.0 |
| [ESP-TFLite-Micro](https://github.com/espressif/esp-tflite-micro) | 1.4.1 | Embedded INT8 inference dependency | Apache-2.0 plus retained third-party notices |
| [microWakeWord](https://github.com/OHF-Voice/micro-wake-word) | `4665173cd35f1cff9a61e06fc427f124766c488e` | Separately installed training code; not copied wholesale into this repository | Apache-2.0; model/data terms are separate |
| [pymicro-features](https://github.com/rhasspy/pymicro-features/tree/96bd69cfad79aa67697e176570d3dd87052c3def) / TensorFlow microfrontend | Copied source revision `96bd69cfad79aa67697e176570d3dd87052c3def`; Python package 2.0.2 | Vendored `pikoo_features`; desktop feature extraction dependency | Apache-2.0; TensorFlow author headers retained; added Pikoo ESP-IDF CMake integration |
| [KissFFT](https://github.com/mborgerding/kissfft) | Source bundled with the pinned feature implementation | Vendored FFT used by microfrontend | Retained BSD-3-Clause notice, Copyright Mark Borgerding, in source headers |
| [esp_codec_dev](https://github.com/espressif/esp-adf-libs/tree/master/esp_codec_dev) | 1.5.11 | Installed ES8311/ES7210 codec dependency | Apache-2.0 |
| [esp_lcd_gc9a01](https://components.espressif.com/components/espressif/esp_lcd_gc9a01/versions/2.0.4) | 2.0.4 | Installed dual circular panel driver; Pikoo board integration is original | Apache-2.0 |
| [ESP-NN](https://github.com/espressif/esp-nn) | 1.4.1 | Resolved optimized inference dependency; physical acceptance remains workload-specific | Apache-2.0 |
| [ws](https://github.com/websockets/ws) | 8.22.0 in simulator lockfile | Installed Node WebSocket dependency used by local simulator | MIT |
| [TensorFlow](https://github.com/tensorflow/tensorflow) | 2.18.1 | Optional training/inference dependency | Apache-2.0 plus bundled third-party notices |
| [NumPy](https://github.com/numpy/numpy) | 2.0.2 | Optional training dependency | BSD-3-Clause core plus bundled dependencies |
| [Apache Arrow / PyArrow](https://github.com/apache/arrow) | 19.0.1 | Optional importer for the pinned MInDS-14 Parquet data | Apache-2.0; retain bundled dependency notices |
| [FFmpeg](https://ffmpeg.org/legal.html) | Optional external CLI; integration baseline 8.1 | Offline pitch/tempo processing in a separate process; no binary or library bundled | Build-dependent LGPL/GPL; the observed Homebrew build reports GPL-3.0-or-later |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) / [MLX checkpoint](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit) | VoiceDesign 4-bit checkpoint `5c390979e4b93af5f2932f90742ca99c7dd04687` | Locally evaluated text-only TTS prototypes; no reference voice; used for reviewed synthetic TRAIN speech in the current wake model | Apache-2.0 model/code; no weights bundled here |
| [MLX-Audio](https://github.com/Blaizzy/mlx-audio) / [MLX](https://github.com/ml-explore/mlx) | 0.5.9 / 0.32.4 | Optional isolated Apple Silicon runtime for the TTS prototype | MIT; dependencies retain their own notices |
| [PyYAML](https://github.com/yaml/pyyaml) | 6.0.2 | Optional training configuration dependency | MIT |
| [pypinyin](https://github.com/mozillazg/python-pinyin) | 0.55.0 | Optional research-only transcript-to-phoneme training labels; installed separately | MIT |
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels) | 2.0.14 | Optional voice-activity dependency | MIT wrapper; bundled WebRTC VAD retains upstream BSD-style terms |
| [Node.js](https://github.com/nodejs/node) | Runtime requirement 24+ | Optional simulator runtime; not bundled in Pikoo | MIT and bundled dependency notices |

Software binaries, firmware images or containers must include the license texts/notices for the exact dependencies they redistribute. This attribution table is not a substitute for that release-specific bundle. Do not overwrite vendored license headers with Pikoo's license.

## Design references and external services

Muse Gadget SDK is a reference for visual pacing and simulator organization. No Muse code or Jollybot assets are included. Waveshare's [DualEye documentation and examples](https://docs.waveshare.net/ESP32-S3-DualEye-LCD-1.28/) are the hardware integration reference; vendor rights are retained.

External voice, reasoning and search APIs are configured by the operator; their access, fees and terms are separate from the source license.

## Current wake weights and data

The current weights are downloadable release assets with [separate non-commercial model terms](models/hi-pikoo/LICENSE.md), a [model card](models/hi-pikoo/MODEL_CARD.md) and [source attribution](models/hi-pikoo/ATTRIBUTION.md). ChildMandarin, LibriSpeech, ESC-50, reviewed public speech and synthetic provider outputs contribute to the current model; original audio is not redistributed. ChildMandarin's gated conditions do not expressly name trained weights. Do not interpret attribution as an assertion of all additional permissions.

Original Pikoo code, graphics and documentation use Apache-2.0. This does not relicense third-party source, data, provider models or the published wake weights. Binary release packages include the actual bundled dependency license texts.
