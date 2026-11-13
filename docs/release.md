# Verification and publishing

**English** | [简体中文](release.zh-CN.md)

## Read evidence by environment

[verification.json](verification.json) records workload, image identity, units and limitations. Results apply to the measured environment and build, not automatically to every release binary or provider. Use the release manifest and SHA256SUMS to identify downloaded artifacts.

| Layer | What it establishes | What it does not establish |
|---|---|---|
| Native core tests | State, tools, cancellation and bounded synthetic playback | Board scheduling or acoustic quality |
| Local TLS fixtures | Protocol behavior, credential separation, errors/reconnects | Production-provider latency or availability |
| Accelerated PCM | Eight-hour-equivalent synthetic workload and bounded queues | Eight elapsed hours of board endurance |
| Board engineering workload | Measured heap, stack, queues and exercised behavior | Universal household wake accuracy or all hardware variants |
| Archive/public checks | File integrity, local links and selected sensitive patterns | Complete legal review or detection of every possible secret |

Recorded software coverage includes 18 service behaviors under ASan/UBSan, 67 Python tool checks, five preview tests, eight enclosure-guide tests, 19 generation-planner tests and 100 network fixture cycles. The accelerated workload covers 28,800 seconds of PCM and backend work with zero virtual underruns. Consult current CI for the exact source revision.

Board evidence includes voice/list/memory/search operations, restart readback, cancellation, authentication failure/recovery, farewell and mute. The measured streaming window is 120 seconds plus fault scenarios; internal-heap low water is 27,308 bytes, smallest sampled largest free block 23,552 bytes and backend stack headroom 6,256 bytes. The tested image hash and separate source-build identity are explicitly recorded in the JSON. These numbers must not be attached to an untested binary as if it had been flashed.

Natural child/household wake performance, subjective listening, final-enclosure AEC, real power-cut recovery and long-duration operation require their own acceptance. Production-provider coverage and fixture-only adapters are listed separately in the evidence.

## Prepare a release

1. Check version agreement between `VERSION`, the firmware build and `release-plan.json`.
2. Validate public examples and run the documented software/network checks.
3. Build the exact target with ESP-IDF 5.5.5 and the reviewed model/policy pair.
4. Confirm partition fit, image identity, dependency notices and model publication metadata.
5. Validate board changes with an explicit workload. Preserve existing private data and record test limitations.
6. Package and verify all archive entries and checksums. Exclude NVS, keys, recordings and family snapshots.

```sh
python tools/package-release.py --build firmware/build-dualeye \
  --model models/hi-pikoo/hi_pikoo.tflite \
  --checkpoint models/hi-pikoo/checkpoint.weights.h5 \
  --idf "$IDF_PATH" --output /absolute/output/pikoo-release
```

Use a new output directory. This command creates the firmware/model ZIPs, manifest and checksums; it does not publish or access USB. The model publication check verifies a hash-bound permission record and retains non-commercial terms.

## Automated publication

The `Publish release` workflow runs from main through manual dispatch or a release-plan/workflow change. It waits for software and public checks on the exact commit, cross-builds the firmware, packages assets and adds the application-only BIN. The publisher checks that main still points to that commit, uploads into a draft, verifies returned size/SHA256, then makes the release public.

An already published release is preserved. Branch cleanup is optional in `release-plan.json` and limited to unprotected `codex/` branches whose tips are ancestors of the checked commit, with a final ref check. Main, archive branches and unmerged work are retained. Ordinary documentation edits do not trigger a new binary release.

## Asset contract

| Asset | Contents |
|---|---|
| Firmware ZIP | Source, USB installer, matching images and dependency notices |
| Model ZIP | TFLite, checkpoint, policy, metadata, attribution and terms |
| Application BIN | Application partition only; use the installer for normal updates |
| `release-manifest.json` | Source/version, target, model/policy and firmware hashes |
| `SHA256SUMS` | Download integrity checks |

Consumers should start with the [quick start](getting-started.md); maintainers should preserve validation scope rather than converting limited tests into universal reliability claims.
