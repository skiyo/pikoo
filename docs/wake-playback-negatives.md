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


### R12 device engineering check (2026-11-03)

The user connected the board and authorized device testing. The98,088-byte
frozen model passed a synthetic ESP32-S3 precheck:600 iterations,10.390ms p99,
10.437ms maximum,48,796-byte arena, no deadlines missed or inference errors;
all16 feature/probability probe frames matched the pinned host backend. Display
rate was14.3fps under this synthetic workload, below the20fps target. This does
not establish full audio/network/display concurrency or wake acceptance.

An exact installed16MiB backup was verified against device digests. The temporary
silent benchmark was followed by a verified original16MiB restoration. A subsequent
user-authorized engineering app-only install runs the same frozen model/policy
as `0.2.2-dev-r12id`, with0dB and protected NVS retained. It is a trial, not a
formally qualified release. The adult short test produced two human-confirmed
hit windows; attempt3 was invalidated by a host-script error. One supplementary
window had no hit despite microphone activity and no I/O/inference errors. The
tool now waits for Enter before each attempt, gives explicit green-cue guidance,
records failures, and verifies bounded cleanup even after interruption;33 tool
checks pass. No family audio was saved and none of these results selects a model.

Self-paced use required several calls; the user reports slower speech works
better than fast speech. Existing cache provenance verifies0.9–1.1 speed
resampling for augmented synthetic TRAIN views; it couples pitch to speed and
does not establish fast connected-speech coverage. Model, thresholds and
server/volume/memory settings were not tuned from family feedback. Formal new
TEST, family two-session, eight-hour background and30-minute voice gates remain
open. See the [device record](reports/wake-r12-device-2026-11-03.json).

A fixed-policy TRAIN-only tempo diagnostic used nine previously admitted originals (six targets and three near negatives), each at original speed and 0.75×/1.5× with coupled resampling or pitch-preserving `atempo` (45 cases). At 1.5×, targets hit 5/6 with pitch preserved and 0/6 with coupled pitch; original speed hit 6/6. At 0.75×, coupled resampling also caused one near-negative hit. This small, already-seen TRAIN probe identifies sensitivity, not generalization or a qualified policy. No family/DEV/TEST audio, API requests, training, threshold changes or device changes were used for the probe. Natural fast connected speech remains unverified.

### Pitch-preserving faster speech comparison (2026-11-03)

`training/wake_tempo.py` adds 1.15×, 1.3× and 1.5× `ffmpeg atempo` derivatives of **already admitted TRAIN originals**, including incomplete/near-name negatives. The new derivatives retain pitch; no pitch shift, acoustic augmentation, API generation or household input is applied to them. Historical TRAIN remains intact, including its older coupled-resampling descendants. This is an addition, not a claim that all old training is pitch-preserving.

The finite comparison starts from the frozen R12 checkpoint, keeps the architecture and three-score/0.90 decision unchanged, and allows two seeds with at most 12 epochs each. There are 1,161 new TRAIN examples from 387 originals (12,001 total). All 144 original synthetic DEV sources also receive three deterministic tempo variants (432 derived DEV cases). These remain reused DEV; they are never labeled independent TEST or new speakers. Each speed must independently meet the existing recall, zero-false/early-wake and latency gates, while the complete original DEV and 261 ordinary negative cases also pass. Original group recall must preserve the current R12 floor rather than the weaker historical baseline.

The opt-in `wake_int8_iterate.py` interface uses `--tempo-config`, optional verified `--reuse-tempo`, and `--preserve-dev-cases` / `--preserve-dev-evaluation`. The private config pins the `ffmpeg` binary hash, exact speed factors and donor-model hash. Inputs still require complete source admission and protection manifests; no public weights or recordings are bundled. Finalization recomputes all 432 saved native tempo traces and verifies the donor floor before emitting a candidate policy. See [the dated report](reports/wake-tempo-2026-11-03.json) for the recorded run state; an in-progress comparison is not a delivered model.

A read-only audit of the fixed chronological seed-42 epoch-9 checkpoint covered **all 1,161 new TRAIN derivatives**. At each speed, all 253 targets hit and all 134 negatives were rejected, with zero early triggers. Reused DEV still failed. This separates ability to memorize the fast TRAIN examples from cross-source generalization; it is not independent evaluation and does not justify flashing. Both seeds subsequently completed all 12 epochs without qualification (24 native INT8 checkpoint evaluations); no candidate was frozen or installed.

### Continuous tempo and acoustic variation (2026-11-03)

R14 changes only the appended TRAIN augmentation: six seeded pitch-preserving views per source, two drawn from each speed band `(1.0, 1.15)`, `(1.15, 1.3)` and `(1.3, 1.5)`. Existing synthetic microphone bandlimit, reverberation, gain and noise are applied to these views; no pitch transformation is added. The original TRAIN prefix stays intact. The config opts in with `TRAIN_continuous_variants_per_source: 6` and `TRAIN_acoustic_augmentation: true`. These do not claim new voices or real children.

The donor, architecture, optimizer/loss, learning rate, seeds and 12-epoch limit per seed remain as in R13. Before training, `DEV_reference_preparation` and its pinned provenance hash require every derived DEV feature, label and clock to match R13, apart from an inert metadata flag. The fixed-speed and original/ordinary DEV gates remain mandatory. This tests a finite augmentation bundle; it does not isolate the effect of each acoustic component. See [the R14 report](reports/wake-tempo-acoustic-2026-11-03.json); initial expected counts are explicitly marked until preparation completes.

Both R14 seeds completed 12 epochs without qualification. Together R13/R14 retain all 48 failed native checkpoint evaluations; no new device model was installed.

### Frozen public-speech encoder and unsupported-prefix guard (2026-11-03)

R15 reuses the existing 96-channel CTC encoder trained from authorized ChildMandarin and Mandarin MInDS14 TRAIN speech. Its historical training used 19,673 clips and 2,312 internal speaker-held-out development clips; the historical phone error rate was 56.3%, **not a wake-word or real-child acceptance result**. All 21 encoder layers are frozen. The wake/context head is new; the old Chinese phrase classifier is not imported. The exact 13,162-example R14 wake data, original/tempo DEV, and fixed three-score/0.90 policy remain in use. Two seeds have a 30-epoch maximum each. The first export is 98,712 bytes with a 37,808-byte host arena; hardware timing and concurrent playback remain unverified. See [the R15 report](reports/wake-phone-encoder-2026-11-03.json).

Coverage auditing found no explicit `nihao + Pikoo` negative in the current manifest. A separate metadata/content audit of old synthetic originals preserved their historical splits and excluded protected recordings. Two ASR screens identified 38 TRAIN and four DEV candidates; two ambiguous originals stay quarantined. Traditional/simplified Hanzi spellings are normalized using the existing name grammar. These screens are not human/phoneme truth. The 38 TRAIN candidates have **not** been appended, and old labels/audio were not overwritten.

The four old DEV originals form a mandatory supplemental reused-DEV guard at original speed plus 1.15×/1.3×/1.5× (16 cases). Their negative role follows the current Hi-only target; they are not fresh TEST. R12 rejects all 16, but that report cannot qualify a new model. `required_secondary_negative_dev` pins the features, source manifest, protocol, content screens and protection hashes. Finalization replays the actual candidate with native Micro and refuses any false wake, source/split conflict or missing case; source isolation must include this manifest before any new TEST. A primary numerical freeze alone does not establish full DEV completion. The encoder's whole source manifest and all source auditions are excluded from future fresh TEST; internal phone validation cannot be called unseen wake evaluation. Restricted recordings, weights and firmware stay private.

### Train-fit diagnosis and encoder fine-tuning (2026-11-04)

A fixed chronological R15 epoch-20 diagnostic replayed all 2,322 seen fast TRAIN examples. Of 804 negatives, floating inference falsely triggered 206, native INT8 triggered 225, and a separate shuffled training-mode check triggered 168. Eight balanced TRAIN reference/Micro fixtures were byte-exact across three resets each. This rules out a Micro/reference mismatch as the sole cause; training-mode normalization also does not solve rejection. These are TRAIN diagnostics, **not independent, frozen-candidate or family acceptance**; the original checkpoint was unchanged.

R15's first seed completed 28 validated epochs. Its second seed was manually stopped after five validated epochs to change direction; unscored partial checkpoints remain private. The full planned 60 epochs were **not** completed and no candidate qualified. R16 changes only `encoder_frozen` from true to false (and the run name), leaving pretrained BatchNorm frozen. The same original encoder, new-head seeds, 13,162 examples, optimizer/loss/rate, policy, original/tempo DEV and required secondary guard remain. The encoder now has 17 trainable layers out of 21; no API requests, new downloads, board changes or private-audio use accompany this change. See [the dated R16 report](reports/wake-phone-finetune-2026-11-04.json). A completed training arm or numerical export alone does not complete the goal.

### Correcting acoustic TRAIN event timing (2026-11-04)

The continuous acoustic wrapper introduced in R14 estimated speech completion **after** adding reverberation, gain and noise. Noise could therefore shift the target event despite unchanged spoken content. A model-independent audit of all 2,322 appended TRAIN examples found 126 of 1,518 positive examples shifted more than 120ms relative to their clean stretched waveform; positive p95 was 140ms and the maximum was 255ms. A separate known-end signal fixture reproduced a 260ms shift from noise alone. These are timing diagnostics, not model acceptance.

R14, R15 and R16 retain their actual failed/partial results. Their unchanged DEV remains valid, but the corrupted TRAIN clocks prevent attributing their differences solely to model architecture. R16 was stopped with 22 and 12 validated epochs for its two seeds, not the full planned 60. The earlier clean-tempo R13 and the installed R12 model did not use this wrapper.

R17 fixes only this timing path: determine crop and completion from the clean pitch-preserving stretched synthetic TRAIN waveform, then extract features from its acoustically augmented counterpart. Binary labels, original audio and the tempo DSP are unchanged. `TRAIN_timing_reference: clean-stretched-before-acoustic-v2` is required; old acoustic caches are rejected rather than silently reused. Clean-reference timing cannot be applied to DEV, real-child or family recordings. The strict base-cache dependency check also required rebuilding the ordinary-negative preparation under the changed source; no provenance check was bypassed. Original DEV arrays and all 432 fixed-speed DEV feature/label/clock records must still match their prior references exactly.

R17 keeps the R16 model initialization, frozen BatchNorm, optimizer, seeds, 30-epoch limit, fixed three-score/0.90 policy, R12 recall floors and mandatory 16-case secondary guard. The existing 144-file blind transcription audit was reconciled without additional API requests or automatic relabeling. No family/TEST audio, downloads, board/server/volume changes or new paid requests are involved. A corrected training pipeline is not a qualified wake model; independent TEST and all hardware/family/background gates remain required. See [the clock-fix report](reports/wake-clean-clock-2026-11-04.json).

R17's first seed ended normally under the predeclared early-stop rule after 19 evaluated epochs, without qualification; the second seed continued. A read-only diagnostic used that terminal checkpoint, not a checkpoint chosen by TRAIN diagnostic results. Across all 2,322 appended seen TRAIN views, native Micro hit 1,513/1,518 targets, rejected all 804 negatives, and had no early wakes. Each group in each speed band had at least 97.6% recall. Eight TRAIN reference/Micro fixtures were byte-exact across three resets. This establishes fit to the added training views, **not** independent or device acceptance. Complete DEV still failed.

A separate read-only trace reconciliation covered all 24 completed R13 checkpoints and the first R17 seed's 19 completed checkpoints. It recomputed each full original/tempo DEV report from saved probabilities and verified model hashes. Persistent R17 misses concentrated on three original childlike piko sources from one held-out prompt family; false activations mostly involved Tikoo. Counts across checkpoints reuse the same DEV and are not independent trials or an equal-budget causal comparison. The two childlike TRAIN prompt families have **girl-like and boy-like source audition labels**; a profile name containing “boy” does not establish actual gender. Prompt families do not establish fixed speaker identities either. No existing labels or admission rules changed. Two new local fictional source auditions were generated with the existing TTS model for possible future TRAIN expansion; age/content review is pending, raw auditions remain protected and unadmitted, and no wake-model score selected them. They are not new TEST sources or verified children.

Both R17 seeds subsequently completed normally under configured early stopping: 19 and 22 evaluated epochs, 41 total, with no qualified checkpoint. This completed the configured comparison, not all 60 maximum epochs, and did not open TEST or change a device.

### Original-donor control with corrected clocks (2026-11-04)

R18 re-runs the original R14 donor route using the corrected R17 cache. It keeps R14's R12 initialization, 96-channel/64-unit/72-step model without BatchNorm, learning rate 0.0001, auxiliary weight 0.2, two seeds and 12-epoch limit per seed. The training change against R14 is clean-reference event/crop timing before acoustics. It is **not** a one-variable comparison against the different R17 phone-encoder route. The current mandatory 16-case secondary guard is also required for acceptance. Cache verification retains the same 13,162 TRAIN examples, 432 tempo DEV cases, original R12 group floors and three-score/0.90 rule; no new audition has been admitted. R18 started only after R17's terminal return code and process exit were verified. No API requests, downloads, TEST, family audio, board, server or volume changes are involved. See [the R18 record](reports/wake-donor-clean-clock-2026-11-04.json); starting a corrected control is not acceptance.

A read-only diagnostic of R18's first seven completed checkpoints compared saved full DEV traces with the pinned R12 donor. Some previously rejected Tikoo and missing-final-syllable examples became false activations after fine-tuning. These are repeated development observations, not new TEST or proof that a particular layer caused the regression.

The conditional R19 control adds `freeze_checkpoint_encoder: true` **only for checkpoint initialization**. It freezes the already wake-trained layers before `ordered_context.input`, leaving ordered time aggregation, the wake head and the training-only auxiliary classifier trainable. It differs from R15's frozen public phonetic encoder. Defaults, data, labels, loss/rate, seeds, model dimensions and decision gates remain unchanged. An initial encoder-weight fingerprint must match before every epoch export; a mismatch stops the run. Three new checks include a real gradient update through the auxiliary-loss training graph, confirming unchanged encoder weights, an updated wake head and detection of deliberate weight corruption; nine existing training-control checks also pass. A minimal Python without training dependencies skips the three optional checks. This verifies the control mechanism, **not** the effectiveness of a frozen encoder or its quantized/device behavior. R19 was predeclared to start only after R18 actually terminated without qualification, and raw source auditions stay excluded. See [the control record](reports/wake-donor-frozen-encoder-2026-11-04.json).

R18 subsequently completed both 12-epoch seeds (24 native evaluations) without qualification. The retention audit now covers all 24 checkpoints; the original seven-checkpoint snapshot is retained. After verifying terminal code 0, no frozen/qualified checkpoint and actual process exit, R19 started. Runtime initialization records 13 frozen encoder layers, 10 encoder weight arrays and six remaining trainable wake weight arrays. An independent read of the serialized first-epoch **96-channel** checkpoint confirmed all 10 encoder arrays match the original donor exactly while both final wake-classifier arrays changed. The diagnostic initially looked for post-export metadata in the checkpoint evaluation; those fields live in completed epoch history. It was corrected to bind history to the same model hash and compare the actual H5 weights, with no training restart or mutation. The first export is 98,064 bytes with a 37,808-byte host arena, and still fails complete DEV. Hardware timing/concurrency and independent/family tests remain unaccepted.

### Partial encoder adaptation after TRAIN-fit diagnosis (2026-11-04)

R19 subsequently completed both 12-epoch seeds without qualification. A controlled read-only comparison used seed42's configured terminal epoch12 in each of R18/R19, verified identical cached TRAIN feature/metadata hashes, and replayed all 2,322 appended views. R18 hit all 1,518 targets, rejected all 804 negatives and had no early triggers in both float/native inference. R19 hit 1,507 targets with 51 negative false activations and one early trigger in native inference; float had 1,508 hits, 48 false activations and one early trigger. Eight reference/Micro fixtures per model were byte-exact. This is a same-budget **seen TRAIN** diagnostic, not an independent test, a multiple-seed causal estimate or proof that a frozen encoder can never fit. It shows that complete freezing was restrictive under this budget; R18's complete TRAIN fit still did not qualify DEV.

The conditional R20 control changes only `checkpoint_encoder_freeze_before: context_2` relative to R19. Earlier layers remain frozen, while the final encoder block and ordered/wake heads can adapt. The default boundary remains `ordered_context`; only these two boundaries are supported, with an explicit checkpoint freeze required. Both real-gradient boundary checks verify unchanged frozen-prefix arrays, continued head learning and whether the final block actually updates; corruption guards remain mandatory. Four control checks and nine existing training checks pass, while a minimal Python skips the four optional runtime checks. No new data, source admission, model dimensions, learning rate, loss, seeds, epoch budget, threshold or acceptance gate changes. R20 starts only after R19's real terminal result and process exit are verified. See [the partial-adaptation record](reports/wake-partial-encoder-2026-11-04.json).

R20 has now started after the actual R19 terminal/exit checks. A preflight first used the system Python, which lacked TensorFlow; it was corrected to the existing pinned training environment, without installation, download or restarting any training. Runtime records a frozen prefix of 10 Keras layers (including parameterless layers), seven prefix weight arrays and nine remaining trainable wake arrays. An independent read of the actual first-epoch 96-channel H5 checkpoint confirms those seven arrays exactly match R12 while the final pointwise block and wake classifier arrays changed. First export remains 98,064 bytes with a 37,808-byte host arena; complete DEV is still unqualified. This verifies the intended adaptation boundary, not device performance or independent/family acceptance.

### Gentler TRAIN tempo after content diagnostics (2026-11-04)

R20 completed all 24 configured native checkpoint evaluations without qualification; every frozen-prefix guard passed. No candidate was frozen or installed.

A model-independent probe used 432 artificial carrier/noise-burst signals. At 1.5×, four of 144 cases retained less than 10% of rate-normalized brief-transient energy; none fell below 50% at 1.15× or 1.3×. These artificial signals do **not** establish missing speech phonemes or incorrect corpus labels. A separate duration/group-selected audit of 12 already admitted TRAIN originals compared raw, guarded and stretched audio. Raw/guarded local transcription rules matched all 12, while 1.5× produced five spelling/decoder disagreements. Eighteen independent cloud transcription requests, including a six-case 1.3× comparison, still showed proper-name/script ambiguity. No source was removed or relabeled. A two-pass DSP probe improved artificial transients but did not establish speech quality and was **not** adopted.

R21 is predeclared against R18's fully trainable R12 donor route, rather than the different immediate R20 partial-freeze route. Only appended TRAIN speed bands change: two seeded views each in `(1,1.1)`, `(1.1,1.2)` and `(1.2,1.3)`. The same 2,322 appended views and original prefix are retained, with no new sources or labels. All 432 fixed-speed DEV feature/label/clock records must still match R13 exactly, **including 1.5×**; original R12 floors, 261 ordinary negatives and the 16-case secondary negative guard remain mandatory. Two seeds, 12 epochs each, model/init/loss/rate and three-score/0.90 policy are unchanged from R18. Eleven tempo checks pass, and all 2,322 legacy default rate values remain identical.

The new audits cost approximately $0.001425 by returned usage; cumulative accounted/reserved synthesis and audit budget is $0.6592022 of $2, not a verified invoice. Family recordings, TEST, USB, server configuration and volume remain untouched. See [the R21 record](reports/wake-milder-tempo-2026-11-04.json); preparation or a completed training run is not acceptance.

R21 has started, after verifying R20 terminal code 0 and no other trainer. Fresh preparation contains exactly 13,162 total TRAIN examples and 2,322 new views, whose factors range from 1.000067 to 1.299778. Independent array/metadata checks confirm all 432 DEV features, labels and clocks exactly match R13, and the base preparation provenance matches R18. The first native checkpoint retains 90/92 original targets with zero original/ordinary-negative false activations, but still fails the fast DEV gates (two near-negative false clips at each speed). It is **not qualified**. Export size is 98,064 bytes and host arena 37,808 bytes; device timing remains untested. The existing two-seed comparison continues without restarting or changing policy.

### Conditional parallel short-context control (2026-11-04)

R22 is prepared conditionally; it has **not started training**. It must wait for the actual R21 terminal result, all 24 failed evaluations, absence of a frozen candidate and process exit. If R21 freezes a numerical candidate, its mandatory finalization takes priority. R21 continues with its archived source, without restart or data changes.

The opt-in `short_context_steps:20` adds a short ordered branch from the shared encoder alongside the existing 72-step route. The original checkpoint is loaded first; its encoder and long hidden path are shared, and the new classifier columns start at zero. This preserves the initial donor function within rounding, without claiming quantized outputs stay identical. The hypothesis is that parallel temporal spans may help faster connected speech; effectiveness is unproven. The same R21 TRAIN arrays, labels, counts, model width, learning rate/loss, two-seed/12-epoch budget and all original/432-tempo/16-secondary DEV gates remain mandatory. Threshold and smoothing are unchanged.

Three new runtime checks cover bounded profiles, donor transfer and actual gradient updates; nine existing training-control checks pass. A loaded 96-channel donor preflight uses eight already-seen TRAIN windows. Initial float transfer differs by at most 3.26e-9. A zero-initialized branch alone cannot validate its temporal contribution, so an additional retained probe activates its classifier with fixed numeric weights, changing outputs by up to 0.02535 without optimization or keyword-policy scoring. With this active branch, all eight batch/stateful-stream comparisons differ by at most 1.20e-7; native Micro and BUILTIN_REF traces are byte-exact across three resets each. The mechanism export is 114,488 bytes with a 42,464-byte host arena (63,521 parameters, up from 55,329). These checks establish a numeric/export contract, **not** wake accuracy, actual ESP32 timing, children/family success or independent TEST. See [the conditional record](reports/wake-dual-context-2026-11-04.json). No new API requests, sources, family recordings, TEST or device/server/volume changes were used.

A read-only equal-budget first-seed diagnostic reconciled all stored original/tempo traces for the 12 configured seed42 checkpoints in each of R18/R21 and verified model hashes. Only the TRAIN tempo bands differ; base preparation and other profile settings match. Original R12 floors were preserved in 0/12 R18 checkpoints and 4/12 R21 checkpoints; neither arm qualified. Ordinary-negative false exposures remained zero. Tempo Tikoo false exposures were 41 versus 36 and missing-final-syllable exposures two versus four. These are repeated exposures to reused DEV, **not** independent examples or a multiple-seed causal estimate; gentler augmentation alone has not resolved fast-speech acceptance.

R21 subsequently completed both 12-epoch seeds (24 native checkpoint evaluations) with no qualified or frozen candidate. Original R12 floors were preserved in four seed42 and one seed43 checkpoints; ordinary-negative false exposures remained zero, while fast DEV still failed. Terminal return code 0, actual process exit and all 24 model/evaluation hashes were verified. No TEST was opened or device changed. R22 may now start under its predeclared condition.

R22 has now started after R21 actually terminated unqualified with no remaining trainer. The reused 2,322 tempo TRAIN views and all 432 DEV feature/label/clock files are byte-identical to R21; base preparation provenance also matches. Actual initialization records 63,521 parameters and zero new classifier columns. Reconstructing the actual first-epoch extended H5 checkpoint independently confirms all 64 new short-classifier weights became nonzero and the short filter/hidden path plus final shared block updated. The first native export is 114,512 bytes with a 42,464-byte host arena, but remains unqualified (one original negative false activation; ordinary negatives zero, tempo gates still fail). This verifies actual branch learning and the saved-checkpoint interface, **not** accuracy improvement or acceptance. No new source, API, TEST or device change occurred.

### Whole-DEV tempo content audit (2026-11-04)

A separate audit covers the **entire** declared 144-source synthetic DEV, with guarded original controls and all 432 fixed-speed derivatives (576 audio views). Selection does not depend on wake-model errors. Reconstruction verifies every derived PCM hash and every cached feature/label/clock record exactly; recordings remain private and cannot become TRAIN or fresh TEST. Full waveform durations range from 0.383 to 2.65 seconds; these lengths alone do not establish utterance validity. No family or real-child recordings are read/uploaded.

Blind offline transcription using the existing Qwen3-ASR0.6b4bit model completed all 576 views without prompts, hotwords or language hints. Exact existing-rule matches are 138/144 at original speed, 129/144 at 1.15×, 127/144 at 1.3× and 111/144 at 1.5×. Across the three transformed conditions, 61 repeated exposures matched at original speed and diverged after tempo processing. These are **transcription consistency screens**, not phonetic truth, independent examples, wake accuracy or grounds for automatic cleaning. Proper-name spelling and script/decoder uncertainty remain.

An independent `gpt-transcribe` audit of the same entire 576-view scope has started, with one request in flight, at least three seconds between request starts, no automatic retry, a $0.15 accounted/reserved phase cap and the existing $2 cumulative cap. Current R22 training, labels, admission, policy and acceptance gates remain unchanged. No new source has been admitted and no TEST opened. See [the dated content record](reports/wake-full-dev-content-2026-11-04.json); partial cloud results do not establish completion.

R22 completed both 12-epoch seeds without qualification (24 native evaluations). Terminal code 0, actual trainer exit, all model/evaluation hashes and pinned backend identifiers were verified. Original R12 floors were preserved in six seed42 and four seed43 checkpoints. Ordinary-negative false exposures were one and zero respectively. No model was frozen or installed.

A read-only equal-budget comparison reconciled all original/tempo traces for each arm's configured seed42 first 12 checkpoints, with byte-identical TRAIN/DEV inputs. R21/R22 had 36/38 repeated Tikoo false exposures and 4/0 missing-final-syllable exposures; original floors were preserved in 4/6 checkpoints. Twelve R21 and eleven R22 `(source, rate)` pairs were missed at every checkpoint, with eleven shared. These repeated DEV exposures are not independent examples or a multiple-seed causal estimate. Parallel windows have not resolved qualification under this budget, without proving that they can never help. No further architecture-only run is queued while the complete independent content audit is in progress.

The independent cloud audit completed all 576 requests successfully; actual process exit, response/source hashes and budget entries were verified. Cloud exact-rule matches at original/1.15×/1.3×/1.5× are 135/124/117/108 out of 144; both-backend matches are 130/115/108/90. Across 13 originals, 21 transformed exposures matched in both original controls but failed both transcription rules after stretching (3/6/12 at increasing rates). These remain content concerns: scripts, name spellings, empty transcripts and decoder differences cannot establish missing phonemes or invalid labels. No automatic relabeling, corpus filtering or acceptance change occurred.

The phase costs approximately $0.0681 by returned usage; total accounted/reserved budget is $0.7273022 of $2, not a verified invoice. Four private neutral-order original/accelerated audio pairs were prepared under a predeclared, keyword-score-independent protocol: adult and childlike positive concerns, a negative concern and a both-match control. Their expected labels stay private during auditory review. Audio is untouched apart from concatenation with an 800ms separator, remains excluded from TRAIN/fresh TEST, and records no household voice. Human content review is pending; this audit does not qualify a wake candidate.

The user accepted the reviewed audio pairs in general terms. Target-content acceptability is recorded for the three positive pairs, including two ASR-concern pairs; those ASR differences therefore do not justify automatically rejecting their audio. This applies only to the reviewed waveforms, with no inferred vowel/age labels or whole-corpus claim. The fourth pair is an originally labeled Tikoo negative, so a general “acceptable” answer does not establish whether the heard word begins with p or t. Its negative label and the Hi-Pikoo-only contract remain unchanged pending one-item content clarification. No new training, data relabeling, TEST or device change occurred.

### Utterance-wise classifier regularization (2026-11-04)

The user subsequently confirmed both utterances in the near-word review pair are **Hi Tikoo**. All four selected pairs therefore retain their original positive/negative classes. No recording was relabeled or removed; the reviewed ASR divergences do not establish damaged audio. This conclusion is limited to the selected waveforms, with no whole-corpus phonetic-gold claim.

R23 is a finite training-only regularization control against R21's single-context R12-donor route. `classifier_dropout:0.2` drops hidden classifier channels with one mask per utterance shared across time, and the auxiliary training head receives the same dropped features. At inference the layer is an identity; the scalar classifier is initialized from the donor, and the encoder/hidden path is shared. Defaults stay unchanged, and combination with the new short branch, BatchNorm or encoder freezing is rejected. It introduces no audio/pitch changes or new voice/data admission. The same 13,162 TRAIN examples, 432 tempo DEV cases, original R12 floors, 261 ordinary negatives, 16-case secondary guard and three-score/0.90 rule remain mandatory. Learning rate/loss and two seeds, 12 epochs each, match R21.

Three new checks verify bounded profiles, the actual time-constant training mask and an auxiliary-loss gradient update; nine existing training-control checks pass. Loaded 96-channel donor inference is identical in the eight-window preflight, batch/stateful-stream outputs agree and native Micro/BUILTIN_REF traces are byte-exact across three resets. Model parameter count is unchanged. This establishes the regularization/export mechanism, not accuracy or hardware acceptance. No new child audition has been admitted, family recordings and TEST remain untouched, and no new API cost is incurred. See [the R23 record](reports/wake-head-dropout-2026-11-04.json).

R23 has started after prior trainer/auditor exit and exact source/cache preflight checks. Actual initialization records the .2 utterance mask and 55,329 parameters. All TRAIN/DEV feature/label/clock files, event/cohort/auxiliary weighting summaries and calibration indices match R21. Its first native epoch remains unqualified, including three original negative false activations and zero ordinary-negative false clips. The finite two-seed run continues; this is not evidence of accuracy improvement, a multiple-seed causal estimate or device acceptance.

### Fixed-checkpoint quantization diagnosis and natural-read pilot (2026-11-04)

R23 completed both 12-epoch seeds with no qualified candidate. Actual exit, terminal code 0 and all 24 model/evaluation hashes were verified. Original R12 floors were retained in four seed42 and six seed43 checkpoints; ordinary-negative false exposures were zero and one. No model was frozen or installed.

A predeclared diagnostic fixed seed42's configured terminal epoch12 and covered all 144 original plus 432 tempo synthetic DEV cases. Float with raw features, float with quantized/dequantized input, and the saved native INT8 traces had identical per-case hit/early/false decisions. All 15 native positive misses also missed in both float modes; none had a full-trace peak crossing the threshold outside its event window, and no input values clipped the declared quantization range. This rules out quantization or event-window placement alone as an explanation for **these misses in this checkpoint**, without establishing an all-model or device conclusion. No labels, calibration, model or policy were changed; the 261 ordinary native cases were not repeated.

The next data step generated a finite 48-file natural-reading pilot with the existing local Qwen3-TTS VoiceDesign model: three preassigned fictional TRAIN-only prompt families, compact and naturally quick delivery, six permanent source auditions and 42 quarantined TRAIN candidates (18 target scripts, 24 near/incomplete negatives). Audio was generated directly, with no DSP time/pitch/voice transformation. Pronunciation constraints match each supplied word, including a t-initial Tikoo negative rather than a shared Pikoo reading instruction. This supplies no verified age/gender or new real-child evidence. Existing voice-design prompts are not verified fixed speakers.

All 48 raw recordings remain unadmitted. Blind local ASR matched 30 existing content rules; an independent all-48 transcription screen is running with a $0.04 phase accounted/reserved cap under the same $2 global cap, one request in flight and three-second minimum start intervals. No family or real-child recording, new model download, TEST or device/server configuration change is involved. New source auditions are permanently excluded from TRAIN; all pilot source families and descendants are excluded from future fresh TEST. Actual style/content evidence is required before admitting any candidates. See [the pilot record](reports/wake-natural-train-pilot-2026-11-04.json).

The independent raw-pilot content screen completed all 48 requests, with source hashes and successful responses verified. Local/cloud rule matches are 30/29; 23 match both, of which **20 are quarantined TRAIN candidates** and three are permanent auditions. None is admitted. Three new private neutral-numbered audition pairs, each compact then naturally quick, were assembled from the six predeclared source-audition recordings with an 800ms separator. These are new waveforms rather than a replay of the older NS auditions. Actual perceived style/gender remains pending; provider prompts and transcription cannot establish childlike voices. A fail-closed content-agreement draft preserves `admitted_to_training:false` and pending style evidence. Uncertain clips remain quarantined, without automatic relabeling. This phase costs approximately $0.005625 by usage; cumulative accounted/reserved budget is $0.7329272 of $2, not an invoice.

The next human review uses **actual TRAIN candidates**, rather than inferring the style of every candidate from two source examples. All 18 positive candidate originals and all six matched Tikoo candidate originals are presented in three eight-utterance packs (six targets, two Tikoo), without selection by either ASR or keyword score. This is prompt-aware TRAIN content/style QC, not blinded model evaluation. Accepted individual candidates may later become TRAIN after evidence checks; mixed-label presentation assemblies cannot become TRAIN/TEST. The six separately predeclared source-audition originals retain their permanent exclusion and are not repurposed. This also permits direct review of potentially valid but difficult-to-transcribe target candidates; ASR agreement alone does not decide admission. Per-record word and actual perceived-style feedback is pending; no candidate has entered training.

### Natural TRAIN admission guard — 2026-11-04

The new local synthetic-original route requires matching per-record human content and perceived-style approval, immutable original label/text/source identity, TRAIN-only source reservation, and hashed raw-manifest/review evidence. Source auditions remain permanently excluded, and a source assigned to DEV cannot enter through this route. ASR agreement and requested age alone cannot admit a recording. The 48 current raw pilot originals were all rejected while approval is pending; zero were admitted.

For this new route, repeated acoustic views preserve sample count and use the clean waveform for the event clock. They bypass the legacy generic interpolation-based speed/pitch augmentation. Faster views continue through the separate pitch-preserving `ffmpeg atempo` stage; historical caches and fixed DEV are unchanged. Twenty-three focused admission/augmentation/tempo regression tests passed. These checks establish software guards, not wake accuracy or child-voice acceptance. See [the actual guard report](reports/wake-natural-admission-2026-11-04.json). Human quality review remains pending; no new training, TEST, server or device changes occurred.

### Human-reviewed natural childlike TRAIN expansion (R25) — 2026-11-04

The user explicitly confirmed all three eight-utterance packs: six complete Hi Pikoo targets followed by two Hi Tikoo non-targets, with an overall childlike impression. This admits exactly 24 synthetic originals (18 positive, six negative), without changing their labels. It does not establish real child age, gender, accent or each record's exact ku/ko vowel. Six permanently designated source auditions and 18 other unreviewed raw candidates remain excluded.

R25 retains the previous 56 extra TRAIN originals and adds the approved 24. It starts from the R12 checkpoint with the R21 single-context architecture, two seeds and at most 12 epochs each. New natural sources bypass generic resampling; clean-clock acoustic views and the separate pitch-preserving tempo stage are used. Complete fixed DEV, original R12 group floors and the 16-case secondary gate remain required. Feature preparation has started; there is no passing model or new TEST/hardware result. See [the admission and experiment record](reports/wake-natural-child-train-2026-11-04.json).

The original TRAIN balancer required exactly six fully stratified cohorts. R25 keeps all six mandatory and permits the explicitly admitted natural-source hashes as a separate unresolved-accent/vowel supplement. Its weights are unchanged by six-way balancing; the later global TRAIN positive/negative balance still applies. It cannot replace a missing original cohort or count as a new DEV cohort. Thirty-three focused tests passed. Preparation produced 13,558 TRAIN examples; the previous 2,322 tempo TRAIN views retain identical features/labels/weights, and all 432 tempo DEV features remain identical. An uppercase private profile identifier and the unsupported supplemental cohort stopped two preprocessing attempts before any epoch; both failures are retained, and the verified new tempo cache was reused after correction.

### R25 terminal result and wider TRAIN tempo control (R26) — 2026-11-04

R25 completed all 24 configured native INT8 evaluations without qualification. All 24 rejected the same 261 ordinary negative DEV cases without false wakes. Original R12 group floors were preserved in nine of 12 first-seed epochs and all 12 second-seed epochs. Both terminal checkpoints still falsely triggered once at each faster DEV rate; the weakest 1.5x group remained at 80% recall. No candidate was frozen or installed. [Terminal report](reports/wake-natural-child-train-2026-11-04.json).

A paired diagnostic uses all 12 completed first-seed epochs for R21 and R25 with identical 432-case DEV identity, labels, features and clocks. It found nine shared case/speed pairs missed in every epoch; each run also had three persistently false-triggered case/speed pairs. These are repeated development exposures, not independent test trials, and do not establish a causal improvement from new voices. [Paired diagnostic](reports/wake-natural-tempo-comparison-2026-11-04.json).

After verifying R25's actual terminal state and absent worker, R26 starts the same bounded comparison with only the TRAIN speed ceiling widened from 1.3 to 1.5. Counts, reviewed originals, clean timing, model, fixed policy and all DEV gates remain unchanged. This tests broader speed coverage without transposing pitch; earlier broader-speed runs on the older corpus remain recorded failures. No added API requests or device changes. [R26 declaration](reports/wake-natural-wide-tempo-2026-11-04.json).

R26's first seed completed all 12 epochs without qualification; seed 43 is still running. Compared with R25's same complete first-seed sequence, 1.5x worst-group recall reached at least 90% in 10/12 epochs (previously 0/12), but original-speed false-wake exposures rose from zero to six and early-wake exposures from zero to three. Only 2/12 epochs preserved all original gates, versus 9/12 before. Ordinary negative exposures remained zero. These are repeated fixed-DEV checkpoint exposures, not independent samples or an eight-hour false-wake rate. No checkpoint is promoted. The actual first R26 checkpoint changed all 16 serialized parameter arrays relative to its donor; this excludes a completely unchanged-weight training failure, not a generalization failure. [All-first-seed comparison](reports/wake-wide-vs-mild-first-seed-2026-11-04.json).

### R26 terminal and fresh-recipe control (R27) — 2026-11-04

R26 finished all 24 configured native evaluations without qualification. Seed 43's terminal checkpoint passed all three tempo gates at worst-group recall 90%, but still failed the original-speed gate; speed recall alone cannot promote it. Across 12 epochs, original-speed false exposures were six/ nine for seeds 42/43 and early exposures three/zero. Ordinary negative false exposures were zero for both seeds. These are repeated DEV exposures, not independent physical false-wake rates. [Complete R26 record](reports/wake-natural-wide-tempo-2026-11-04.json).

After actual terminal verification, R27 is prepared to train from random initialization using the original R12 fresh96 recipe (.0005 learning rate, at most 30 epochs, two seeds), retaining R26's data and complete gates. This changes initialization, learning rate and training ceiling jointly; it does not isolate a causal initialization effect. Preflight confirmed 55,329 parameters, all 16 arrays trainable, distinct seed fingerprints and no donor-weight equality. Actual training now records its initial fingerprint before optimization. No test audio, family data or new API calls were used in preflight. [Fresh declaration](reports/wake-natural-fresh-2026-11-04.json).

The user accepted all nine original/faster pairs in the recurrent-case lexical review as complete Hi Pikoo (piku/piko accepted). This is 18 views of seven reused DEV sources selected from prior failures, not a new independent test or a wake-accuracy result. No exact vowel or age annotation was inferred; no labels/cohorts were changed and none entered TRAIN. ASR disagreement is not grounds to discard these cases. [Content review](reports/wake-recurrent-dev-content-review-2026-11-04.json). R27 has now started: its actual seed42 initial fingerprint exactly matches the fresh preflight, differs from the donor, and all16weight arrays are trainable; all13,558TRAIN examples and fixedDEV are retained.

### Untrained normalization-branch preflight — 2026-11-04

While R27 continues, the existing fresh96 normalization branch was checked without a second training run. Five normalization layers were given deterministic non-default statistics to stress inference export. Eight admitted original TRAIN fixtures matched batch versus stateful float output within 5.96e-8 and matched native Micro versus BUILTIN_REF byte-for-byte across three native resets each. The untrained graph has 57,249 parameters, a 98,528-byte model and 37,808-byte host arena use. No keyword accuracy, actual device timing or release acceptance is established. This only prepares a potential later normalization comparison if the current finite trial fails; current data, weights and policy are unchanged. [Numeric report](reports/wake-normalization-preflight-2026-11-04.json).

R27 seed42 ended under the existing early-stopping rule at epoch26 (maximum30), with no qualified checkpoint. All26 model hashes and native backends were checked. Across repeated DEV checkpoint exposures it recorded16ordinary false wakes,65original false wakes and5original early wakes; none preserved the entire original gate. These are not distinct sample counts or physical false-wake rates. Seed43 is running and its actual initial fingerprint matches the independent fresh-seed preflight. [Fresh trial record](reports/wake-natural-fresh-2026-11-04.json).

A fixed terminal-epoch26 diagnostic, not a best-checkpoint choice, checked eight admitted TRAIN fixtures. Trained batch versus its original saved stateful stream differed by at most5.96e-8; Micro and BUILTIN_REF matched every output byte across three native resets, and all eight fixtures met the fixed TRAIN decision check. This is neither complete TRAIN fit nor independent accuracy; the checkpoint remains rejected. It finds no export/backend discrepancy on these fixtures. [Terminal export diagnostic](reports/wake-fresh-terminal-export-diagnostic-2026-11-04.json).

### R27 terminal and normalized fresh control (R28) — 2026-11-04

R27's two seeds ended under the declared early-stopping rule at26and25epochs. All51saved models were hash-checked against their native evaluations; none qualified. Seed43 recorded18ordinary-negative false exposures,59original false exposures and8original early exposures. These are repeated development checkpoint exposures, not independent error rates. [R27 complete result](reports/wake-natural-fresh-2026-11-04.json).

After verifying actual process termination, R28 started the preflighted normalization branch. Apart from the name, `batch_normalization=True` is the only profile difference from R27. Actual initialization has57,249parameters,36weight arrays and26trainable arrays, with no pretrained weights; the untrained stress-test model is never loaded. Input verification confirms identical13,558TRAIN examples, TRAIN balancing/admission, extra manifest/review, and all tempo TRAIN/DEV files. Original R12 floors, full432tempoDEV and16secondarycases remain required. First native evaluations have not qualified; no device/API/server change occurred. [R28 actual startup](reports/wake-normalized-fresh-train-2026-11-04.json).

### R28 terminal result and matched P/T TRAIN quarantine — 2026-11-04

R28 ended at 19 and 23 epochs under its declared stopping rule. All 42 saved native INT8 evaluations were hash/backend checked; none qualified. Across repeated DEV checkpoint exposures, seeds 42/43 recorded 7/54 ordinary false wakes, 82/115 original false wakes and 16/11 original early wakes. Neither seed preserved all original R12 gates in any epoch. These are repeated development exposures, not physical false-wake rates. No model was frozen or installed. [Terminal report](reports/wake-normalized-fresh-train-2026-11-04.json).

A read-only diagnostic used the first seed's terminal epoch 19 and its archived source, without choosing a best checkpoint. On all 576 reused synthetic DEV views, raw float, input-quantize/dequantize float and saved native INT8 had identical per-case hit/early/false decisions. All nine native positive misses were also float misses; no input clipping occurred. The 261 ordinary negatives were not re-evaluated in this diagnostic. This narrows the cause for this checkpoint and these inputs; it does not establish universal numerical equivalence or independent accuracy. [Diagnostic](reports/wake-normalized-terminal-quantization-diagnostic-2026-11-04.json).

Read-only aggregation of all 51 earlier R27 checkpoints found T-initial names dominated phrase-negative false exposures. A new local pilot therefore generated 24 matched P/T pairs (48 raw originals) from three existing TRAIN-only prompt families, without API calls or downloads. Full raw files last 0.72–2.32 seconds; energy-active spans are 0.58–2.16 seconds (median 0.95), which cannot prove word completion. Blind local ASR matched 34/48 requested contents; all 48 remain quarantined pending original-waveform human content and perceived-style review. No age, accent or exact vowel is inferred from generation prompts or ASR. Both members must be reviewed before a pair can enter TRAIN. Preview assemblies remain permanently excluded. [Failure-family analysis](reports/wake-fresh-false-family-diagnostic-2026-11-04.json), [quarantine record](reports/wake-matched-pt-train-quarantine-2026-11-04.json).

The optional `--natural-train-manifest` and `--natural-train-review` route appends approved natural originals **after** the existing tempo preparation. It retains the established cache and adds same-length acoustic views with clean event timing, without stretching already-fast new utterances again. Both review flags and complete retained TRAIN lineage are required. The route rejects reused base/earlier-extra originals, retains earlier-stage proof, and writes separate metadata. Reviewed adult or childlike unresolved-vowel sources may be supplemental only by exact admitted hash; they cannot replace any of the six required original cohorts. All 32 focused admission, augmentation, tempo and qualification tests passed. This validates software protections, not model accuracy. The next training trial has not started; household audio, TEST, device, server and volume remain untouched.

The matched pilot now has an executable pair-admission guard, beyond its written protocol. A pair-required source reservation requires hashed pair evidence covering every raw original exactly once, with one positive and one negative from the same prompt family. Unknown, rejected or protected counterpart verdicts block admission, and both pair members must appear together in the admitted manifest. Legacy unpaired reviews retain their existing rules. Ten targeted tests passed, and all 48 actual unreviewed pilot originals were rejected by the guard. No pilot original has entered TRAIN and no new training has started. [Pair guard evidence](reports/wake-matched-pair-admission-guard-2026-11-04.json).

### Frozen candidate under explicitly tolerated full T-greetings — 2026-11-04

The user clarified that accidental activation by **complete Hi Tikoo/Tiko** is acceptable, without requesting dedicated T-name training. The positive target remains **Hi piku/piko**; T-greetings are neutral, with no promised recall, and are never counted as successful target trials. Ordinary speech, Hi alone, name alone, incomplete names and 你好 Pikoo still require rejection. The prior stricter failures remain unchanged.

A new policy was declared before read-only rescoring of seven completed experiments in fixed chronological order. The first complete revised qualification appeared at checkpoint 102: R26 seed42 epoch06. Its original weights are unchanged and no new synthesis or training was performed. All original source/model/backend hashes and historical metrics were checked, with all 144 raw and 432 tempo traces retained. Only the ten admitted full T-name DEV originals are neutral; their triggers remain separately reported.

The candidate retained 90/92 original-speed target hits, every R12 group floor, zero false wakes among the remaining 42 phrase negatives and no early target wakes, and zero activations in all 261 ordinary-speech/environment DEV cases. Each 1.15x, 1.3x and 1.5x tempo gate met the 90% worst-group target. All 16 supplemental unsupported-greeting DEV cases also passed on the actual native backend. Eight balanced TRAIN fixtures matched Micro/BUILTIN_REF output byte-for-byte across three resets each. The private model is 98,064 bytes; measured host arena use is 37,808 bytes, not ESP32 timing or total device RAM. [Complete scope and evidence](reports/wake-t-tolerance-convergence-2026-11-04.json).

`wake_tolerated_confusables.load/score` binds the exact source manifest, protected registry and user-declared policy. The finalizer requires that policy explicitly; a revised result cannot silently pass the old strict path. Sixteen scope/finalizer tests and 31 mixed-TEST tests passed. The new 150-slot post-freeze TEST replaces the old T-negative category with incomplete-name negatives and retains all six target cohorts, 70 synthetic slots and 80 family slots. No dedicated T-name requests are added. Old TEST waveforms and all prior TRAIN/DEV/audition metadata are excluded; no new TEST has been generated or scored. Family participation is postponed at the user's request. The candidate is frozen, not released or installed; child, two-session and eight-hour acceptance remain pending.

The private normal-device firmware `0.2.2-dev-r30t` compiled successfully. Image checks confirm the exact frozen model and policy, unchanged partition table/app offset, and disabled benchmark/veto/volume-upgrade switches. The app is 2,655,440 bytes within its 6 MiB partition. This was an offline build only: no USB access or flash operation occurred. The private image is ready for the later test workflow, not a hardware acceptance result.
