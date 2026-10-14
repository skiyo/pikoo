# Open-source publication checks

**English** | [简体中文](open-source-validation.zh-CN.md)

Date: **2026-10-14**. Scope: bilingual documentation, attribution, public startup and explicit model configuration. These checks do not replace hardware, live speech or long-duration acceptance.

| Check | Actual result |
|---|---|
| Clean-tree onboarding | Copied only public tracked/new sources to an independent temporary directory, with no weights, private configuration or installed modules. `npm ci --ignore-scripts --no-audit --no-fund` passed; launcher compiled and started the offline simulator using Node 24.21.0 |
| Offline service | Reported mock mode, wake disabled and no model. Five page/asset routes returned HTTP 200. Received one complete 230,400-byte pair of 240×240 RGB565 frames; launcher-managed stop succeeded. Total install/start/check time: 4.429 seconds on the development Mac; not a performance guarantee |
| C++ checks | Session/audio core passed; 13 deterministic eye states, clipping, boundaries, transitions and blink passed with ASan/UBSan |
| Simulator/server | 18 Node simulator regressions and 8 server adapter tests passed; missing/unreadable-model error cases included |
| Python tools | 4 tests passed |
| Python training | Minimal environment: 10 passed, 2 optional-runtime tests skipped. Existing Python 3.11 training environment: all 12 passed, including alignment/quantization |
| Firmware configuration | Actual ESP-IDF reconfigure rejected missing weights with the intended message. Full historical 1.83-EN firmware built with an explicit private V5 model. No binary or weights published; this is not DualEye board acceptance |
| Public files | Local links, language pairs, whitespace, dependency inventory and targeted credential/personal-data scan checked before commit. Current Git tree contains no `.tflite`, audio recordings or private runtime configuration |
| Local private use | Existing localhost service still reported live mode and a 45,128-byte model. Private start/stop entry points outside the repo preserved |
| GitHub settings | English description and topics configured; private vulnerability reporting verified enabled. Apache-2.0 recognized by GitHub |
| Actions | Workflow example only; publishing credential lacks workflow-write scope. No active-CI success claim |

Third-party attribution covers pinned software and separates vendored code from dependencies and inspiration. The npm inventory contains 195 resolved dependency entries, including transitive dependencies; declarations are not a complete redistribution license bundle or a security audit.

Git history is retained and still contains an earlier research model. Its rights are unresolved and it is not granted Apache-2.0 model licensing. Current model cards and aggregate reports remain; local private files are preserved.

See [historical validation summary](validation-summary.md) for unresolved automatic-memory timeouts, real microphone and hardware/endurance work.
