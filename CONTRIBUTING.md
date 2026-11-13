# Contributing

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

## Prepare a focused change

Read the [architecture](docs/architecture.md) and [development guide](docs/development.md). Describe the user-visible problem and expected behavior before adding a protocol or tool. Keep board-specific code outside shared core logic. Use explicit protocol names and bounded data structures.

## Validate the affected layers

Run `bash tools/check.sh` in the documented environment. Run targeted network fixtures when changing transport/adapters and cross-compile when touching firmware. Hardware claims require measurements on the target board. Normal checks must not capture household audio or call paid providers. Include actual results and limitations, including skipped tests.

Documentation changes should update English and Chinese together. Check commands against `--help`, validate JSON examples, inspect links and explain expected output. Keep examples free of real hosts, keys, recordings and user data. Do not rewrite copyright or third-party terms while translating prose.

## Submit and review

A useful PR explains the trigger, resulting behavior, implementation boundary and validation. For UI/eye changes include a safe preview; for performance include workload, units and measurement environment. Do not claim simulator measurements as board evidence. Keep unrelated formatting/dependency upgrades separate.

Preserve dependency locks and notices. Model changes require matching policy, hashes, provenance and publication permission; source licensing does not override model/data terms. See [release](docs/release.md) and [public checks](docs/public-audit.md).
