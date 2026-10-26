# Local wake-word development

**English** | [简体中文](README.zh-CN.md) · [Project](../README.md)

This module develops Pikoo’s local “你好 Pikoo” wake pipeline (pī kū / PEE-koo). It prepares authorized audio, trains and exports candidates, and evaluates whether a candidate is suitable for the device. It does not run the realtime Agent or identify family members.

Training is optional for exploring the [offline simulator](../docs/getting-started.md) or starting a voice session with a button. **The current public tree includes no wake-model weights.** Model history and redistribution limits are described in the [model card](models/MODEL_CARD.md).

## Choose a starting point

| Task | Tools / guide |
|---|---|
| Prepare permitted audio and manifests | `generate_synthetic.py`, `import_children.py`, `merge_manifests.py` |
| Review content and quarantine uncertain material | `clean_corpus.py`, `review_local_corpus.py` |
| Train or export a candidate | `train.py` with the pinned upstream checkout |
| Compare streaming validation/test results | `evaluate_iteration.py`; select the split explicitly |
| Check static device compatibility | `check_esp32_model.py`, `micro_check/` |
| Measure speech-context or device-capacity behavior | [Context diagnostics](../docs/wake-context.md), [capacity guide](../docs/wake-capacity.md) |
| Review pronunciation work | [Pronunciation coverage](../docs/wake-pronunciations.md) |
| Inspect earlier experiments, data-source procedures and failed candidates | [Preserved research notes](research-notes.zh-CN.md) |

The research notes retain the previous README’s commands, dates and numeric results. They are historical evidence, not a claim that an old candidate is the current recommended model.

## Set up the environment

Run from the repository root. Python 3.11 is the training baseline; the optional dependencies include TensorFlow and are much larger than the graphics-only demo.

```sh
python3.11 -m venv training/.venv
training/.venv/bin/pip install -r training/requirements.txt
mkdir -p training/vendor
git clone https://github.com/OHF-Voice/micro-wake-word.git training/vendor/micro-wake-word
git -C training/vendor/micro-wake-word checkout 4665173cd35f1cff9a61e06fc427f124766c488e
```

Use authorized local WAV files or a permitted synthesis source. The macOS-only `generate_synthetic.py` uses `say`/`afconvert`:

```sh
training/.venv/bin/python training/generate_synthetic.py --output training/data/synthetic
training/.venv/bin/python training/train.py \
  --upstream training/vendor/micro-wake-word \
  --manifest training/data/synthetic/manifest.json \
  --output training/runs/my-model --defer-test
```

This creates a research candidate, not an accepted wake model. Keep the training/validation/test split fixed before augmentation. Choose candidates using validation; score sealed independent tests only after the model and threshold are frozen. `evaluate_iteration.py` requires an explicit `--split validation` or `--split test`.

## Data and evaluation rules

- Household recordings are evaluation-only. They must not guide training, augmentation, quantization calibration, cleaning, thresholds or candidate selection. Retain `evaluation_only=true` and protected hashes.
- Separate speakers and source recordings across splits; derived audio inherits its parent split. Ordinary child speech is a negative source, not evidence of child wake-word recall.
- Synthetic childlike voices, pitch shifts and ASR agreement do not establish real-child pronunciation or accuracy. A previously inspected diagnostic recording is not a fresh blind test.
- Keep dataset access/permission records, original hashes, uncertain-content quarantine and failed results. A dataset-card label alone does not establish redistribution rights.

Dataset import/download instructions remain in the research notes; obtain access approval before using restricted data. Do not publish household audio, restricted recordings or derived weights without documented rights. Historical experimental weights in Git history are not relicensed by the project’s Apache-2.0 code license.

## Export and device acceptance

The feature pipeline uses 16 kHz mono PCM16 and microfrontend features. The documented streaming model contract, quantization and registered operators must match the worker and firmware.

```sh
training/.venv/bin/python training/check_esp32_model.py \
  --model /absolute/private/authorized-model.tflite \
  --output training/runs/esp32-static-check.json
```

The training/static checker defaults to **64 KiB**. An explicit experimental `--max-model-bytes 524288` permits up to **512 KiB**; the current DualEye firmware uses that larger experimental flash budget, while the isolated legacy 1.83-inch target retains its own limit. A fitting file does not establish tensor-arena use, inference latency, accuracy or audio/display concurrency. Read the [firmware guide](../docs/firmware.md) before building or flashing.

Keep static checks, native Micro parity, actual board resource measurements, streaming validation and human wake acceptance as separate results. The existing household acceptance plan targets at least 18/20 wakes per person at one metre and at most one false wake over eight hours; these are targets, not completed results. See [device validation](../docs/device-validation.md).

## Checks and evidence

From the repository root, `bash tools/check.sh` includes training/tool unit tests without private audio or model credentials. Optional-runtime tests may be skipped when their dependencies are absent; a skip is not a pass. Use the [development guide](../docs/development.md) for the complete environment.

Experiments, large models and scored test recordings are not prerequisites for a documentation change. New candidate claims belong in dated reports with model hashes, source/split provenance and acceptance limits.
