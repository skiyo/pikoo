# Hi Pikoo wake model

**English** | [简体中文](README.zh-CN.md)

This directory contains the local full-phrase “Hi, Pikoo” wake artifacts. Dialogue inference is provided by configured external services; these files do not contain a conversational language model.

| File | Use |
|---|---|
| `hi_pikoo.tflite` | Quantized streaming inference model embedded by firmware |
| `checkpoint.weights.h5` | Training weights; requires the matching Python architecture |
| `model-config.json` | Checkpoint architecture/configuration metadata |
| `wake-policy.json` | Frozen frontend/decision policy bound to the model hash |
| `SHA256SUMS` | Integrity checks for distributed files |
| `MODEL_CARD.md` | Input/output contract, measurements and limitations |
| `LICENSE.md`, `ATTRIBUTION.md`, `PERMISSION.md` | Model terms, sources and publication record |

Clone the repository or download the [2.0.0 model ZIP](https://github.com/skiyo/pikoo/releases/download/v2.0.0/hi-pikoo-model-2.0.0.zip). Git LFS is not needed. In this directory run `shasum -a 256 -c SHA256SUMS` on macOS or `sha256sum -c SHA256SUMS` on Linux. Keep the model and policy together; changing one independently causes build validation to fail.

To build firmware, follow [Quick start](../../docs/getting-started.md). To reconstruct or train a network, read [Training](../../training/README.md) and the [model card](MODEL_CARD.md). Checkpoint metadata includes descriptive fields; do not blindly pass every JSON key as a constructor argument.

The model artifact has its own version, independent of the Pikoo application version. Weights and model-containing firmware retain non-commercial terms; source code uses Apache-2.0. Raw datasets and private recordings are not included. A published checkpoint does not imply that all natural-speaker or endurance acceptance targets have been established.
