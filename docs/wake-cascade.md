# Experimental local phonetic veto

[English](wake-cascade.md) | [简体中文](wake-cascade.zh-CN.md)

This is an **offline development experiment**, not a released wake pipeline. It does not establish real-child recall, microphone performance, or an eight-hour false-wake rate. The normal device application is restored after each private diagnostic batch.

## Why test a second stage?

Larger KWS models improved target recall but did not pass all development requirements. B14 preserves the required recall groups but mistakes one pitch/tempo variant of “你好皮球” for the wake phrase. A pretrained local phonetic model can provide a different signal for those contrasts.

Strict target confirmation is also fallible: in the initial TRAIN probe, correct Mandarin commands scored below 0.7. The alternative under investigation keeps a full-phrase primary KWS at its existing 0.9 threshold and lets a local ESP-SR MN7_cn model **veto specific confidently recognized non-target commands**. An unknown result retains the primary decision. This operating point is an architecture experiment; it does not turn earlier failed single-model evaluations into passes.

## Fixed replay and conservative validation

1. Run the unchanged streaming frontend and five-inference moving average.
2. Round the first primary trigger up to a 512-sample capture block.
3. Replay four seconds before that boundary, 600 ms of causal lookahead, and 800 ms of appended silence into MN7. The fixed replay has 86,400 mono PCM16 samples at 16 kHz.
4. Apply a versioned veto policy to the highest-probability completed command in that bounded window. The provisional policy uses a 0.5 veto cutoff, with a 0.1 internal decoder threshold. An ambiguous near-`pi ke` command is not a veto.
5. A future implementation must retain the five-second rearm guard after a rejected primary trigger. An optional implementation is now compiled behind `PIKOO_WAKE_VETO`; it has not been flashed or hardware-accepted.

`training/cascade_gate.py` preserves all 1,046 original development rows, including clips that never triggered the primary model. It rejects incomplete or duplicate replays, mismatched identities, changed primary decisions, protected audio and wrong replay lengths. When rejecting a negative, it also requires that the original clip ends before rearming could occur; otherwise it demands a full causal replay instead of claiming zero false wakes. Quality requirements remain those in [the original policy](../training/policies/dualeye-v11-development.json).

Household recordings remain test-only. The sealed synthetic test is not used for development selection. Childlike synthesis is reported separately from authorized recordings of ordinary child speech, which are negative examples rather than real-child wake targets.

## Owned-USB diagnostic

The command benchmark accepts a zero-count private case image as a USB replay mode. It disables microphone, amplifier and networking. It receives and verifies the bounded complete waveform before inference, keeping USB transfer and recognition scheduling separate.

- `B id label samples` starts a bounded case of at most 160,000 samples.
- `F sequence base64` sends at most 512 little-endian PCM16 samples and requires a matching acknowledgement; the host defaults to smaller 128-sample frames.
- `E checksum` verifies the complete FNV-1a checksum before recognition. `R` explicitly resynchronizes the diagnostic protocol; a retry replays the whole case and is recorded.
- Results contain identities, scores, timing and free-memory counts, never PCM.

`tools/command_probe.py` implements the host transport. Out-of-order acknowledgements, checksum mismatches, device errors, panics and timeouts fail the batch. It does not flash devices or authorize a corpus by itself: the caller owns USB, verifies provenance, snapshots the exact private image, and restores/read-verifies the normal application in a `finally` block. Interrupted batches are incomplete results.

## Resource and license boundaries

The primary B14 model is 189,936 bytes. The installed MN7/FST pack is 2,681,351 bytes, separate from the 512 KiB primary KWS budget. The application partition remains 6 MiB. Combined production memory, AFE/audio/display concurrency and wake latency have not yet passed hardware acceptance.

ESP-SR 2.5.3 uses the ESPRESSIF MIT license with its ESPRESSIF-product limitation; it is not relicensed as Apache-2.0. No pretrained weights, restricted corpora, household audio or private firmware images are included here. See [third-party notices](../THIRD_PARTY.md).

The 128-case TRAIN replay completed (48 targets, 80 negatives). Strict MN7 confirmation at 0.5 retained 37/48 targets; the predeclared veto retained all 48. These are engineering controls, not validation accuracy. The integrated private image builds to 5,506,400 bytes in a 6 MiB application partition; concurrent runtime memory and latency remain unverified.


## Completed outcome

The full B14/0.5 veto replay completed all 294 primary triggers and preserved the complete 1,046-row development corpus: 293/316 targets, **1/730 false wakes**. It failed. The stronger TRAIN-predeclared B13/0.1 veto was rejected on the third negative replay because MN7 returned unknown; this is an early rejection, not a completed accuracy test. Both batches restored and read-verified the normal application. The optional integration remains OFF and was never installed as a normal release.
