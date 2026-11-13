# Verification and release

**English** | [简体中文](release.zh-CN.md)

Pikoo 2.0.0 passes the listed software and real-board scenarios through configured HTTPS CONNECT. Direct OpenAI did not establish a session in the tested network; direct board concurrency remains unverified. No new tag or published binary asset is created by this work.

## Real-board evidence

The final ESP32-S3 image is 2,740,848 bytes, static DIRAM is 168,907 bytes, and Agent event tracing is disabled. A 16 MiB Flash backup was verified in 64 chunks before application-only flashing. Config/data partitions were checked across flashes; original family data was restored and re-read equal after synthetic tests. Volume and orientation settings are preserved. No manual USB replug was needed.

| Scenario | Observed result |
|---|---|
| Local wake | Final image woke on the first fixed complete English phrase; score 0.960. This is an engineering fixture, not recall-rate acceptance. |
| Lists and explicit memory | Actual tool writes and readback pass; software restart preserves the full snapshot. |
| Search | Live + independent Responses reasoning/search pass. Three HTTP 200 results; the search call takes 5,166 ms within its 8,000 ms deadline. |
| Authentication | A fake LLM key returns 401 while voice remains usable; no list/memory change. Replacing the key and restarting restores tool-based memory reading. |
| Interruption | Stop during actual story playback leads to quiet output; the next arithmetic question is answered correctly. |
| Late results | Interrupting an in-flight backend request produces a discarded cancelled result, with no memory write. The next tool request completes normally. |
| Privacy | Farewell returns to local standby; ten seconds muted adds neither captured nor uploaded samples. |
| Final-image stability | 120-second voice-stream window plus fault scenarios, 188.89 seconds combined: zero unexpected reconnects, queue overflows, I²S/frame-send errors or observed playback-supply gaps. |

During that final-image run, internal-heap low water is **27,308 bytes**, the smallest sampled largest block is **23,552 bytes**, and backend stack headroom is **6,256 bytes**. Playback peaks at 14,400 samples (900 ms at 16 kHz). A deliberate 1.5-second sender pause reaches an observed 46 of 80 upload frames and drains back to zero without overflow. These are board measurements, not desktop RSS. Four final-image TLS observations are recorded separately; their percentiles are a small engineering sample, not a 100-connection board benchmark.

## Software checks

- Native playback/session/eyes checks, 17 service behaviors under ASan/UBSan, 66 Python tools, four eye-preview checks and 19 planner checks pass.
- 100 loopback TLS/CONNECT/service combinations pass with independent fake credentials, certificate/authentication/rate-limit/disconnect faults and both LLM/search adapter protocols.
- Eight hours of equivalent PCM plus 28,800 backend jobs finish in accelerated desktop time with zero virtual underruns. This is not an eight-hour wall-clock device soak. Exact timings, memory units and limits are in [sanitized verification](verification.json).
- The optional training suite is separate: 138 of 206 cases passed and 68 needing optional runtimes/upstream checkouts skipped. It is excluded from default runtime checks.

## Acceptance limits

Actual accounts used here are OpenAI Live and Responses. Other adapters have fake-provider regression coverage. Direct board concurrency, real power removal, subjective listening, enclosure AEC, real-child/household wake and long-duration family use remain separate checks. Do not infer them from synthetic speech, successful I²S writes or desktop replay. Host microphone recording was not performed; output timing, device transcripts and storage readback provide the automated evidence.

## Packaging and rights

Public model/firmware packaging remains blocked while [model redistribution permission](../models/hi-pikoo/distribution-status.json) is pending. Hardware test success grants no upstream rights. See the [public audit](public-audit.md). When cleared, `tools/package-release.py` checks the matching model policy and build and includes dependency notices, provenance and checksums. Never include NVS, configuration, credentials, family data or recordings.
