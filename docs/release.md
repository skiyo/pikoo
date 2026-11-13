# Verification and release

**English** | [简体中文](release.zh-CN.md)

Desktop silent checks are complete; this architecture awaits board acceptance. The project version remains 2.0.0. This work creates no new tag and replaces no published assets.

## Current evidence

- Shared C++ configuration, Live client delegation, both LLM/search protocols, cancellation and persistence behaviors pass ASan/UBSan.
- 61 Python tooling checks, four eye-preview checks and 19 training-planner checks pass.
- 100 loopback TLS/CONNECT/voice-and-backend combinations pass, including certificate, authentication, rate-limit and disconnect scenarios, using fake credentials.
- Eight hours of synthetic PCM plus 28,800 backend tool jobs complete in accelerated time with zero virtual underruns. Desktop peak RSS is about 3.06 MiB, with about 160 KiB high-water increase after warmup. This is neither board memory evidence nor an eight-hour wall-clock run.
- A clean-source ESP32-S3 build passes: image 2,736,720 bytes, static DIRAM 168,779 bytes. Installer dry-runs and GitHub push/PR checks pass. Exact results are recorded in [sanitized verification](verification.json).

The host network driver uses Python SSL with the actual shared C++ HTTP/provider/Agent core. It does not validate ESP nested mbedTLS. Default runtime checks do not require TensorFlow. In a separate lightweight training environment, 138 of 206 Python cases passed, 68 cases requiring optional training runtimes or pinned upstream checkouts skipped, and none failed.

## Board gate

After connecting a board, back it up, verify the backup, provision the new format and keep it muted. Measure internal-heap low water, largest block, queue peaks and reconnect while Live and backend HTTPS coexist. Allocation failures, duplicate writes and old playback replay fail acceptance. Human acoustics, AEC, enclosure wake behavior and household use are separate checks.

No board was flashed in this work; existing family data, volume and orientation are untouched. Main integration requires board-resource acceptance. Earlier firmware's physical results cannot certify this architecture.

## Packaging

`tools/package-release.py` produces source/firmware and model bundles, license texts, provenance and SHA256SUMS from tracked source, the matching model policy and checked build images. Never include NVS, configuration, credentials, family data or recordings. Verify checksums and executable permissions before separately publishing. Retain source and model terms independently.
