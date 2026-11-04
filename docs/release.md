# Release verification — 1.0.0

**English** | [简体中文](release.zh-CN.md)

## Release contents

This release contains the current dual-eye firmware and source, local simulator, native Live/Terra Gateway integration, wake inference model and training checkpoint, original enclosure STLs, bilingual setup/development documentation and dependency notices. [Download](https://github.com/skiyo/pikoo/releases/tag/v1.0.0).

- `hi-pikoo-firmware-1.0.0.zip`: source, bootloader, partition table, app, SR resources, USB tools and bundled dependency license texts. No NVS or credentials.
- `hi-pikoo-model-1.0.0.zip`: TFLite, checkpoint, configuration, frozen runtime policy, model card, terms and attribution. No corpus audio.
- `release-manifest.json`, `SHA256SUMS`: version, model/policy/app identities and package checksums.

## Checks for this release

- Native C++ audio/session/playback and eye checks passed, including deterministic frames, clipping, transitions and stale-audio behavior.
- Simulator/server and JavaScript corpus-tool regressions passed. Python USB/tool checks: 56 passed; training unit suite: 206 run, 15 optional-runtime tests skipped. Skips are not acceptance evidence.
- A clean source snapshot installed dependencies and served the offline simulator with no `.env.local`, model, private config or API calls.
- ESP-IDF 5.5.5 built firmware 1.0.0 in a separate source/build directory. Published model and policy hashes are bound into the firmware; no USB writes were performed.
- The training checkpoint loaded with the published network configuration (55,329 parameters).
- Local Markdown links and release assets are checked before publication; package manifests exclude NVS/audio/secrets and include checksums.

The release packaging command is explicit and does not flash or train:

```sh
python3 tools/package-release.py --build /absolute/build \
  --model /absolute/models/hi_pikoo.tflite \
  --checkpoint /absolute/models/checkpoint.weights.h5 \
  --idf "$IDF_PATH" --output /absolute/release-assets
```

Stage the intended release source before packaging, because the packager takes only files listed in the Git index. Keep all binaries and checkpoints outside the source index. Verify package-local `SHA256SUMS` after extraction.

## Physical limits

This packaging release does not certify formal family recall, real-child accuracy, 8-hour false-wake, 72-hour endurance or universal acoustic echo cancellation. Firmware was compiled, not reflashed to the household device for this publication. Model inference timing and source limits are documented in its [model card](../models/hi-pikoo/MODEL_CARD.md).

## Rollback and persistence

Use the previous app only after confirming the same partition layout, preserving current NVS. Full factory recovery requires that board's private 16 MiB backup. Server software rollback keeps newer family memory/lists and the complete learning state. Restore a website's prior Worker deployment without changing data resources.
