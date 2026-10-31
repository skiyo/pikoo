# Hi Pikoo wake research

English | [简体中文](wake-hi-piku.zh-CN.md)

Updated 2026-10-31. The current target is **Hi + piku OR Hi + piko**.
The user approved the dual pronunciation before the first real-corpus fit;
`hi-piku-piko-v2` records that revision. The greeting and complete name remain
required. Tikoo, a name alone and the historical Chinese greeting are excluded.
Conversation language, server, volume and installed wake model are unchanged.

## Current results

The [machine-readable record](reports/hi-pikoo-2026-10-31.json) preserves all
28 completed fits across seven bounded studies and their failures. Reclocking
the same weights is not counted as new training. **No candidate currently meets the deployment gate.**
The installed device has not been changed and sealed TEST remains closed.

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
- At least one configuration reached 84.6% worst-cohort recall while still firing
  on excluded examples. Other configurations rejected all DEV negatives while
  missing too many targets. These are failed synthetic DEV results, not child
  performance or independent TEST results. Some cohorts contain only three clips.
- Estimated paid generation cost is **$0.2831082**, including prior auditions,
  failures and one conservative uncertain-request charge. The entire run cap is
  **$2**. This is a generation usage ledger, not a reconciled provider bill or
  the cost of the separately running conversation service.

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
   TEST uses a separate manifest and requires a matching frozen model hash and
   passed DEV. No child-voice policy bypass or paid fallback is attempted.
3. `training/hi_pikoo_local_audition.py` and `generate_local_tts.py --jobs-file`:
   reuse an already-downloaded local model, no reference recordings or downloads.
   Fresh synthetic jobs inherit their predeclared source-family partition.
4. `training/hi_pikoo_review.py`: blind offline ASR with no expected transcript or
   hotword. `hi_pikoo_admit.py` combines the preserved transcript, source evidence
   and protected hashes. Uncertain/extra/incomplete utterances stay quarantined;
   no trimming of failed speech into successful positive clips.
5. `training/hi_pikoo_train.py`: new weights, no historical classifier. Two
   contexts × two seeds, at most 30 epochs, DEV early stopping. Optional `--channels 48
  --batch-normalization` is a separately recorded capacity study; the default is
  24 channels. The current checkpoint proxy ranks
  qualified float DEV first, otherwise worst-group recall minus 0.1 per false
  wake and 0.05 per early wake. Final qualification still uses INT8/Micro,
  never the float proxy. Synthetic TRAIN gets 12 positive/6 negative variants;
  DEV originals and their padding stay fixed per waveform hash. Only TRAIN gets
   speed/room/noise augmentation and quantization calibration. Public speech is
   bounded by speaker; near/incomplete synthetic negatives remain explicit.
6. `training/hi_pikoo_verify.py`: all-step trained float sequence/export checks,
   INT8 reference vs native Micro byte parity across resets, then qualified
   candidate freeze. No sealed TEST, family input or device writes in this step.

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
builds retain five-score/0.90 behavior. The current source builds with the private
legacy model; it does not install a new model.

Untrained prototypes passed all-step float/static checks and native TFLM
300-invocation/three-reset checks, with host arenas 14,240/17,056 bytes. All four first-round trained exports also passed native Micro/reference byte
parity on eight balanced TRAIN fixtures over three resets, with the same host
arenas; recognition still failed. **Host allocation is not ESP32 allocation
or inference latency.** Device gates remain arena ≤256KiB, frontend+inference
p99 ≤20ms/max ≤30ms and audio/display concurrency without watchdog/overflows.

After freezing: newly generated independent TEST, safe recoverable board resource
checks, then four family members at one metre, two sessions ×20 attempts each
(target ≥18/20 per person/session), plus eight-hour background testing (≤1 false
wake). Family audio stays evaluation-only: no training, cleaning, augmentation,
calibration or model selection. Consumed tests never become fresh tests.

No recordings, restricted weights, credentials or model-bearing firmware are
published. Original code is Apache-2.0; external model/data/service terms remain
separate. See [third-party boundaries](../THIRD_PARTY.md).
