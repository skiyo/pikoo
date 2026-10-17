# Development

**English** | [简体中文](development.zh-CN.md) · [Home](../README.md)

## Environment and boundaries

Use Node.js 24+, a C++17 compiler, Bash and Python 3.11 for host development. Install Node dependencies with `(cd server && npm ci --ignore-scripts)`. Optional wake/training packages are pinned in `training/requirements.txt`; ESP-IDF 5.5.5 and components are pinned in `firmware/dependencies.lock`. Do not silently refresh lockfiles or upgrade upstream packages.

The original eye renderer has no ESP-IDF dependency. The default firmware now targets non-touch DualEye; the 1.83-EN project is isolated under `firmware/boards/legacy183/`. Real voice and AEC acceptance are tracked separately. Changes to simulator protocol behavior should maintain parity with device cancellation, playback drain and privacy requirements.

## Checks

```sh
bash tools/check.sh
```

This runs the C++ core and eye checks, simulator Node tests, server tests, and Python tool/training unit tests. It needs no credentials, dataset or model weights. Optional TensorFlow-dependent unit tests report skips when the optional runtime is absent; skipped tests are not passes. Use `PIKOO_CHECK_PYTHON=/path/to/python` to run with an installed training environment.

For targeted work use `bash tools/test-eyes.sh`, `bash tools/test-core.sh`, `node --test firmware/simulator/*.test.mjs` or `(cd server && npm test)`. See [actual validation summary](validation-summary.md) before making acceptance claims.

`docs/ci-checks.yml.example` is an Actions example, not an active workflow. The current publishing credential lacks workflow-write scope; no CI-success badge is displayed. A maintainer with the needed access may install the reviewed example at `.github/workflows/checks.yml` and verify its actual run before advertising CI.

## Native and device builds

Build desktop graphics using `bash tools/build-eyes.sh`. Tests produce ignored artifacts under `firmware/build-host/`. For the historical firmware, use ESP-IDF 5.5.5 and explicitly provide `-DPIKOO_WAKE_MODEL=/absolute/private/authorized-model.tflite`; see [firmware notes](firmware.md). The missing-model error and 64 KiB limit are intentional. No public firmware binary is currently supplied.

`tools/Pikoo-USB.command` and `tools/device.py` provide partition-checked DualEye installation, upgrades, diagnostics and recovery. See [firmware](firmware.md). Do not use the old board mapping on DualEye. Configuration contains secrets; store it outside Git, revoke replaced tokens, and follow the board's official download-mode instructions.

## Documentation and releases

English is the default for public entry and core docs; mirrored Chinese files end in `.zh-CN.md`. Keep language links, examples and acceptance boundaries consistent. Historical Chinese records remain intact with a dated English summary. Current UI language remains Chinese.

Before publishing, check licenses and attribution, sanitize documentation/logs, run host checks and verify offline startup from a clean tree. Never bundle credentials, household data, audio or restricted weights. Future model releases need a provenance record covering training and distribution; binary firmware releases also need the complete applicable third-party license bundle.

See [CONTRIBUTING](../CONTRIBUTING.md), [SECURITY](../SECURITY.md) and [THIRD_PARTY](../THIRD_PARTY.md).
