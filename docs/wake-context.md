# Continuous-context wake diagnostics

[English](wake-context.md) | [简体中文](wake-context.zh-CN.md)

## Finding on 2026-10-24

The BM17 engineering model remains unqualified. A controlled development probe
reproduced sensitivity to ordinary speech immediately before the wake phrase.
This is a model/pipeline weakness, **not an established explanation of the
household's intermittent misses**. A silent 90-second prefix did not reproduce
the failure in the initial two-target probe.

The subsequent complete development check used all 195 existing targets and
a separate deterministic 30-second prefix assembled from TRAIN non-targets:

| Condition | Adult synthetic hits | Childlike synthetic hits |
|---|---:|---:|
| Cold, 1-second silence | 97/101 | 89/94 |
| Speech directly before target | 42/101 | 24/94 |
| Speech, 0.3-second gap | 65/101 | 41/94 |
| Speech, 1-second gap | 95/101 | 90/94 |

The cold total is 186/195, matching the earlier clip-based development result.
The adjacent-speech condition is much worse. The target set includes correlated
pitch/tempo derivatives. These counts do not establish human recognition rates
or a production pass. See the [sanitized report](../training/reports/wake-context-20261024.json).
The full check also covered 712 non-targets: zero cold false wakes, but the
same childlike non-target activated in each of the three speech-prefix
conditions. These are correlated replays of one clip, not three independent
false-wake events. Thus the current model also fails the new context check.

An earlier 24-target isolation diagnostic kept the model and five-inference
0.90 cutoff fixed:

| Prefix before the target | Adult synthetic hits | Childlike synthetic hits |
|---|---:|---:|
| 1 second of silence | 12/12 | 12/12 |
| 5 seconds of ordinary speech, no gap | 7/12 | 7/12 |
| 90 seconds of ordinary speech, no gap | 6/12 | 4/12 |
| Same 90 seconds, then 1 second of silence | 12/12 | 12/12 |
| Same 90 seconds, then 3 seconds of silence | 12/12 | 12/12 |

These are the same 24 existing development targets in every condition, not
independent trials, speakers or real-child acceptance. The speech prefix was
concatenated authorized ChildMandarin **TRAIN non-target** audio, not household
audio and not simultaneous background mixing. Its reuse does not measure a
false-wake rate per hour. No prefix windows exceeded the threshold in this
probe. Model-only resets recovered 11/12 adult and 12/12 childlike targets;
frontend-only resets recovered 8/12 and 6/12. Neither reset experiment proves
a safe firmware fix. Periodic resets could introduce recognition blind spots.

The model SHA-256 is
`383f3bc8f49302e1a9e8d45aff517cf107d6c3e888d81ca33d690f18f21fb4b2`.
Weights and licensed audio stay local. No model, microphone gain or wake
threshold was changed during this investigation. Fresh device telemetry showed
successful local wake, no inference errors and no dropped wake blocks; that
snapshot does not exclude other microphone or enclosure effects.

## Reproduce the development check

The pinned [training environment](../training/requirements.txt) is required.
Use a reviewed development manifest and a private protected-audio hash ledger:

```sh
python training/evaluate_context.py \
  --model /private/candidate.tflite \
  --manifest /private/reviewed-development/manifest.json \
  --protected-hashes /private/protected-recordings.json \
  --prefix-seconds 30 --gaps 0,0.3,1 --include-non-targets \
  --output /private/context-development.json
```

The tool uses all validation targets and a deterministic shuffled prefix of
non-target recordings. It uses the same reference kernels and input rounding
as the firmware. It never scores the test split. Household/evaluation-only
manifests and protected waveform copies are rejected. Reports record hashes,
prefix selection, style, source, background threshold windows and target
scores. Background windows are not counted as target hits or independent
false-wake events. Decision windows crossing the prefix/target boundary are
excluded from target scores. A report with `completed=false` is partial.
`--include-non-targets` also checks all validation near-words and ordinary
speech after the same prefixes; their activations are false wakes, not recall.

Cold, adjacent-speech and short-gap results must remain separate in future
candidate comparisons. Any resulting training change must use authorized
TRAIN data, pass the original recall/false-wake checks and continuous-context
development checks, then freeze before new independent and physical testing.
Do not lower the threshold or tune using household acceptance recordings.

## Offline training experiment

`train.py --speech-context-probability 0.5` explicitly replaces the idle lead
on half of TRAIN positive examples with ordinary TRAIN speech and a 0–300 ms
gap. An extra speech prefix warms frontend state before the retained causal
window. The complete target and completion tail remain intact. Only authorized
ChildMandarin/MInDS TRAIN non-targets supply context, with a fixed independent
random seed and hash checks. The new option defaults to zero, preserves the
baseline random sequence and evaluation construction, and changes the feature
cache key when enabled. This is a training hypothesis, not a deployed fix.

The positive-only six-epoch experiment A improved cold streaming targets from
186/195 to 193/195 but introduced **14/712 non-target false wakes**; it failed
the original gate and was not flashed. `--speech-context-negatives` explicitly
applies the same probability to TRAIN non-targets as well, including near-words.
Experiment B tests this balanced construction from the original checkpoint;
it does not inherit A's weights.

A's adjacent-speech result was 99/101 adult and 93/94 childlike targets,
compared with the baseline's 42/101 and 24/94. This confirms a useful direction
but does not offset its false wakes. Its adjacent-speech non-target false wakes
totaled 19/712, compared with 1/712 for the baseline. See the
[failed A report](../training/reports/wake-context-a-20261024.json).

B reduced cold false wakes to 4/712, with 187/195 targets. Its adjacent-speech
result was 185/195 targets and 3/712 non-target false wakes. It also failed the
complete 181-recording supplemental development gate, including English-name
groups; it was not flashed. See the [failed B report](../training/reports/wake-context-b-20261024.json).

The bounded experiment C starts from A's stronger positive-recognition
checkpoint, retaining balanced speech context and adding 136 causal hard
negative prefixes mined from **all 9,534 TRAIN non-targets** with B. Of those,
98 are real Chinese child ordinary-speech negatives, not child wake positives.
Mining never reads validation, independent tests or household recordings. C
must pass the same original, full supplemental and continuous-context checks;
training completion alone does not authorize deployment.

C finished eight epochs and failed with 189/195 cold targets and 3/712 false
wakes; the full supplement scored 63/72 targets, including failures in the
adult/childlike English-name groups. D reused the exact C feature cache and
kept A's batch-normalization parameters/statistics fixed during training. It
also failed: 188/195 cold targets, 4/712 false wakes and 60/72 supplementary
targets. The shared training/scalar-view normalization freeze has a regression
test. Neither model proceeded to the full continuous-context check after
failing prerequisite gates; neither was flashed.

See the [C report](../training/reports/wake-context-c-20261024.json) and
[D report](../training/reports/wake-context-d-20261024.json). All 907 manifest
validation clips retain bitwise-identical features in C/D. The 20 generated
internal validation noise windows differ from A/B because the expanded TRAIN
set advances the random generator; external streaming gates retain the original
manifest and do not use these windows. C and D use identical arrays.

The three C false wakes are pitch/tempo derivatives of the same existing
development phrase, “给我讲一个故事”. They remain failures. New TRAIN-only
utterances of that category and content-audited name examples are the next
data experiment; validation recordings are never copied into training.

## TTS content quality

The small new corpus uses the [official Gemini TTS interface](https://ai.google.dev/gemini-api/docs/speech-generation),
with text and `speech_metadata` separated. Requests are paced at 30 seconds,
without retries after quota errors. Eight new Flash TTS clips were generated;
all four target clips failed the local content screen (for example, “皮克” or
“Pico” instead of the complete pi/ku target). They are quarantined, not relabeled
or trained. ASR is a content screen, not human pronunciation/age acceptance.
The project's Flash TTS API returned a free-tier limit of ten requests/day;
that model was stopped. A separate bounded Flash-Lite experiment uses explicit
first-tone homophone text and undergoes the same strict content review. This
does not change the supported wake phrase.

Both ASR content screens approved two Flash-Lite childlike TRAIN targets, and
human listening confirmed that both complete name syllables use first tones.
These are two clips from one fictional voice, not real child recordings or
wake-model acceptance. Two adult Flash-Lite targets had conflicting ASR results
and stayed quarantined. Three newly synthesized ordinary-speech negatives
passed both screens. Together with four reviewed near-words, the nine new TRAIN
clips entered E. E still failed: 186/195 cold targets, 2/712 false wakes, and
64/72 supplemental targets. Literal-English name groups scored 11/13 adult and
6/9 childlike. It was not flashed; see the [E report](../training/reports/wake-context-e-20261024.json).

## Fast-speech training hypothesis

Some missed supplemental targets have only about 0.8–1.1 seconds of active
speech. This motivates a separate TRAIN-only tempo experiment; it does not
establish the cause of household misses. `prepare_voice_variants.py --fast-speech`
explicitly permits tempo up to 2.0 and rejects any non-TRAIN input, evaluation
flags or protected recording hashes. The default tempo limit remains 1.25.
Pitch-preserving duration and split protection have regression tests.

F adds two independently content-screened 3.1 Flash TTS adult targets, then
uses deterministic hash selection of 64 original TRAIN clips per style/label
bucket (adult/childlike, target/non-target), with at most eight per prompt/voice
group and 0.9–2.6-second source duration. The 256 sources produce 512 derivatives
at 1.4× and 1.8× tempo, without pitch shift. Both target and near-word negatives
receive the changes. No development recording is transformed or copied into
training. Correlated derivatives are augmentation, not new independent speakers
or child acceptance. F retains the fixed threshold and all prerequisite gates;
training and a small file size do not establish an acceptable release.

F completed eight epochs with the same 192,688-byte export. It failed with
186/195 cold targets, 5/712 false wakes, and 61/72 supplemental targets. The
literal-English groups scored 9/13 adult and 6/9 childlike. All 907 original
manifest validation features remain bitwise-identical. The small eight-TRAIN-case
float/INT8 check passed, but the full streaming gates failed; no independent or
physical test followed. See the [F report](../training/reports/wake-context-f-20261024.json).
This bounded combined continuation does not prove that tempo augmentation
generally cannot help. It was not flashed.

A separate content-only audit now covers the **entire 181-recording supplement**,
without using model scores to select clips. It checks fictional TTS with another
ASR model. The first eight-utterance request produced eight valid reviews, but
the next response had a different utterance count and was rejected without
assigning labels. Subsequent requests explicitly use `--batch-size 1`, with
30 seconds between requests; the eight valid cached reviews are retained.
Quota/API errors still stop the run. Exact transcript screening also rejects
unexpected English or digits instead of erasing them during normalization;
alignment and content guards have regression tests.
No household or independent wake-test recordings are included.
ASR disagreements require inspection; they do not authorize deleting failed
model scores or calling a corrected corpus an independent test. Existing gates
and manifests remain unchanged.

## Follow-up diagnosis and G/H/I results

A replay of 17 selected existing development failures/control clips compared
the float streaming graph with the correct INT8 reference backend. Four of the
five false wakes also occur in float; one additional false wake crosses the
cutoff only after quantization. Ten of the eleven selected missed positives
also miss in float. Thus export error alone cannot explain this candidate's
failure. Frame-level differences do expose gaps in the small eight-TRAIN-case
parity diagnostic (worst absolute error 0.245 on this selected set). These are
failure diagnostics, not an unbiased accuracy estimate or independent test.
See the [diagnosis](../training/reports/wake-context-f-diagnosis-20261024.json).

The raw ordinary-speech parent and its five pitch variants all transcribe
locally as “给我讲一个故事”. This automated content evidence does not justify
deleting their negative labels; no labels or original failures were removed.
G marks all 120 previously unmarked synthetic TRAIN recordings of the two
existing ordinary phrases as hard negatives. They gain eight repetitions,
including four causal prefixes, across all included training voices/variants.
It starts from E, adds the two reviewed adult targets, and omits F's new fast
derivatives. The same full 181-row supplement and legacy gates remain required.

The predeclared H control reused exactly G's features but started
from the original BM17 checkpoint and freeze its normalization. BM17's prior
full supplement scored 67/72 (adult literal-English 11/13, childlike 8/9), still
below the required English-name gates. D froze already-adapted A statistics;
it did not test preserving the original BM17 statistics. Neither G nor H qualified. G scored 188/195 cold targets, 2/712 false wakes
and 64/72 supplemental targets; H scored 185/195, 3/712 and 61/72.
I kept the original encoder and all fourteen original logits frozen, adding
a zero-initialized 64-unit nonlinear correction. It preserved every initial
class probability, but still failed: 187/195, 5/712 and 64/72. Its 203,496-byte
export (9,166 trainable parameters) fitting the budget does not establish
accuracy. See the [G](../training/reports/wake-context-g-20261024.json),
[H](../training/reports/wake-context-h-20261024.json) and
[I](../training/reports/wake-context-i-20261024.json) reports.
No full context or new independent tests followed the failed prerequisite
gates; none was flashed. The original external 907/181 audio replays remain
unchanged. Increased TRAIN repetitions advanced the legacy shared RNG: 517/907
internal validation windows differ from A. G/H/I share identical arrays, but
we do not claim their internal windows are identical to A. The opt-in
`--stable-split-rng` now isolates each split; legacy default/cache behavior is
unchanged. Regression tests verify this separation.

The external content audit stopped at **24/181**, with 19 transcript matches
and five disagreements: the API returned a 20-request/day free-tier quota for
2.5 Flash. No quota retry was started. The 3.8 reviewer now uses the documented
[Interactions audio input](https://ai.google.dev/gemini-api/docs/audio) and
[structured JSON format](https://ai.google.dev/gemini-api/docs/structured-output),
with stored interactions disabled. Eight focused protocol/transport tests pass,
but both the legacy and Interactions live probes timed out; the whole content
audit remains incomplete. A text-only 3.8 control also timed out, so the failure
is not proven to be specific to audio or request schema. Stable 3.1 Flash-Lite
passed one live single-clip compatibility check; a separately recorded full
181-clip review is now running at one request every 30 seconds, with no automatic
retries or paid-tier enablement. Its results do not overwrite the 2.5 audit.
This does not change the server's Live provider.

## Causal per-step experiment (J)

G/H/I did not qualify. J changes the TRAIN objective: supervise every causal
step, including cold initial states, instead of only a complete clip's final
output. The original encoder and fourteen class logits stay frozen; only the
64-unit residual head learns. Per-layer padding matches zero streaming states.
The existing 17-step pooling horizon is preserved. A 600-frame TRAIN sequence
still exports input `[1,3,40]`, one scalar output, and the original inference
receptive field.

Three graph regressions pass, including all-class/all-step equality and frozen
weights after fitting. An actual checkpoint prototype checks 1,600 streaming
steps with maximum float difference 5.37e-7 and exports a 202,968-byte INT8
graph passing static operator/shape/budget checks. A small one-epoch TRAIN
smoke run completes fitting/export with frozen weights unchanged. This is
implementation evidence, not accuracy, Micro runtime, or child acceptance.
See the [prototype record](../training/reports/wake-context-causal-prototype-20261024.json).

J uses 22,860 TRAIN examples and a fixed 12 epochs without held-out early
stopping. Actual frontend emission timestamps determine labels at the last
of each three consumed features. Before the complete annotated waveform,
labels are other; afterward, complete targets/near-phrases receive their class.
Long cropped non-targets remain other. Positive words are never cropped;
following sentences are excluded when an annotated wake endpoint exists.
Right-padding has zero loss weight; valid steps are normalized per example.
Only authorized TRAIN speech supplies warm context. Three data regressions
cover split/hash guards, timestamp alignment, padding, and complete-word rules.
Feature caches retain float32 values losslessly; an initial uint16 storage
smoke attempt rejected fractional features before any fitting.

Reproduction requires an authorized trained class checkpoint with provenance,
a TRAIN manifest, a protected-hash ledger, and the existing pinned environment.
No weights or audio are distributed here:

```sh
python training/prove_causal.py --upstream "$UPSTREAM" --manifest "$MANIFEST" \
  --checkpoint "$CHECKPOINT" --protected-hashes "$PROTECTED" --output "$PROTOTYPE"
python training/train_causal.py --upstream "$UPSTREAM" --manifest "$MANIFEST" \
  --checkpoint "$CHECKPOINT" --protected-hashes "$PROTECTED" \
  --parity-proof "$PROTOTYPE/report.json" --output "$NEW_RUN" --epochs 12
```

The final fixed epoch must still pass the unchanged full 907/181 streaming
gates and continuous-context checks, then frozen independent tests and Micro
checks. These commands never flash a board.

J finished all 12 epochs but failed: 181/195 cold targets, 2/712 false wakes,
and 63/72 supplemental targets. Literal-English groups scored 8/13 adult and
8/9 childlike. Three of eight TRAIN float/INT8 diagnostics also failed, with
maximum absolute difference 0.345. J was not flashed and did not proceed to
full context or independent testing. See the [J report](../training/reports/wake-context-j-20261024.json).
The standalone public prototype command also completed its eight-case all-step
proof and static export; neither prototype's success overrides J's failures.

An export-only K control is checking the same trained J checkpoint and same
100 calibration examples with Dense layers expressed as identical 1x1
convolutions. This enables per-output-channel weight scales in the supported
reference kernels. Three regressions cover rank-two/rank-four float functions
and integer reference portability. K does not retrain, change the cutoff, or
waive any accuracy gate; a quantization improvement alone would not qualify it.

K also failed. The export is float-identical and 205,776 bytes, but the eight
TRAIN checks still include three failures (worst absolute error 0.304). Cold
recall is 181/195 with 2/712 false wakes; the supplement stays at 63/72. This
control does not establish Dense weight precision as the main cause. Neither
J nor K is deployable; see the [K report](../training/reports/wake-context-k-20261024.json).

## Ordered acoustic branch (L)

The next hypothesis adds local acoustic order that a correction of frozen
whole-phrase features cannot recover. L keeps the original encoder/logits
fixed and learns a separate branch from its first stride-three activation:
24-channel kernels 5/9/13, an ordered 20-step ending kernel, and a 32-unit
head, with 9,470 trainable parameters. New branch activations use ReLU6;
the original encoder is unchanged. Initial zero correction preserves every
original class probability. Training data/objective and fixed 12-epoch budget
remain J's, with bytewise cache comparison required after fitting.

A nonzero-branch regression verifies all-step batch/stream equality, frozen
weights after fitting, and an export identity anchor. The full prototype's
1,600 steps have maximum float difference 7.46e-7. Its first export correctly
failed because the shared original phrase-pooling state remained float.
A unit-depthwise identity consumer preserves the function while making that
state quantizable; the second 223,568-byte export passes the unchanged strict
all-integer/operator/shape check. Micro allocation, actual timing, accuracy,
and child acceptance are still pending. See the [prototype record](../training/reports/wake-context-branch-prototype-20261024.json).
Pass `--short-context` to both proof and training commands to select this
experimental architecture; its own hash-matched proof is required.

The content-only 3.1 audit stopped at 72/181 on a read timeout. A model-metadata
request succeeded, and one explicit cached continuation uses a 90-second
timeout with the same 30-second pacing and zero automatic retries. Reviews
are now atomically persisted as a complete cache, including already-reviewed
later rows; mixed-model/label/hash caches are rejected. Nine reviewer tests
pass. ASR disagreement alone still never edits labels or erases model failures.

L finished and passed the eight-case TRAIN float/INT8 diagnostic (maximum
absolute error 0.094), but failed accuracy: 177/195 cold targets, 2/712 false
wakes, and 58/72 supplementary targets. Literal-English groups scored 7/13
adult and 5/9 childlike. All three feature/label/mask cache files match J
bytewise. The 224,120-byte trained export was not flashed; see the
[L report](../training/reports/wake-context-l-20261024.json).

## Completion uncertainty (M)

A TRAIN-only energy diagnosis of all 723 distinct positive files finds 131
with more than 200 ms of trailing quiet and 14 with more than 500 ms. This
is not phonetic alignment. It exposes a supervision ambiguity: a completed
keyword followed by quiet can still receive an other label before file end.

M retains L's model, features and numeric labels, but ignores uncertain target
ending loss. An optional `--mask-completion-uncertainty` masks the interval
from conservative final energy activity minus 240 ms until full waveform end.
Energy never assigns positive labels or trims a word. Only the complete file
boundary assigns wake labels; every post-completion positive step remains
supervised. Negatives are unchanged. Per-example weights are renormalized,
with the same fixed class-weight rule and 12-epoch budget. Four data regressions
cover unchanged features/classes and ignored-region semantics. Legacy defaults
stay unchanged; M must prove identical feature/class caches and a changed mask,
then pass all unchanged gates. It is a training hypothesis, not a release.

M also failed: 183/195 cold targets, 3/712 false wakes and 62/72 supplementary
targets; literal-English groups scored 8/13 adult and 7/9 childlike. Its eight
TRAIN quantization checks passed. Features and numeric classes match J bytewise,
and only masks differ, as required. The 224,120-byte model was not flashed;
see the [M report](../training/reports/wake-context-m-20261024.json). This bounded
control did not establish completion ambiguity as a sufficient fix.

The next prototype tests whether the original fixed first projection loses
useful acoustic distinctions. It keeps the complete original path and adds a
separate trainable 96-filter raw projection for the short branch. Select it
with both `--short-context --raw-branch`. Two branch regressions pass, including
nonzero-correction all-step parity and frozen original weights; the full
checkpoint/static prototype is still running. No new fitting or deployment
is authorized by unit tests alone, and no inference cutoff is changed.

The raw projection prototype completed: 240,464 bytes, 21,918 trainable branch
parameters, all-integer static checks passed, and maximum all-class float
difference 7.46e-7 across 1,600 steps. N then trained all 12 epochs but failed:
188/195 cold targets, 3/712 false wakes, and 62/72 supplemental targets. Its
eight-case TRAIN float/INT8 diagnostic passed (worst error 0.049). See the
[N report](../training/reports/wake-context-n-20261024.json). No full context,
independent test, or flashing followed a failed prerequisite.

## Positive event objective (O)

O tests the actual detector's five-step event instead of requiring every late
positive frame to remain high. `--mil-target-completion` requires the explicit
completion-uncertainty mask. Positives use the strongest complete five-step
window inside that existing region; padding and early incomplete prefixes
cannot satisfy the objective. The original positive supervision mass is kept.
All non-target per-frame categorical loss remains unchanged in this control.
Six initial regressions and a one-epoch real-architecture TRAIN smoke passed.
The training-only wrapper is not part of the exported inference network.

O still failed: 184/195 cold targets, 2/712 false wakes and 61/72 supplemental
targets, with adult/childlike literal-English groups at 8/13 and 6/9. The
241,008-byte export's eight-case quantization check passed. Its learned batch
sequence also matches the saved stateful stream on eight balanced TRAIN examples,
including all 1,600 steps and fresh states per example (maximum error 6.86e-7).
That numeric contract is now mandatory for future causal exports and has a
regression that detects an intentionally corrupted export. It is not accuracy
or device acceptance. See the [O report](../training/reports/wake-context-o-20261024.json).

An all-TRAIN fitting diagnosis used the same 22,860 correlated augmented examples:
5,498/5,784 positive eligible events fired, while 37/17,076 non-target examples
still produced false events. These counts are not independent evaluation or
real-child wake acceptance. A separate 16-TRAIN feature probe disproved the
idea that the new branch was ignored: its trained feature RMS is 2.35 versus
1.15 for original pooled features; zeroing it changes some probabilities by
almost one. See the [TRAIN event summary](../training/reports/wake-training-events-o-20261024.json).

## Negative event objective (P)

`--mil-negative-events` adds a unit-weight rejection loss for each negative
example's strongest valid five-step event, retaining its original per-frame
class loss. This addresses a short mistake being diluted by many correct
frames. Non-wake probabilities are summed directly to retain finite reject
gradients even when a wake probability rounds to one. Padding is excluded;
positive events get no added rejection penalty. Nine objective regressions
cover both modes, saturated errors, padding, and frozen-encoder training.
A one-epoch real-architecture smoke, static export, source snapshots and trained
sequence check passed. P kept O's network/data and fixed 12-epoch budget;
all feature/class/mask caches remained byte-identical. Inference stays at
the original 0.90/five rule. No qualification or flashing is implied.

Runs now snapshot their source files and input manifest, and reject source or
manifest drift before fitting/export. O's earlier source state was reconstructed
byte-for-byte against all eight stored training fingerprints; its failed
results and weights were not changed.

## Completed content audit and next data review

The full 181-recording second-ASR audit completed: **136 transcript agreements
and 45 disagreements**, not 45 proven bad recordings. See the [content record](../training/reports/wake-content-development-20261024.json).
Two target disagreements, selected by hash within each synthetic style without
model scores, await human listening. Existing labels/gates and all failed
scores remain unchanged. ASR spelling cannot establish exact vowels or tones.

A separate modern Google TTS TRAIN experiment obtained seven of eight planned
childlike clips (four targets, three near-negatives). All seven pass the local
content screen; external review is separate and is now complete (six agreements). The project's
3.1 Flash TTS API returned its ten-request/day free-tier quota and generation
stopped. No paid fallback was enabled. Explicit bounded read timeouts preserve
cached results; timeout/HTTP errors never automatically retry.

A model-score-independent private review pack is prepared for 931 TRAIN
synthetic anchors: 901 native originals, 29 explicitly PSOLA-derived pitch-level
anchors, and one recovered original TRAIN ancestor. It covers the lineage of
all 723 current positive training rows. PSOLA anchors are not claimed to be
native pronunciation. Real ChildMandarin recordings and household audio are
not uploaded. The current manifest's 1,142 distinct parent references have no
protected-ledger intersection. Upload/training guards also reject protected
parent hashes, sealed flags, reference audio and directory escapes. No fitting
label or development gate has been edited from this preparation.


## P result and calibration extent correction

P completed its fixed 12 epochs. The original 907-recording gate passed:
181/195 targets and 0/712 false wakes. The entire 181-recording supplement still
failed: 60/72 targets, with literal-English adult and childlike groups at 7/13
and 7/9; non-target false wakes were 0/109. One of eight TRAIN quantization
cases exceeded the original 0.15 maximum-error limit (0.1845). These failures
remain recorded; no independent acceptance or flashing followed. See the
[P report](../training/reports/wake-context-p-20261024.json).

The calibration range incorrectly counted interior uncertainty-mask zeros as
right padding, truncating real tail features. The correction uses the last
valid weight and retains all intervening real inputs. Three regressions cover
interior gaps, padding and invalid masks. Q only re-exports P's unchanged float
weights using the same 100 TRAIN calibration examples; it still failed (see below).
Development labels, threshold and the five-inference detector stay unchanged.

External content screening of seven new Google TRAIN clips is now complete:
six transcript agreements and one disagreement. The disagreement is quarantined,
not automatically relabeled negative; none entered P/Q. The full 931-anchor
TRAIN review has started, one request per 30 seconds and no automatic retry.
Local screening reuses 891 existing same-hash transcripts and runs the existing
offline recognizer only for the missing 40. Household and real-child audio are
not uploaded.


## Export controls Q–S and immutable evaluation outputs

These controls did not refit P or change its learned float probabilities:

| Control | Export change | Bytes | Original hits /195 | False wakes /712 | Supplement hits /72 | Worst TRAIN quantization error |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [Q](../training/reports/wake-context-q-20261024.json) | Corrected real-step calibration extent | 241,008 | 181 | 0 | 61 | 0.1923 |
| [R](../training/reports/wake-context-r-20261024.json) | Fuse two linear logit projections before rounding | 239,896 | 181 | 0 | 61 | 0.1662 |
| [S](../training/reports/wake-context-s-20261024.json) | Also fold a softmax-invariant common logit shift into weights | 239,896 | 181 | 0 | 61 | 0.1805 |

All failed the original 0.15 quantization ceiling and supplemental recall gate.
R/S first proved all-class float equality and unchanged original batch-to-saved
stream behavior over eight TRAIN cases /1,600 steps; these are numeric controls,
not accuracy acceptance. No failed candidate was flashed. Four fusion regressions
cover unchanged probabilities, source immutability, nonlinear-head rejection and
centering without added runtime reduction ops. Fusion remains export research;
it is not silently enabled in the ordinary training path.

An experiment-wrapper output-name collision was recovered from untouched stage
reports; models, scores and audio did not change. Future evaluation uses
`training/evaluate_candidate.py` with explicit inputs and a fresh output directory,
never copied candidate letters. Existing directories are refused and input/model
fingerprints are rechecked between stages. Two identity regressions passed. Its
first full software replay reproduced S's original/additional gates and exact
quantization report; this repeated development check is not a fresh test.

## TRAIN coverage finding

The current 723 positive TRAIN rows include only **two original adult literal
Pikoo clips and no original childlike literal Pikoo clips** (plus ten adult
variants). Chinese-surface homophones also teach pi-ku; the counts describe a
prompt/synthesis-domain gap, not verified phonetic or real-child coverage.
An existing modern Qwen3 TRAIN source contains 32 literal-name originals:
12 have prior content agreement (seven adult /five childlike). Second-recognizer
review is complete: seven agree with both (five adult /two childlike).
The original other 20 remain quarantined with their original
evidence. No model score selected these clips, no new large model was downloaded,
and none has yet entered fitting. See the [coverage record](../training/reports/wake-training-coverage-20261024.json).

The 931-anchor local pass is complete: 930 transcript agreements and one
negative-utterance disagreement. It reused 891 same-hash transcripts and decoded
only the missing 40 with the existing offline recognizer. External review is
still in progress; the 12 priority literal-name reviews have finished and the
full worker has resumed. Only one low-rate API worker runs at a time. ASR agreement
does not verify tone or actual child wake performance.

The seven two-recognizer-agreed original TRAIN names plus six new Google content
agreements form a private delta: five adult targets, five childlike targets and
three childlike negatives. Six of the 19 input clips remain quarantined with
their evidence; no labels or source audio were changed/deleted. The delta is
not fitted, does not certify the entire TRAIN corpus clean, and is not an
independent or human acceptance test.
