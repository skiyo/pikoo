# Playback false-wake investigation

English | [简体中文](wake-playback-negatives.zh-CN.md)

This refresh addresses unintended activation by ordinary speech, television and
short-video playback. It preserves the complete **Hi piku / Hi piko** target
and its three-score mean / 0.90 threshold. The installed architecture remains
unchanged; an additional offline comparison expands only the classifier from
32 to 64 units and verifies the original float function before any updates.
It does not modify conversation language, voice, gain, server networking, or
family memory.

## Data and boundaries

| Source | Role | Terms and limitations |
| --- | --- | --- |
| [LibriSpeech](https://www.openslr.org/12/) `train.100` | Natural English speech negatives | CC BY 4.0. Speaker identity assigns TRAIN/DEV before audio scoring. Read speech is not actual television dialogue. |
| Previously authorized [ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin) | Ordinary Mandarin child-speech negatives | Official TRAIN/DEV separation; restricted noncommercial research terms. No new corpus download or household collection. Recordings and derived models remain private. |
| [ESC-50](https://github.com/karolpiczak/ESC-50), commit `33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6` | Environmental sounds and nonverbal vocalizations | 300 TRAIN and 100 DEV clips across 50 categories. Original recording folds stay separate. ESC-10 is CC BY; other selected clips retain CC BY-NC terms. Fold 5 audio stays unopened during development. |
| Same-partition speech playlists | State retention across recording boundaries | Ordinary recordings concatenated with 150ms gaps; every parent remains in its original partition. These are constructed playback challenges, not independent natural conversations. |

Audio is downloaded through command-line HTTP requests in bounded subsets,
not through a browser or a multi-GB corpus archive. Failed requests are not
replaced with fabricated records. No paid generation is needed for this corpus.

Household recordings, pronunciation auditions, and consumed TEST recordings
are excluded by the existing protected-hash registry. DEV failures may guide
model selection, but only TRAIN scores may change hard-negative weights.
Ordinary speech containing a known target spelling/homophone is excluded.
Speaker, original recording, playlist ancestry, waveform hashes, and local file
paths are checked before feature extraction.

## Reproduction

Use the existing pinned `training/requirements.txt` environment, FFmpeg, and the
clean pinned microWakeWord checkout. Keep all outputs outside the public repo.

1. `training/wake_playback_negatives.py collect --output PRIVATE_RUN` obtains
   and converts the bounded environmental corpus.
2. `collect-speech` reuses authorized Chinese child audio and obtains English
   negatives. `playlists` adds continuous state-retention challenges.
3. `score` runs **whole original recordings**, with continuous frontend and
   model state inside each recording, through the pinned native Micro kernels.
   All three reset replays must agree. The fixed device policy scores the trace.
4. `training/wake_negative_finetune.py` requires the audited original model
   checkpoint, TRAIN/DEV feature cache, protected registry and negative baseline.
   It runs two fixed seeds with bounded epochs. Overlapping training windows
   cover the entire negative recording, including its suffix.
   `--warm-frontend` also slices features computed across complete TRAIN
   recordings, preserving frontend noise/PCAN state. `--head-units 64` is an
   explicitly recorded capacity experiment, not an automatic device upgrade.
5. Compare the full existing wake DEV and complete new negative DEV after
   INT8 conversion. A candidate is development-eligible only if every existing
   positive group retains at least its baseline hits, previous negative/early
   errors do not increase, and new false clips fall by at least 80%.

Each CLI has `--help` for explicit paths. Existing output directories are not
silently reused as a fresh experiment. Failed candidates and their provenance
remain available; a quiet classifier does not count as a solution.

## Interpretation and deployment

Report false **clips** separately from events with a stated 3-second cooldown.
Do not extrapolate a short playback challenge into an eight-hour false-wake
acceptance result. Concatenated recordings overlap their source clips and are
reported as additional challenge time, not independent hours of data.

Batch/stream agreement, native reset consistency, a small model file, and DEV
improvements do not establish actual ESP32 or family acceptance. A selected
candidate still requires frozen, independent checks and recoverable device
testing. The tools never flash or alter the connected board automatically.
Current results are recorded in the dated JSON report in `docs/reports/`.

`wake_negative_recalibrate.py` compares original and source-stratified TRAIN
calibration without gradient updates or threshold changes. It verifies the
complete old DEV on native Micro and then scores the complete new corpus.
Calibration uses no DEV or TEST waveforms.

Original source code uses Apache-2.0. Audio and derived weights retain their
separate restrictions and are not included in public Git commits.

## Result on 2026-11-02

[Actual comparison record](reports/wake-playback-negatives-2026-11-02.json):
1,455 original negatives (751 reused Chinese child recordings, 304 downloaded
English recordings and 400 environmental recordings), plus 12 derived playlists.
Twelve trained candidates and two calibration variants were evaluated. Paid API
cost was $0. No replacement qualified and the device was not modified.

| Model | Existing synthetic positive DEV hits | New negative DEV false clips |
| --- | --- | --- |
| Installed baseline | 86/92 | 6/261 |
| Best preserving all old DEV subgroup/error counts | 86/92 | 4/261 |
| Example stronger rejection tradeoff (warm frontend, seed 43) | 85/92 | 1/261 |

The negative DEV comprises 257 originals and four derived playlists, about
27.5 minutes of challenge time including overlapping source material. This is
reused model-selection DEV, not an independent test or eight-hour acceptance.
Source references: Piczak (2015), ESC-50; Panayotov et al. (2015), LibriSpeech;
[Zhou et al. (2024), ChildMandarin](https://arxiv.org/abs/2409.18584).

## Continued goal: native INT8 selection

`training/wake_int8_iterate.py` now exports and evaluates **every epoch** on
the pinned native Micro backend. It evaluates all 144 original wake DEV cases
and all 261 new negative challenges, with three identical reset replays per
recording. Floating-point accuracy no longer selects the checkpoint.

The formal freeze gate retains at least 90% recall in every original subgroup,
preserves the installed baseline's subgroup hit counts, permits no original
false/early activations, and requires **zero** new negative DEV false clips.
The earlier at-most-one-negative milestone remains an intermediate milestone.
No candidate has been installed by this continuation.

Prepared TRAIN/DEV arrays are reused only after input, protected-registry,
source/preparation semantics, and array hashes match. Original recordings,
the consumed TEST and historical failures remain unchanged. The first full
qualification freezes a candidate before a new independent TEST is opened.

The continuation compares TRAIN-only event weighting and six positive
age/accent/pronunciation cohorts. An optional JSON profile can initialize from
an audited previous checkpoint or the existing phonetic encoder trained only
on public Chinese child TRAIN recordings. The encoder's phone error rate is
not wake-word acceptance. No large model download or household training is
involved. CLI flags are documented by `--help`.

A separate blind content review used
[GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe)
on all 144 **fictional synthetic** original DEV recordings. Actual public child
recordings and household audio were not uploaded. Its 263 billed audio seconds
give an estimated $0.019725 at the documented rate, within the existing $2
corpus budget; this is not an invoice reconciliation. ASR disagreement does
not automatically delete or relabel a recording. Human content clarification
is kept separate from actual household wake acceptance.

### Training-only phrase supervision

The next bounded comparison adds an auxiliary six-class head during training:
ordinary speech, complete wake phrase, T-initial name, Hi alone, name alone,
and missing final syllable. The exported model retains its original **binary
sigmoid probability**; auxiliary layers are not exported. This differs from
deploying a phrase-family softmax, and does not change the device trigger rule.

`training/wake_train_events.py` restores the authenticated preparation source
snapshot and replays every original TRAIN example. Features, labels, weights,
shapes and dtypes must be byte-identical to the original cache before event
metadata can be used. Synthetic competitor events use the measured speech end
with the original augmentation speed and padding; a quiet file tail is not a
phoneme event. Binary labels and original recordings remain unchanged. DEV
waveforms, TEST and household audio are not read by this recovery step.

`--phrase-events` supplies the verified archive; optional profile field
`auxiliary_phrase_weight` is restricted to 0, 0.2 or 0.5. Metadata must match
the original cache and current protected registry. The same complete native
INT8 DEV gate remains mandatory. An implemented auxiliary head is not evidence
of better recall or real-world false-wake performance.

### Conservative TRAIN quarantine (2026-11-03)

Independent blind ASR covered all 407 unique synthetic TRAIN recordings.
The existing conservative content rule agreed on 323; 84 uncertain recordings
are quarantined in a separate comparison, along with all augmented descendants
(762 examples). An ASR disagreement is **not** a confirmed audio error: accent,
unfamiliar-name spelling and ASR failures can exclude genuine targets. No
recording or label is deleted, and the complete DEV remains unchanged.

`--train-admission` requires a complete partition of the original synthetic
TRAIN hashes and excludes uncertain examples from training, calibration and
cohort weighting. Public ordinary negatives remain present. Auxiliary event
metadata follows the same retained original indices. The resulting comparison
has 10,150 TRAIN examples, two temporal profiles and two seeds per profile,
at most 20 epochs each. It has not qualified for deployment.

The preceding four cohort/phonetic profiles all completed without a qualified
candidate. See [the dated running snapshot](reports/wake-clean-train-2026-11-03.json)
for actual results, API cost estimates and software checks. There is still no
new independent TEST, ESP32 timing/concurrency or household acceptance.

### Native freeze handoff and genuinely fresh TEST sources

`training/wake_native_finalize.py` bridges a first qualified native freeze to
the existing `wake-policy.json` tooling. It rechecks complete saved DEV traces,
model/backend hashes, the fixed trigger rule, resolved independent content
questions, and eight retained TRAIN-only reference/Micro fixtures. It emits no
qualified policy when any gate fails. Successful finalization still leaves
TEST, real-child and hardware acceptance false.

The previous consumed synthetic TEST used ballad/verse. New waveforms from
those same identities are not a new independent source family. Metadata-only
`training/wake_test_isolation.py` therefore reserves echo/shimmer, absent from
the declared TRAIN/DEV and consumed TEST manifests; it neither reads audio nor
generates TEST. These identities are in the
[official Realtime voice list](https://developers.openai.com/api/docs/guides/realtime-conversations#voice-options).
The finalized policy binds this reservation by hash. The generator requires
`--fresh-test-isolation` and uses separate IDs, manifest, plan and seal files,
preserving the old test. New synthesis must wait for a qualified freeze.

ASR audits and synthesis share the same $2 ledger. The separate 1,000-request
synthesis limit now excludes explicitly identified ASR audit entries, while
still counting legacy auditions and unknown attempts conservatively. No new
API requests are made by these preparation or validation tools.

### Incomplete-phrase boundary loss

The next bounded comparison uses `--phrase-boundaries`: multiply negative
TRAIN loss weights by four during the final incomplete target prefix
(`completion - 600ms` through `completion - 120ms`) and competitor speech
ending (`completion - 120ms` through `completion + 450ms`). Complete positive
events, ignored steps and padding are not amplified by this operation. Ordinary
public negatives are unchanged. Subsequent cohort balancing and the 3:1 event
mass balance still use TRAIN only.

Timing comes from the byte-verified original TRAIN metadata and the same
conservative recording admission. The comparison keeps the 48-channel,
72-step binary deployment architecture and fixed 3-score/0.90 rule, and tests
training with/without the auxiliary head. Both seeds have at most 20 epochs.
Initialization is chosen from completed prior long-context checkpoints under
a predeclared DEV rule; it is not a release decision. A prior freeze stops the
queued comparison. This operation neither adds device inference work nor
demonstrates successful natural wake detection by itself.

### Adult coverage pilot and appended TRAIN (2026-11-03)

After conservative quarantine, standard-English piku had only six adult TRAIN
originals. `adult-refresh` defines a bounded 200-request TRAIN-only plan using
the four existing adult TRAIN identities. Only **20** were generated, limited
by `--new-attempt-limit 20`; expansion stopped for review. Existing manifests,
DEV and source-isolated TEST voices were preserved.

Blind GPT-Transcribe agreed with the existing content rule on 17/20; the already
downloaded offline Qwen3-ASR agreed on 12/20. Twelve recordings had matching
normalized transcripts from both systems: nine targets and three competitors.
They form a separate consensus-reviewed TRAIN supplement; eight uncertainties
remain quarantined. This is weak-label audio evidence, **not phonetic gold** or
per-record human listening. Adult style uses the previously reviewed unchanged
built-in source identities; four voices do not become twenty new speakers.

`--extra-train-manifest`, `--extra-train-review` and `--base-admitted-manifest`
bind that supplement to its audio hashes, independent review and original
TRAIN-only identities. `training/wake_extra_train.py` appends 126 examples,
bringing effective TRAIN to 10,276, without moving or rebuilding base/DEV
features. Ordinary cached negatives explicitly use feature-domain digests in
their completed metadata, not fabricated original-audio hashes. Backend parity
fixtures map to retained base indices; TEST isolation must include the extra
source manifest too.

The next finite comparison is 48-channel continuation versus a fresh 96-channel
model, both long-context with training-only auxiliary supervision. Each has two
seeds, at most 30 epochs, unchanged trigger and acceptance gates. Static file
size, host arena and eventual ESP32 timing/concurrency remain separate checks.
No board was changed by this pilot. Actual pilot, diagnostic and training
results are in [the dated snapshot](reports/wake-adult-coverage-2026-11-03.json).

For the first completed fresh 96-channel seed, a read-only diagnostic compared
the final native-selected checkpoint with its floating-point weights on the
same 144 original synthetic DEV cases. Per-case valid-target/negative trigger
decisions and aggregate metrics matched. Frame probabilities were not identical
(95th-percentile absolute difference about 0.00391, maximum about 0.267).
One batch/causal-float-stream replay differed by less than 1e-7. This does not
explain away the remaining recall/near-word errors as conversion failures on
that checkpoint. It neither reselects a model using float scores nor opens a
new TEST; it is not the required frozen-candidate TRAIN parity or ESP32 test.

All four adult-coverage profiles subsequently completed without qualification.
A read-only check of the originally declared 3-score/.95 policy also found no
qualified checkpoint; the trigger policy remains unchanged. The next bounded
data step adds at most 80 synthetic adult TRAIN requests, reuses the first
20 audits, and requires the same blind cloud/offline consensus before admission.
Uncertain utterances remain quarantined. This adds utterances from existing
TRAIN voice identities, not new speakers, and does not open TEST or change the
device. The cumulative generation/audit budget remains capped at $2.

That bounded addition completed: the cumulative 100 synthetic TRAIN sources
yielded 52 admitted utterances (39 targets, 13 competitors), retaining all
12 previously admitted sources. The other 48 remain uncertain, not confirmed
bad labels. The first 20 blind audits were reused after verifying identical
audio; only the new 80 incurred new cloud transcription requests. No age or
phonetic gold claim is made from ASR agreement. A two-seed fresh 96-channel
comparison now holds architecture, loss and trigger policy fixed while
expanding admitted TRAIN coverage. Details are in the
[expanded-source snapshot](reports/wake-expanded-adults-2026-11-03.json).

Both expanded-source seeds completed (30 and 24 epochs) without qualification.
The first native-ranked best checkpoint hit 91/92 synthetic targets and had
zero false activations on the 261 new negatives, but still activated on three
original near-word negatives. The other seed also remained below the full
gate. Read-only checks of the originally allowed higher threshold and
five-score policies found no old-DEV gate survivor; no trigger was changed.
The next comparison holds the expanded data, fresh 96-channel architecture,
two seeds and 3-score/.90 policy fixed, enabling only the existing fixed 4x
TRAIN prefix/competitor-ending loss. Earlier narrower-model failures remain.
See the [boundary snapshot](reports/wake-expanded-boundaries-2026-11-03.json).

Fresh TEST has an additional explicit coverage preflight. Native finalization
will carry all six required cohorts into the policy. The current OpenAI
adult-only plan cannot satisfy that contract and is rejected before reading a
key or creating a seal, ledger or audio. A CLI fixture verifies that behavior
without credentials or network requests. Childlike TEST sources and independent
audio/age review still need to be prepared; intended style metadata does not
prove audible child age or pronunciation. An adult-only TEST cannot stand in
for the full acceptance, and synthetic childlike scores cannot replace family
child testing. No new TEST has been generated or consumed.

A same-checkpoint TRAIN-fit diagnostic on R8 seed42 epoch28 covered 10,696
reconstructed admitted TRAIN windows: float inference hit all 2,892 target
windows, rejected all 7,804 negative windows and produced no early target
activations under the fixed decision rule. These are correlated augmented
windows, not independent recordings or TEST scores. Base array hashes matched;
appended data was reconstructed from pinned code/source/seeds with matching
metadata, since the original appended feature bytes were not archived.
On the same 144 reused DEV cases, float/native per-case decisions matched,
including three near-word false activations and one target miss. Probabilities
and exact trigger timing were not identical. This supports investigating
generalization and remaining independent label questions for this checkpoint;
it does not prove that every model has the same cause or justify a release.
No label, model or policy was changed. See the
[TRAIN-fit diagnostic](reports/wake-train-fit-2026-11-03.json).

A TRAIN-only metadata audit also found that all 32 adult originals assigned
to `piko` come from OpenAI. Fifteen use an ASR-inferred variant tag and the
17 newer ones explicitly use agreed ASR spelling as a proxy. None establishes
per-record /ku/ versus /ko/ phonetic annotation. Thus these cohort labels do
not prove actual adult /ko/ coverage; this is an unresolved coverage question,
not a finding that all 32 recordings are wrong. Both vowels remain valid
binary targets, and no label or training inclusion was changed by the audit.

The boundary comparison also ended without qualification (30/22 epochs).
Source revision now takes priority over adding more unchanged-data epochs.
Google's current [TTS guide](https://aistudio.google.com/docs/speech-generation)
places permanent age/accent traits in a stable voice identity rather than a
long turn-style prompt. The existing project was visibly verified as Free
Tier without changing billing. Read-only catalog queries worked; one prompted
child voice request was safety-blocked, was not retried, and a subsequent
metadata lookup found no matching created resource. This single rejection is
not a claim about every possible child voice request.

A separate adult-only source pilot generated four clips on two prebuilt
catalog IDs absent from 121 historical source-metadata manifests. Identifier
separation is not biometric speaker-independence evidence. All clips remain
unadmitted, and actual /ku/ versus /ko/ still needs independent listening;
blind ASR spelling is insufficient. File durations are 1.16–1.56 seconds,
while detected active spans are about 0.58–0.80 seconds, so naturalness and
voiced duration are not inferred from file duration. Existing synthetic DEV
content questions also remain pending. No household audio, new TEST, board
change or new OpenAI request was involved. See the
[source-review record](reports/wake-google-source-review-2026-11-03.json).


The complete original finite policy grid is now accounted for across the three
latest clean fresh-initialization comparisons: 50, 54 and 52 checkpoints,
respectively, with 3/5-score smoothing and thresholds .80/.85/.90/.95. Of the
1,248 policy cells, 49 higher-threshold cells were rejected by the monotonic
positive-hit bound; the others use saved native evidence. None passed the
original 144-case gate. Consequently no additional 261-negative replay was
needed for these newly checked policies. Previous fixed-policy failures remain
unchanged; no trigger setting was installed. See the
[complete grid record](reports/wake-original-grid-2026-11-03.json).

The finalization tool also no longer hardcodes 3-score/.90: it requires agreement
between a permitted original-grid policy, its declared plan, frozen evaluation
and saved DEV evidence, then checks negative peak/activation consistency. Seven
targeted tests passed. This is tooling readiness, not a qualified model. Pending
independent synthetic-content answers and actual /ku/-/ko/ source coverage still
need resolution before a new source admission or formal candidate can proceed.


Human listening has now closed all seven independent synthetic DEV content
questions: E was heard as piko, F/G as piku, all accepted as complete targets.
The four new adult catalog-source auditions were all heard as piko, including
the two requested as piku. Admission records preserve requested spelling and
store the actual listening verdict separately. Four originals are appended to
the 52 earlier audited TRAIN sources, with no new API request. Catalog adult
age remains provider metadata; this reply did not annotate perceived age.

Audition order is not model evaluation order. Original audio hashes bind these
answers to DEV cases. Two childlike vowel tags swap under the human-heard
view; the historical 144-case gate and all its failures stay intact, and the
new comparison must also pass a second full gate with those two corrected tags.
No waveform, binary target label, endpoint or probability trace is changed by
the overlay. Remaining variant metadata is not claimed as phonetic gold.

The next bounded comparison uses two fresh 96-channel seeds, at most 30 epochs
each, with the prior model/loss/optimizer and all negative data retained. It
adds the four reviewed piko TRAIN originals plus the additional grouping gate;
it is not a single-factor causal experiment. No independent TEST or board
operation follows without qualification. See the
[review and comparison record](reports/wake-human-reviewed-piko-2026-11-03.json).


The human-reviewed piko-source comparison completed both seeds at 23 epochs
(46 checkpoints). All 368 original-grid cells were audited against both DEV
grouping gates; none qualified. The native-ranked seed42 checkpoint rejected
all 52 old and 261 new negatives with no early activation, but its historical
childlike piko group remained at 11/13. No new TEST or device operation occurred.
A bounded two-seed comparison now tests AdamW weight decay .01 while retaining
R10's data, model, learning rate, auxiliary loss and both gates. Regularization
is a generalization hypothesis, not proof of the failure's cause. It adds no
inference layer or API request; hardware resource validation remains required.


A metadata-only child-source coverage audit found 245 admitted synthetic
childlike TRAIN originals: 164 targets and 81 competitors, concentrated in two
prompt families. DEV has 24 targets and 14 competitors from one other family.
Declared families do not overlap across TRAIN/DEV, but these are not verified
fixed voice identities or independent real speakers. The four recently added
catalog piko originals add adult coverage only. These counts exclude quarantined
sources and augmentation descendants. This is a coverage limitation, not proof
of the model failure's cause. If the regularization comparison fails, prioritize
stable, provenance-backed childlike voice diversity and matched negatives over
further same-family repeats. No household recordings, TEST audio, scoring or
new API request was used. See the
[child-source coverage audit](reports/wake-child-source-coverage-2026-11-03.json).


There were also 37 childlike target originals in the independent-ASR uncertainty
quarantine. Eight were selected with a fixed seed, four from each TRAIN prompt
family, independently of wake scores. The user accepted all eight complete
Hi+piku/piko utterances after listening to raw-audio review reels. No exact
vowel or age was newly annotated. A versioned human-review proposal can restore
those eight originals and their 96 existing TRAIN feature descendants, leaving
76 unconfirmed originals quarantined. This adds no new speaker identity and
uses no family data. The current regularization comparison is unchanged;
loader integration and a separate new-data comparison must follow its terminal
audit if needed. Three focused admission tests passed. See the
[human TRAIN review record](reports/wake-child-TRAIN-human-review-2026-11-03.json).
