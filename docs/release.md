# Verification and release

**English** | [简体中文](release.zh-CN.md)

Pikoo 2.0.0 engineering checks cover the shared C++ core and the ESP32-S3 board. See [machine-readable results](verification.json) for measurements and limits.

## Verification scope

- Native playback, session and eyes; 18 service behaviors under ASan/UBSan; 67 Python tooling checks; five preview and 19 planner checks.
- 100 local TLS/service fault combinations with independent fake credentials and both LLM/search protocols.
- Accelerated eight-hour equivalent PCM and 28,800 backend jobs with zero virtual underruns; this is a desktop workload, not an eight-hour board soak.
- Board speaker wake, voice, list and explicit-memory tool writes, restart readback, search, interruption, cancellation, authentication failure/recovery, farewell and mute.
- Final board workload: 120 seconds of voice streaming plus fault scenarios; zero unexpected reconnects, queue overflows, I²S/frame-send errors or observed playback-supply gaps. Internal-heap low water: 27,308 bytes. Smallest sampled largest block: 23,552 bytes. Backend stack headroom: 6,256 bytes.
- App image: 2,740,848 bytes; static DIRAM: 168,907 bytes. Build identity and SHA-256 are in the results file. Changing source or build options requires a new build and validation.

Synthetic speech does not establish household/child wake rates, subjective sound, enclosure AEC, real power-loss recovery or long-duration reliability. Provider and transport combinations require their own deployment checks. Optional training runtimes are tested separately.

## Release checklist

Validate configuration, run `tools/check.sh`, cross-build the target board, verify image/partition ranges, run board acceptance and check license notices and checksums. Packages must exclude NVS, credentials, recordings and user data.

Public model/firmware packaging remains blocked while [model redistribution permission](../models/hi-pikoo/distribution-status.json) is pending. Technical test success does not grant upstream rights. See [public repository checks](public-audit.md).

English defaults and bilingual stop commands pass native tests and cross-compilation. Board metrics identify the tested image; changing language defaults does not re-certify acoustic behavior.
