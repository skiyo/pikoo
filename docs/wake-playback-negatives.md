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
