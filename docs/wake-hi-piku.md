# Hi Pikoo wake research

English | [简体中文](wake-hi-piku.zh-CN.md)

Updated 2026-10-31. The current target is **Hi + piku OR Hi + piko**.
The user approved the dual pronunciation before the first real-corpus fit;
`hi-piku-piko-v2` records that revision. The greeting and complete name remain
required. Tikoo, a name alone and the historical Chinese greeting are excluded.
Conversation language, server, volume and installed wake model are unchanged.

## Current results

2026-11-01 [device follow-up](reports/hi-pikoo-device-2026-11-01.json): the
authorized private trial is now installed after a verified complete flash backup.
The silent board probe matched 16 host feature/output frames; 600 timed calls
gave 6.303ms p99, 6.406ms maximum and a 25,116-byte arena, with 19.6fps eyes and
no deadline/inference errors. Normal firmware joined Wi-Fi and showed standby
with zero uploaded samples and the existing 0dB setting. This passes the bounded
resource gate, not recognition, natural-interruption or long-run acceptance.
The following corpus and packaging results describe the 2026-10-31 snapshot.

The first human wake succeeded, followed by a separate Gateway→OpenAI TLS reset
issue. The [network follow-up](reports/live-network-2026-11-01.json) records
failed attempts as well as the mitigation: Taiwan exit plus explicit IPv4 and
classical key-exchange groups, with hostname/certificate checks and normal TLS
version negotiation retained. Three real Live starts/normal closes, a Terra
call and device greeting reception succeeded afterward. IPv4 alone had still
failed. Human listening and long-run stability remain unaccepted; this does
not change wake weights, thresholds or any failed recognition result.

The [machine-readable record](reports/hi-pikoo-2026-10-31.json) preserves all
52 completed fits across thirteen bounded studies and their failures. Reclocking
the same weights is not counted as new training. **No candidate meets the formal
development gate.** The user separately authorized a best-available private
trial. This does not turn failed DEV into a pass or authorize a public model release.
The installed device has not been changed; no USB board was enumerated during
packaging. See the machine-readable record for the final sealed-test/build state.

- Corpus: 883 retained new synthetic originals, 551 admitted and 332 quarantined;
  343 OpenAI originals and 540 local Qwen3 originals. TRAIN has 407 originals,
  DEV 144. Ordinary public TRAIN contributes 1,468 speaker-stratified negatives.
  Source auditions are outside numerical training; household audio is excluded.
- GPT requested-childlike auditions sounded adult and are counted as adult.
  Qwen3 E/F auditions were perceived girl-like, G boy-like. These are synthetic
  source/prompt families, not verified real children or guaranteed distinct voices.
  Five piko recordings have manual vowel reviews; other vowel groups are
  ASR-inferred rather than gold phoneme labels.
- Reference 24-channel models are about 40–43kB. The 48-channel/BatchNorm study
  produced 55,552/60,544-byte INT8 models with host arenas 17,680/24,272 bytes.
  Larger capacity did not jointly solve cross-voice recall and confusable rejection.
  **Host allocation is not ESP32 timing or memory acceptance.**
- All 52 fits were compared on the same reused 144-case DEV, never described as
  independent testing. The best zero-false/zero-early policy is v7, context 20,
  seed 43: **86/92 target clips**, **0/52 negative clips**, weakest group **10/13**,
  with 126.25ms p95 delay on detected targets. The model is 40,424 bytes; the
  frozen rule is three-score averaging at 0.90. Synthetic childlike piku is
  11/11, childlike piko 10/13; this is not real-child acceptance. Some adult
  pronunciation cohorts contain only three clips.
- Additional phrase-family supervision and 48/96-channel phonetic initialization
  did not beat that policy. Phonetic pretraining used 21,985 full public original
  TRAIN utterances, split into 19,673 training and 2,312 speaker-held-out
  development utterances. Its phoneme error rates remain 63.4%/56.3%; these weak
  encoders are neither mature ASR nor evidence of successful wake recognition.
  Their CTC heads are never deployed. Source permission boundaries still apply.
- Three difficult synthetic childlike DEV targets remain failures. A separate
  six-clip audio-language-model diagnostic heard complete names and did not
  justify deleting them. Diagnostic transcripts are fallible evidence, not gold
  phonemes or revised labels.
- The entire paid generation/audit/retry cap remains **$2**, including earlier
  auditions, failures and uncertain-request reservations. The report contains
  the final estimate. This is not a reconciled provider bill or the cost of the
  separately running conversation service.

Frozen-candidate TEST generated 150 new synthetic adult recordings using held-out
voice IDs. Only **76/150** passed blind ASR/generator content agreement: targets
**35/41 detected**, negatives **0/35 false wakes**, no early wakes. The other 74
are unresolved transcription conflicts, not proven bad audio. These conditional
subset rates cannot represent whole-test accuracy. The TEST failed, remains
consumed, and did not change model selection or parameters. It provides no
real-child result. Final estimated generation/audit spend is **$0.3984836**.

Both the private voice firmware (2,597,312 bytes) and silent benchmark image
(512,544 bytes) compile under ESP-IDF 5.5.5. Image/partition dry-runs and the
offline preview/worker startup passed. No board was available, flashed or
measured; neither image is a public release or a passed hardware acceptance.

## Natural timing and exterior silence

Natural “Hi Pikoo” generally needs about **1–2 seconds of speech**; it need not
be lengthened or read syllable by syllable. The admitted corpus median active
span is 1.04s. Twelve admitted clips have more than 500ms of trailing quiet;
nine have more than 300ms of removable exterior padding. This affects a subset
of the corpus and does not explain all recognition failures.

A prior audition was 6.7s long with about 1.32s of active speech and a 5.36s quiet
tail. That source audition was outside numerical training. Its short preview is
an evaluation-only derivative; neither audition enters training.

`hi_pikoo_timing.py` audits only new fictional TRAIN/DEV files. Originals stay
immutable. The canonical feature view keeps 200ms before and 300ms after measured
activity, preserves every internal pause, and never cuts words out of an utterance.
Both positive and negative synthesis use the same rule. Repetition, missing words
and extra words still fail content admission. Timing cannot repair pronunciation.

The energy clock uses 20ms RMS, a 5-PCM-unit floor or 5% of peak (about −26dB),
plus a 40ms endpoint guard. An earlier 1%-of-peak clock included weak TTS tail
noise. Original reports are preserved; `hi_pikoo_reclock.py` writes separate DEV
measurement corrections with unchanged weights/audio and never calls them new TEST.

## Pipeline

1. `training/hi_pikoo_contract.py`: explicit target revisions; preserve raw rows.
2. `training/hi_pikoo_generate.cjs`: existing-key Realtime synthesis with a private
   exclusive lock, reservation-before-request and no automatic retries. Separate
   pilot, approved TRAIN expansion, adult DEV and frozen-candidate TEST phases.
   TEST uses a separate manifest and matching frozen model hash. Failed-DEV
   private trials require explicit `--allow-trial-test yes`; they remain failed.
   No child-voice policy bypass or paid fallback is attempted.
3. `training/hi_pikoo_local_audition.py` and `generate_local_tts.py --jobs-file`:
   reuse an already-downloaded local model, no reference recordings or downloads.
   Fresh synthetic jobs inherit their predeclared source-family partition.
4. `training/hi_pikoo_review.py`: blind offline ASR with no expected transcript or
   hotword. `hi_pikoo_admit.py` combines the preserved transcript, source evidence
   and protected hashes. Uncertain/extra/incomplete utterances stay quarantined;
   no trimming of failed speech into successful positive clips.
5. `training/hi_pikoo_train.py`: new weights, no historical classifier. Two
   contexts × two seeds, at most 30 epochs, DEV early stopping. Separately
   recorded studies allow 24/48/96 channels, BatchNorm, phrase-family loss, or an
   independently trained public-phone encoder. The latest checkpoint proxy uses
   group-balanced event-confidence error, prefix and negative-family penalties;
   an earlier discrete proxy prematurely favored silent classifiers. This fix
   changes checkpoint selection, never final gates. Synthetic TRAIN gets
   12 positive/6 negative variants;
  DEV originals and their padding stay fixed per waveform hash. Only TRAIN gets
   speed/room/noise augmentation and quantization calibration. Public speech is
   bounded by speaker; near/incomplete synthetic negatives remain explicit.
6. `training/hi_pikoo_phone_pretrain.py`: full-original public TRAIN only,
   speaker-separated phone DEV, CTC, bounded memory-mapped features; no household
   or official TEST input. Optional initialization verifies encoder/report hashes.
7. `training/hi_pikoo_common_dev.py` and `hi_pikoo_verify.py`: common reused DEV,
   trained float sequence/export checks, reference/native Micro byte parity
   across resets and complete DEV replay before freezing. A trial requires an
   explicit authorization file and retains `development_passed:false`.
8. `training/hi_pikoo_sealed_review.py` and `hi_pikoo_sealed_score.py`: fresh
   candidate-bound synthetic adult TEST, blind content review, fixed-policy
   native Micro scoring. A consumption marker is written before inference;
   failed/consumed tests are never silently replaced or used for selection.

Example collection arguments (private output and an existing authorized key):

```sh
node training/hi_pikoo_generate.cjs \
  --key-file .env.local --output training/runs/hi-piku-private \
  --audition-root /absolute/private/earlier-auditions
```

Training additionally requires explicit `--target-contract`, admitted
`--manifest`, `--background-manifest`, `--protected-hashes`, pinned `--upstream`
and a new private `--output`. Raw generation manifests intentionally fail
admission. `--resume-export` can reuse saved weights after an export failure only
when the model definition, input hashes and every prepared feature/label/mask
array are identical. Restore a run’s source snapshot for an older model definition.
Failures and resumed provenance remain recorded.

## Device contract and gates

16kHz mono PCM16 → the existing microfrontend (30ms window, 10ms step, 40 bins)
→ stateful INT8 [1,3,40] → one probability, every 30ms. Host and firmware use the
same float32 ring-average rule. DEV compares 3/5 scores and thresholds
0.80/0.85/0.90/0.95; any DEV false/early wake rejects a policy before recall ranking.
A qualified policy needs every positive cohort ≥90% recall and p95 delay ≤800ms.
Tiny cohort counts and synthetic-source limitations must accompany those rates.

`wake-policy.json` binds the model SHA-256, explicit names, frontend fingerprint,
frozen date, DEV result, smoothing and threshold. `PIKOO_WAKE_POLICY` supplies it
to firmware/worker; new Hi Pikoo candidates require a matching policy. Legacy
builds retain five-score/0.90 behavior. Unqualified trial policies are rejected
by default. A privately authorized build must explicitly set
`PIKOO_WAKE_ALLOW_TRIAL=ON`; the worker requires `PIKOO_ALLOW_TRIAL_WAKE=1`.
Both show an unqualified-trial warning. None of these flags marks DEV passed.

Untrained prototypes passed all-step float/static checks and native TFLM
300-invocation/three-reset checks, with host arenas 14,240/17,056 bytes. All four first-round trained exports also passed native Micro/reference byte
parity on eight balanced TRAIN fixtures over three resets, with the same host
arenas; recognition still failed. **Host allocation is not ESP32 allocation
or inference latency.** The selected trial also passed all 144 DEV originals
on native Micro with three identical resets. Device gates remain arena ≤256KiB, frontend+inference
p99 ≤20ms/max ≤30ms and audio/display concurrency without watchdog/overflows.

After freezing: newly generated independent TEST, safe recoverable board resource
checks, then four family members at one metre, two sessions ×20 attempts each
(target ≥18/20 per person/session), plus eight-hour background testing (≤1 false
wake). A synthetic-only diagnostic image leaves microphone, network and amplifier
off, emits a deterministic backend probe and reports real board timing/arena
when actually run. Compilation or a host dry-run does not satisfy these gates.
Family audio stays evaluation-only: no training, cleaning, augmentation,
calibration or model selection. Consumed tests never become fresh tests.

No recordings, restricted weights, credentials or model-bearing firmware are
published. Original code is Apache-2.0; external model/data/service terms remain
separate. See [third-party boundaries](../THIRD_PARTY.md).

Research context: [limited/synthetic KWS data](https://arxiv.org/abs/2002.01322)
and [phonetic/KWS multi-task learning](https://arxiv.org/abs/2107.07634)
motivated the bounded encoder experiment; their reported performance does not
transfer to this implementation. The independent CTC training uses the
[TensorFlow CTC API](https://www.tensorflow.org/api_docs/python/tf/nn/ctc_loss).
No pretrained encoder or implementation from those papers was copied.
