# Hi Pikoo wake research

English | [简体中文](wake-hi-piku.zh-CN.md)

Updated 2026-10-31. The current target is **Hi + piku OR Hi + piko**.
The user approved the dual pronunciation before the first real-corpus fit;
`hi-piku-piko-v2` records that revision. The greeting and complete name remain
required. Tikoo, a name alone and the historical Chinese greeting are excluded.
Conversation language, server, volume and installed wake model are unchanged.

## Evidence and current limits

- The independent causal networks have 17,393/18,641 parameters for 20/72 ordered
  steps. The first trained INT8 exports are 40,080/42,576 bytes. These are small
  weights, not a hardware timing or accuracy claim.
- Four first-round fits (two contexts × seeds 42/43) completed. **None qualified
  on complete admitted DEV.** At five-score/0.90, worst-group recall was 66.7%,
  with 6–7 negative clips firing and 4–10 early detections under the initial
  file-end clock. These results stay failed; they are not sealed TEST results.
  Most false wakes were the excluded “Hi Tikoo” confusable.
- User listening accepted GPT pronunciation/naturalness, but its requested
  childlike delivery sounded adult. It is counted as adult. Reused local Qwen3
  text-only VoiceDesign auditions E/F were perceived girl-like, G boy-like;
  C/D/H were rejected as younger-child sources. **All are fictional synthesis**,
  not real children or verified per-clip ages/speaker identities.
- Before targeted expansion: 493 retained originals yielded 267 admitted clips,
  226 quarantined. TRAIN/DEV source families are separated. The screen combines
  source auditions and blind local ASR; it is not gold phoneme/age annotation.
  Five separately auditioned piko clips were heard as ko and are recorded as
  such. Raw manifests and old labels are retained; revised labels are derived.
- Long phonetic prompts produced extra/repeated speech and were disabled.
  Source audition audio stays outside numerical training. Ordinary ChildMandarin
  TRAIN recordings supply bounded negatives, never target-positive evidence.
- OpenAI spending before targeted expansion was approximately **$0.217**, including
  prior auditions and a conservative uncertain-request charge. **The full run
  cap is $2**, not $20. Expansion is a finite 100-request adult TRAIN batch using
  the same ledger, with budget checks before every request. Actual final usage
  and uncertain reservations remain separate from a reconciled provider bill.
- Later finite comparisons with the corrected admission and event clock also
remained unqualified. A further TRAIN-only local expansion is in progress.
No candidate is frozen, released or flashed. Household recordings have not
  been used. Household recall, ESP32 timing and eight-hour false wakes remain
  untested for this target.

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
   contexts × two seeds, at most 30 epochs, DEV early stopping. The current checkpoint proxy ranks
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
when input hashes and every prepared feature/label/mask array are identical.
Failures and resumed provenance remain recorded.

The follow-up experiment corrects an event-clock limitation: a conservative
20ms RMS endpoint (40dB below peak, five-PCM-unit floor, plus 40ms guard) excludes
quiet tail from the timestamp without deleting waveform samples. It is
independent of model scores and cannot establish that a phoneme was pronounced.
The earlier file-end experiment is preserved separately. No household sample
informs this change.

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
