# Wake-model training

**English** | [简体中文](README.zh-CN.md)

Target: complete **Hi + piku / piko**, naturally connected or spoken with Chinese-accented Hi. Incidental full Hi Tikoo/Tiko triggers are tolerated, not a recall promise. Hi alone, an isolated name and incomplete phrases remain negative. This pipeline runs offline and is not part of live dialogue.

## Use the published model

[Model card](../models/hi-pikoo/MODEL_CARD.md) · [Weights and checkpoint](https://github.com/skiyo/pikoo/releases/tag/v2.0.0) · [Terms and sources](../models/hi-pikoo/ATTRIBUTION.md)

The package contains `hi_pikoo.tflite`, `checkpoint.weights.h5`, `model-config.json`, `wake-policy.json` and checksums. Source weights are 98,064 bytes; family recordings and raw datasets are excluded. The checkpoint configuration is 96 channels, 64 head units, 72 ordered context steps, no batch normalization, seed 42. Reconstruct with `hi_pikoo_model.build(upstream, **configuration)` using only its supported arguments; the JSON also contains metadata, not all fields are function arguments.

## Training environment

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r training/requirements.txt
git clone https://github.com/OHF-Voice/micro-wake-word.git training/vendor/micro-wake-word
git -C training/vendor/micro-wake-word checkout 4665173cd35f1cff9a61e06fc427f124766c488e
.venv/bin/python training/hi_pikoo_train.py --help
.venv/bin/python training/wake_int8_iterate.py --help
```

TensorFlow 2.18.1, NumPy 2.0.2 and pymicro-features 2.0.2 are pinned. Streaming layers/conversion come from the pinned Apache-2.0 microWakeWord checkout. Install FFmpeg separately for pitch-preserving `atempo` augmentation; no FFmpeg binary is bundled.

## Data contract

Declare the target in a JSON contract before preparing data: `target=hi-piku-piko-v2`, `accepted_names=[piku,piko]`, `declared_before_corpus_training=true`. Manifests contain local relative paths, waveform SHA-256, split, binary label, target contract, source family/speaker and content-review evidence. Read `hi_pikoo_train.py:admit` and the command `--help` before preparing a corpus. A protected-hash registry lists recordings that may never enter TRAIN/DEV.

Use legally accessed source data locally. ChildMandarin contributes real-child ordinary speech, not recordings of the target phrase. Synthetic “childlike” is a delivery style, not real-child evidence. Exact generated-waveform pronunciation/content review is required; prompts and ASR alone cannot establish labels.

TRAIN/DEV/TEST must isolate source families and all descendants. Family recordings are TEST only after a candidate is frozen, never training, augmentation, calibration or model selection. Keep original waveforms, review evidence and source terms private. No data/model downloads or paid synthesis are initiated by the normal software checks.

## Pipeline

1. `hi_pikoo_train.py` prepares bounded 16 kHz microfrontend features and trains/exports the independent causal network from reviewed manifests. See its explicit manifest, background, protected-registry, upstream, contract and output arguments.
2. `wake_int8_iterate.py` supports controlled refinement with native Micro DEV scoring. Optional admission and tempo arguments require corresponding evidence; do not manufacture gate files to bypass validation.
3. `wake_tempo.py` applies FFmpeg `atempo` at 1.15/1.30/1.50 to TRAIN while preserving pitch. Time labels are transformed before acoustic augmentation. Descendants remain in their source split.
4. `sequence_export_check.py`, `streaming_runtime.py` and `micro_check/` validate stateful export, reset and backend agreement. Compare quantized/native decisions, not float accuracy alone.
5. Freeze the candidate and its policy before opening independent TEST. `wake_native_finalize.py` retains strict evaluation/provenance gates; the distributed policy is its sanitized runtime subset, not a fabricated acceptance certificate.

The repository provides code and the current checkpoint, not the raw private training manifests. Reproducing byte-identical weights requires the exact authorized data and evidence; rebuilding the released firmware only requires the published TFLite/policy pair.

## Deployment checks

```sh
.venv/bin/python training/check_esp32_model.py --model /absolute/models/hi_pikoo.tflite --max-model-bytes 524288 --output /tmp/pikoo-model-check.json
python3 tools/check_wake_policy.py --model /absolute/models/hi_pikoo.tflite --policy models/hi-pikoo/wake-policy.json --output /tmp/wake_policy_generated.hpp
```

Use the correct Micro backend for agreement. Device inference/arena numbers, full concurrent audio/display behavior, natural-rate family recall and continuous background false wakes are different checks. Do not reset the audio frontend between negative clips in a continuous playback trial. Formal real-child/8-hour/72-hour acceptance remains incomplete; see the model card.


Optional Node-based synthesis and audit tools use their own locked dependency: run `npm ci --ignore-scripts` in `training/` before explicit generation. Importing planning/unit-test modules does not access providers.

## Choose a workflow

- To use Pikoo, use the published TFLite/policy pair; training is unnecessary.
- To inspect a checkpoint, reconstruct the architecture described in `model-config.json`, load weights and verify stateful export before changing thresholds.
- To train a replacement, obtain authorized data, create the required reviewed manifests and reserve independent TEST before selection.

Keep corpus roots, generated audio, API credentials and experiment outputs outside the public repository. Start with each script's `--help`; do not copy private paths into public commands. Feature extraction, floating-point training, quantization, native runtime agreement and board scheduling are separate validation stages. Report skips and the actual data/evaluation scope. Read the [model card](../models/hi-pikoo/MODEL_CARD.md) before comparing metrics.
