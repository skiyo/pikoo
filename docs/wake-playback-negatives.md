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


The AdamW comparison is terminal: 41 checkpoints and all 328 policy cells
produced zero qualified survivors. The human-restoration loader is now wired
and rejects unreviewed promotions, label changes and protected review scopes;
23 affected loader/training tests passed. A separate two-seed comparison uses
the R10 Adam control and restores only the eight confirmed targets/96 cached
feature descendants (10,840 TRAIN windows total). All 76 unconfirmed originals
remain quarantined; both DEV grouping gates stay mandatory. No new waveform,
voice identity, API request, TEST or board operation is introduced.


The restored-child comparison completed 24/27 epochs (51 checkpoints) and froze
the first fully native-qualified candidate at seed43 epoch27, retaining the
3-score/.90 policy. Historical and human-heard DEV views both hit 90/92 targets;
the six cohorts hit 28/28, 3/3, 26/27, 10/10, 11/11 and 12/13. All 52 old and
261 new negatives were rejected, with zero measured early activations and
about 54.9ms p95 event delay on these synthetic cases. These are reused DEV
results, not independent TEST or real-child accuracy.

The frozen 98,088-byte model uses 37,808 bytes of host Micro arena. Eight
TRAIN-only reference/Micro fixtures were byte-exact across three resets;
one post-freeze 405-case DEV replay reproduced all saved target traces and
negative peaks/decisions exactly. No board timing or concurrency is accepted.
See the [frozen candidate record](reports/wake-native-candidate-2026-11-03.json).

Independent TEST remains unscored. A separate, bounded 12-request source pilot
uses untouched echo/shimmer identities after the qualified freeze. It plans
all six intended cohorts, leaves actual age/vowels unreviewed, and cannot enter
TRAIN or benchmark scoring. Human listening must establish source quality;
ordinary adult-only sealed generation still fails the full-scope preflight.
The existing shared $2 ledger remains enforced (about $0.58915 accounted or
reserved after the pilot). The [official Realtime reference](https://developers.openai.com/api/reference/resources/realtime/client-events)
lists these voices; API voice names do not establish a childlike listening
verdict. Firmware, independent TEST, family and eight-hour acceptance remain.


Human listening rejected the pilot's childlike-age assumption: all twelve
samples sounded adult, and TS3 contained only Hi without the name. TS3 stays
quarantined; no pilot clip enters TRAIN or benchmark scores. The candidate
remains frozen, with full TEST coverage still incomplete. A mixed-source TEST
route is proposed using newly collected local family speech only after this
freeze and held-out standard-adult synthesis. Consent/readiness, a verified
bounded capture tool and all-six-cohort content coverage are required first;
no family recording has occurred. The same family testers may have prior tests,
so new recordings must not be misrepresented as previously unseen people.
No model tuning or unqualified device installation follows this source failure.

`tools/wake_test_capture.py` now extracts **one existing, opt-in** four-second
`wake capture` log into a new private directory outside the repository. It does
not open USB or record anything. It requires idle diagnostics before/after,
exact packet ordering and 64,000 samples, stable upload/reconnect/error counters,
and no observed reset. Seven integrity/privacy tests cover truncated/duplicate
packets, corrupt payloads, missing diagnostics, upload/state changes and crashes.
This proves bounded transport integrity only: consent, post-freeze collection
time and human content labels must be recorded separately before TEST admission.
The mixed-source capture/benchmark workflow is not yet ready for a family run.


The follow-up TEST tooling is implemented but has not been exercised with the
connected board or real household audio:

- `tools/wake_test_session.py` records one explicitly requested four-second
  clip through an existing, project-owned USB monitor. It refuses active calls,
  checks private log/status ownership, arms local-only TEST mode while muted,
  renews the gate after human readiness, and uses a visual start cue. It never
  sends `end`, changes volume, flashes or selects a model. Exit/interrupt first
  mutes the microphone, then disables TEST mode; if muting cannot be confirmed,
  it preserves the isolation gate and reports failure. It leaves the microphone
  muted; normal standby must be restored explicitly after the test session.
- `training/wake_mixed_test.py` predeclares 150 slots: 20 targets for each of
  six actual-content cohorts and five negatives in each of six categories.
  This includes 80 fresh family TEST recordings and 70 held-out synthetic clips;
  it does not claim the same family people are previously unseen speakers.
  Child cases are actual, user-declared children, reported separately from
  synthetic childlike DEV. A protocol file does not authorize recording.
- `training/wake_mixed_test_score.py` checks complete source/content labels,
  waveform hashes, post-declaration dates, raw family transport proofs and the
  exact native backend before scoring. It uses full waveforms without training
  crops, random lead-in or augmentation. A consumption marker is created before
  inference; retries cannot claim a fresh TEST. No threshold search is available.
  Formal hardware, two-session and eight-hour acceptance flags stay false.
- The old no-recording trial helper no longer sends `end` while settling;
  mute/unmute already stop the transient session and preserve its stored topic.

The private prior-recording snapshot unions eight metadata sources and protects
1,885 unique hashes, including TRAIN/DEV, old TEST and source auditions. The real
empty bundle was correctly refused at preflight (0/150 rows), without inference
or a consumption marker. Thirty-two relevant tooling/isolation tests passed on
generated fixtures. No new synthesis request, family recording, device change or
model/policy change occurred. The adult-synthesis sub-bundle generation and human
content-label collection still need integration; this is not an end-to-end TEST
pass. Family readiness remains deferred at the user's request.


The synthetic sub-bundle is now integrated with the full protocol. The separate
`wake_mixed_test_source.py` preflight validates the unchanged150-slot plan, native
freeze, untouched-speaker reservation and prior-recording snapshot. The Node
`wake_mixed_test_generate.cjs` wrapper emits only the70 predeclared adult sources,
uses the protected historical cumulative ledger and generation lock, refuses a
new budget or public/symlinked output, and never retries failed attempts. Requests
are at least five seconds apart. No family audio is sent to a provider.

All70 API generations completed (40 intended targets and30 negatives), adding
about$0.060292 to the same ledger: about$0.64944 accounted/reserved out of$2.
These are completed API outputs, not70 content-qualified examples. Existing local
Qwen3-ASR inspected all70 offline; four target sources were flagged for possible
missing names or extra words and await human CONTENT review. All70 still need
human labels; the other66 were not automatically admitted. ASR spelling/timing is
not vowel/age gold, and no failed source was cropped, repaired or regenerated.
The frozen wake model has not scored any of these recordings.

`wake_mixed_test_labels.py` provides explicit assemble/label/seal operations.
Assembly preserves all150 slots, including80 absent family recordings. Each label
records actual complete Hi+piku/piko or a specific negative, observed age/accent,
quality, extra-word/repetition status, waveform hash and pre-score endpoint.
Requested prompts never fill these observations. Draft revisions are logged;
sealing requires all actual cohorts and labels and refuses partial evidence.
A real70/150 partial bundle was refused before inference or TEST consumption.
Family capture now derives its pseudonymous speaker/prompt from the protocol's
case ID and binds both ID and protocol hash into the raw transport evidence.

Fifty-six relevant software checks passed (including the stdlib-only Python
preflight/label path). No household recording, USB access, firmware write,
threshold change or training took place. Household availability remains deferred;
QC1–4 is a new synthetic-content question, separate from the old TS1–12 pack.
The [official model pricing](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini)
was rechecked without changing the generator model or the$2 cap. Independent TEST,
ESP32 resource/concurrency, family two-session and eight-hour gates remain open.


Human QC1–4 feedback rejected every complete target: only Hi or other phrases
were heard. All four original attempts remain intact and are recorded as invalid
content in the TEST-only draft, with exact words, age and accent left unknown.
They are not four qualified positive examples. The other66 sources remain
unreviewed; the original150-slot protocol is not ready for scoring as-is. All
four provider responses completed below512 output tokens (118/145/139/150), so
raising the generation token limit is not justified by this evidence. A separate
four-request source-quality pilot is predeclared but NOT run; any future
benchmark source repair needs an explicit pre-score provenance amendment that
retains the failed attempts and every actual coverage/quality threshold. No
family recording or wake-model tuning follows this feedback.

A separate private full ESP32-S3 build completed using IDF5.5.5 and the frozen
98,088-byte model. Generated3/.90 policy was compiled; the exact model occurs once
in both application image and ELF. All12 required operator names appear in the
firmware resolver. The application is2,655,248 bytes, leaving3,636,208 bytes in its
6MiB partition. Every SDK configuration value and the SR resource image match
the saved0.2.1-live16 baseline. Original build, dependency lock, weights and policy
hashes were preserved. All diagnostic/veto/trial/volume-migration flags were off.
Four build-request safety tests passed. The helper now supports a private
`PIKOO_BUILD_DIR` and optional `PIKOO_FIRMWARE_VERSION` and always disables cached
volume migration in an ordinary build; no USB/flash command was executed.
Linker RAM statistics are NOT runtime free-heap measurements. Tensor allocation,
ESP-NN/device parity, timing, audio/display/network concurrency and all real-world
acceptance remain unmeasured for this candidate. The private image is not release
eligible and is not installed. See [firmware build options](firmware.md).


The bounded source-quality pilot is complete: four new source auditions used
explicit per-response literal reading instructions, retaining512 output tokens
and the same model/voices. This is supported by the [official client-event
schema](https://developers.openai.com/api/reference/resources/realtime/client-events);
it is not a guarantee of correct speech. The old request path is unchanged, and
strict-mode caches must match request policy, text, voice, style, model and raw
hash. Eighteen related generator/preflight checks passed.

The new auditions are1.15/1.45/1.15/1.15 seconds. Existing local ASR read complete
Hi+name text in all four, but this is not phonetic or age gold. Estimated added
usage is$0.0026188; the shared ledger is about$0.65206/$2. Original protocol,
benchmark manifest, four invalid recordings, weights and frozen policy hashes
remain unchanged. QP1–4 (distinct from rejectedQC1–4) await human content/vowel
and adult/accent review. No wake inference, family recording, device access or
benchmark replacement occurred.

These four recipe auditions stay excluded from TRAIN and direct benchmark use.
A disabled amendment draft preserves150 scored slots, all six20-target cohort
minima and30 negatives. Only after human recipe review may a separately declared
four-request batch create NEW benchmark source attempts, with every failed
original retained and a separate amended manifest. No consumed model TEST may be
recycled through this route; no thresholds or family data are changed.


### Formal trial preparation (2026-11-03)

The future [family trial workflow](wake-family-trials.md) now uses natural Hi +
piku/piko instead of the legacy Chinese cue. Formal mode requires the full
matching six-cohort TEST and its completed consumption proof before accessing
the existing project monitor. It checks the running version, model and policy
hashes, uses a silent visual cue, and requires post-run human confirmation before
18/20 machine hits can count. The four-person/two-session summary rejects missing,
duplicate or overlapping runs. Interrupt cleanup mutes before removing isolation.
All31 related fixture checks pass; the actual candidate correctly refuses formal
entry while independent TEST is missing. No human or USB trial was performed.

The identity-diagnostic extension compiles as private `0.2.2-dev-r12id`,
2,655,456 bytes, with the same frozen model, 3/.90 policy and SDK settings.
Model/policy hashes and version are present in the image; previous artifacts
are archived. This is compilation evidence, not a flashed or accepted device.
QC1–4 remain rejected; QP1–4 are separate source auditions awaiting review.
No additional generation charge or family recording was introduced.

### Content-only source repair tooling (2026-11-03)

`training/wake_mixed_test_repair.py` now implements the prospective repair route
for the four human-rejected QC sources. It requires actual human QP1–4 recipe
observations: full greeting/name, heard vowel, adult age impression, standard
accent, and no repetition/extra words. Prompt text and local ASR cannot fill
these fields. No real repair plan is active while those observations are missing.

The declaration binds the unchanged full protocol, frozen model/policy, original
70-source manifest, rejection, recipe audition manifest and human recipe review.
It fixes four **new** requests, one attempt each, with the already checked
literal-response policy. Generation reuses the historical $2 ledger/lock and
1000-attempt limit, at most one request per five seconds, with no automatic retry.
Output is separate (`source-repair1/`); original failed audio remains unchanged.
Audition/raw-source reuse is rejected by both WAV and PCM hashes.

Developer sequence, only after the pending recipe observations are available:

1. Run `wake_mixed_test_repair.py --help`; create the separate immutable
   `source-repair1-plan.json` using the actual rejection, audition manifest and
   human recipe review. An absent/partial review refuses before writing a plan.
2. Pass `--source-repair PATH` to `wake_mixed_test_generate.cjs`, with the existing
   full-protocol, protected-source, backend, isolation and cumulative-budget
   arguments. Use the bundle's `source-repair1` output directory, never `synthetic`.
3. Pass that same plan to `wake_mixed_test_labels.py --source-repair PATH` for
   assemble/label/seal. The amended manifest and review use separate
   `.source-repair1` filenames. New sources still need their own content labels;
   approval of a recipe does not approve future generated words automatically.
4. Pass the plan and amended manifest/review explicitly to
   `wake_mixed_test_score.py --source-repair PATH`. All 150 cases, six actual
   20-target cohorts and 30 negatives remain mandatory. Other cases cannot be
   rewritten through this amendment. The report discloses the four retained
   invalid attempts and four additional requests separately from model scores.

A sealed review cannot authorize more generation. A consumed KWS TEST cannot
be amended or rerun as fresh. The 24 affected Python and 3 Node checks use only
generated fixture PCM/metadata, including one full 150-case sealed preflight.
The actual bundle refused declaration because QP human review is still absent;
model, original manifests, protocol and budget hashes were preserved. No paid
request, independent-TEST inference, family recording or device operation occurred.


Human QP1–4 follow-up confirms all four complete target phrases and adult, ordinary
English accents. Exact ku/ko labels were not supplied; they remain unset rather
than copied from synthesis prompts or ASR. The partial review correctly refuses
source-repair declaration. No new API request, scoring, family recording or board
operation was performed. Original QC failures remain unchanged.


Human QP vowel review is complete: **piko, piku, piku, piku**. The approved
recipe unlocked the immutable four-request source plan. Four distinct new
benchmark originals were generated once each; the auditions were not reused.
The first declaration exposed Python3.9's lack of support for JavaScript UTC
`Z` timestamps; normalization now preserves the exact UTC instant, with naive
timestamps still rejected. All25 affected Python checks pass, and the actual
private declaration/assembly now succeed. Preflight failures made no API calls.

New RT1–4 files last1.60/1.20/4.05/1.15s. Blind local ASR found three full
greetings; RT3 returned only Hi, with380ms measured activity and3650ms quiet
tail. It remains content-suspect pending human listening, not an automatically
relabelled negative or an accepted positive. Originals and quiet tails are
retained; the listening reel concatenates whole raw files. No wake scores exist.
The amended manifest still has150 slots,70 recorded sources and80 missing
family captures. The four old rejected sources, original source/slot manifests,
protocol, weights and fixed3/.90 policy are unchanged. Incremental generation
is estimated at$0.0039692, cumulative accounted/reserved$0.6560276 of$2; neither
number is a reconciled provider bill. Family and device acceptance remain open.


Human RT review confirms RT3 is Hi only; RT1/2/4 are otherwise normal. The three
complete targets still lack exact human ku/ko annotations. The failed original
remains intact and does not become a valid negative in the fixed target slot.

A prospective **single** follow-up is now supported: `wake_mixed_test_repair.py`
accepts `--previous-repair` and `--previous-human-review` to declare
`source-repair2-plan.json`. It requires all four original content observations,
explicit rejection of RT3, and acceptance of the other three. It allows one new
TEST-074 request with the already approved model/voice/text/style; no third
repair round or changed good source is allowed. Generation output, manifests
and sealed reviews remain separate under `source-repair2`. The original four
QC failures and first-repair RT3 remain bound through immutable evidence hashes.
All150 slots/six20-target cohorts/30 negatives remain required. Content approval
does not invent missing vowel labels. All28 affected Python and3 Node checks
pass, including a full150-case sealed follow-up fixture without model inference.

The actual one-request follow-up completed once. RX1 is4.05s raw, with720ms
measured activity and3310ms quiet tail; blind offline ASR returned Hi, Piku.
This is content evidence pending human review, not wake recall or human phoneme
gold. Raw audio is untouched; the reel is RT1→RT2→RX1→RT4, preserving the three
previously accepted sources. The amended full-scope manifest still has70
recorded sources and80 missing family captures; no KWS TEST was consumed.
Incremental generation is estimated at$0.0017496, cumulative accounted/reserved
$0.6577772 of$2. No family recording, device access or frozen-policy change occurred.


The user accepted all four active targets in the RT1→RT2→RX1→RT4 reel. These
are recorded as complete positive TEST targets, not TRAIN examples. The answer
did not assign individual ku/ko labels; those fields remain unset, and the same
clips will not be repeatedly queried. `hi-piku-or-piko` now represents this
truthfully in an unsealed draft, with positive label1 and explicit pending vowel
and endpoint annotations. It does not fabricate six-cohort coverage: the full
TEST validator still refuses missing subtypes or endpoints. All30 affected
Python checks pass. No new API call, model score, family capture or flash occurred.

Current material readiness is **150 slots,70 raw sources,4 human-accepted
targets,66 recorded sources without human content labels,80 missing family
captures**. This is not a ready or passed independent TEST. The existing frozen
DEV-qualified candidate has not been newly trained or installed by this review.
